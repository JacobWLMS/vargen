"""Text-to-image generation step — supports FLUX, SDXL, SD1.5 with IP-Adapter, ControlNet, LoRA."""

import logging
import torch
from pathlib import Path
from PIL import Image

log = logging.getLogger(__name__)


def run_txt2img(model_ref, params: dict, mm, pipeline) -> Image.Image | list[Image.Image]:
    """Generate image(s) from text. Supports IP-Adapter, ControlNet, LoRA as modifiers.

    Params:
        prompt, negative, width, height, steps, guidance, seed, architecture
    Modifiers (from StepConfig, injected by engine):
        _ip_adapter: IPAdapterConfig
        _controlnet: ControlNetConfig
        _loras: list[LoRAConfig]
        _batch_index: int (current batch iteration)
    """
    prompt = params.get("prompt", "")
    negative = params.get("negative", "")
    width = params.get("width", 1024)
    height = params.get("height", 1024)
    steps = params.get("steps", 20)
    guidance = params.get("guidance", 3.5)
    seed = params.get("seed", -1)

    # For batch mode, vary the seed per iteration
    batch_idx = params.get("_batch_index", 0)
    if seed == -1:
        generator = None
    else:
        generator = torch.Generator("cpu").manual_seed(seed + batch_idx)

    model_path = mm.model_path(model_ref)
    fmt = model_ref.format or _detect_format(model_path)
    arch = params.get("architecture", _guess_architecture(model_ref, fmt))

    # Get modifier configs (injected by engine)
    ip_adapter_cfg = params.get("_ip_adapter")
    controlnet_cfg = params.get("_controlnet")
    lora_cfgs = params.get("_loras", [])

    log.info(f"Loading: {model_ref.repo} (arch={arch}, quantize={model_ref.quantize})")
    if ip_adapter_cfg:
        log.info(f"  + IP-Adapter: {ip_adapter_cfg.model} (weight={ip_adapter_cfg.weight})")
    if controlnet_cfg:
        log.info(f"  + ControlNet: {controlnet_cfg.model} (strength={controlnet_cfg.strength})")
    if lora_cfgs:
        log.info(f"  + LoRAs: {[l.model for l in lora_cfgs]}")

    # Load base pipeline
    loader = LOADERS.get(arch)
    if not loader:
        raise ValueError(f"Unknown architecture: {arch}. Supported: {list(LOADERS.keys())}")
    pipe = loader(model_ref, params, mm, pipeline, model_path)

    # Apply LoRAs
    for lora_cfg in lora_cfgs:
        lora_ref = pipeline.models.get(lora_cfg.model)
        if lora_ref:
            lora_path = mm.model_path(lora_ref)
            log.info(f"  Loading LoRA: {lora_path}")
            pipe.load_lora_weights(str(lora_path))
            pipe.fuse_lora(lora_scale=lora_cfg.weight)

    # Apply IP-Adapter
    ip_image = None
    if ip_adapter_cfg:
        ipa_ref = pipeline.models.get(ip_adapter_cfg.model)
        if ipa_ref:
            ipa_path = mm.model_path(ipa_ref)
            log.info(f"  Loading IP-Adapter: {ipa_path}")
            # diffusers native IP-Adapter support
            if ipa_ref.subfolder:
                pipe.load_ip_adapter(
                    str(ipa_path.parent) if ipa_path.is_file() else str(ipa_path),
                    subfolder=ipa_ref.subfolder,
                    weight_name=ipa_path.name if ipa_path.is_file() else None,
                )
            else:
                pipe.load_ip_adapter(
                    ipa_ref.repo,
                    weight_name=ipa_ref.file,
                )
            pipe.set_ip_adapter_scale(ip_adapter_cfg.weight)
            # Resolve reference image
            ref_key = ip_adapter_cfg.reference.strip("{}")
            ip_image = params.get(ref_key) or params.get("input_image")

    # Apply ControlNet
    if controlnet_cfg:
        cn_ref = pipeline.models.get(controlnet_cfg.model)
        if cn_ref:
            cn_path = mm.model_path(cn_ref)
            log.info(f"  Loading ControlNet: {cn_path}")
            from diffusers import ControlNetModel
            controlnet = ControlNetModel.from_pretrained(
                str(cn_path) if cn_path.is_dir() else cn_ref.repo,
                torch_dtype=torch.float16,
            )
            # Rebuild pipeline with controlnet
            pipe = _rebuild_with_controlnet(pipe, controlnet, arch)

    # Memory optimization
    if hasattr(pipe, "enable_model_cpu_offload"):
        pipe.enable_model_cpu_offload()
    if hasattr(pipe, "enable_attention_slicing"):
        pipe.enable_attention_slicing()

    mm.register("gen_pipeline", pipe)

    log.info(f"Generating: {width}x{height}, {steps} steps, guidance {guidance}")

    kwargs = {
        "prompt": prompt,
        "width": width,
        "height": height,
        "num_inference_steps": steps,
        "guidance_scale": guidance,
        "generator": generator,
    }

    if negative and arch not in ("flux", "flux-gguf"):
        kwargs["negative_prompt"] = negative

    if ip_image is not None:
        kwargs["ip_adapter_image"] = ip_image

    if controlnet_cfg:
        cn_image = params.get("_controlnet_image") or params.get("input_image")
        if cn_image:
            kwargs["image"] = cn_image
            kwargs["controlnet_conditioning_scale"] = controlnet_cfg.strength

    result = pipe(**kwargs)
    return result.images[0]


