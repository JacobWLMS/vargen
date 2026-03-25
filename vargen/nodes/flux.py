"""FLUX pipeline nodes — FLUX.1-dev/schnell support."""

import torch
import logging

from . import register_node, NodeTypeDef, PortDef, WidgetDef

log = logging.getLogger(__name__)


def exec_load_flux(inputs, widgets, ctx):
    """Load FLUX model — supports GGUF and standard formats."""
    from diffusers import FluxPipeline

    model_name = widgets.get("model", "")
    if not model_name:
        raise ValueError("No FLUX model selected")

    model_path = ctx["model_manager"].find_model("diffusion_models", model_name)
    if not model_path:
        model_path = ctx["model_manager"].find_model("checkpoints", model_name)

    log.info(f"Loading FLUX: {model_name}")

    if model_path and str(model_path).endswith(".gguf"):
        from diffusers import FluxTransformer2DModel, GGUFQuantizationConfig
        gguf_config = GGUFQuantizationConfig(compute_dtype=torch.bfloat16)
        transformer = FluxTransformer2DModel.from_single_file(
            str(model_path), quantization_config=gguf_config, torch_dtype=torch.bfloat16,
        )
        pipe = FluxPipeline.from_pretrained(
            "black-forest-labs/FLUX.1-dev", transformer=transformer, torch_dtype=torch.bfloat16,
        )
    elif model_path:
        pipe = FluxPipeline.from_single_file(str(model_path), torch_dtype=torch.bfloat16)
    else:
        pipe = FluxPipeline.from_pretrained(model_name, torch_dtype=torch.bfloat16)

    pipe.enable_model_cpu_offload()
    if hasattr(pipe, "enable_attention_slicing"):
        pipe.enable_attention_slicing()

    log.info(f"FLUX loaded: {model_name}")
    return {"MODEL": pipe.transformer, "_pipe": pipe, "_arch": "flux"}


def exec_flux_sampler(inputs, widgets, ctx):
    """FLUX-specific sampler — uses FluxPipeline directly."""
    pipe = inputs.get("_pipe")
    if not pipe:
        raise ValueError("FLUX Sampler needs a pipeline — connect from Load FLUX")

    prompt = ""
    positive = inputs.get("POSITIVE")
    if positive:
        prompt = positive.get("text", "")

    seed = int(widgets.get("seed", -1))
    steps = int(widgets.get("steps", 20))
    guidance = float(widgets.get("guidance", 3.5))
    width = int(widgets.get("width", 1024))
    height = int(widgets.get("height", 1024))

    if seed == -1:
        seed = torch.randint(0, 2**32, (1,)).item()
    generator = torch.Generator("cpu").manual_seed(seed)

    log.info(f"FLUX sampling: {steps}steps guidance={guidance} {width}x{height} seed={seed}")

    result = pipe(
        prompt=prompt,
        width=width,
        height=height,
        num_inference_steps=steps,
        guidance_scale=guidance,
        generator=generator,
    )
    image = result.images[0]
    log.info(f"FLUX output: {image.size}")
    return {"IMAGE": image}


register_node(NodeTypeDef(
    type_id="load_flux", category="loaders", label="Load FLUX",
    inputs=[],
    outputs=[PortDef("MODEL", "MODEL")],
    widgets=[
        WidgetDef("model", "combo", label="Model", options=[]),
    ],
    execute=exec_load_flux, color="#f59e0b",
    description="Load FLUX.1-dev/schnell model (supports GGUF)",
))

register_node(NodeTypeDef(
    type_id="flux_sampler", category="sampling", label="FLUX Sampler",
    inputs=[
        PortDef("MODEL", "MODEL"),
        PortDef("POSITIVE", "CONDITIONING", optional=True),
    ],
    outputs=[PortDef("IMAGE", "IMAGE")],
    widgets=[
        WidgetDef("seed", "number", default=-1, label="Seed"),
        WidgetDef("steps", "slider", default=20, min=1, max=50, step=1, label="Steps"),
        WidgetDef("guidance", "slider", default=3.5, min=0, max=20, step=0.5, label="Guidance"),
        WidgetDef("width", "number", default=1024, min=512, max=2048, step=64, label="Width"),
        WidgetDef("height", "number", default=1024, min=512, max=2048, step=64, label="Height"),
    ],
    execute=exec_flux_sampler, color="#f59e0b",
    description="FLUX-specific sampler — outputs IMAGE directly (no VAE Decode needed)",
))
