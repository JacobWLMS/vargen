"""Text-to-image generation step — supports FLUX, SDXL, SD1.5, and variants."""

import logging
import torch
from pathlib import Path
from PIL import Image

log = logging.getLogger(__name__)


def run_txt2img(model_ref, params: dict, mm, pipeline) -> Image.Image:
    """Generate an image from text.

    Params:
        prompt: text prompt (or {caption} reference)
        negative: negative prompt
        width: image width (default: 1024)
        height: image height (default: 1024)
        steps: inference steps (default: 20)
        guidance: guidance scale (default: 3.5 for FLUX, 7.0 for SDXL)
        seed: random seed (-1 for random)
    """
    prompt = params.get("prompt", "")
    negative = params.get("negative", "")
    width = params.get("width", 1024)
    height = params.get("height", 1024)
    steps = params.get("steps", 20)
    guidance = params.get("guidance", 3.5)
    seed = params.get("seed", -1)

    generator = None if seed == -1 else torch.Generator("cpu").manual_seed(seed)

    model_path = mm.model_path(model_ref)
    fmt = model_ref.format or _detect_format(model_path)
    arch = params.get("architecture", _guess_architecture(model_ref, fmt))

    log.info(f"Loading: {model_ref.repo} (format={fmt}, arch={arch}, quantize={model_ref.quantize})")

    loader = LOADERS.get(arch)
    if not loader:
        raise ValueError(f"Unknown architecture: {arch}. Supported: {list(LOADERS.keys())}")

    pipe = loader(model_ref, params, mm, pipeline, model_path)

    # Memory optimization — always enable for low VRAM
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

    # Negative prompt not supported by FLUX
    if negative and arch != "flux":
        kwargs["negative_prompt"] = negative

    result = pipe(**kwargs)
    return result.images[0]


# ── Architecture-specific loaders ──────────────────────────────

def _load_flux_gguf(model_ref, params, mm, pipeline, model_path):
    """FLUX with GGUF quantized transformer."""
    from diffusers import FluxPipeline, FluxTransformer2DModel, GGUFQuantizationConfig

    gguf_config = GGUFQuantizationConfig(compute_dtype=torch.bfloat16)
    transformer = FluxTransformer2DModel.from_single_file(
        str(model_path),
        quantization_config=gguf_config,
        torch_dtype=torch.bfloat16,
    )

    # Load remaining components from base repo
    pipe = FluxPipeline.from_pretrained(
        "black-forest-labs/FLUX.1-dev",
        transformer=transformer,
        torch_dtype=torch.bfloat16,
    )
    return pipe


def _load_flux_diffusers(model_ref, params, mm, pipeline, model_path):
    """FLUX from diffusers-format repo or single file."""
    from diffusers import FluxPipeline

    quant_config = _get_quant_config(model_ref.quantize)
    kwargs = {"torch_dtype": torch.bfloat16}
    if quant_config:
        kwargs["quantization_config"] = quant_config

    if model_path.is_file():
        pipe = FluxPipeline.from_single_file(str(model_path), **kwargs)
    else:
        pipe = FluxPipeline.from_pretrained(str(model_path), **kwargs)
    return pipe


def _load_sdxl(model_ref, params, mm, pipeline, model_path):
    """SDXL from checkpoint file or diffusers repo."""
    from diffusers import StableDiffusionXLPipeline

    quant_config = _get_quant_config(model_ref.quantize)
    kwargs = {"torch_dtype": torch.float16}
    if quant_config:
        kwargs["quantization_config"] = quant_config

    if model_path.is_file():
        pipe = StableDiffusionXLPipeline.from_single_file(str(model_path), **kwargs)
    else:
        pipe = StableDiffusionXLPipeline.from_pretrained(str(model_path), **kwargs)
    return pipe


def _load_sd15(model_ref, params, mm, pipeline, model_path):
    """SD 1.5 from checkpoint file or diffusers repo."""
    from diffusers import StableDiffusionPipeline

    quant_config = _get_quant_config(model_ref.quantize)
    kwargs = {"torch_dtype": torch.float16}
    if quant_config:
        kwargs["quantization_config"] = quant_config

    if model_path.is_file():
        pipe = StableDiffusionPipeline.from_single_file(str(model_path), **kwargs)
    else:
        pipe = StableDiffusionPipeline.from_pretrained(str(model_path), **kwargs)
    return pipe


def _load_auto(model_ref, params, mm, pipeline, model_path):
    """Auto-detect pipeline type."""
    from diffusers import AutoPipelineForText2Image

    quant_config = _get_quant_config(model_ref.quantize)
    kwargs = {"torch_dtype": torch.bfloat16, "trust_remote_code": True}
    if quant_config:
        kwargs["quantization_config"] = quant_config

    if model_path.is_file():
        # Try SDXL first for single files, fall back to SD1.5
        try:
            from diffusers import StableDiffusionXLPipeline
            return StableDiffusionXLPipeline.from_single_file(str(model_path), **kwargs)
        except Exception:
            from diffusers import StableDiffusionPipeline
            return StableDiffusionPipeline.from_single_file(str(model_path), **kwargs)
    else:
        return AutoPipelineForText2Image.from_pretrained(str(model_path), **kwargs)


# ── Registry ───────────────────────────────────────────────────

LOADERS = {
    "flux": _load_flux_diffusers,
    "flux-gguf": _load_flux_gguf,
    "sdxl": _load_sdxl,
    "sd15": _load_sd15,
    "sd": _load_sd15,
    "auto": _load_auto,
}


# ── Helpers ────────────────────────────────────────────────────

def _get_quant_config(quantize: str | None):
    """Build a BitsAndBytesConfig from quantization string."""
    if not quantize:
        return None

    from diffusers import BitsAndBytesConfig

    if quantize == "nf4":
        return BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_quant_type="nf4",
            bnb_4bit_compute_dtype=torch.bfloat16,
        )
    elif quantize in ("fp8", "int8"):
        return BitsAndBytesConfig(load_in_8bit=True)
    elif quantize == "fp4":
        return BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_quant_type="fp4",
            bnb_4bit_compute_dtype=torch.bfloat16,
        )
    return None


def _detect_format(path: Path) -> str:
    """Detect model format from file extension."""
    p = Path(path)
    if p.is_dir():
        return "diffusers"
    suffix = p.suffix.lower()
    return {"gguf": "gguf", ".safetensors": "safetensors", ".bin": "bin", ".ckpt": "checkpoint"}.get(suffix, "unknown")


def _guess_architecture(model_ref, fmt: str) -> str:
    """Guess model architecture from name/repo/format."""
    name = (model_ref.repo + (model_ref.file or "")).lower()

    if fmt == "gguf" and "flux" in name:
        return "flux-gguf"
    if "flux" in name:
        return "flux"
    if "sdxl" in name or "xl" in name or "pony" in name:
        return "sdxl"
    if "sd15" in name or "sd_1" in name or "v1-5" in name:
        return "sd15"

    # Default to auto-detection
    return "auto"
