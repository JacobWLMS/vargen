"""Loader nodes — load models, images, create empty latents."""

import torch
import logging
from PIL import Image
from pathlib import Path

from . import register_node, NodeTypeDef, PortDef, WidgetDef

log = logging.getLogger(__name__)

DTYPE_MAP = {
    "auto": None,
    "fp16": torch.float16,
    "bf16": torch.bfloat16,
    "fp32": torch.float32,
}

OFFLOAD_MODES = ["auto", "sequential_cpu", "model_cpu", "gpu_only", "cpu_only"]


def exec_load_checkpoint(inputs, widgets, ctx):
    ckpt_name = widgets.get("checkpoint", "")
    if not ckpt_name:
        raise ValueError("No checkpoint selected")

    model_path = ctx["model_manager"].find_model("checkpoints", ckpt_name)
    if not model_path:
        model_path = ctx["model_manager"].find_model("diffusion_models", ckpt_name)
    if not model_path:
        raise ValueError(f"Checkpoint not found: {ckpt_name}")

    dtype_setting = widgets.get("dtype", "auto")
    offload_mode = widgets.get("offload", "auto")
    attn_slicing = widgets.get("attention_slicing", True)
    vae_tiling = widgets.get("vae_tiling", True)

    log.info(f"Loading: {model_path}")
    is_gguf = str(model_path).lower().endswith(".gguf")
    is_flux = "flux" in ckpt_name.lower() or "flux" in str(model_path).lower()

    # Resolve dtype
    if dtype_setting == "auto":
        torch_dtype = torch.bfloat16 if (is_flux or is_gguf) else torch.float16
    else:
        torch_dtype = DTYPE_MAP.get(dtype_setting, torch.float16)

    if is_flux or is_gguf:
        try:
            pipe = _load_flux_checkpoint(model_path, is_gguf, torch_dtype, ctx.get("model_manager"))
            arch = "flux"
        except Exception as e:
            log.warning(f"FLUX load failed: {e}. Trying as SD checkpoint...")
            pipe = _load_sd_checkpoint(model_path, torch_dtype)
            arch = "sdxl" if hasattr(pipe, 'text_encoder_2') else "sd15"
    else:
        pipe = _load_sd_checkpoint(model_path, torch_dtype)
        arch = "sdxl" if hasattr(pipe, 'text_encoder_2') else "sd15"

    # Default: keep everything on CPU. Each node moves what it needs to GPU.
    # This is the key to running on 8GB — only one component in VRAM at a time.
    if offload_mode == "auto":
        log.info("Offload: per-node (components stay on CPU, moved to GPU per-node)")
        # Don't call any offload method — pipe stays on CPU
        # Individual nodes (CLIP encode, KSampler, VAE decode) handle their own GPU
    else:
        _setup_vram_offload(pipe, offload_mode)

    if attn_slicing and hasattr(pipe, "enable_attention_slicing"):
        pipe.enable_attention_slicing()
        log.info("Attention slicing: enabled")

    if vae_tiling:
        if hasattr(pipe, 'vae') and hasattr(pipe.vae, 'enable_tiling'):
            pipe.vae.enable_tiling()
            log.info("VAE tiling: enabled")
        elif hasattr(pipe, 'enable_vae_tiling'):
            pipe.enable_vae_tiling()
            log.info("VAE tiling: enabled (legacy)")

    log.info(f"Loaded {arch}: {ckpt_name} (dtype={dtype_setting}, offload={offload_mode})")

    return {
        "MODEL": pipe.unet if hasattr(pipe, 'unet') else getattr(pipe, 'transformer', None),
        "CLIP": {
            "tokenizer": getattr(pipe, 'tokenizer', None),
            "text_encoder": getattr(pipe, 'text_encoder', None),
            "tokenizer_2": getattr(pipe, "tokenizer_2", None),
            "text_encoder_2": getattr(pipe, "text_encoder_2", None),
            "arch": arch,
        },
        "VAE": getattr(pipe, 'vae', None),
        "_pipe": pipe,
    }


