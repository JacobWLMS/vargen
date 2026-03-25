"""ControlNet nodes — load, preprocess, and apply ControlNet conditioning."""

import torch
import logging
import numpy as np
from PIL import Image

from . import register_node, NodeTypeDef, PortDef, WidgetDef

log = logging.getLogger(__name__)


def exec_load_controlnet(inputs, widgets, ctx):
    from diffusers import ControlNetModel

    model_name = widgets.get("model", "")
    if not model_name:
        raise ValueError("No ControlNet model selected")

    model_path = ctx["model_manager"].find_model("controlnet", model_name)

    if model_path:
        log.info(f"Loading ControlNet from file: {model_path}")
        controlnet = ControlNetModel.from_single_file(str(model_path), torch_dtype=torch.float16)
    else:
        # Try as HuggingFace repo
        log.info(f"Loading ControlNet from repo: {model_name}")
        controlnet = ControlNetModel.from_pretrained(model_name, torch_dtype=torch.float16)

    return {"CONTROLNET": controlnet}


def exec_apply_controlnet(inputs, widgets, ctx):
    """Apply ControlNet to a pipeline — rebuilds pipeline with ControlNet support."""
    from diffusers import StableDiffusionXLControlNetPipeline, StableDiffusionControlNetPipeline

    pipe = inputs.get("_pipe")
    controlnet = inputs.get("CONTROLNET")
    image = inputs.get("IMAGE")

    if not pipe:
        raise ValueError("Apply ControlNet needs a pipeline — connect MODEL from Load Checkpoint")
    if not controlnet:
        raise ValueError("Apply ControlNet needs a CONTROLNET — connect from Load ControlNet")
    if not image:
        raise ValueError("Apply ControlNet needs an IMAGE — connect a control image")

    strength = float(widgets.get("strength", 0.8))
    start = float(widgets.get("start_percent", 0.0))
    end = float(widgets.get("end_percent", 1.0))

    log.info(f"Applying ControlNet: strength={strength}, range={start}-{end}")

    # Rebuild pipeline with ControlNet
    if hasattr(pipe, 'text_encoder_2'):
        # SDXL
        cn_pipe = StableDiffusionXLControlNetPipeline(
            vae=pipe.vae, text_encoder=pipe.text_encoder,
            text_encoder_2=pipe.text_encoder_2, tokenizer=pipe.tokenizer,
            tokenizer_2=pipe.tokenizer_2, unet=pipe.unet,
            controlnet=controlnet, scheduler=pipe.scheduler,
        )
    else:
        # SD1.5
        cn_pipe = StableDiffusionControlNetPipeline(
            vae=pipe.vae, text_encoder=pipe.text_encoder,
            tokenizer=pipe.tokenizer, unet=pipe.unet,
            controlnet=controlnet, scheduler=pipe.scheduler,
            safety_checker=None, feature_extractor=None,
        )

    cn_pipe.enable_model_cpu_offload()

    return {
        "MODEL": cn_pipe.unet,
        "_pipe": cn_pipe,
        "_cn_image": image,
        "_cn_strength": strength,
        "_cn_start": start,
        "_cn_end": end,
    }


# ── Preprocessors ─────────────────────────────

def exec_canny(inputs, widgets, ctx):
    image = inputs.get("IMAGE")
    if not image:
        raise ValueError("Canny needs an IMAGE input")

    low = int(widgets.get("low_threshold", 100))
    high = int(widgets.get("high_threshold", 200))

    import cv2
    img_np = np.array(image.convert("RGB"))
    edges = cv2.Canny(img_np, low, high)
    edges = np.stack([edges, edges, edges], axis=-1)
    result = Image.fromarray(edges)
    log.info(f"Canny edge detection: {result.size}")
    return {"IMAGE": result}


def exec_depth_map(inputs, widgets, ctx):
    """Estimate depth using MiDaS (via torch hub or transformers)."""
    image = inputs.get("IMAGE")
    if not image:
        raise ValueError("Depth Map needs an IMAGE input")

    log.info("Generating depth map...")

    try:
        from transformers import pipeline as hf_pipeline
        depth_estimator = hf_pipeline("depth-estimation", model="Intel/dpt-large", device=-1)
        result = depth_estimator(image)
        depth_image = result["depth"]
        if not isinstance(depth_image, Image.Image):
            depth_image = Image.fromarray(np.array(depth_image))
        depth_image = depth_image.convert("RGB")
    except Exception as e:
        log.warning(f"Depth estimation failed: {e}, using grayscale fallback")
        depth_image = image.convert("L").convert("RGB")

    log.info(f"Depth map: {depth_image.size}")
    return {"IMAGE": depth_image}


# ── Register ──────────────────────────────────

register_node(NodeTypeDef(
    type_id="load_controlnet", category="controlnet", label="Load ControlNet",
    inputs=[],
    outputs=[PortDef("CONTROLNET", "CONTROLNET")],
    widgets=[
        WidgetDef("model", "combo", label="Model", options=[]),
    ],
    execute=exec_load_controlnet, color="#06b6d4",
    description="Load a ControlNet model",
))

register_node(NodeTypeDef(
    type_id="apply_controlnet", category="controlnet", label="Apply ControlNet",
    inputs=[
        PortDef("MODEL", "MODEL"),
        PortDef("CONTROLNET", "CONTROLNET"),
        PortDef("IMAGE", "IMAGE"),
    ],
    outputs=[
        PortDef("MODEL", "MODEL"),
    ],
    widgets=[
        WidgetDef("strength", "slider", default=0.8, min=0, max=2, step=0.05, label="Strength"),
        WidgetDef("start_percent", "slider", default=0.0, min=0, max=1, step=0.05, label="Start %"),
        WidgetDef("end_percent", "slider", default=1.0, min=0, max=1, step=0.05, label="End %"),
    ],
    execute=exec_apply_controlnet, color="#06b6d4",
    description="Apply ControlNet conditioning to a model",
))

register_node(NodeTypeDef(
    type_id="canny_edge", category="controlnet", label="Canny Edge Detection",
    inputs=[PortDef("IMAGE", "IMAGE")],
    outputs=[PortDef("IMAGE", "IMAGE")],
    widgets=[
        WidgetDef("low_threshold", "slider", default=100, min=0, max=500, step=10, label="Low"),
        WidgetDef("high_threshold", "slider", default=200, min=0, max=500, step=10, label="High"),
    ],
    execute=exec_canny, color="#06b6d4",
    description="Detect edges using Canny algorithm",
))

register_node(NodeTypeDef(
    type_id="depth_map", category="controlnet", label="Depth Map (MiDaS)",
    inputs=[PortDef("IMAGE", "IMAGE")],
    outputs=[PortDef("IMAGE", "IMAGE")],
    widgets=[],
    execute=exec_depth_map, color="#06b6d4",
    description="Estimate depth from image using MiDaS",
))
