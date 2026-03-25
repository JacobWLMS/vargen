"""Conditioning nodes — CLIP text encode with per-node GPU management."""

import torch
import gc
import logging

from . import register_node, NodeTypeDef, PortDef, WidgetDef

log = logging.getLogger(__name__)


def _move_to_device(pipe, device):
    """Move pipeline text encoding components to device."""
    if hasattr(pipe, 'text_encoder') and pipe.text_encoder is not None:
        pipe.text_encoder.to(device)
    if hasattr(pipe, 'text_encoder_2') and pipe.text_encoder_2 is not None:
        pipe.text_encoder_2.to(device)


def _offload_text_encoders(pipe):
    """Move text encoders back to CPU after encoding."""
    if hasattr(pipe, 'text_encoder') and pipe.text_encoder is not None:
        pipe.text_encoder.to('cpu')
    if hasattr(pipe, 'text_encoder_2') and pipe.text_encoder_2 is not None:
        pipe.text_encoder_2.to('cpu')
    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()


def exec_clip_text_encode(inputs, widgets, ctx):
    clip = inputs.get("CLIP")
    if not clip:
        raise ValueError("CLIP Text Encode needs a CLIP input — connect from Load Checkpoint")

    text = widgets.get("text", "")
    log.info(f"Encoding: {text[:80]}...")

    pipe = inputs.get("_pipe")
    arch = clip.get("arch", "sdxl")
    device = "cuda" if torch.cuda.is_available() else "cpu"

    if arch == "sdxl" and pipe and hasattr(pipe, 'encode_prompt'):
        # Move text encoders to GPU
        _move_to_device(pipe, device)
        log.info(f"Text encoders on {device}")

        prompt_embeds, _, pooled_prompt_embeds, _ = pipe.encode_prompt(
            prompt=text, device=device,
            num_images_per_prompt=1, do_classifier_free_guidance=False,
        )

        # Move text encoders back to CPU — free VRAM for next node
        _offload_text_encoders(pipe)
        log.info(f"Text encoders offloaded. VRAM free: {torch.cuda.mem_get_info()[0] // (1024*1024)}MB" if torch.cuda.is_available() else "CPU mode")

        # Detach embeddings from GPU graph
        prompt_embeds = prompt_embeds.cpu()
        pooled_prompt_embeds = pooled_prompt_embeds.cpu()

        return {
            "CONDITIONING": {
                "prompt_embeds": prompt_embeds,
                "pooled_prompt_embeds": pooled_prompt_embeds,
                "text": text,
                "arch": arch,
            }
        }
    elif arch == "flux" and pipe:
        # FLUX: use pipeline's encode method
        _move_to_device(pipe, device)
        log.info(f"FLUX text encoders on {device}")

        prompt_embeds, pooled_prompt_embeds, _ = pipe.encode_prompt(
            prompt=text, prompt_2=None,
        )

        _offload_text_encoders(pipe)

        prompt_embeds = prompt_embeds.cpu()
        pooled_prompt_embeds = pooled_prompt_embeds.cpu()

        return {
            "CONDITIONING": {
                "prompt_embeds": prompt_embeds,
                "pooled_prompt_embeds": pooled_prompt_embeds,
                "text": text,
                "arch": arch,
            }
        }
    else:
        # SD1.5 or fallback — just pass text, let sampler handle encoding
        tokenizer = clip.get("tokenizer")
        text_encoder = clip.get("text_encoder")
        if not tokenizer or not text_encoder:
            return {"CONDITIONING": {"text": text, "arch": arch}}

        text_encoder.to(device)
        text_inputs = tokenizer(text, padding="max_length", max_length=77,
                                truncation=True, return_tensors="pt")
        with torch.no_grad():
            text_embeds = text_encoder(text_inputs.input_ids.to(device))[0]

        text_encoder.to('cpu')
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

        return {"CONDITIONING": {"prompt_embeds": text_embeds.cpu(), "text": text, "arch": arch}}


def exec_conditioning_combine(inputs, widgets, ctx):
    cond1 = inputs.get("CONDITIONING_1")
    cond2 = inputs.get("CONDITIONING_2")
    if not cond1 or not cond2:
        raise ValueError("Need both conditioning inputs")

    embeds1 = cond1.get("prompt_embeds")
    embeds2 = cond2.get("prompt_embeds")
    if embeds1 is not None and embeds2 is not None:
        combined = torch.cat([embeds1, embeds2], dim=1)
    else:
        combined = embeds1 or embeds2

    return {"CONDITIONING": {
        "prompt_embeds": combined,
        "text": f"{cond1.get('text', '')} + {cond2.get('text', '')}",
        "arch": cond1.get("arch", "sdxl"),
    }}


register_node(NodeTypeDef(
    type_id="clip_text_encode", category="conditioning", label="CLIP Text Encode",
    inputs=[PortDef("CLIP", "CLIP")],
    outputs=[PortDef("CONDITIONING", "CONDITIONING")],
    widgets=[WidgetDef("text", "textarea", default="", label="Text")],
    execute=exec_clip_text_encode, color="#facc15",
    description="Encode text using CLIP. Loads encoder to GPU, encodes, offloads — only uses VRAM during encoding.",
))

register_node(NodeTypeDef(
    type_id="conditioning_combine", category="conditioning", label="Conditioning Combine",
    inputs=[PortDef("CONDITIONING_1", "CONDITIONING"), PortDef("CONDITIONING_2", "CONDITIONING")],
    outputs=[PortDef("CONDITIONING", "CONDITIONING")],
    widgets=[],
    execute=exec_conditioning_combine, color="#fb923c",
))
