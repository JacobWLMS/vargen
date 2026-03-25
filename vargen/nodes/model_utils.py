"""Model utility nodes — FreeU, textual inversion, VAE loading, latent operations."""

import torch
import logging
import numpy as np
from PIL import Image

from . import register_node, NodeTypeDef, PortDef, WidgetDef

log = logging.getLogger(__name__)


# ── FreeU ─────────────────────────────────────

def exec_freeu(inputs, widgets, ctx):
    pipe = inputs.get("_pipe")
    if not pipe:
        raise ValueError("FreeU needs a pipeline — connect from Load Checkpoint")

    b1 = float(widgets.get("b1", 1.1))
    b2 = float(widgets.get("b2", 1.2))
    s1 = float(widgets.get("s1", 0.6))
    s2 = float(widgets.get("s2", 0.4))

    pipe.enable_freeu(s1=s1, s2=s2, b1=b1, b2=b2)
    log.info(f"FreeU enabled: b1={b1} b2={b2} s1={s1} s2={s2}")
    return {"MODEL": pipe.unet, "_pipe": pipe}


# ── Textual Inversion ─────────────────────────

def exec_load_textual_inversion(inputs, widgets, ctx):
    pipe = inputs.get("_pipe")
    if not pipe:
        raise ValueError("Load TI needs a pipeline — connect from Load Checkpoint")

    embedding_name = widgets.get("embedding", "")
    token = widgets.get("token", "") or None

    if not embedding_name:
        raise ValueError("No embedding selected")

    model_path = ctx["model_manager"].find_model("embeddings", embedding_name)
    if not model_path:
        raise ValueError(f"Embedding not found: {embedding_name}")

    log.info(f"Loading textual inversion: {model_path} (token: {token or 'auto'})")
    pipe.load_textual_inversion(str(model_path), token=token)
    return {"MODEL": pipe.unet, "CLIP": inputs.get("CLIP"), "_pipe": pipe}


# ── Load standalone VAE ───────────────────────

def exec_load_vae(inputs, widgets, ctx):
    from diffusers import AutoencoderKL

    vae_name = widgets.get("vae", "")
    if not vae_name:
        raise ValueError("No VAE selected")

    model_path = ctx["model_manager"].find_model("vae", vae_name)
    if model_path:
        log.info(f"Loading VAE from file: {model_path}")
        vae = AutoencoderKL.from_single_file(str(model_path), torch_dtype=torch.float16)
    else:
        log.info(f"Loading VAE from repo: {vae_name}")
        vae = AutoencoderKL.from_pretrained(vae_name, torch_dtype=torch.float16)

    return {"VAE": vae}


# ── Latent Upscale ────────────────────────────

def exec_latent_upscale(inputs, widgets, ctx):
    latent = inputs.get("LATENT")
    if latent is None:
        raise ValueError("Latent Upscale needs LATENT input")

    method = widgets.get("method", "bilinear")
    scale = float(widgets.get("scale_by", 2.0))

    h, w = latent.shape[-2], latent.shape[-1]
    new_h, new_w = int(h * scale), int(w * scale)

    mode = {"nearest": "nearest", "bilinear": "bilinear", "bicubic": "bicubic", "bislerp": "bilinear"}.get(method, "bilinear")
    upscaled = torch.nn.functional.interpolate(latent.float(), size=(new_h, new_w), mode=mode, align_corners=False if mode != "nearest" else None)
    upscaled = upscaled.to(latent.dtype)

    log.info(f"Latent upscaled: {h}x{w} → {new_h}x{new_w} ({method})")
    return {"LATENT": upscaled, "_width": new_w * 8, "_height": new_h * 8}


# ── Image Composite ──────────────────────────

def exec_image_composite(inputs, widgets, ctx):
    base = inputs.get("IMAGE")
    overlay = inputs.get("IMAGE_2")
    mask = inputs.get("MASK")

    if not base or not overlay:
        raise ValueError("Image Composite needs IMAGE and IMAGE_2")

    x = int(widgets.get("x", 0))
    y = int(widgets.get("y", 0))

    base = base.convert("RGBA")
    overlay = overlay.convert("RGBA")

    if mask:
        if isinstance(mask, Image.Image):
            mask = mask.convert("L")
        overlay.putalpha(mask.resize(overlay.size))

    result = base.copy()
    result.paste(overlay, (x, y), overlay)
    return {"IMAGE": result.convert("RGB")}