def _load_flux_checkpoint(model_path, is_gguf, torch_dtype, mm=None):
    from diffusers import FluxPipeline

    if is_gguf:
        try:
            from diffusers import FluxTransformer2DModel, GGUFQuantizationConfig
        except ImportError:
            raise ValueError("GGUF requires: pip install gguf>=0.10.0")

        log.info("Loading FLUX GGUF (quantized)")
        gguf_config = GGUFQuantizationConfig(compute_dtype=torch_dtype)
        transformer = FluxTransformer2DModel.from_single_file(
            str(model_path), quantization_config=gguf_config, torch_dtype=torch_dtype,
        )
        # Try to use local fp8 text encoders to save VRAM
        from transformers import T5EncoderModel, CLIPTextModel

        extra_kwargs = {}
        if mm:
            t5_path = (mm.find_model("text_encoders", "t5xxl_fp8_e4m3fn.safetensors")
                       or model_manager.find_model("text_encoders", "t5xxl_fp16.safetensors"))
            if t5_path:
                log.info(f"Using local T5 encoder: {t5_path.name}")
                try:
                    from diffusers import BitsAndBytesConfig
                    if "fp8" in t5_path.name:
                        quant_config = BitsAndBytesConfig(load_in_8bit=True)
                        text_encoder_2 = T5EncoderModel.from_pretrained(
                            "black-forest-labs/FLUX.1-dev", subfolder="text_encoder_2",
                            quantization_config=quant_config, torch_dtype=torch_dtype,
                        )
                        extra_kwargs["text_encoder_2"] = text_encoder_2
                        log.info("T5 loaded in 8-bit (saves ~2.5GB VRAM)")
                except Exception as e:
                    log.warning(f"Local T5 load failed: {e}, using default")

        log.info("Loading FLUX pipeline components...")
        pipe = FluxPipeline.from_pretrained(
            "black-forest-labs/FLUX.1-dev", transformer=transformer, torch_dtype=torch_dtype,
            **extra_kwargs,
        )
    elif model_path.is_file():
        pipe = FluxPipeline.from_single_file(str(model_path), torch_dtype=torch_dtype)
    else:
        pipe = FluxPipeline.from_pretrained(str(model_path), torch_dtype=torch_dtype)

    return pipe


def _load_sd_checkpoint(model_path, torch_dtype):
    from diffusers import StableDiffusionXLPipeline, StableDiffusionPipeline, AutoPipelineForText2Image

    kwargs = {"torch_dtype": torch_dtype, "trust_remote_code": True}

    if model_path.is_file():
        errors = []
        # Try SDXL
        try:
            log.info("Trying SDXL pipeline...")
            return StableDiffusionXLPipeline.from_single_file(str(model_path), **kwargs)
        except Exception as e:
            errors.append(f"SDXL: {e}")
            log.info(f"Not SDXL: {e}")

        # Try SD1.5
        try:
            log.info("Trying SD1.5 pipeline...")
            return StableDiffusionPipeline.from_single_file(str(model_path), **kwargs)
        except Exception as e:
            errors.append(f"SD1.5: {e}")
            log.info(f"Not SD1.5: {e}")

        raise ValueError(f"Failed to load checkpoint. Tried:\n" + "\n".join(errors))
    else:
        return AutoPipelineForText2Image.from_pretrained(str(model_path), **kwargs)


def _setup_vram_offload(pipe, mode="auto"):
    if not torch.cuda.is_available():
        log.info("No CUDA: running on CPU")
        pipe.to("cpu")
        return

    free_mb = torch.cuda.mem_get_info()[0] // (1024 * 1024)
    total_mb = torch.cuda.mem_get_info()[1] // (1024 * 1024)
    log.info(f"VRAM: {free_mb}MB free / {total_mb}MB total")

    if mode == "auto":
        if free_mb < 4000:
            mode = "sequential_cpu"
        elif free_mb < 8000:
            mode = "model_cpu"
        else:
            mode = "gpu_only"

    try:
        if mode == "sequential_cpu":
            log.info("Offload: sequential CPU (layer-by-layer, slowest, lowest VRAM)")
            pipe.enable_sequential_cpu_offload()
        elif mode == "model_cpu":
            log.info("Offload: model CPU (whole model swap)")
            pipe.enable_model_cpu_offload()
        elif mode == "gpu_only":
            log.info("Offload: none (keeping on GPU)")
            pipe.to("cuda")
        elif mode == "cpu_only":
            log.info("Offload: CPU only (no GPU)")
            pipe.to("cpu")
    except Exception as e:
        log.warning(f"Offload mode '{mode}' failed: {e}. Trying model_cpu_offload...")
        try:
            pipe.enable_model_cpu_offload()
        except Exception as e2:
            log.warning(f"model_cpu_offload also failed: {e2}. Keeping on CPU.")
            pipe.to("cpu")


