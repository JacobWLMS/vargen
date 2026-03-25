"""Pixel-based upscaling step (RealESRGAN etc.)."""

import logging
import numpy as np
import torch
from PIL import Image
from pathlib import Path

log = logging.getLogger(__name__)


def run_upscale(model_ref, params: dict, mm, pipeline) -> Image.Image:
    """Upscale an image using a pixel-based upscale model.

    Params:
        input: source image (usually {previous_step} reference)
        scale: target scale factor (default: 2)
        input_image: fallback if 'input' not provided
    """
    input_img = params.get("input") or params.get("input_image")
    if input_img is None:
        raise ValueError("upscale step requires 'input'")
    if not isinstance(input_img, Image.Image):
        raise ValueError(f"upscale 'input' must be a PIL Image, got {type(input_img)}")

    scale = params.get("scale", 2)
    model_path = mm.model_path(model_ref)

    log.info(f"Loading upscale model from {model_path}")

    # Use spandrel for universal upscale model loading
    try:
        image = _upscale_spandrel(model_path, input_img, scale)
    except ImportError:
        # Fallback to simple torch resize
        log.warning("spandrel not installed, using lanczos resize")
        w, h = input_img.size
        image = input_img.resize((w * scale, h * scale), Image.LANCZOS)

    log.info(f"Upscaled: {input_img.size} → {image.size}")
    return image


def _upscale_spandrel(model_path: Path, image: Image.Image, scale: int) -> Image.Image:
    """Upscale using spandrel (supports RealESRGAN, SwinIR, etc.)."""
    import spandrel

    model = spandrel.ModelLoader().load_from_file(str(model_path))
    model = model.eval()

    if torch.cuda.is_available():
        model = model.cuda()

    # Convert PIL → tensor
    img_np = np.array(image.convert("RGB")).astype(np.float32) / 255.0
    img_tensor = torch.from_numpy(img_np).permute(2, 0, 1).unsqueeze(0)

    if torch.cuda.is_available():
        img_tensor = img_tensor.cuda()

    with torch.no_grad():
        output = model(img_tensor)

    # Convert back to PIL
    output = output.squeeze(0).permute(1, 2, 0).cpu().clamp(0, 1).numpy()
    output = (output * 255).astype(np.uint8)
    result = Image.fromarray(output)

    # Resize to target scale if model scale differs
    target_w = image.width * scale
    target_h = image.height * scale
    if result.size != (target_w, target_h):
        result = result.resize((target_w, target_h), Image.LANCZOS)

    # Cleanup
    del model
    if torch.cuda.is_available():
        torch.cuda.empty_cache()

    return result
