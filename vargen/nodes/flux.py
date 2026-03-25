"""FLUX sampling node — works with Load Checkpoint (FLUX auto-detected)."""

import torch
import logging

from . import register_node, NodeTypeDef, PortDef, WidgetDef

log = logging.getLogger(__name__)


def _setup_pipe(pipe):
    """Apply standard offload/optimization to a FLUX pipeline."""
    if torch.cuda.is_available():
        free_mb = torch.cuda.mem_get_info()[0] // (1024 * 1024)
        if free_mb < 4000:
            pipe.enable_sequential_cpu_offload()
        elif free_mb < 8000:
            pipe.enable_model_cpu_offload()
    if hasattr(pipe, "enable_attention_slicing"):
        pipe.enable_attention_slicing()


def exec_flux_sampler(inputs, widgets, ctx):
    """FLUX sampler — supports txt2img and img2img. Outputs IMAGE directly."""
    pipe = inputs.get("_pipe")
    if not pipe:
        raise ValueError("FLUX Sampler needs a pipeline — connect MODEL from Load Checkpoint (select a FLUX model)")

    # Verify it's actually a FLUX pipeline
    from diffusers import FluxPipeline
    if not isinstance(pipe, FluxPipeline):
        pipe_type = type(pipe).__name__
        raise ValueError(
            f"FLUX Sampler got a {pipe_type} pipeline, not FLUX. "
            f"Either select a FLUX model in Load Checkpoint, or use KSampler for SDXL/SD1.5 models."
        )

    prompt = widgets.get("prompt", "")
    positive = inputs.get("POSITIVE")
    if positive and positive.get("text"):
        prompt = positive["text"]

    seed = int(widgets.get("seed", -1))
    steps = int(widgets.get("steps", 20))
    guidance = float(widgets.get("guidance", 3.5))
    width = int(widgets.get("width", 1024))
    height = int(widgets.get("height", 1024))
    max_seq_len = int(widgets.get("max_sequence_length", 512))
    denoise = float(widgets.get("denoise", 1.0))
    image_input = inputs.get("IMAGE")

    if seed == -1:
        seed = torch.randint(0, 2**32, (1,)).item()
    generator = torch.Generator("cpu").manual_seed(seed)

    # img2img mode
    if image_input is not None and denoise < 1.0:
        log.info(f"FLUX img2img: {steps}steps guidance={guidance} denoise={denoise} seed={seed}")
        try:
            from diffusers import FluxImg2ImgPipeline
            img2img_pipe = FluxImg2ImgPipeline(**pipe.components)
            _setup_pipe(img2img_pipe)
            result = img2img_pipe(
                prompt=prompt, image=image_input, strength=denoise,
                num_inference_steps=steps, guidance_scale=guidance,
                generator=generator, max_sequence_length=max_seq_len,
            )
        except torch.cuda.OutOfMemoryError:
            raise  # Let executor handle OOM
        except Exception as e:
            log.warning(f"FluxImg2ImgPipeline failed: {e}. Falling back to txt2img.")
            import gc
            gc.collect()
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
            result = pipe(
                prompt=prompt, width=width, height=height,
                num_inference_steps=steps, guidance_scale=guidance,
                generator=generator, max_sequence_length=max_seq_len,
            )
    else:
        # txt2img mode
        log.info(f"FLUX txt2img: {steps}steps guidance={guidance} {width}x{height} seed={seed}")
        result = pipe(
            prompt=prompt, width=width, height=height,
            num_inference_steps=steps, guidance_scale=guidance,
            generator=generator, max_sequence_length=max_seq_len,
        )

    image = result.images[0]
    log.info(f"FLUX done: {image.size}")
    return {"IMAGE": image}


register_node(NodeTypeDef(
    type_id="flux_sampler", category="sampling", label="FLUX Sampler",
    inputs=[
        PortDef("MODEL", "MODEL"),
        PortDef("POSITIVE", "CONDITIONING", optional=True),
        PortDef("IMAGE", "IMAGE", optional=True),
    ],
    outputs=[PortDef("IMAGE", "IMAGE")],
    widgets=[
        WidgetDef("prompt", "textarea", default="", label="Prompt"),
        WidgetDef("seed", "number", default=-1, label="Seed"),
        WidgetDef("steps", "slider", default=20, min=1, max=50, step=1, label="Steps"),
        WidgetDef("guidance", "slider", default=3.5, min=0, max=20, step=0.5, label="Guidance"),
        WidgetDef("denoise", "slider", default=1.0, min=0, max=1, step=0.05, label="Denoise"),
        WidgetDef("width", "number", default=1024, min=512, max=2048, step=64, label="Width"),
        WidgetDef("height", "number", default=1024, min=512, max=2048, step=64, label="Height"),
        WidgetDef("max_sequence_length", "slider", default=512, min=64, max=512, step=64, label="Max Seq Len"),
    ],
    execute=exec_flux_sampler, color="#f59e0b",
    description="FLUX sampler — txt2img (denoise=1.0) or img2img (connect IMAGE + set denoise<1). Outputs IMAGE directly.",
))
