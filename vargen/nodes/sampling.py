"""Sampling nodes — KSampler and variants."""

import torch
import logging

from . import register_node, NodeTypeDef, PortDef, WidgetDef

log = logging.getLogger(__name__)

SAMPLERS = [
    "euler", "euler_ancestral", "heun", "heunpp2", "dpm_2", "dpm_2_ancestral",
    "lms", "dpm_fast", "dpm_adaptive", "dpmpp_2s_ancestral", "dpmpp_sde",
    "dpmpp_sde_gpu", "dpmpp_2m", "dpmpp_2m_sde", "dpmpp_2m_sde_gpu",
    "dpmpp_3m_sde", "dpmpp_3m_sde_gpu", "ddpm", "lcm", "ddim", "uni_pc",
    "uni_pc_bh2",
]

SCHEDULERS = [
    "normal", "karras", "exponential", "sgm_uniform", "simple",
    "ddim_uniform", "beta", "linear_quadratic",
]


def exec_ksampler(inputs, widgets, ctx):
    pipe = inputs.get("_pipe")
    if not pipe:
        raise ValueError("KSampler needs a pipeline (connect Load Checkpoint)")

    positive = inputs.get("POSITIVE")
    negative = inputs.get("NEGATIVE")
    latent = inputs.get("LATENT")

    seed = widgets.get("seed", -1)
    steps = widgets.get("steps", 20)
    cfg = widgets.get("cfg", 7.0)
    sampler = widgets.get("sampler", "euler")
    scheduler = widgets.get("scheduler", "normal")
    denoise = widgets.get("denoise", 1.0)

    if seed == -1:
        seed = torch.randint(0, 2**32, (1,)).item()

    log.info(f"KSampler: {steps} steps, cfg={cfg}, sampler={sampler}/{scheduler}, denoise={denoise}, seed={seed}")

    generator = torch.Generator("cpu").manual_seed(seed)

    # Get dimensions from latent or positive conditioning
    width = inputs.get("_width", 1024)
    height = inputs.get("_height", 1024)

    kwargs = {
        "num_inference_steps": steps,
        "guidance_scale": cfg,
        "generator": generator,
    }

    positive_text = positive.get("text", "") if positive else ""
    negative_text = negative.get("text", "") if negative else ""

    if denoise < 1.0 and inputs.get("IMAGE"):
        # img2img mode
        kwargs["image"] = inputs["IMAGE"]
        kwargs["strength"] = denoise
        kwargs["prompt"] = positive_text
        if negative_text:
            kwargs["negative_prompt"] = negative_text
    else:
        # txt2img mode
        kwargs["prompt"] = positive_text
        kwargs["width"] = width
        kwargs["height"] = height
        if negative_text:
            kwargs["negative_prompt"] = negative_text

    result = pipe(**kwargs)
    image = result.images[0]

    return {"IMAGE": image, "LATENT": None}


# ── Register ──────────────────────────────────

register_node(NodeTypeDef(
    type_id="ksampler",
    category="sampling",
    label="KSampler",
    inputs=[
        PortDef("MODEL", "MODEL"),
        PortDef("POSITIVE", "CONDITIONING"),
        PortDef("NEGATIVE", "CONDITIONING"),
        PortDef("LATENT", "LATENT"),
        PortDef("IMAGE", "IMAGE", optional=True),  # for img2img
    ],
    outputs=[
        PortDef("IMAGE", "IMAGE"),
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
    execute=exec_ksampler,
    color="#e88a2a",
    description="Sample from the model using various samplers and schedulers",
))
