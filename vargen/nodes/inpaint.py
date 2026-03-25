"""Inpainting nodes — mask-based image inpainting."""

import torch
import logging
import numpy as np
from PIL import Image, ImageFilter

from . import register_node, NodeTypeDef, PortDef, WidgetDef

log = logging.getLogger(__name__)


def exec_inpaint(inputs, widgets, ctx):
    """Inpaint masked region of an image."""
    from diffusers import StableDiffusionXLInpaintPipeline, StableDiffusionInpaintPipeline, AutoPipelineForInpainting

    pipe = inputs.get("_pipe")
    image = inputs.get("IMAGE")
    mask = inputs.get("MASK")
    positive = inputs.get("POSITIVE")
    negative = inputs.get("NEGATIVE")

    if not pipe:
        raise ValueError("Inpaint needs a pipeline — connect from Load Checkpoint")
    if not image:
        raise ValueError("Inpaint needs an IMAGE")
    if not mask:
        raise ValueError("Inpaint needs a MASK")

    steps = int(widgets.get("steps", 20))
    cfg = float(widgets.get("cfg", 7.0))
    denoise = float(widgets.get("denoise", 0.8))
    seed = int(widgets.get("seed", -1))

    if seed == -1:
        seed = torch.randint(0, 2**32, (1,)).item()
    generator = torch.Generator("cpu").manual_seed(seed)

    # Convert mask to proper format (white = inpaint area)
    if isinstance(mask, Image.Image):
        mask_image = mask.convert("L")
    else:
        mask_image = Image.fromarray((mask * 255).astype(np.uint8)).convert("L")

    log.info(f"Inpainting: {steps} steps, cfg={cfg}, denoise={denoise}, seed={seed}")

    # Rebuild as inpaint pipeline
    try:
        inpaint_pipe = AutoPipelineForInpainting.from_pipe(pipe)
    except Exception:
        log.warning("AutoPipelineForInpainting failed, using base pipeline with mask")
        inpaint_pipe = pipe

    inpaint_pipe.enable_model_cpu_offload()

    kwargs = {
        "image": image,
        "mask_image": mask_image,
        "num_inference_steps": steps,
        "guidance_scale": cfg,
        "strength": denoise,
        "generator": generator,
    }

    if positive and "prompt_embeds" in positive:
        kwargs["prompt_embeds"] = positive["prompt_embeds"]
        if "pooled_prompt_embeds" in positive:
            kwargs["pooled_prompt_embeds"] = positive["pooled_prompt_embeds"]
    elif positive:
        kwargs["prompt"] = positive.get("text", "")

    if negative and "prompt_embeds" in negative:
        kwargs["negative_prompt_embeds"] = negative["prompt_embeds"]
        if "pooled_prompt_embeds" in negative:
            kwargs["negative_pooled_prompt_embeds"] = negative["pooled_prompt_embeds"]
    elif negative:
        kwargs["negative_prompt"] = negative.get("text", "")

    result = inpaint_pipe(**kwargs)
    output = result.images[0]
    log.info(f"Inpainted: {output.size}")
    return {"IMAGE": output}


# ── Mask operations ───────────────────────────

def exec_solid_mask(inputs, widgets, ctx):
    w = int(widgets.get("width", 512))
    h = int(widgets.get("height", 512))
    value = float(widgets.get("value", 1.0))
    arr = np.full((h, w), int(value * 255), dtype=np.uint8)
    return {"MASK": Image.fromarray(arr, mode="L")}


def exec_invert_mask(inputs, widgets, ctx):
    mask = inputs.get("MASK")
    if not mask:
        raise ValueError("No MASK input")
    if isinstance(mask, Image.Image):
        arr = np.array(mask.convert("L"))
    else:
        arr = np.array(mask)
    return {"MASK": Image.fromarray(255 - arr, mode="L")}


def exec_grow_mask(inputs, widgets, ctx):
    mask = inputs.get("MASK")
    if not mask:
        raise ValueError("No MASK input")
    pixels = int(widgets.get("pixels", 8))
    if isinstance(mask, Image.Image):
        mask_img = mask.convert("L")
    else:
        mask_img = Image.fromarray(mask, mode="L")

    # Grow by dilating
    for _ in range(pixels):
        mask_img = mask_img.filter(ImageFilter.MaxFilter(3))
    return {"MASK": mask_img}


