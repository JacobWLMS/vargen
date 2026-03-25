"""Loader nodes — load models, images, create empty latents."""

import torch
import logging
from PIL import Image
from pathlib import Path

from . import register_node, NodeTypeDef, PortDef, WidgetDef

log = logging.getLogger(__name__)

DTYPE_MAP = {
    "auto": None,
    "fp16": torch.float16,
    "bf16": torch.bfloat16,
    "fp32": torch.float32,
}

OFFLOAD_MODES = ["auto", "model_cpu", "group_offload", "sequential_cpu", "gpu_only", "cpu_only"]


def exec_load_checkpoint(inputs, widgets, ctx):
    ckpt_name = widgets.get("checkpoint", "")
    if not ckpt_name:
        raise ValueError("No checkpoint selected")

    model_path = ctx["model_manager"].find_model("checkpoints", ckpt_name)
    if not model_path:
        model_path = ctx["model_manager"].find_model("diffusion_models", ckpt_name)
    if not model_path:
        raise ValueError(f"Checkpoint not found: {ckpt_name}")

    dtype_setting = widgets.get("dtype", "auto")
    offload_mode = widgets.get("offload", "auto")
    attn_slicing = widgets.get("attention_slicing", True)
    vae_tiling = widgets.get("vae_tiling", True)

    log.info(f"Loading: {model_path}")
    is_gguf = str(model_path).lower().endswith(".gguf")
    is_flux = "flux" in ckpt_name.lower() or "flux" in str(model_path).lower()

    # Resolve dtype
    if dtype_setting == "auto":
        torch_dtype = torch.bfloat16 if (is_flux or is_gguf) else torch.float16
    else:
        torch_dtype = DTYPE_MAP.get(dtype_setting, torch.float16)

    if is_flux or is_gguf:
        try:
            pipe = _load_flux_checkpoint(model_path, is_gguf, torch_dtype)
            arch = "flux"
        except Exception as e:
            log.warning(f"FLUX load failed: {e}. Trying as SD checkpoint...")
            pipe = _load_sd_checkpoint(model_path, torch_dtype)
            arch = "sdxl" if hasattr(pipe, 'text_encoder_2') else "sd15"
    else:
        pipe = _load_sd_checkpoint(model_path, torch_dtype)
        arch = "sdxl" if hasattr(pipe, 'text_encoder_2') else "sd15"

    _setup_vram_offload(pipe, offload_mode)

    if attn_slicing and hasattr(pipe, "enable_attention_slicing"):
        pipe.enable_attention_slicing()
        log.info("Attention slicing: enabled")

    if vae_tiling:
        if hasattr(pipe, 'vae') and hasattr(pipe.vae, 'enable_tiling'):
            pipe.vae.enable_tiling()
            log.info("VAE tiling: enabled")
        elif hasattr(pipe, 'enable_vae_tiling'):
            pipe.enable_vae_tiling()
            log.info("VAE tiling: enabled (legacy)")

    log.info(f"Loaded {arch}: {ckpt_name} (dtype={dtype_setting}, offload={offload_mode})")

    return {
        "MODEL": pipe.unet if hasattr(pipe, 'unet') else getattr(pipe, 'transformer', None),
        "CLIP": {
            "tokenizer": getattr(pipe, 'tokenizer', None),
            "text_encoder": getattr(pipe, 'text_encoder', None),
            "tokenizer_2": getattr(pipe, "tokenizer_2", None),
            "text_encoder_2": getattr(pipe, "text_encoder_2", None),
            "arch": arch,
        },
        "VAE": getattr(pipe, 'vae', None),
        "_pipe": pipe,
    }


def _load_flux_checkpoint(model_path, is_gguf, torch_dtype):
    from diffusers import FluxPipeline

    if is_gguf:
        try:
            from diffusers import FluxTransformer2DModel, GGUFQuantizationConfig
        except ImportError:
            raise ValueError("GGUF requires: pip install gguf>=0.10.0")

        log.info("Loading FLUX GGUF (quantized)")
        gguf_config = GGUFQuantizationConfig(compute_dtype=torch_dtype)
        transformer = FluxTransformer2DModel.from_single_file(
            str(model_path), quantization_config=gguf_config, torch_dtype=torch_dtype,
        )
        log.info("Loading FLUX pipeline components (cached after first download)...")
        pipe = FluxPipeline.from_pretrained(
            "black-forest-labs/FLUX.1-dev", transformer=transformer, torch_dtype=torch_dtype,
        )
    elif model_path.is_file():
        pipe = FluxPipeline.from_single_file(str(model_path), torch_dtype=torch_dtype)
    else:
        pipe = FluxPipeline.from_pretrained(str(model_path), torch_dtype=torch_dtype)

    return pipe


