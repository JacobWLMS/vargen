"""Sampling nodes — KSampler using actual diffusers pipeline with pre-encoded conditioning."""

import torch
import logging

from . import register_node, NodeTypeDef, PortDef, WidgetDef

log = logging.getLogger(__name__)

SAMPLERS = [
    "euler", "euler_ancestral", "heun", "dpm_2", "dpm_2_ancestral",
    "lms", "dpmpp_2s_ancestral", "dpmpp_sde", "dpmpp_2m", "dpmpp_2m_sde",
    "dpmpp_3m_sde", "ddpm", "lcm", "ddim", "uni_pc", "uni_pc_bh2",
]

SCHEDULERS = [
    "normal", "karras", "exponential", "sgm_uniform", "simple",
    "ddim_uniform", "beta",
]


def exec_ksampler(inputs, widgets, ctx):
    pipe = inputs.get("_pipe")
    if not pipe:
        raise ValueError("KSampler needs a pipeline — connect MODEL from Load Checkpoint")

    positive = inputs.get("POSITIVE")
    negative = inputs.get("NEGATIVE")
    latent_input = inputs.get("LATENT")
    image_input = inputs.get("IMAGE")

    seed = int(widgets.get("seed", -1))
    steps = int(widgets.get("steps", 20))
    cfg = float(widgets.get("cfg", 7.0))
    denoise = float(widgets.get("denoise", 1.0))

    if seed == -1:
        seed = torch.randint(0, 2**32, (1,)).item()

    generator = torch.Generator("cpu").manual_seed(seed)
    width = inputs.get("_width", 1024)
    height = inputs.get("_height", 1024)

    log.info(f"KSampler: {steps} steps, cfg={cfg}, denoise={denoise}, seed={seed}, {width}x{height}")

    kwargs = {
        "num_inference_steps": steps,
        "guidance_scale": cfg,
        "generator": generator,
        "output_type": "latent",  # Output latent, not image
    }

    # Use pre-encoded conditioning if available
    has_embeds = positive and "prompt_embeds" in positive

    if has_embeds:
        kwargs["prompt_embeds"] = positive["prompt_embeds"]
        if "pooled_prompt_embeds" in positive:
            kwargs["pooled_prompt_embeds"] = positive["pooled_prompt_embeds"]

        if negative and "prompt_embeds" in negative:
            kwargs["negative_prompt_embeds"] = negative["prompt_embeds"]
            if "pooled_prompt_embeds" in negative:
                kwargs["negative_pooled_prompt_embeds"] = negative["pooled_prompt_embeds"]
    else:
        # Fallback to text
        kwargs["prompt"] = positive.get("text", "") if positive else ""
        neg_text = negative.get("text", "") if negative else ""
        if neg_text:
            kwargs["negative_prompt"] = neg_text

    if denoise < 1.0 and image_input is not None:
        # img2img mode
        kwargs["image"] = image_input
        kwargs["strength"] = denoise
    else:
        # txt2img mode
        kwargs["width"] = int(width)
        kwargs["height"] = int(height)

    result = pipe(**kwargs)

    # result.images contains latents when output_type="latent"
    latent = result.images
    if not isinstance(latent, torch.Tensor):
        # Some pipelines return a list or other format
        latent = torch.tensor(latent)

    log.info(f"KSampler output latent: {latent.shape if hasattr(latent, 'shape') else type(latent)}")
    return {"LATENT": latent, "IMAGE": None, "_pipe": pipe}


register_node(NodeTypeDef(
    type_id="ksampler", category="sampling", label="KSampler",
    inputs=[
        PortDef("MODEL", "MODEL"),
        PortDef("POSITIVE", "CONDITIONING"),
        PortDef("NEGATIVE", "CONDITIONING"),
        PortDef("LATENT", "LATENT"),
        PortDef("IMAGE", "IMAGE", optional=True),
    ],
    outputs=[
        PortDef("LATENT", "LATENT"),
    ],
    widgets=[
        WidgetDef("seed", "number", default=-1, label="Seed"),
        WidgetDef("steps", "slider", default=20, min=1, max=150, step=1, label="Steps"),
        WidgetDef("cfg", "slider", default=7.0, min=0, max=30, step=0.5, label="CFG"),
        WidgetDef("sampler", "combo", default="euler", options=SAMPLERS, label="Sampler"),
        WidgetDef("scheduler", "combo", default="normal", options=SCHEDULERS, label="Scheduler"),
        WidgetDef("denoise", "slider", default=1.0, min=0, max=1, step=0.01, label="Denoise"),
    ],
    execute=exec_ksampler, color="#e88a2a",
    description="Sample from the model — outputs LATENT (needs VAE Decode for image)",
))
