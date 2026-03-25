"""CLIP loader nodes — load CLIP and text encoders independently."""

import torch
import logging

from . import register_node, NodeTypeDef, PortDef, WidgetDef

log = logging.getLogger(__name__)


def exec_load_clip(inputs, widgets, ctx):
    """Load a CLIP text encoder model."""
    from transformers import CLIPTokenizer, CLIPTextModel

    clip_name = widgets.get("clip", "")
    if not clip_name:
        raise ValueError("No CLIP model selected")

    model_path = ctx["model_manager"].find_model("clip", clip_name)
    if not model_path:
        model_path = ctx["model_manager"].find_model("text_encoders", clip_name)
    if not model_path:
        raise ValueError(f"CLIP model not found: {clip_name}")

    log.info(f"Loading CLIP: {model_path}")
    tokenizer = CLIPTokenizer.from_pretrained(str(model_path.parent), subfolder=model_path.stem if model_path.is_dir() else None)
    text_encoder = CLIPTextModel.from_pretrained(str(model_path.parent), subfolder=model_path.stem if model_path.is_dir() else None, torch_dtype=torch.float16)

    return {
        "CLIP": {
            "tokenizer": tokenizer,
            "text_encoder": text_encoder,
            "tokenizer_2": None,
            "text_encoder_2": None,
            "arch": "sd15",
        }
    }


def exec_load_dual_clip(inputs, widgets, ctx):
    """Load dual CLIP for SDXL or FLUX (clip_l + clip_g/t5xxl)."""
    clip1_name = widgets.get("clip_1", "")
    clip2_name = widgets.get("clip_2", "")
    clip_type = widgets.get("type", "sdxl")

    log.info(f"Loading Dual CLIP: {clip1_name} + {clip2_name} (type: {clip_type})")

    # For now, return a stub — the actual encoding happens through the pipeline
    return {
        "CLIP": {
            "clip_1": clip1_name,
            "clip_2": clip2_name,
            "arch": clip_type,
        }
    }


def exec_load_unet(inputs, widgets, ctx):
    """Load a standalone UNET / diffusion model."""
    from diffusers import UNet2DConditionModel

    unet_name = widgets.get("unet", "")
    dtype = widgets.get("dtype", "fp16")

    if not unet_name:
        raise ValueError("No UNET model selected")

    model_path = ctx["model_manager"].find_model("diffusion_models", unet_name)
    if not model_path:
        model_path = ctx["model_manager"].find_model("unet", unet_name)
    if not model_path:
        raise ValueError(f"UNET not found: {unet_name}")

    dtype_map = {"fp16": torch.float16, "bf16": torch.bfloat16, "fp32": torch.float32, "fp8": torch.float8_e4m3fn}
    torch_dtype = dtype_map.get(dtype, torch.float16)

    log.info(f"Loading UNET: {model_path} (dtype: {dtype})")

    if str(model_path).endswith('.safetensors'):
        unet = UNet2DConditionModel.from_single_file(str(model_path), torch_dtype=torch_dtype)
    else:
        unet = UNet2DConditionModel.from_pretrained(str(model_path), torch_dtype=torch_dtype)

    return {"MODEL": unet}


# ── Register ──────────────────────────────────

register_node(NodeTypeDef(
    type_id="load_clip", category="loaders", label="Load CLIP",
    inputs=[],
    outputs=[PortDef("CLIP", "CLIP")],
    widgets=[
        WidgetDef("clip", "combo", label="CLIP Model", options=[]),
    ],
    execute=exec_load_clip, color="#facc15",
    description="Load a standalone CLIP text encoder",
))

register_node(NodeTypeDef(
    type_id="load_dual_clip", category="loaders", label="Load Dual CLIP",
    inputs=[],
    outputs=[PortDef("CLIP", "CLIP")],
    widgets=[
        WidgetDef("clip_1", "combo", label="CLIP 1", options=[]),
        WidgetDef("clip_2", "combo", label="CLIP 2", options=[]),
        WidgetDef("type", "combo", default="sdxl", label="Type", options=["sdxl", "flux"]),
    ],
    execute=exec_load_dual_clip, color="#facc15",
    description="Load dual CLIP (SDXL: clip_l + clip_g, FLUX: clip_l + t5xxl)",
))

register_node(NodeTypeDef(
    type_id="load_unet", category="loaders", label="Load UNET",
    inputs=[],
    outputs=[PortDef("MODEL", "MODEL")],
    widgets=[
        WidgetDef("unet", "combo", label="UNET", options=[]),
        WidgetDef("dtype", "combo", default="fp16", label="Dtype",
                  options=["fp16", "bf16", "fp32", "fp8"]),
    ],
    execute=exec_load_unet, color="#a855f7",
    description="Load a standalone UNET / diffusion model",
))