def _load_sd_checkpoint(model_path, torch_dtype):
    from diffusers import StableDiffusionXLPipeline, StableDiffusionPipeline, AutoPipelineForText2Image

    kwargs = {"torch_dtype": torch_dtype, "trust_remote_code": True}

    if model_path.is_file():
        errors = []
        # Try SDXL
        try:
            log.info("Trying SDXL pipeline...")
            return StableDiffusionXLPipeline.from_single_file(str(model_path), **kwargs)
        except Exception as e:
            errors.append(f"SDXL: {e}")
            log.info(f"Not SDXL: {e}")

        # Try SD1.5
        try:
            log.info("Trying SD1.5 pipeline...")
            return StableDiffusionPipeline.from_single_file(str(model_path), **kwargs)
        except Exception as e:
            errors.append(f"SD1.5: {e}")
            log.info(f"Not SD1.5: {e}")

        raise ValueError(f"Failed to load checkpoint. Tried:\n" + "\n".join(errors))
    else:
        return AutoPipelineForText2Image.from_pretrained(str(model_path), **kwargs)


def _setup_vram_offload(pipe, mode="auto"):
    """Set up VRAM offloading using diffusers' built-in hooks.

    Modes:
    - auto: pick best mode based on free VRAM
    - model_cpu: move whole models between CPU/GPU (recommended default)
    - group_offload: move layer groups with CUDA streams (fast + low VRAM)
    - sequential_cpu: move individual layers (slowest, lowest VRAM)
    - gpu_only: keep everything on GPU (needs lots of VRAM)
    - cpu_only: no GPU at all
    """
    if not torch.cuda.is_available():
        log.info("No CUDA: running on CPU")
        pipe.to("cpu")
        return

    free_mb = torch.cuda.mem_get_info()[0] // (1024 * 1024)
    total_mb = torch.cuda.mem_get_info()[1] // (1024 * 1024)
    log.info(f"VRAM: {free_mb}MB free / {total_mb}MB total")

    if mode == "auto":
        if free_mb < 6000:
            mode = "group_offload"
        elif free_mb < 10000:
            mode = "model_cpu"
        else:
            mode = "gpu_only"

    methods = {
        "group_offload": _try_group_offload,
        "sequential_cpu": lambda p: p.enable_sequential_cpu_offload(),
        "model_cpu": lambda p: p.enable_model_cpu_offload(),
        "gpu_only": lambda p: p.to("cuda"),
        "cpu_only": lambda p: p.to("cpu"),
    }

    # Try requested mode, fall back through chain
    fallback_order = [mode, "group_offload", "model_cpu", "sequential_cpu", "cpu_only"]
    seen = set()
    for m in fallback_order:
        if m in seen or m not in methods:
            continue
        seen.add(m)
        try:
            methods[m](pipe)
            log.info(f"Offload: {m}")
            return
        except Exception as e:
            log.warning(f"Offload '{m}' failed: {e}")

    log.warning("All offload methods failed. Running on CPU.")
    pipe.to("cpu")


def _try_group_offload(pipe):
    """Use group offloading with CUDA streams — fast + low VRAM."""
    try:
        from diffusers.hooks import apply_group_offloading
        # Apply to each model component individually
        for attr_name in ["transformer", "unet", "text_encoder", "text_encoder_2", "vae"]:
            component = getattr(pipe, attr_name, None)
            if component is not None and hasattr(component, 'parameters'):
                try:
                    apply_group_offloading(
                        component,
                        offload_type="leaf_level",
                        offload_device=torch.device("cpu"),
                        onload_device=torch.device("cuda"),
                        use_stream=True,
                    )
                except Exception:
                    # Some components don't support group offloading
                    pass
        log.info("Group offloading with CUDA streams enabled")
    except ImportError:
        raise RuntimeError("Group offloading requires diffusers >= 0.32.0")


