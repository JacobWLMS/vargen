"""Latent space nodes — VAE encode/decode, empty latent."""

import torch
import numpy as np
import logging
from PIL import Image

from . import register_node, NodeTypeDef, PortDef, WidgetDef

log = logging.getLogger(__name__)


def exec_empty_latent(inputs, widgets, ctx):
    width = int(widgets.get("width", 1024))
    height = int(widgets.get("height", 1024))
    batch = int(widgets.get("batch_size", 1))
    latent = torch.randn(batch, 4, height // 8, width // 8, dtype=torch.float16)
    log.info(f"Empty latent: {batch}x4x{height // 8}x{width // 8}")
    return {"LATENT": latent, "_width": width, "_height": height}


def exec_vae_decode(inputs, widgets, ctx):
    vae = inputs.get("VAE")
    latent = inputs.get("LATENT")
    if vae is None:
        raise ValueError("VAE Decode needs a VAE — connect from Load Checkpoint")
    if latent is None:
        raise ValueError("VAE Decode needs LATENT — connect from KSampler")

    tiled = bool(widgets.get("tiled", False))
    log.info(f"VAE Decode: latent {latent.shape if hasattr(latent, 'shape') else type(latent)} (tiled={tiled})")

    # Move VAE to GPU if available
    if torch.cuda.is_available():
        vae = vae.to("cuda")
        device = "cuda"
    else:
        device = next(vae.parameters()).device if hasattr(vae, 'parameters') else 'cpu'

    if tiled and hasattr(vae, 'enable_tiling'):
        vae.enable_tiling()

    with torch.no_grad():
        latent = latent.to(device=device, dtype=vae.dtype)
        if hasattr(vae, 'config') and hasattr(vae.config, 'scaling_factor'):
            latent = latent / vae.config.scaling_factor
        decoded = vae.decode(latent, return_dict=False)[0]

    if tiled and hasattr(vae, 'disable_tiling'):
        vae.disable_tiling()

    vae.to("cpu")
    if torch.cuda.is_available():
        torch.cuda.empty_cache()

    # Tensor → PIL
    decoded = (decoded / 2 + 0.5).clamp(0, 1)
    decoded = decoded.cpu().permute(0, 2, 3, 1).float().numpy()
    decoded = (decoded[0] * 255).round().astype("uint8")
    result = Image.fromarray(decoded)
    log.info(f"VAE Decoded: {result.size}")
    return {"IMAGE": result}


def exec_vae_encode(inputs, widgets, ctx):
    vae = inputs.get("VAE")
    image = inputs.get("IMAGE")
    if vae is None or image is None:
        raise ValueError("VAE Encode needs both VAE and IMAGE")

    log.info(f"VAE Encode: {image.size}")
    device = next(vae.parameters()).device if hasattr(vae, 'parameters') else 'cpu'

    img_np = np.array(image.convert("RGB")).astype(np.float32) / 255.0
    img_tensor = torch.from_numpy(img_np).permute(2, 0, 1).unsqueeze(0)
    img_tensor = img_tensor * 2.0 - 1.0
    img_tensor = img_tensor.to(device=device, dtype=vae.dtype)

    with torch.no_grad():
        latent = vae.encode(img_tensor).latent_dist.sample()
        if hasattr(vae, 'config') and hasattr(vae.config, 'scaling_factor'):
            latent = latent * vae.config.scaling_factor

    log.info(f"VAE Encoded: {latent.shape}")
    return {"LATENT": latent}


# ── Register ──────────────────────────────────

register_node(NodeTypeDef(
    type_id="empty_latent", category="latent", label="Empty Latent Image",
    inputs=[],
    outputs=[PortDef("LATENT", "LATENT")],
    widgets=[
        WidgetDef("width", "number", default=1024, min=64, max=4096, step=64, label="Width"),
        WidgetDef("height", "number", default=1024, min=64, max=4096, step=64, label="Height"),
        WidgetDef("batch_size", "number", default=1, min=1, max=64, step=1, label="Batch"),
    ],
    execute=exec_empty_latent, color="#f472b6",
    description="Create an empty latent image (random noise)",
))

register_node(NodeTypeDef(
    type_id="vae_decode", category="latent", label="VAE Decode",
    inputs=[PortDef("VAE", "VAE"), PortDef("LATENT", "LATENT")],
    outputs=[PortDef("IMAGE", "IMAGE")],
    widgets=[
        WidgetDef("tiled", "toggle", default=False, label="Tiled (low VRAM)"),
    ],
    execute=exec_vae_decode, color="#f87171",
    description="Decode latent to image using VAE",
))

register_node(NodeTypeDef(
    type_id="vae_encode", category="latent", label="VAE Encode",
    inputs=[PortDef("VAE", "VAE"), PortDef("IMAGE", "IMAGE")],
    outputs=[PortDef("LATENT", "LATENT")],
    widgets=[],
    execute=exec_vae_encode, color="#f87171",
    description="Encode image to latent using VAE",
))
