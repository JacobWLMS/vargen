"""Conditioning nodes — CLIP text encode, set areas, combine."""

import torch
import logging

from . import register_node, NodeTypeDef, PortDef, WidgetDef

log = logging.getLogger(__name__)


def exec_clip_text_encode(inputs, widgets, ctx):
    pipe = inputs.get("_pipe")
    if not pipe:
        raise ValueError("CLIP Text Encode needs a pipeline (connect Load Checkpoint)")

    text = widgets.get("text", "")
    log.info(f"Encoding text: {text[:80]}...")

    # Use the pipeline's text encoder
    if hasattr(pipe, 'encode_prompt'):
        # SDXL
        prompt_embeds, negative_prompt_embeds, pooled, neg_pooled = pipe.encode_prompt(
            prompt=text, device=pipe.device, num_images_per_prompt=1, do_classifier_free_guidance=False
        )
        return {"CONDITIONING": {"embeds": prompt_embeds, "pooled": pooled, "text": text}}
    else:
        # SD1.5
        text_inputs = pipe.tokenizer(text, padding="max_length", max_length=77,
                                      truncation=True, return_tensors="pt")
        text_embeds = pipe.text_encoder(text_inputs.input_ids.to(pipe.device))[0]
        return {"CONDITIONING": {"embeds": text_embeds, "text": text}}


def exec_clip_set_last_layer(inputs, widgets, ctx):
    clip = inputs.get("CLIP")
    stop_at = widgets.get("stop_at_clip_layer", -1)
    # Store clip skip setting for use during encoding
    return {"CLIP": clip, "_clip_skip": stop_at}


def exec_conditioning_combine(inputs, widgets, ctx):
    cond1 = inputs.get("CONDITIONING_1")
    cond2 = inputs.get("CONDITIONING_2")
    if not cond1 or not cond2:
        raise ValueError("Need both conditioning inputs")
    # Simple concatenation
    combined = {
        "embeds": torch.cat([cond1["embeds"], cond2["embeds"]], dim=1),
        "text": f"{cond1.get('text', '')} + {cond2.get('text', '')}",
    }
    return {"CONDITIONING": combined}


# ── Register ──────────────────────────────────

register_node(NodeTypeDef(
    type_id="clip_text_encode",
    category="conditioning",
    label="CLIP Text Encode",
    inputs=[
        PortDef("CLIP", "CLIP"),
    ],
    outputs=[
        PortDef("CONDITIONING", "CONDITIONING"),
    ],
    widgets=[
        WidgetDef("text", "textarea", default="", label="Text"),
    ],
    execute=exec_clip_text_encode,
    color="#eab308",
    description="Encode text prompt using CLIP",
))

register_node(NodeTypeDef(
    type_id="clip_set_last_layer",
    category="conditioning",
    label="CLIP Set Last Layer",
    inputs=[PortDef("CLIP", "CLIP")],
    outputs=[PortDef("CLIP", "CLIP")],
    widgets=[
        WidgetDef("stop_at_clip_layer", "number", default=-1, min=-24, max=-1, step=1, label="Stop at Layer"),
    ],
    execute=exec_clip_set_last_layer,
    color="#eab308",
    description="Set CLIP skip (which layer to stop at)",
))

register_node(NodeTypeDef(
    type_id="conditioning_combine",
    category="conditioning",
    label="Conditioning Combine",
    inputs=[
        PortDef("CONDITIONING_1", "CONDITIONING"),
        PortDef("CONDITIONING_2", "CONDITIONING"),
    ],
    outputs=[PortDef("CONDITIONING", "CONDITIONING")],
    widgets=[],
    execute=exec_conditioning_combine,
    color="#eab308",
    description="Combine two conditioning inputs",
))