def exec_load_lora(inputs, widgets, ctx):
    pipe = inputs.get("_pipe")
    if not pipe:
        raise ValueError("LoRA needs a pipeline — connect from Load Checkpoint")

    lora_name = widgets.get("lora", "")
    strength = float(widgets.get("strength", 0.7))
    fuse = bool(widgets.get("fuse", True))

    if not lora_name:
        raise ValueError("No LoRA selected")

    model_path = ctx["model_manager"].find_model("loras", lora_name)
    if not model_path:
        raise ValueError(f"LoRA not found: {lora_name}")

    log.info(f"Loading LoRA: {model_path} (strength={strength}, fuse={fuse})")
    pipe.load_lora_weights(str(model_path))

    if fuse:
        pipe.fuse_lora(lora_scale=strength)
        log.info("LoRA fused into model weights")
    else:
        pipe.set_adapters(pipe.get_list_adapters(), adapter_weights=[strength])
        log.info("LoRA loaded (unfused, dynamic weight)")

    return {"MODEL": pipe.unet, "CLIP": inputs.get("CLIP"), "_pipe": pipe}


def exec_load_image(inputs, widgets, ctx):
    image = ctx.get("input_image")
    if image is None:
        raise ValueError("No input image — upload one to the Load Image node")
    if not isinstance(image, Image.Image):
        image = Image.open(image)
    color_mode = widgets.get("color_mode", "RGB")
    if color_mode != "keep":
        image = image.convert(color_mode)
    return {"IMAGE": image}


def exec_load_upscale_model(inputs, widgets, ctx):
    model_name = widgets.get("model", "")
    if not model_name:
        raise ValueError("No upscale model selected")

    model_path = ctx["model_manager"].find_model("upscale_models", model_name)
    if not model_path:
        raise ValueError(f"Upscale model not found: {model_name}")

    import spandrel
    model = spandrel.ModelLoader().load_from_file(str(model_path)).eval()
    device = widgets.get("device", "cuda" if torch.cuda.is_available() else "cpu")
    model = model.to(device)
    log.info(f"Loaded upscale model: {model_name} (device={device})")
    return {"UPSCALE_MODEL": model}


# ── Register ──────────────────────────────────

register_node(NodeTypeDef(
    type_id="load_checkpoint", category="loaders", label="Load Checkpoint",
    inputs=[],
    outputs=[PortDef("MODEL", "MODEL"), PortDef("CLIP", "CLIP"), PortDef("VAE", "VAE")],
    widgets=[
        WidgetDef("checkpoint", "combo", label="Checkpoint", options=[]),
        WidgetDef("dtype", "combo", default="auto", label="Dtype",
                  options=["auto", "fp16", "bf16", "fp32"]),
        WidgetDef("offload", "combo", default="auto", label="VRAM Offload",
                  options=OFFLOAD_MODES),
        WidgetDef("attention_slicing", "toggle", default=True, label="Attention Slicing"),
        WidgetDef("vae_tiling", "toggle", default=True, label="VAE Tiling"),
    ],
    execute=exec_load_checkpoint, color="#a855f7",
    description="Load SD1.5/SDXL/FLUX checkpoint. Auto-detects GGUF and FLUX from filename.",
))

register_node(NodeTypeDef(
    type_id="load_lora", category="loaders", label="Load LoRA",
    inputs=[PortDef("MODEL", "MODEL"), PortDef("CLIP", "CLIP")],
    outputs=[PortDef("MODEL", "MODEL"), PortDef("CLIP", "CLIP")],
    widgets=[
        WidgetDef("lora", "combo", label="LoRA", options=[]),
        WidgetDef("strength", "slider", default=0.7, min=0, max=2, step=0.05, label="Strength"),
        WidgetDef("fuse", "toggle", default=True, label="Fuse (permanent, faster)"),
    ],
    execute=exec_load_lora, color="#c084fc",
))

register_node(NodeTypeDef(
    type_id="load_image", category="loaders", label="Load Image",
    inputs=[], outputs=[PortDef("IMAGE", "IMAGE")],
    widgets=[
        WidgetDef("color_mode", "combo", default="RGB", label="Color Mode",
                  options=["RGB", "RGBA", "L", "keep"]),
    ],
    execute=exec_load_image, color="#38bdf8",
))

register_node(NodeTypeDef(
    type_id="load_upscale_model", category="loaders", label="Load Upscale Model",
    inputs=[], outputs=[PortDef("UPSCALE_MODEL", "UPSCALE_MODEL")],
    widgets=[
        WidgetDef("model", "combo", label="Model", options=[]),
        WidgetDef("device", "combo", default="cuda", label="Device",
                  options=["cuda", "cpu"]),
    ],
    execute=exec_load_upscale_model, color="#2dd4bf",
))
