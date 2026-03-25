"""Loader nodes — load models, images, create empty latents."""

import torch
import logging
from PIL import Image
from pathlib import Path

from . import register_node, NodeTypeDef, PortDef, WidgetDef

log = logging.getLogger(__name__)


def exec_load_checkpoint(inputs, widgets, ctx):
    ckpt_name = widgets.get("checkpoint", "")
    if not ckpt_name:
        raise ValueError("No checkpoint selected")

    model_path = ctx["model_manager"].find_model("checkpoints", ckpt_name)
    if not model_path:
        model_path = ctx["model_manager"].find_model("diffusion_models", ckpt_name)
    if not model_path:
        raise ValueError(f"Checkpoint not found: {ckpt_name}")

    log.info(f"Loading: {model_path}")
    is_gguf = str(model_path).lower().endswith(".gguf")
    is_flux = "flux" in ckpt_name.lower() or "flux" in str(model_path).lower()

    # FLUX models (including GGUF)
    if is_flux or is_gguf:
        pipe = _load_flux_checkpoint(model_path, is_gguf)
        arch = "flux"
    else:
        pipe = _load_sd_checkpoint(model_path)
        arch = "sdxl" if hasattr(pipe, 'text_encoder_2') else "sd15"

    # VRAM management
    _setup_vram_offload(pipe)

    log.info(f"Loaded {arch}: {ckpt_name}")

    # Return individual components
    return {
        "MODEL": pipe.unet,
        "CLIP": {
            "tokenizer": pipe.tokenizer,
            "text_encoder": pipe.text_encoder,
            "tokenizer_2": getattr(pipe, "tokenizer_2", None),
            "text_encoder_2": getattr(pipe, "text_encoder_2", None),
            "arch": arch,
        },
        "VAE": pipe.vae,
        "_pipe": pipe,
    }


def _load_flux_checkpoint(model_path, is_gguf):
    """Load FLUX model — handles GGUF, safetensors, and HF repo."""
    from diffusers import FluxPipeline

    if is_gguf:
        try:
            from diffusers import FluxTransformer2DModel, GGUFQuantizationConfig
        except ImportError:
            raise ValueError(
                "GGUF support requires: pip install gguf>=0.10.0\n"
                "Run: pip install gguf"
            )
        log.info("Loading FLUX GGUF (quantized)")
        gguf_config = GGUFQuantizationConfig(compute_dtype=torch.bfloat16)
        transformer = FluxTransformer2DModel.from_single_file(
            str(model_path), quantization_config=gguf_config, torch_dtype=torch.bfloat16,
        )
        pipe = FluxPipeline.from_pretrained(
            "black-forest-labs/FLUX.1-dev", transformer=transformer, torch_dtype=torch.bfloat16,
        )
    elif model_path.is_file():
        pipe = FluxPipeline.from_single_file(str(model_path), torch_dtype=torch.bfloat16)
    else:
        pipe = FluxPipeline.from_pretrained(str(model_path), torch_dtype=torch.bfloat16)

    return pipe


def _load_sd_checkpoint(model_path):
    """Load SD1.5/SDXL checkpoint — tries SDXL first, falls back to SD1.5."""
    from diffusers import StableDiffusionXLPipeline, StableDiffusionPipeline, AutoPipelineForText2Image

    kwargs = {"torch_dtype": torch.float16, "trust_remote_code": True}

    if model_path.is_file():
        try:
            return StableDiffusionXLPipeline.from_single_file(str(model_path), **kwargs)
        except Exception:
            try:
                return StableDiffusionPipeline.from_single_file(str(model_path), **kwargs)
            except Exception as e:
                raise ValueError(f"Failed to load checkpoint as SD1.5 or SDXL: {e}")
    else:
        return AutoPipelineForText2Image.from_pretrained(str(model_path), **kwargs)


