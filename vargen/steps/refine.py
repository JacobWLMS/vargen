"""Image-to-image refinement step — supports SDXL, SD1.5, and auto-detect."""

import logging
import torch
from pathlib import Path
from PIL import Image

log = logging.getLogger(__name__)


def run_img2img(model_ref, params: dict, mm, pipeline) -> Image.Image:
    """Refine an image using img2img diffusion.

    Params:
        input: source image (usually {previous_step} reference)
        prompt: text prompt
        negative: negative prompt
        steps: inference steps (default: 5)
        denoise: denoising strength (default: 0.5)
        guidance: guidance scale (default: 1.0)
        architecture: force architecture ("sdxl", "sd15", "flux", "auto")
    """
    input_img = params.get("input") or params.get("input_image")
    if input_img is None:
        raise ValueError("img2img step requires 'input'")
    if not isinstance(input_img, Image.Image):
        raise ValueError(f"img2img 'input' must be a PIL Image, got {type(input_img)}")

    prompt = params.get("prompt", "")
    negative = params.get("negative", "")
    steps = params.get("steps", 5)
    denoise = params.get("denoise", 0.5)
    guidance = params.get("guidance", 1.0)

    model_path = mm.model_path(model_ref)
    arch = params.get("architecture", _guess_architecture(model_ref))

    log.info(f"Loading refiner: {model_ref.repo} (arch={arch}, quantize={model_ref.quantize})")

    loader = LOADERS.get(arch, _load_auto)
    pipe = loader(model_ref, model_path)

    if hasattr(pipe, "enable_model_cpu_offload"):
        pipe.enable_model_cpu_offload()
    if hasattr(pipe, "enable_attention_slicing"):
        pipe.enable_attention_slicing()

    mm.register("refine_pipeline", pipe)

    input_img = input_img.convert("RGB")
    log.info(f"Refining: {steps} steps, denoise {denoise}, guidance {guidance}")

    kwargs = {
        "prompt": prompt,
        "image": input_img,
        "num_inference_steps": steps,
        "strength": denoise,
        "guidance_scale": guidance,
    }
    if negative:
        kwargs["negative_prompt"] = negative

    result = pipe(**kwargs)
    return result.images[0]


# ── Architecture-specific loaders ──────────────────────────────

def _load_sdxl_img2img(model_ref, model_path):
    from diffusers import StableDiffusionXLImg2ImgPipeline
    kwargs = {"torch_dtype": torch.float16}
    quant = _get_quant_config(model_ref.quantize)
    if quant:
        kwargs["quantization_config"] = quant
    if model_path.is_file():
        return StableDiffusionXLImg2ImgPipeline.from_single_file(str(model_path), **kwargs)
    return StableDiffusionXLImg2ImgPipeline.from_pretrained(str(model_path), **kwargs)


def _load_sd15_img2img(model_ref, model_path):
    from diffusers import StableDiffusionImg2ImgPipeline
    kwargs = {"torch_dtype": torch.float16}
    quant = _get_quant_config(model_ref.quantize)
    if quant:
        kwargs["quantization_config"] = quant
    if model_path.is_file():
        return StableDiffusionImg2ImgPipeline.from_single_file(str(model_path), **kwargs)
    return StableDiffusionImg2ImgPipeline.from_pretrained(str(model_path), **kwargs)


def _load_flux_img2img(model_ref, model_path):
    from diffusers import FluxImg2ImgPipeline
    kwargs = {"torch_dtype": torch.bfloat16}
    quant = _get_quant_config(model_ref.quantize)
    if quant:
        kwargs["quantization_config"] = quant
    if model_path.is_file():
        return FluxImg2ImgPipeline.from_single_file(str(model_path), **kwargs)
    return FluxImg2ImgPipeline.from_pretrained(str(model_path), **kwargs)


def _load_auto(model_ref, model_path):
    from diffusers import AutoPipelineForImage2Image
    kwargs = {"torch_dtype": torch.bfloat16, "trust_remote_code": True}
    quant = _get_quant_config(model_ref.quantize)
    if quant:
        kwargs["quantization_config"] = quant
    if model_path.is_file():
        try:
            return _load_sdxl_img2img(model_ref, model_path)
        except Exception:
            return _load_sd15_img2img(model_ref, model_path)
    return AutoPipelineForImage2Image.from_pretrained(str(model_path), **kwargs)


LOADERS = {
    "sdxl": _load_sdxl_img2img,
    "sd15": _load_sd15_img2img,
    "sd": _load_sd15_img2img,
    "flux": _load_flux_img2img,
    "auto": _load_auto,
}


# ── Helpers ────────────────────────────────────────────────────

def _get_quant_config(quantize):
    if not quantize:
        return None
    from diffusers import BitsAndBytesConfig
    if quantize == "nf4":
        return BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="nf4", bnb_4bit_compute_dtype=torch.bfloat16)
    elif quantize in ("fp8", "int8"):
        return BitsAndBytesConfig(load_in_8bit=True)
    return None


def _guess_architecture(model_ref) -> str:
    name = (model_ref.repo + (model_ref.file or "")).lower()
    if "flux" in name:
        return "flux"
    if "sdxl" in name or "xl" in name or "pony" in name:
        return "sdxl"
    if "sd15" in name or "sd_1" in name or "v1-5" in name:
        return "sd15"
    return "auto"
