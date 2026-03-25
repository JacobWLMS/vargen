"""Image operation nodes — save, preview, upscale, scale, crop, composite."""

import torch
import numpy as np
import logging
import time
from pathlib import Path
from PIL import Image

from . import register_node, NodeTypeDef, PortDef, WidgetDef

log = logging.getLogger(__name__)

OUTPUT_DIR = Path(__file__).parent.parent.parent / "outputs"


def exec_save_image(inputs, widgets, ctx):
    image = inputs.get("IMAGE")
    if image is None:
        raise ValueError("No image to save")
    prefix = widgets.get("filename_prefix", "vargen")
    fmt = widgets.get("format", "png")
    quality = int(widgets.get("quality", 95))
    ts = int(time.time())
    OUTPUT_DIR.mkdir(exist_ok=True)

    ext = {"png": ".png", "jpeg": ".jpg", "webp": ".webp"}[fmt]
    path = OUTPUT_DIR / f"{prefix}_{ts}{ext}"

    save_kwargs = {}
    if fmt == "jpeg":
        save_kwargs["quality"] = quality
        image = image.convert("RGB")
    elif fmt == "webp":
        save_kwargs["quality"] = quality

    image.save(path, **save_kwargs)
    log.info(f"Saved: {path} ({fmt}, q={quality})")
    return {"IMAGE": image, "_saved_path": str(path), "_saved_url": f"/api/outputs/{path.name}"}


def exec_preview_image(inputs, widgets, ctx):
    image = inputs.get("IMAGE")
    return {"IMAGE": image}


def exec_upscale_with_model(inputs, widgets, ctx):
    image = inputs.get("IMAGE")
    model = inputs.get("UPSCALE_MODEL")
    if image is None or model is None:
        raise ValueError("Need both IMAGE and UPSCALE_MODEL")

    img_np = np.array(image.convert("RGB")).astype(np.float32) / 255.0
    img_tensor = torch.from_numpy(img_np).permute(2, 0, 1).unsqueeze(0)
    if torch.cuda.is_available():
        img_tensor = img_tensor.cuda()

    with torch.no_grad():
        output = model(img_tensor)

    output = output.squeeze(0).permute(1, 2, 0).cpu().clamp(0, 1).numpy()
    result = Image.fromarray((output * 255).astype(np.uint8))
    log.info(f"Upscaled: {image.size} → {result.size}")
    return {"IMAGE": result}


def exec_image_scale(inputs, widgets, ctx):
    image = inputs.get("IMAGE")
    if image is None:
        raise ValueError("No image")
    method = widgets.get("method", "lanczos")
    width = widgets.get("width", image.width)
    height = widgets.get("height", image.height)
    scale_by = widgets.get("scale_by", 0)

    resample = {"nearest": Image.NEAREST, "bilinear": Image.BILINEAR, "bicubic": Image.BICUBIC, "lanczos": Image.LANCZOS}.get(method, Image.LANCZOS)

    if scale_by > 0:
        width = int(image.width * scale_by)
        height = int(image.height * scale_by)

    result = image.resize((width, height), resample)
    log.info(f"Scaled: {image.size} → {result.size}")
    return {"IMAGE": result}


def exec_image_invert(inputs, widgets, ctx):
    from PIL import ImageOps
    image = inputs.get("IMAGE")
    if image is None:
        raise ValueError("No image")
    return {"IMAGE": ImageOps.invert(image.convert("RGB"))}


def exec_image_blur(inputs, widgets, ctx):
    from PIL import ImageFilter
    image = inputs.get("IMAGE")
    radius = widgets.get("radius", 3)
    return {"IMAGE": image.filter(ImageFilter.GaussianBlur(radius=radius))}


def exec_image_crop(inputs, widgets, ctx):
    image = inputs.get("IMAGE")
    x = widgets.get("x", 0)
    y = widgets.get("y", 0)
    w = widgets.get("width", image.width)
    h = widgets.get("height", image.height)
    return {"IMAGE": image.crop((x, y, x + w, y + h))}


# ── Register ──────────────────────────────────

register_node(NodeTypeDef(
    type_id="save_image", category="image", label="Save Image",
    inputs=[PortDef("IMAGE", "IMAGE")],
    outputs=[PortDef("IMAGE", "IMAGE")],
    widgets=[
        WidgetDef("filename_prefix", "text", default="vargen", label="Prefix"),
        WidgetDef("format", "combo", default="png", label="Format", options=["png", "jpeg", "webp"]),
        WidgetDef("quality", "slider", default=95, min=1, max=100, step=1, label="Quality (JPEG/WebP)"),
    ],
    execute=exec_save_image, color="#4ade80",
    description="Save image to outputs directory",
))

register_node(NodeTypeDef(
    type_id="preview_image", category="image", label="Preview Image",
    inputs=[PortDef("IMAGE", "IMAGE")],
    outputs=[PortDef("IMAGE", "IMAGE")],
    widgets=[],
    execute=exec_preview_image, color="#4ade80",
    description="Preview image (no save)",
))

register_node(NodeTypeDef(
    type_id="upscale_with_model", category="image", label="Upscale (Model)",
    inputs=[PortDef("UPSCALE_MODEL", "UPSCALE_MODEL"), PortDef("IMAGE", "IMAGE")],
    outputs=[PortDef("IMAGE", "IMAGE")],
    widgets=[],
    execute=exec_upscale_with_model, color="#60a5fa",
    description="Upscale image using a trained model (RealESRGAN, etc.)",
))

register_node(NodeTypeDef(
    type_id="image_scale", category="image", label="Image Scale",
    inputs=[PortDef("IMAGE", "IMAGE")],
    outputs=[PortDef("IMAGE", "IMAGE")],
    widgets=[
        WidgetDef("method", "combo", default="lanczos", options=["nearest", "bilinear", "bicubic", "lanczos"], label="Method"),
        WidgetDef("width", "number", default=1024, min=64, max=8192, step=64, label="Width"),
        WidgetDef("height", "number", default=1024, min=64, max=8192, step=64, label="Height"),
        WidgetDef("scale_by", "slider", default=0, min=0, max=8, step=0.25, label="Scale By (0=use w/h)"),
    ],
    execute=exec_image_scale, color="#4ade80",
    description="Resize image with various interpolation methods",
))

register_node(NodeTypeDef(
    type_id="image_invert", category="image", label="Invert Image",
    inputs=[PortDef("IMAGE", "IMAGE")],
    outputs=[PortDef("IMAGE", "IMAGE")],
    widgets=[],
    execute=exec_image_invert, color="#4ade80",
))

register_node(NodeTypeDef(
    type_id="image_blur", category="image", label="Gaussian Blur",
    inputs=[PortDef("IMAGE", "IMAGE")],
    outputs=[PortDef("IMAGE", "IMAGE")],
    widgets=[WidgetDef("radius", "slider", default=3, min=1, max=50, step=1, label="Radius")],
    execute=exec_image_blur, color="#4ade80",
))

register_node(NodeTypeDef(
    type_id="image_crop", category="image", label="Crop Image",
    inputs=[PortDef("IMAGE", "IMAGE")],
    outputs=[PortDef("IMAGE", "IMAGE")],
    widgets=[
        WidgetDef("x", "number", default=0, min=0, max=8192, step=1, label="X"),
        WidgetDef("y", "number", default=0, min=0, max=8192, step=1, label="Y"),
        WidgetDef("width", "number", default=512, min=1, max=8192, step=1, label="Width"),
        WidgetDef("height", "number", default=512, min=1, max=8192, step=1, label="Height"),
    ],
    execute=exec_image_crop, color="#4ade80",
))