def _setup_vram_offload(pipe):
    """Configure VRAM offloading based on available memory."""
    if torch.cuda.is_available():
        free_mb = torch.cuda.mem_get_info()[0] // (1024 * 1024)
        total_mb = torch.cuda.mem_get_info()[1] // (1024 * 1024)
        log.info(f"VRAM: {free_mb}MB free / {total_mb}MB total")

        if free_mb < 4000:
            log.info("Very low VRAM (<4GB): sequential CPU offload")
            pipe.enable_sequential_cpu_offload()
        elif free_mb < 8000:
            log.info("Low VRAM (<8GB): model CPU offload")
            pipe.enable_model_cpu_offload()
        else:
            log.info("Sufficient VRAM: keeping on GPU")
            pipe.to("cuda")
    else:
        log.info("No CUDA: running on CPU")
        pipe.to("cpu")

    if hasattr(pipe, "enable_attention_slicing"):
        pipe.enable_attention_slicing()
    if hasattr(pipe, 'enable_vae_tiling'):
        pipe.enable_vae_tiling()


def exec_load_lora(inputs, widgets, ctx):
    pipe = inputs.get("_pipe")
    if not pipe:
        raise ValueError("LoRA needs a pipeline — connect to Load Checkpoint")

    lora_name = widgets.get("lora", "")
    strength = widgets.get("strength", 0.7)
    if not lora_name:
        raise ValueError("No LoRA selected")

    model_path = ctx["model_manager"].find_model("loras", lora_name)
    if not model_path:
        raise ValueError(f"LoRA not found: {lora_name}")

    log.info(f"Loading LoRA: {model_path} (strength: {strength})")
    pipe.load_lora_weights(str(model_path))
    pipe.fuse_lora(lora_scale=strength)

    return {
        "MODEL": pipe.unet,
        "CLIP": inputs.get("CLIP"),
        "_pipe": pipe,
    }


def exec_load_image(inputs, widgets, ctx):
    image = ctx.get("input_image")
    if image is None:
        raise ValueError("No input image — upload one to the Load Image node")
    if not isinstance(image, Image.Image):
        image = Image.open(image).convert("RGB")
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
    if torch.cuda.is_available():
        model = model.cuda()
    log.info(f"Loaded upscale model: {model_name}")
    return {"UPSCALE_MODEL": model}


# ── Register ──────────────────────────────────

register_node(NodeTypeDef(
    type_id="load_checkpoint", category="loaders", label="Load Checkpoint",
    inputs=[],
    outputs=[PortDef("MODEL", "MODEL"), PortDef("CLIP", "CLIP"), PortDef("VAE", "VAE")],
    widgets=[WidgetDef("checkpoint", "combo", label="Checkpoint", options=[])],
    execute=exec_load_checkpoint, color="#a855f7",
    description="Load a Stable Diffusion / SDXL checkpoint",
))

register_node(NodeTypeDef(
    type_id="load_lora", category="loaders", label="Load LoRA",
    inputs=[PortDef("MODEL", "MODEL"), PortDef("CLIP", "CLIP")],
    outputs=[PortDef("MODEL", "MODEL"), PortDef("CLIP", "CLIP")],
    widgets=[
        WidgetDef("lora", "combo", label="LoRA", options=[]),
        WidgetDef("strength", "slider", default=0.7, min=0, max=2, step=0.05, label="Strength"),
    ],
    execute=exec_load_lora, color="#c084fc",
))

register_node(NodeTypeDef(
    type_id="load_image", category="loaders", label="Load Image",
    inputs=[], outputs=[PortDef("IMAGE", "IMAGE")], widgets=[],
    execute=exec_load_image, color="#38bdf8",
))

register_node(NodeTypeDef(
    type_id="load_upscale_model", category="loaders", label="Load Upscale Model",
    inputs=[], outputs=[PortDef("UPSCALE_MODEL", "UPSCALE_MODEL")],
    widgets=[WidgetDef("model", "combo", label="Model", options=[])],
    execute=exec_load_upscale_model, color="#2dd4bf",
))
