"""Loader nodes — load models, images, create empty latents."""

import torch
import logging
from PIL import Image
from pathlib import Path

from . import register_node, NodeTypeDef, PortDef, WidgetDef

log = logging.getLogger(__name__)


def exec_load_checkpoint(inputs, widgets, ctx):
    from diffusers import StableDiffusionXLPipeline, StableDiffusionPipeline, AutoPipelineForText2Image

    ckpt_name = widgets.get("checkpoint", "")
    if not ckpt_name:
        raise ValueError("No checkpoint selected")

    model_path = ctx["model_manager"].find_model("checkpoints", ckpt_name)
    if not model_path:
        model_path = ctx["model_manager"].find_model("diffusion_models", ckpt_name)
    if not model_path:
        raise ValueError(f"Checkpoint not found: {ckpt_name}")

    log.info(f"Loading checkpoint: {model_path}")
    kwargs = {"torch_dtype": torch.float16, "trust_remote_code": True}

    try:
        pipe = StableDiffusionXLPipeline.from_single_file(str(model_path), **kwargs)
        arch = "sdxl"
    except Exception:
        try:
            pipe = StableDiffusionPipeline.from_single_file(str(model_path), **kwargs)
            arch = "sd15"
        except Exception:
            pipe = AutoPipelineForText2Image.from_pretrained(str(model_path), **kwargs)
            arch = "auto"

    pipe.enable_model_cpu_offload()
    if hasattr(pipe, "enable_attention_slicing"):
        pipe.enable_attention_slicing()

    log.info(f"Loaded {arch} checkpoint: {ckpt_name}")

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


def exec_empty_latent(inputs, widgets, ctx):
    width = int(widgets.get("width", 1024))
    height = int(widgets.get("height", 1024))
    batch = int(widgets.get("batch_size", 1))
    latent = torch.randn(batch, 4, height // 8, width // 8, dtype=torch.float16)
    log.info(f"Empty latent: {batch}x4x{height // 8}x{width // 8}")
    return {"LATENT": latent, "_width": width, "_height": height}


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


# ── VAE nodes ─────────────────────────────────

def exec_vae_decode(inputs, widgets, ctx):
    vae = inputs.get("VAE")
    latent = inputs.get("LATENT")
    if vae is None:
        raise ValueError("VAE Decode needs a VAE input")
    if latent is None:
        raise ValueError("VAE Decode needs a LATENT input")

    log.info(f"VAE Decode: latent shape {latent.shape}")
    device = next(vae.parameters()).device if hasattr(vae, 'parameters') else 'cpu'

    with torch.no_grad():
        latent = latent.to(device=device, dtype=vae.dtype)
        # Scale latent
        if hasattr(vae, 'config') and hasattr(vae.config, 'scaling_factor'):
            latent = latent / vae.config.scaling_factor
        image = vae.decode(latent, return_dict=False)[0]

    # Convert to PIL
    image = (image / 2 + 0.5).clamp(0, 1)
    image = image.cpu().permute(0, 2, 3, 1).float().numpy()
    image = (image[0] * 255).round().astype("uint8")
    result = Image.fromarray(image)
    log.info(f"VAE Decoded: {result.size}")
    return {"IMAGE": result}


def exec_vae_encode(inputs, widgets, ctx):
    vae = inputs.get("VAE")
    image = inputs.get("IMAGE")
    if vae is None or image is None:
        raise ValueError("VAE Encode needs both VAE and IMAGE")

    import numpy as np
    log.info(f"VAE Encode: image {image.size}")
    device = next(vae.parameters()).device if hasattr(vae, 'parameters') else 'cpu'

    # PIL to tensor
    img_np = np.array(image.convert("RGB")).astype(np.float32) / 255.0
    img_tensor = torch.from_numpy(img_np).permute(2, 0, 1).unsqueeze(0)
    img_tensor = img_tensor * 2.0 - 1.0  # normalize to [-1, 1]
    img_tensor = img_tensor.to(device=device, dtype=vae.dtype)

    with torch.no_grad():
        latent = vae.encode(img_tensor).latent_dist.sample()
        if hasattr(vae, 'config') and hasattr(vae.config, 'scaling_factor'):
            latent = latent * vae.config.scaling_factor

    log.info(f"VAE Encoded: {latent.shape}")
    return {"LATENT": latent}


# ── Register ──────────────────────────────────

register_node(NodeTypeDef(
    type_id="load_checkpoint", category="loaders", label="Load Checkpoint",
    inputs=[],
    outputs=[PortDef("MODEL", "MODEL"), PortDef("CLIP", "CLIP"), PortDef("VAE", "VAE")],
    widgets=[WidgetDef("checkpoint", "combo", label="Checkpoint", options=[])],
    execute=exec_load_checkpoint, color="#7c3aed",
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
    execute=exec_load_lora, color="#7c3aed",
))

register_node(NodeTypeDef(
    type_id="load_image", category="loaders", label="Load Image",
    inputs=[], outputs=[PortDef("IMAGE", "IMAGE")], widgets=[],
    execute=exec_load_image, color="#60a0ff",
))

register_node(NodeTypeDef(
    type_id="empty_latent", category="loaders", label="Empty Latent Image",
    inputs=[],
    outputs=[PortDef("LATENT", "LATENT")],
    widgets=[
        WidgetDef("width", "number", default=1024, min=64, max=4096, step=64, label="Width"),
        WidgetDef("height", "number", default=1024, min=64, max=4096, step=64, label="Height"),
        WidgetDef("batch_size", "number", default=1, min=1, max=64, step=1, label="Batch"),
    ],
    execute=exec_empty_latent, color="#ff80c0",
))

register_node(NodeTypeDef(
    type_id="load_upscale_model", category="loaders", label="Load Upscale Model",
    inputs=[], outputs=[PortDef("UPSCALE_MODEL", "UPSCALE_MODEL")],
    widgets=[WidgetDef("model", "combo", label="Model", options=[])],
    execute=exec_load_upscale_model, color="#60a0ff",
))

register_node(NodeTypeDef(
    type_id="vae_decode", category="loaders", label="VAE Decode",
    inputs=[PortDef("VAE", "VAE"), PortDef("LATENT", "LATENT")],
    outputs=[PortDef("IMAGE", "IMAGE")],
    widgets=[],
    execute=exec_vae_decode, color="#ff6060",
    description="Decode latent to image using VAE",
))

register_node(NodeTypeDef(
    type_id="vae_encode", category="loaders", label="VAE Encode",
    inputs=[PortDef("VAE", "VAE"), PortDef("IMAGE", "IMAGE")],
    outputs=[PortDef("LATENT", "LATENT")],
    widgets=[],
    execute=exec_vae_encode, color="#ff6060",
    description="Encode image to latent using VAE",
))