def exec_feather_mask(inputs, widgets, ctx):
    mask = inputs.get("MASK")
    if not mask:
        raise ValueError("No MASK input")
    radius = int(widgets.get("radius", 8))
    if isinstance(mask, Image.Image):
        mask_img = mask.convert("L")
    else:
        mask_img = Image.fromarray(mask, mode="L")
    result = mask_img.filter(ImageFilter.GaussianBlur(radius=radius))
    return {"MASK": result}


def exec_image_to_mask(inputs, widgets, ctx):
    image = inputs.get("IMAGE")
    if not image:
        raise ValueError("No IMAGE input")
    channel = widgets.get("channel", "alpha")
    if channel == "alpha" and image.mode == "RGBA":
        return {"MASK": image.split()[3]}
    elif channel == "red":
        return {"MASK": image.convert("RGB").split()[0]}
    elif channel == "green":
        return {"MASK": image.convert("RGB").split()[1]}
    elif channel == "blue":
        return {"MASK": image.convert("RGB").split()[2]}
    else:
        return {"MASK": image.convert("L")}


# ── Register ──────────────────────────────────

register_node(NodeTypeDef(
    type_id="inpaint", category="sampling", label="Inpaint",
    inputs=[
        PortDef("MODEL", "MODEL"),
        PortDef("IMAGE", "IMAGE"),
        PortDef("MASK", "MASK"),
        PortDef("POSITIVE", "CONDITIONING", optional=True),
        PortDef("NEGATIVE", "CONDITIONING", optional=True),
    ],
    outputs=[PortDef("IMAGE", "IMAGE")],
    widgets=[
        WidgetDef("seed", "number", default=-1, label="Seed"),
        WidgetDef("steps", "slider", default=20, min=1, max=100, step=1, label="Steps"),
        WidgetDef("cfg", "slider", default=7.0, min=0, max=30, step=0.5, label="CFG"),
        WidgetDef("denoise", "slider", default=0.8, min=0, max=1, step=0.05, label="Denoise"),
    ],
    execute=exec_inpaint, color="#ec4899",
    description="Inpaint masked region of an image",
))

register_node(NodeTypeDef(
    type_id="solid_mask", category="mask", label="Solid Mask",
    inputs=[],
    outputs=[PortDef("MASK", "MASK")],
    widgets=[
        WidgetDef("width", "number", default=512, min=1, max=8192, step=64, label="Width"),
        WidgetDef("height", "number", default=512, min=1, max=8192, step=64, label="Height"),
        WidgetDef("value", "slider", default=1.0, min=0, max=1, step=0.1, label="Value"),
    ],
    execute=exec_solid_mask, color="#22c55e",
    description="Create a solid mask (white=inpaint, black=keep)",
))

register_node(NodeTypeDef(
    type_id="invert_mask", category="mask", label="Invert Mask",
    inputs=[PortDef("MASK", "MASK")],
    outputs=[PortDef("MASK", "MASK")],
    widgets=[],
    execute=exec_invert_mask, color="#22c55e",
))

register_node(NodeTypeDef(
    type_id="grow_mask", category="mask", label="Grow Mask",
    inputs=[PortDef("MASK", "MASK")],
    outputs=[PortDef("MASK", "MASK")],
    widgets=[WidgetDef("pixels", "slider", default=8, min=1, max=64, step=1, label="Pixels")],
    execute=exec_grow_mask, color="#22c55e",
))

register_node(NodeTypeDef(
    type_id="feather_mask", category="mask", label="Feather Mask",
    inputs=[PortDef("MASK", "MASK")],
    outputs=[PortDef("MASK", "MASK")],
    widgets=[WidgetDef("radius", "slider", default=8, min=1, max=64, step=1, label="Radius")],
    execute=exec_feather_mask, color="#22c55e",
))

register_node(NodeTypeDef(
    type_id="image_to_mask", category="mask", label="Image to Mask",
    inputs=[PortDef("IMAGE", "IMAGE")],
    outputs=[PortDef("MASK", "MASK")],
    widgets=[
        WidgetDef("channel", "combo", default="alpha", label="Channel",
                  options=["alpha", "red", "green", "blue", "luminance"]),
    ],
    execute=exec_image_to_mask, color="#22c55e",
    description="Extract mask from image channel",
))
