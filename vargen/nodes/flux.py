"""FLUX sampling node — works with Load Checkpoint (FLUX auto-detected)."""

import torch
import logging

from . import register_node, NodeTypeDef, PortDef, WidgetDef

log = logging.getLogger(__name__)


def exec_flux_sampler(inputs, widgets, ctx):
    """FLUX-specific sampler — uses FluxPipeline. Outputs IMAGE directly (no VAE Decode needed)."""
    pipe = inputs.get("_pipe")
    if not pipe:
        raise ValueError("FLUX Sampler needs a pipeline — connect MODEL from Load Checkpoint (select a FLUX model)")

    # Prompt from widget or from connected conditioning
    prompt = widgets.get("prompt", "")
    positive = inputs.get("POSITIVE")
    if positive and positive.get("text"):
        prompt = positive["text"]

    negative = widgets.get("negative", "")
    negative_input = inputs.get("NEGATIVE")
    if negative_input and negative_input.get("text"):
        negative = negative_input["text"]

    seed = int(widgets.get("seed", -1))
    steps = int(widgets.get("steps", 20))
    guidance = float(widgets.get("guidance", 3.5))
    width = int(widgets.get("width", 1024))
    height = int(widgets.get("height", 1024))
    max_seq_len = int(widgets.get("max_sequence_length", 512))

    if seed == -1:
        seed = torch.randint(0, 2**32, (1,)).item()
    generator = torch.Generator("cpu").manual_seed(seed)

    log.info(f"FLUX: {steps}steps guidance={guidance} {width}x{height} seed={seed}")

    kwargs = {
        "prompt": prompt,
        "width": width,
        "height": height,
        "num_inference_steps": steps,
        "guidance_scale": guidance,
        "generator": generator,
        "max_sequence_length": max_seq_len,
    }

    # IP-Adapter image passthrough
    ip_image = inputs.get("_ip_adapter_image")
    if ip_image is not None:
        kwargs["ip_adapter_image"] = ip_image

    result = pipe(**kwargs)
    image = result.images[0]
    log.info(f"FLUX done: {image.size}")
    return {"IMAGE": image}


register_node(NodeTypeDef(
    type_id="flux_sampler", category="sampling", label="FLUX Sampler",
    inputs=[
        PortDef("MODEL", "MODEL"),
        PortDef("POSITIVE", "CONDITIONING", optional=True),
        PortDef("NEGATIVE", "CONDITIONING", optional=True),
    ],
    outputs=[PortDef("IMAGE", "IMAGE")],
    widgets=[
        WidgetDef("prompt", "textarea", default="", label="Prompt"),
        WidgetDef("negative", "textarea", default="", label="Negative"),
        WidgetDef("seed", "number", default=-1, label="Seed"),
        WidgetDef("steps", "slider", default=20, min=1, max=50, step=1, label="Steps"),
        WidgetDef("guidance", "slider", default=3.5, min=0, max=20, step=0.5, label="Guidance"),
        WidgetDef("width", "number", default=1024, min=512, max=2048, step=64, label="Width"),
        WidgetDef("height", "number", default=1024, min=512, max=2048, step=64, label="Height"),
        WidgetDef("max_sequence_length", "slider", default=512, min=64, max=512, step=64, label="Max Seq Len"),
    ],
    execute=exec_flux_sampler, color="#f59e0b",
    description="FLUX sampler — outputs IMAGE directly. Connect MODEL from Load Checkpoint (FLUX auto-detected from filename).",
))
