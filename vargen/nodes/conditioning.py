"""Conditioning nodes — CLIP text encode using actual diffusers components."""

import torch
import logging

from . import register_node, NodeTypeDef, PortDef, WidgetDef

log = logging.getLogger(__name__)


def exec_clip_text_encode(inputs, widgets, ctx):
    clip = inputs.get("CLIP")
    if not clip:
        raise ValueError("CLIP Text Encode needs a CLIP input — connect from Load Checkpoint")

    text = widgets.get("text", "")
    log.info(f"Encoding: {text[:80]}...")

    pipe = inputs.get("_pipe")
    arch = clip.get("arch", "sdxl")

    if arch == "sdxl" and pipe and hasattr(pipe, 'encode_prompt'):
        # SDXL: use pipeline's encode_prompt for proper dual-encoder handling
        device = pipe._execution_device if hasattr(pipe, '_execution_device') else 'cpu'
        prompt_embeds, _, pooled_prompt_embeds, _ = pipe.encode_prompt(
            prompt=text,
            device=device,
            num_images_per_prompt=1,
            do_classifier_free_guidance=False,
        )
        return {
            "CONDITIONING": {
                "prompt_embeds": prompt_embeds,
                "pooled_prompt_embeds": pooled_prompt_embeds,
                "text": text,
                "arch": arch,
            }
        }
    else:
        # SD1.5 or fallback
        tokenizer = clip.get("tokenizer")
        text_encoder = clip.get("text_encoder")
        if not tokenizer or not text_encoder:
            # Fallback: just pass text through
            return {"CONDITIONING": {"text": text, "arch": arch}}

        device = next(text_encoder.parameters()).device
        text_inputs = tokenizer(text, padding="max_length", max_length=77,
                                truncation=True, return_tensors="pt")
        with torch.no_grad():
            text_embeds = text_encoder(text_inputs.input_ids.to(device))[0]

        return {
            "CONDITIONING": {
                "prompt_embeds": text_embeds,
                "text": text,
                "arch": arch,
            }
        }


def exec_conditioning_combine(inputs, widgets, ctx):
    cond1 = inputs.get("CONDITIONING_1")
    cond2 = inputs.get("CONDITIONING_2")
    if not cond1 or not cond2:
        raise ValueError("Need both conditioning inputs")

    embeds1 = cond1.get("prompt_embeds")
    embeds2 = cond2.get("prompt_embeds")
    if embeds1 is not None and embeds2 is not None:
        combined_embeds = torch.cat([embeds1, embeds2], dim=1)
    else:
        combined_embeds = embeds1 or embeds2

    return {"CONDITIONING": {
        "prompt_embeds": combined_embeds,
        "text": f"{cond1.get('text', '')} + {cond2.get('text', '')}",
        "arch": cond1.get("arch", "sdxl"),
    }}


register_node(NodeTypeDef(
    type_id="clip_text_encode", category="conditioning", label="CLIP Text Encode",
    inputs=[PortDef("CLIP", "CLIP")],
    outputs=[PortDef("CONDITIONING", "CONDITIONING")],
    widgets=[WidgetDef("text", "textarea", default="", label="Text")],
    execute=exec_clip_text_encode, color="#facc15",
    description="Encode text using CLIP text encoder",
))

register_node(NodeTypeDef(
    type_id="conditioning_combine", category="conditioning", label="Conditioning Combine",
    inputs=[PortDef("CONDITIONING_1", "CONDITIONING"), PortDef("CONDITIONING_2", "CONDITIONING")],
    outputs=[PortDef("CONDITIONING", "CONDITIONING")],
    widgets=[],
    execute=exec_conditioning_combine, color="#fb923c",
))