def exec_load_lora(inputs, widgets, ctx):
    pipe = inputs.get("_pipe")
    if not pipe:
        raise ValueError("LoRA needs a pipeline — connect from Load Checkpoint")

    lora_name = widgets.get("lora", "")
    strength = float(widgets.get("strength", 0.7))
    fuse = bool(widgets.get("fuse", True))

    if not lora_name:
        raise ValueError("No LoRA selected")

    model_path = ctx["model_manager"].find_model("loras", lora_name)
    if not model_path:
        raise ValueError(f"LoRA not found: {lora_name}")

    log.info(f"Loading LoRA: {model_path} (strength={strength}, fuse={fuse})")
    pipe.load_lora_weights(str(model_path))

    if fuse:
        pipe.fuse_lora(lora_scale=strength)
        log.info("LoRA fused into model weights")
    else:
        pipe.set_adapters(pipe.get_list_adapters(), adapter_weights=[strength])
        log.info("LoRA loaded (unfused, dynamic weight)")

    return {"MODEL": pipe.unet, "CLIP": inputs.get("CLIP"), "_pipe": pipe}


def exec_load_image(inputs, widgets, ctx):
    image = ctx.get("input_image")
    if image is None:
        raise ValueError("No input image — upload one to the Load Image node")
    if not isinstance(image, Image.Image):
        image = Image.open(image)
    color_mode = widgets.get("color_mode", "RGB")
    if color_mode != "keep":
        image = image.convert(color_mode)
    return {"IMAGE": image}


def exec_load_upscale_model(inputs, widgets, ctx):
    model_name = widgets.get("model", "")
    if not model_name:
        raise ValueError("No upscale model selected")

    model_path = ctx["model_manager"].find_model("upscale_models", model_name)
    if not model_path:
        raise ValueError(f"Upscale model not found: {model_name}")

    import spandrel
    model = spandrel.ModelLoader().load_from_file(str(model_path)).eval()
    device = widgets.get("device", "cuda" if torch.cuda.is_available() else "cpu")
    model = model.to(device)
    log.info(f"Loaded upscale model: {model_name} (device={device})")
    return {"UPSCALE_MODEL": model}


# ── Register ──────────────────────────────────

register_node(NodeTypeDef(
    type_id="load_checkpoint", category="loaders", label="Load Checkpoint",
    inputs=[],
    outputs=[PortDef("MODEL", "MODEL"), PortDef("CLIP", "CLIP"), PortDef("VAE", "VAE")],
    widgets=[
        WidgetDef("checkpoint", "combo", label="Checkpoint", options=[]),
        WidgetDef("dtype", "combo", default="auto", label="Dtype",
                  options=["auto", "fp16", "bf16", "fp32"]),
        WidgetDef("offload", "combo", default="auto", label="VRAM Offload",
                  options=OFFLOAD_MODES),
        WidgetDef("attention_slicing", "toggle", default=True, label="Attention Slicing"),
        WidgetDef("vae_tiling", "toggle", default=True, label="VAE Tiling"),
    ],
    execute=exec_load_checkpoint, color="#a855f7",
    description="Load SD1.5/SDXL/FLUX checkpoint. Auto-detects GGUF and FLUX from filename.",
))

register_node(NodeTypeDef(
    type_id="load_lora", category="loaders", label="Load LoRA",
    inputs=[PortDef("MODEL", "MODEL"), PortDef("CLIP", "CLIP")],
    outputs=[PortDef("MODEL", "MODEL"), PortDef("CLIP", "CLIP")],
    widgets=[
        WidgetDef("lora", "combo", label="LoRA", options=[]),
        WidgetDef("strength", "slider", default=0.7, min=0, max=2, step=0.05, label="Strength"),
        WidgetDef("fuse", "toggle", default=True, label="Fuse (permanent, faster)"),
    ],
    execute=exec_load_lora, color="#c084fc",
))

register_node(NodeTypeDef(
    type_id="load_image", category="loaders", label="Load Image",
    inputs=[], outputs=[PortDef("IMAGE", "IMAGE")],
    widgets=[
        WidgetDef("color_mode", "combo", default="RGB", label="Color Mode",
                  options=["RGB", "RGBA", "L", "keep"]),
    ],
    execute=exec_load_image, color="#38bdf8",
))

register_node(NodeTypeDef(
    type_id="load_upscale_model", category="loaders", label="Load Upscale Model",
    inputs=[], outputs=[PortDef("UPSCALE_MODEL", "UPSCALE_MODEL")],
    widgets=[
        WidgetDef("model", "combo", label="Model", options=[]),
        WidgetDef("device", "combo", default="cuda", label="Device",
                  options=["cuda", "cpu"]),
    ],
    execute=exec_load_upscale_model, color="#2dd4bf",
))