def _rebuild_with_controlnet(pipe, controlnet, arch):
    """Rebuild a pipeline with ControlNet support."""
    if arch in ("sdxl", "auto"):
        from diffusers import StableDiffusionXLControlNetPipeline
        return StableDiffusionXLControlNetPipeline(
            vae=pipe.vae, text_encoder=pipe.text_encoder,
            text_encoder_2=pipe.text_encoder_2, tokenizer=pipe.tokenizer,
            tokenizer_2=pipe.tokenizer_2, unet=pipe.unet,
            controlnet=controlnet, scheduler=pipe.scheduler,
        )
    elif arch in ("sd15", "sd"):
        from diffusers import StableDiffusionControlNetPipeline
        return StableDiffusionControlNetPipeline(
            vae=pipe.vae, text_encoder=pipe.text_encoder,
            tokenizer=pipe.tokenizer, unet=pipe.unet,
            controlnet=controlnet, scheduler=pipe.scheduler,
            safety_checker=None, feature_extractor=None,
        )
    # FLUX ControlNet handled differently
    return pipe


# ── Architecture-specific loaders ──────────────────────────────

def _load_flux_gguf(model_ref, params, mm, pipeline, model_path):
    from diffusers import FluxPipeline, FluxTransformer2DModel, GGUFQuantizationConfig
    gguf_config = GGUFQuantizationConfig(compute_dtype=torch.bfloat16)
    transformer = FluxTransformer2DModel.from_single_file(
        str(model_path), quantization_config=gguf_config, torch_dtype=torch.bfloat16,
    )
    pipe = FluxPipeline.from_pretrained(
        "black-forest-labs/FLUX.1-dev", transformer=transformer, torch_dtype=torch.bfloat16,
    )
    return pipe


def _load_flux_diffusers(model_ref, params, mm, pipeline, model_path):
    from diffusers import FluxPipeline
    kwargs = {"torch_dtype": torch.bfloat16}
    quant = _get_quant_config(model_ref.quantize)
    if quant:
        kwargs["quantization_config"] = quant
    if model_path.is_file():
        return FluxPipeline.from_single_file(str(model_path), **kwargs)
    return FluxPipeline.from_pretrained(str(model_path), **kwargs)


def _load_sdxl(model_ref, params, mm, pipeline, model_path):
    from diffusers import StableDiffusionXLPipeline
    kwargs = {"torch_dtype": torch.float16}
    quant = _get_quant_config(model_ref.quantize)
    if quant:
        kwargs["quantization_config"] = quant
    if model_path.is_file():
        return StableDiffusionXLPipeline.from_single_file(str(model_path), **kwargs)
    return StableDiffusionXLPipeline.from_pretrained(str(model_path), **kwargs)


def _load_sd15(model_ref, params, mm, pipeline, model_path):
    from diffusers import StableDiffusionPipeline
    kwargs = {"torch_dtype": torch.float16}
    quant = _get_quant_config(model_ref.quantize)
    if quant:
        kwargs["quantization_config"] = quant
    if model_path.is_file():
        return StableDiffusionPipeline.from_single_file(str(model_path), **kwargs)
    return StableDiffusionPipeline.from_pretrained(str(model_path), **kwargs)


def _load_auto(model_ref, params, mm, pipeline, model_path):
    from diffusers import AutoPipelineForText2Image
    kwargs = {"torch_dtype": torch.bfloat16, "trust_remote_code": True}
    quant = _get_quant_config(model_ref.quantize)
    if quant:
        kwargs["quantization_config"] = quant
    if model_path.is_file():
        try:
            return _load_sdxl(model_ref, params, mm, pipeline, model_path)
        except Exception:
            return _load_sd15(model_ref, params, mm, pipeline, model_path)
    return AutoPipelineForText2Image.from_pretrained(str(model_path), **kwargs)


LOADERS = {
    "flux": _load_flux_diffusers,
    "flux-gguf": _load_flux_gguf,
    "sdxl": _load_sdxl,
    "sd15": _load_sd15,
    "sd": _load_sd15,
    "auto": _load_auto,
}


def _get_quant_config(quantize):
    if not quantize:
        return None
    from diffusers import BitsAndBytesConfig
    if quantize == "nf4":
        return BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="nf4", bnb_4bit_compute_dtype=torch.bfloat16)
    elif quantize in ("fp8", "int8"):
        return BitsAndBytesConfig(load_in_8bit=True)
    return None


def _detect_format(path):
    p = Path(path)
    if p.is_dir():
        return "diffusers"
    return {".gguf": "gguf", ".safetensors": "safetensors", ".bin": "bin", ".ckpt": "checkpoint"}.get(p.suffix.lower(), "unknown")


def _guess_architecture(model_ref, fmt):
    name = (model_ref.repo + (model_ref.file or "")).lower()
    if fmt == "gguf" and "flux" in name:
        return "flux-gguf"
    if "flux" in name:
        return "flux"
    if "sdxl" in name or "xl" in name or "pony" in name:
        return "sdxl"
    if "sd15" in name or "sd_1" in name or "v1-5" in name:
        return "sd15"
    return "auto"
