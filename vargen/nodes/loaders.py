"""Loader nodes — load models, images, and create empty latents."""

import torch
import logging
from PIL import Image
from pathlib import Path

from . import register_node, NodeTypeDef, PortDef, WidgetDef

log = logging.getLogger(__name__)


def exec_load_checkpoint(inputs, widgets, ctx):
    from diffusers import StableDiffusionXLPipeline, StableDiffusionPipeline, AutoPipelineForText2Image

    ckpt_name = widgets["checkpoint"]
    model_path = ctx["model_manager"].find_model("checkpoints", ckpt_name)
    if not model_path:
        raise ValueError(f"Checkpoint not found: {ckpt_name}")

    log.info(f"Loading checkpoint: {model_path}")

    # Try SDXL first, fall back to SD1.5
    kwargs = {"torch_dtype": torch.float16, "trust_remote_code": True}
    try:
        pipe = StableDiffusionXLPipeline.from_single_file(str(model_path), **kwargs)
    except Exception:
        try:
            pipe = StableDiffusionPipeline.from_single_file(str(model_path), **kwargs)
        except Exception:
            pipe = AutoPipelineForText2Image.from_pretrained(str(model_path), **kwargs)

    if hasattr(pipe, "enable_model_cpu_offload"):
        pipe.enable_model_cpu_offload()

    return {"MODEL": pipe.unet, "CLIP": pipe.tokenizer, "VAE": pipe.vae, "_pipe": pipe}


def exec_load_lora(inputs, widgets, ctx):
    pipe = inputs.get("_pipe")
    if not pipe:
        raise ValueError("LoRA requires a loaded pipeline (connect to Load Checkpoint)")

    lora_name = widgets["lora"]
    strength = widgets.get("strength", 0.7)
    model_path = ctx["model_manager"].find_model("loras", lora_name)
    if not model_path:
        raise ValueError(f"LoRA not found: {lora_name}")

    log.info(f"Loading LoRA: {model_path} (strength: {strength})")
    pipe.load_lora_weights(str(model_path))
    pipe.fuse_lora(lora_scale=strength)

    return {"MODEL": pipe.unet, "CLIP": pipe.tokenizer, "_pipe": pipe}


def exec_load_image(inputs, widgets, ctx):
    image = ctx.get("input_image")
    if image is None:
        raise ValueError("No input image provided")
    if not isinstance(image, Image.Image):
        image = Image.open(image).convert("RGB")
    return {"IMAGE": image}


def exec_empty_latent(inputs, widgets, ctx):
    width = widgets.get("width", 1024)
    height = widgets.get("height", 1024)
    batch = widgets.get("batch_size", 1)

    latent = torch.zeros(batch, 4, height // 8, width // 8)
    return {"LATENT": latent, "_width": width, "_height": height}


def exec_load_upscale_model(inputs, widgets, ctx):
    model_name = widgets["model"]
    model_path = ctx["model_manager"].find_model("upscale_models", model_name)
    if not model_path:
        raise ValueError(f"Upscale model not found: {model_name}")

    try:
        import spandrel
        model = spandrel.ModelLoader().load_from_file(str(model_path))
        model = model.eval()
        if torch.cuda.is_available():
            model = model.cuda()
        return {"UPSCALE_MODEL": model}
    except ImportError:
        raise ValueError("spandrel package required for upscale models")


# ── Register ──────────────────────────────────

register_node(NodeTypeDef(
    type_id="load_checkpoint",
    category="loaders",
    label="Load Checkpoint",
    inputs=[],
    outputs=[
        PortDef("MODEL", "MODEL"),
        PortDef("CLIP", "CLIP"),
        PortDef("VAE", "VAE"),
    ],
    widgets=[
        WidgetDef("checkpoint", "combo", label="Checkpoint", options=[]),
    ],
    execute=exec_load_checkpoint,
    color="#7c3aed",
    description="Load a Stable Diffusion / SDXL checkpoint",
))

register_node(NodeTypeDef(
    type_id="load_lora",
    category="loaders",
    label="Load LoRA",
    inputs=[
        PortDef("MODEL", "MODEL"),
        PortDef("CLIP", "CLIP"),
    ],
    outputs=[
        PortDef("MODEL", "MODEL"),
        PortDef("CLIP", "CLIP"),
    ],
    widgets=[
        WidgetDef("lora", "combo", label="LoRA", options=[]),
        WidgetDef("strength", "slider", default=0.7, min=0, max=2, step=0.05, label="Strength"),
    ],
    execute=exec_load_lora,
    color="#7c3aed",
    description="Load and apply a LoRA",
))

register_node(NodeTypeDef(
    type_id="load_image",
    category="loaders",
    label="Load Image",
    inputs=[],
    outputs=[PortDef("IMAGE", "IMAGE")],
    widgets=[],
    execute=exec_load_image,
    color="#22c55e",
    description="Load the input reference image",
))

register_node(NodeTypeDef(
    type_id="empty_latent",
    category="loaders",
    label="Empty Latent Image",
    inputs=[],
    outputs=[PortDef("LATENT", "LATENT")],
    widgets=[
        WidgetDef("width", "number", default=1024, min=64, max=4096, step=64, label="Width"),
        WidgetDef("height", "number", default=1024, min=64, max=4096, step=64, label="Height"),
        WidgetDef("batch_size", "number", default=1, min=1, max=64, step=1, label="Batch Size"),
    ],
    execute=exec_empty_latent,
    color="#ec4899",
    description="Create an empty latent image",
))

register_node(NodeTypeDef(
    type_id="load_upscale_model",
    category="loaders",
    label="Load Upscale Model",
    inputs=[],
    outputs=[PortDef("UPSCALE_MODEL", "UPSCALE_MODEL")],
    widgets=[
        WidgetDef("model", "combo", label="Model", options=[]),
    ],
    execute=exec_load_upscale_model,
    color="#7c3aed",
    description="Load a pixel upscale model (RealESRGAN, etc.)",
))