# ── Image Blend ───────────────────────────────

def exec_image_blend(inputs, widgets, ctx):
    image1 = inputs.get("IMAGE")
    image2 = inputs.get("IMAGE_2")
    if not image1 or not image2:
        raise ValueError("Image Blend needs IMAGE and IMAGE_2")

    factor = float(widgets.get("factor", 0.5))
    image2 = image2.resize(image1.size)
    result = Image.blend(image1.convert("RGB"), image2.convert("RGB"), factor)
    return {"IMAGE": result}


# ── Register ──────────────────────────────────

register_node(NodeTypeDef(
    type_id="freeu", category="model", label="FreeU",
    inputs=[PortDef("MODEL", "MODEL")],
    outputs=[PortDef("MODEL", "MODEL")],
    widgets=[
        WidgetDef("b1", "slider", default=1.1, min=1.0, max=1.5, step=0.05, label="B1 (backbone 1)"),
        WidgetDef("b2", "slider", default=1.2, min=1.0, max=1.5, step=0.05, label="B2 (backbone 2)"),
        WidgetDef("s1", "slider", default=0.6, min=0.0, max=1.0, step=0.05, label="S1 (skip 1)"),
        WidgetDef("s2", "slider", default=0.4, min=0.0, max=1.0, step=0.05, label="S2 (skip 2)"),
    ],
    execute=exec_freeu, color="#f97316",
    description="FreeU: enhance quality by scaling backbone/skip features. SDXL: b1=1.1 b2=1.2 s1=0.6 s2=0.4",
))

register_node(NodeTypeDef(
    type_id="load_textual_inversion", category="loaders", label="Load Embedding",
    inputs=[PortDef("MODEL", "MODEL"), PortDef("CLIP", "CLIP")],
    outputs=[PortDef("MODEL", "MODEL"), PortDef("CLIP", "CLIP")],
    widgets=[
        WidgetDef("embedding", "combo", label="Embedding", options=[]),
        WidgetDef("token", "text", default="", label="Trigger Token (auto if empty)"),
    ],
    execute=exec_load_textual_inversion, color="#a855f7",
    description="Load textual inversion / embedding. Use trigger token in prompts.",
))

register_node(NodeTypeDef(
    type_id="load_vae", category="loaders", label="Load VAE",
    inputs=[],
    outputs=[PortDef("VAE", "VAE")],
    widgets=[WidgetDef("vae", "combo", label="VAE", options=[])],
    execute=exec_load_vae, color="#f87171",
    description="Load standalone VAE (e.g. sdxl-vae-fp16-fix)",
))

register_node(NodeTypeDef(
    type_id="latent_upscale", category="latent", label="Latent Upscale",
    inputs=[PortDef("LATENT", "LATENT")],
    outputs=[PortDef("LATENT", "LATENT")],
    widgets=[
        WidgetDef("method", "combo", default="bilinear", label="Method",
                  options=["nearest", "bilinear", "bicubic"]),
        WidgetDef("scale_by", "slider", default=2.0, min=0.5, max=4.0, step=0.25, label="Scale"),
    ],
    execute=exec_latent_upscale, color="#f472b6",
    description="Upscale latent before VAE decode (hires fix)",
))

register_node(NodeTypeDef(
    type_id="image_composite", category="image", label="Image Composite",
    inputs=[PortDef("IMAGE", "IMAGE"), PortDef("IMAGE_2", "IMAGE"), PortDef("MASK", "MASK", optional=True)],
    outputs=[PortDef("IMAGE", "IMAGE")],
    widgets=[
        WidgetDef("x", "number", default=0, min=0, max=8192, step=1, label="X"),
        WidgetDef("y", "number", default=0, min=0, max=8192, step=1, label="Y"),
    ],
    execute=exec_image_composite, color="#4ade80",
    description="Composite one image onto another with optional mask",
))

register_node(NodeTypeDef(
    type_id="image_blend", category="image", label="Image Blend",
    inputs=[PortDef("IMAGE", "IMAGE"), PortDef("IMAGE_2", "IMAGE")],
    outputs=[PortDef("IMAGE", "IMAGE")],
    widgets=[
        WidgetDef("factor", "slider", default=0.5, min=0, max=1, step=0.05, label="Blend Factor"),
    ],
    execute=exec_image_blend, color="#4ade80",
    description="Blend two images together (0=image1, 1=image2)",
))
