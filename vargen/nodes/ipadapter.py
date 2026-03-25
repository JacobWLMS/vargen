"""IP-Adapter nodes — load and apply IP-Adapter for image-guided generation."""

import torch
import logging
from PIL import Image

from . import register_node, NodeTypeDef, PortDef, WidgetDef

log = logging.getLogger(__name__)

IP_ADAPTER_MODELS = {
    "ip-adapter_sdxl": {"repo": "h94/IP-Adapter", "subfolder": "sdxl_models", "weight": "ip-adapter_sdxl.safetensors"},
    "ip-adapter-plus_sdxl": {"repo": "h94/IP-Adapter", "subfolder": "sdxl_models", "weight": "ip-adapter-plus_sdxl_vit-h.safetensors"},
    "ip-adapter-plus-face_sdxl": {"repo": "h94/IP-Adapter", "subfolder": "sdxl_models", "weight": "ip-adapter-plus-face_sdxl_vit-h.safetensors"},
    "ip-adapter_sd15": {"repo": "h94/IP-Adapter", "subfolder": "models", "weight": "ip-adapter_sd15.safetensors"},
    "ip-adapter-plus_sd15": {"repo": "h94/IP-Adapter", "subfolder": "models", "weight": "ip-adapter-plus_sd15.safetensors"},
    "ip-adapter-plus-face_sd15": {"repo": "h94/IP-Adapter", "subfolder": "models", "weight": "ip-adapter-plus-face_sd15.safetensors"},
}


def exec_load_ip_adapter(inputs, widgets, ctx):
    pipe = inputs.get("_pipe")
    if not pipe:
        raise ValueError("Load IP-Adapter needs a pipeline — connect from Load Checkpoint")

    preset = widgets.get("preset", "ip-adapter-plus-face_sdxl")
    weight = float(widgets.get("weight", 0.8))

    adapter = IP_ADAPTER_MODELS.get(preset)
    if not adapter:
        raise ValueError(f"Unknown IP-Adapter preset: {preset}")

    log.info(f"Loading IP-Adapter: {preset} (weight={weight})")

    try:
        pipe.load_ip_adapter(
            adapter["repo"],
            subfolder=adapter["subfolder"],
            weight_name=adapter["weight"],
        )
        pipe.set_ip_adapter_scale(weight)
        log.info("IP-Adapter loaded successfully")
    except Exception as e:
        raise ValueError(f"Failed to load IP-Adapter: {e}")

    return {
        "MODEL": pipe.unet,
        "_pipe": pipe,
        "_ip_adapter_loaded": True,
    }


def exec_apply_ip_adapter(inputs, widgets, ctx):
    """Set IP-Adapter reference image — connect to KSampler which will use it."""
    pipe = inputs.get("_pipe")
    image = inputs.get("IMAGE")

    if not pipe:
        raise ValueError("Apply IP-Adapter needs a pipeline — connect from Load IP-Adapter")
    if not image:
        raise ValueError("Apply IP-Adapter needs a reference IMAGE")

    weight = float(widgets.get("weight", 0.8))

    # Update scale if changed
    if hasattr(pipe, 'set_ip_adapter_scale'):
        pipe.set_ip_adapter_scale(weight)

    log.info(f"IP-Adapter reference set (weight={weight})")

    return {
        "MODEL": pipe.unet,
        "_pipe": pipe,
        "_ip_adapter_image": image,
    }


register_node(NodeTypeDef(
    type_id="load_ip_adapter", category="ipadapter", label="Load IP-Adapter",
    inputs=[PortDef("MODEL", "MODEL")],
    outputs=[PortDef("MODEL", "MODEL")],
    widgets=[
        WidgetDef("preset", "combo", default="ip-adapter-plus-face_sdxl", label="Preset",
                  options=list(IP_ADAPTER_MODELS.keys())),
        WidgetDef("weight", "slider", default=0.8, min=0, max=2, step=0.05, label="Weight"),
    ],
    execute=exec_load_ip_adapter, color="#8b5cf6",
    description="Load IP-Adapter model for image-guided generation",
))

register_node(NodeTypeDef(
    type_id="apply_ip_adapter", category="ipadapter", label="Apply IP-Adapter",
    inputs=[
        PortDef("MODEL", "MODEL"),
        PortDef("IMAGE", "IMAGE"),
    ],
    outputs=[PortDef("MODEL", "MODEL")],
    widgets=[
        WidgetDef("weight", "slider", default=0.8, min=0, max=2, step=0.05, label="Weight"),
    ],
    execute=exec_apply_ip_adapter, color="#8b5cf6",
    description="Set reference image for IP-Adapter identity/style transfer",
))
