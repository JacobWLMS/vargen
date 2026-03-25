"""Sampling nodes — KSampler with real scheduler swapping and full diffusers params."""

import torch
import logging

from . import register_node, NodeTypeDef, PortDef, WidgetDef

log = logging.getLogger(__name__)

SAMPLER_MAP = {
    "euler": "EulerDiscreteScheduler",
    "euler_ancestral": "EulerAncestralDiscreteScheduler",
    "heun": "HeunDiscreteScheduler",
    "dpm_2": "KDPM2DiscreteScheduler",
    "dpm_2_ancestral": "KDPM2AncestralDiscreteScheduler",
    "lms": "LMSDiscreteScheduler",
    "dpmpp_2s_ancestral": "DPMSolverSinglestepScheduler",
    "dpmpp_sde": "DPMSolverSDEScheduler",
    "dpmpp_2m": "DPMSolverMultistepScheduler",
    "dpmpp_2m_sde": "DPMSolverMultistepScheduler",
    "dpmpp_3m_sde": "DPMSolverMultistepScheduler",
    "ddpm": "DDPMScheduler",
    "ddim": "DDIMScheduler",
    "uni_pc": "UniPCMultistepScheduler",
    "lcm": "LCMScheduler",
    "pndm": "PNDMScheduler",
}

SAMPLERS = list(SAMPLER_MAP.keys())

SCHEDULERS = ["normal", "karras", "exponential", "sgm_uniform", "trailing"]


def _swap_scheduler(pipe, sampler_name: str, scheduler_type: str):
    """Swap the pipeline's scheduler to match the selected sampler."""
    import diffusers

    cls_name = SAMPLER_MAP.get(sampler_name)
    if not cls_name:
        log.warning(f"Unknown sampler: {sampler_name}, keeping default")
        return

    cls = getattr(diffusers, cls_name, None)
    if not cls:
        log.warning(f"Scheduler class not found: {cls_name}")
        return

    kwargs = {}

    # Karras sigmas
    if scheduler_type == "karras" and hasattr(cls, '__init__'):
        kwargs["use_karras_sigmas"] = True
    elif scheduler_type == "exponential":
        kwargs["use_exponential_sigmas"] = True

    # SDE variants
    if "sde" in sampler_name:
        if cls_name == "DPMSolverMultistepScheduler":
            kwargs["algorithm_type"] = "sde-dpmsolver++"
        if "3m" in sampler_name:
            kwargs["solver_order"] = 3

    try:
        pipe.scheduler = cls.from_config(pipe.scheduler.config, **kwargs)
        log.info(f"Scheduler: {cls_name} ({scheduler_type})")
    except Exception as e:
        log.warning(f"Failed to set scheduler {cls_name}: {e}")


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
    sampler = widgets.get("sampler", "euler")
    scheduler = widgets.get("scheduler", "normal")
    denoise = float(widgets.get("denoise", 1.0))
    clip_skip = int(widgets.get("clip_skip", 0))

    if seed == -1:
        seed = torch.randint(0, 2**32, (1,)).item()

    # Swap scheduler
    _swap_scheduler(pipe, sampler, scheduler)

    # Apply CLIP skip if set
    if clip_skip > 0 and hasattr(pipe, 'text_encoder'):
        if hasattr(pipe.text_encoder.config, 'num_hidden_layers'):
            pipe.text_encoder.config.num_hidden_layers -= clip_skip

    generator = torch.Generator("cpu").manual_seed(seed)
    width = inputs.get("_width", 1024)
    height = inputs.get("_height", 1024)

    log.info(f"KSampler: {steps}steps cfg={cfg} {sampler}/{scheduler} denoise={denoise} seed={seed} {width}x{height}")

    kwargs = {
        "num_inference_steps": steps,
        "guidance_scale": cfg,
        "generator": generator,
        "output_type": "latent",
    }

    # Use pre-encoded conditioning
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
        kwargs["prompt"] = positive.get("text", "") if positive else ""
        neg_text = negative.get("text", "") if negative else ""
        if neg_text:
            kwargs["negative_prompt"] = neg_text

    if denoise < 1.0 and image_input is not None:
        kwargs["image"] = image_input
        kwargs["strength"] = denoise
    else:
        kwargs["width"] = int(width)
        kwargs["height"] = int(height)

    result = pipe(**kwargs)
    latent = result.images
    if not isinstance(latent, torch.Tensor):
        latent = torch.tensor(latent)

    log.info(f"KSampler done: latent {latent.shape}")
    return {"LATENT": latent, "_pipe": pipe}


register_node(NodeTypeDef(
    type_id="ksampler", category="sampling", label="KSampler",
    inputs=[
        PortDef("MODEL", "MODEL"),
        PortDef("POSITIVE", "CONDITIONING"),
        PortDef("NEGATIVE", "CONDITIONING"),
        PortDef("LATENT", "LATENT"),
        PortDef("IMAGE", "IMAGE", optional=True),
    ],
    outputs=[PortDef("LATENT", "LATENT")],
    widgets=[
        WidgetDef("seed", "number", default=-1, label="Seed"),
        WidgetDef("steps", "slider", default=20, min=1, max=150, step=1, label="Steps"),
        WidgetDef("cfg", "slider", default=7.0, min=0, max=30, step=0.5, label="CFG"),
        WidgetDef("sampler", "combo", default="euler", options=SAMPLERS, label="Sampler"),
        WidgetDef("scheduler", "combo", default="normal", options=SCHEDULERS, label="Scheduler"),
        WidgetDef("denoise", "slider", default=1.0, min=0, max=1, step=0.01, label="Denoise"),
        WidgetDef("clip_skip", "slider", default=0, min=0, max=12, step=1, label="CLIP Skip"),
    ],
    execute=exec_ksampler, color="#e88a2a",
    description="Sample from model with full scheduler/sampler control. Outputs LATENT.",
))
