"""Sampling nodes — KSampler works with raw UNET + scheduler, no _pipe."""

import torch
import gc
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


def _swap_scheduler(scheduler, sampler_name, scheduler_type):
    import diffusers
    cls_name = SAMPLER_MAP.get(sampler_name)
    if not cls_name:
        return scheduler
    cls = getattr(diffusers, cls_name, None)
    if not cls:
        return scheduler
    kwargs = {}
    if scheduler_type == "karras":
        kwargs["use_karras_sigmas"] = True
    elif scheduler_type == "exponential":
        kwargs["use_exponential_sigmas"] = True
    if "sde" in sampler_name and cls_name == "DPMSolverMultistepScheduler":
        kwargs["algorithm_type"] = "sde-dpmsolver++"
    try:
        return cls.from_config(scheduler.config, **kwargs)
    except Exception as e:
        log.warning(f"Scheduler swap failed: {e}")
        return scheduler


def exec_ksampler(inputs, widgets, ctx):
    """KSampler — takes raw UNET + conditioning + latent. Manages its own GPU."""
    model = inputs.get("MODEL")
    scheduler = inputs.get("_scheduler")
    positive = inputs.get("POSITIVE")
    negative = inputs.get("NEGATIVE")
    latent_input = inputs.get("LATENT")
    image_input = inputs.get("IMAGE")
    arch = inputs.get("_arch", "sdxl")

    if model is None:
        raise ValueError("KSampler needs MODEL — connect from Load UNET or Load Checkpoint")

    seed = int(widgets.get("seed", -1))
    steps = int(widgets.get("steps", 20))
    cfg = float(widgets.get("cfg", 7.0))
    sampler = widgets.get("sampler", "euler")
    scheduler_type = widgets.get("scheduler", "normal")
    denoise = float(widgets.get("denoise", 1.0))
    width = inputs.get("_width", 1024)
    height = inputs.get("_height", 1024)

    if seed == -1:
        seed = torch.randint(0, 2**32, (1,)).item()
    generator = torch.Generator("cpu").manual_seed(seed)

    log.info(f"KSampler: {steps}steps cfg={cfg} {sampler}/{scheduler_type} denoise={denoise} seed={seed}")

    # For now, we need _pipe for diffusers pipeline execution
    # TODO: implement raw UNET denoising loop without pipeline wrapper
    pipe = inputs.get("_pipe")
    if pipe:
        # Swap scheduler
        if scheduler:
            pipe.scheduler = _swap_scheduler(scheduler, sampler, scheduler_type)
        else:
            pipe.scheduler = _swap_scheduler(pipe.scheduler, sampler, scheduler_type)

        # Move UNET to GPU
        device = "cuda" if torch.cuda.is_available() else "cpu"
        if hasattr(pipe, 'unet') and pipe.unet is not None:
            pipe.unet.to(device)
        elif hasattr(pipe, 'transformer') and pipe.transformer is not None:
            pipe.transformer.to(device)
        log.info(f"UNET on {device}")

        kwargs = {
            "num_inference_steps": steps,
            "guidance_scale": cfg,
            "generator": generator,
            "output_type": "latent",
        }

        # Conditioning
        has_embeds = positive and "prompt_embeds" in positive
        if has_embeds:
            kwargs["prompt_embeds"] = positive["prompt_embeds"].to(device)
            if "pooled_prompt_embeds" in positive and positive["pooled_prompt_embeds"] is not None:
                kwargs["pooled_prompt_embeds"] = positive["pooled_prompt_embeds"].to(device)
            if negative and "prompt_embeds" in negative:
                kwargs["negative_prompt_embeds"] = negative["prompt_embeds"].to(device)
                if "pooled_prompt_embeds" in negative and negative["pooled_prompt_embeds"] is not None:
                    kwargs["negative_pooled_prompt_embeds"] = negative["pooled_prompt_embeds"].to(device)
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

        # Offload UNET
        if hasattr(pipe, 'unet') and pipe.unet is not None:
            pipe.unet.to('cpu')
        elif hasattr(pipe, 'transformer') and pipe.transformer is not None:
            pipe.transformer.to('cpu')
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

        latent = latent.cpu()
        log.info(f"KSampler done: {latent.shape}")
        return {"LATENT": latent, "_pipe": pipe, "_scheduler": pipe.scheduler}
    else:
        raise ValueError("KSampler currently requires _pipe from Load Checkpoint. "
                        "Use Load Checkpoint instead of separate Load UNET for now.")


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
        WidgetDef("batch_size", "slider", default=1, min=1, max=16, step=1, label="Batch Size"),
    ],
    execute=exec_ksampler, color="#e88a2a",
    description="Sample from UNET. Moves model to GPU for sampling, offloads after.",
))
