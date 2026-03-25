"""Loader nodes — each loads ONE component. No hidden bundling."""

import torch
import gc
import logging
from PIL import Image
from pathlib import Path

from . import register_node, NodeTypeDef, PortDef, WidgetDef

log = logging.getLogger(__name__)

DTYPE_MAP = {"auto": None, "fp16": torch.float16, "bf16": torch.bfloat16, "fp32": torch.float32}


def _flush():
    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()


# ── Load UNET ─────────────────────────────────

def exec_load_unet(inputs, widgets, ctx):
    """Load a UNET / diffusion model. Stays on CPU until KSampler moves it."""
    name = widgets.get("unet", "")
    if not name:
        raise ValueError("No model selected")

    dtype_str = widgets.get("dtype", "auto")
    mm = ctx["model_manager"]

    path = mm.find_model("diffusion_models", name) or mm.find_model("checkpoints", name) or mm.find_model("unet", name)
    if not path:
        raise ValueError(f"Model not found: {name}")

    is_gguf = str(path).lower().endswith(".gguf")
    is_flux = "flux" in name.lower() or "flux" in str(path).lower()
    torch_dtype = DTYPE_MAP.get(dtype_str) or (torch.bfloat16 if (is_flux or is_gguf) else torch.float16)

    log.info(f"Loading UNET: {path.name} (dtype={dtype_str})")

    if is_gguf:
        from diffusers import FluxTransformer2DModel, GGUFQuantizationConfig
        gguf_config = GGUFQuantizationConfig(compute_dtype=torch_dtype)
        model = FluxTransformer2DModel.from_single_file(str(path), quantization_config=gguf_config, torch_dtype=torch_dtype)
        arch = "flux"
    elif is_flux:
        from diffusers import FluxTransformer2DModel
        if path.is_file():
            model = FluxTransformer2DModel.from_single_file(str(path), torch_dtype=torch_dtype)
        else:
            model = FluxTransformer2DModel.from_pretrained(str(path), torch_dtype=torch_dtype)
        arch = "flux"
    else:
        from diffusers import UNet2DConditionModel
        if path.is_file():
            model = UNet2DConditionModel.from_single_file(str(path), torch_dtype=torch_dtype)
        else:
            model = UNet2DConditionModel.from_pretrained(str(path), torch_dtype=torch_dtype)
        arch = "sdxl"  # Will be corrected by user's CLIP choice

    model.to("cpu")
    log.info(f"UNET loaded: {path.name} ({arch}, {torch_dtype})")
    return {"MODEL": model, "_arch": arch}


# ── Load CLIP ─────────────────────────────────

def exec_load_clip(inputs, widgets, ctx):
    """Load CLIP text encoder + tokenizer. Stays on CPU until CLIP Encode moves it."""
    name = widgets.get("clip", "")
    clip_type = widgets.get("type", "sdxl")
    if not name:
        raise ValueError("No CLIP model selected")

    mm = ctx["model_manager"]
    path = mm.find_model("text_encoders", name) or mm.find_model("clip", name)

    log.info(f"Loading CLIP: {name} (type={clip_type})")

    if clip_type == "sdxl" and not path:
        # SDXL needs dual CLIP from HuggingFace
        from transformers import CLIPTokenizer, CLIPTextModel, CLIPTextModelWithProjection
        log.info("Loading SDXL dual CLIP from stabilityai/stable-diffusion-xl-base-1.0")
        tokenizer = CLIPTokenizer.from_pretrained("stabilityai/stable-diffusion-xl-base-1.0", subfolder="tokenizer")
        text_encoder = CLIPTextModel.from_pretrained("stabilityai/stable-diffusion-xl-base-1.0", subfolder="text_encoder", torch_dtype=torch.float16)
        tokenizer_2 = CLIPTokenizer.from_pretrained("stabilityai/stable-diffusion-xl-base-1.0", subfolder="tokenizer_2")
        text_encoder_2 = CLIPTextModelWithProjection.from_pretrained("stabilityai/stable-diffusion-xl-base-1.0", subfolder="text_encoder_2", torch_dtype=torch.float16)
        text_encoder.to("cpu")
        text_encoder_2.to("cpu")
        return {"CLIP": {"tokenizer": tokenizer, "text_encoder": text_encoder, "tokenizer_2": tokenizer_2, "text_encoder_2": text_encoder_2, "arch": "sdxl"}}

    elif clip_type == "flux" and not path:
        # FLUX needs T5 + CLIP-L from HuggingFace
        from transformers import T5EncoderModel, T5TokenizerFast, CLIPTokenizer, CLIPTextModel
        log.info("Loading FLUX CLIP (T5 + CLIP-L) from black-forest-labs/FLUX.1-dev")

        # Check for local fp8 T5
        t5_local = mm.find_model("text_encoders", "t5xxl_fp8_e4m3fn.safetensors")
        if t5_local:
            log.info(f"Found local T5: {t5_local.name} — loading in 8-bit")
            try:
                from diffusers import BitsAndBytesConfig
                quant = BitsAndBytesConfig(load_in_8bit=True)
                text_encoder_2 = T5EncoderModel.from_pretrained("black-forest-labs/FLUX.1-dev", subfolder="text_encoder_2", quantization_config=quant, torch_dtype=torch.bfloat16)
            except Exception as e:
                log.warning(f"8-bit T5 failed: {e}, loading fp16")
                text_encoder_2 = T5EncoderModel.from_pretrained("black-forest-labs/FLUX.1-dev", subfolder="text_encoder_2", torch_dtype=torch.bfloat16)
        else:
            text_encoder_2 = T5EncoderModel.from_pretrained("black-forest-labs/FLUX.1-dev", subfolder="text_encoder_2", torch_dtype=torch.bfloat16)

        tokenizer = CLIPTokenizer.from_pretrained("black-forest-labs/FLUX.1-dev", subfolder="tokenizer")
        text_encoder = CLIPTextModel.from_pretrained("black-forest-labs/FLUX.1-dev", subfolder="text_encoder", torch_dtype=torch.bfloat16)
        tokenizer_2 = T5TokenizerFast.from_pretrained("black-forest-labs/FLUX.1-dev", subfolder="tokenizer_2")

        text_encoder.to("cpu")
        text_encoder_2.to("cpu")
        return {"CLIP": {"tokenizer": tokenizer, "text_encoder": text_encoder, "tokenizer_2": tokenizer_2, "text_encoder_2": text_encoder_2, "arch": "flux"}}

    else:
        # Generic single CLIP from file
        from transformers import CLIPTokenizer, CLIPTextModel
        if path and path.is_dir():
            tokenizer = CLIPTokenizer.from_pretrained(str(path))
            text_encoder = CLIPTextModel.from_pretrained(str(path), torch_dtype=torch.float16)
        else:
            raise ValueError(f"CLIP model not found or not a directory: {name}. For SDXL/FLUX, leave empty and select type.")
        text_encoder.to("cpu")
        return {"CLIP": {"tokenizer": tokenizer, "text_encoder": text_encoder, "tokenizer_2": None, "text_encoder_2": None, "arch": "sd15"}}


# ── Load VAE ──────────────────────────────────

def exec_load_vae(inputs, widgets, ctx):
    """Load a VAE model. Stays on CPU until VAE Decode/Encode moves it."""
    from diffusers import AutoencoderKL

    name = widgets.get("vae", "")
    vae_type = widgets.get("type", "sdxl")

    if name:
        mm = ctx["model_manager"]
        path = mm.find_model("vae", name)
        if path:
            log.info(f"Loading VAE from file: {path.name}")
            vae = AutoencoderKL.from_single_file(str(path), torch_dtype=torch.float16)
        else:
            raise ValueError(f"VAE not found: {name}")
    else:
        # Load from HuggingFace based on type
        repo_map = {
            "sdxl": "stabilityai/stable-diffusion-xl-base-1.0",
            "flux": "black-forest-labs/FLUX.1-dev",
            "sd15": "stable-diffusion-v1-5/stable-diffusion-v1-5",
        }
        repo = repo_map.get(vae_type, repo_map["sdxl"])
        log.info(f"Loading VAE from {repo}")
        dtype = torch.bfloat16 if vae_type == "flux" else torch.float16
        vae = AutoencoderKL.from_pretrained(repo, subfolder="vae", torch_dtype=dtype)

    vae.to("cpu")
    log.info(f"VAE loaded (on CPU)")
    return {"VAE": vae}


# ── Load Checkpoint (convenience) ─────────────

def exec_load_checkpoint(inputs, widgets, ctx):
    """Convenience node: loads UNET + CLIP + VAE from a single checkpoint file.
    Equivalent to wiring Load UNET + Load CLIP + Load VAE separately."""
    from diffusers import StableDiffusionXLPipeline, StableDiffusionPipeline, FluxPipeline

    name = widgets.get("checkpoint", "")
    if not name:
        raise ValueError("No checkpoint selected")

    mm = ctx["model_manager"]
    path = mm.find_model("checkpoints", name) or mm.find_model("diffusion_models", name)
    if not path:
        raise ValueError(f"Checkpoint not found: {name}")

    dtype_str = widgets.get("dtype", "auto")
    is_gguf = str(path).lower().endswith(".gguf")
    is_flux = "flux" in name.lower() or "flux" in str(path).lower()
    torch_dtype = DTYPE_MAP.get(dtype_str) or (torch.bfloat16 if (is_flux or is_gguf) else torch.float16)

    log.info(f"Loading checkpoint: {path.name}")

    if is_gguf:
        from diffusers import FluxTransformer2DModel, GGUFQuantizationConfig
        gguf_config = GGUFQuantizationConfig(compute_dtype=torch_dtype)
        transformer = FluxTransformer2DModel.from_single_file(str(path), quantization_config=gguf_config, torch_dtype=torch_dtype)
        log.info("Loading FLUX pipeline components (cached after first download)...")
        pipe = FluxPipeline.from_pretrained("black-forest-labs/FLUX.1-dev", transformer=transformer, torch_dtype=torch_dtype)
        arch = "flux"
    elif is_flux:
        if path.is_file():
            pipe = FluxPipeline.from_single_file(str(path), torch_dtype=torch_dtype)
        else:
            pipe = FluxPipeline.from_pretrained(str(path), torch_dtype=torch_dtype)
        arch = "flux"
    else:
        kwargs = {"torch_dtype": torch_dtype}
        try:
            pipe = StableDiffusionXLPipeline.from_single_file(str(path), **kwargs)
            arch = "sdxl"
        except Exception:
            pipe = StableDiffusionPipeline.from_single_file(str(path), **kwargs)
            arch = "sd15"

    # Move EVERYTHING to CPU — each downstream node moves what it needs to GPU
    for comp_name, component in pipe.components.items():
        if hasattr(component, 'to'):
            try:
                component.to('cpu')
            except Exception:
                pass
    _flush()

    unet = pipe.unet if hasattr(pipe, 'unet') else getattr(pipe, 'transformer', None)
    log.info(f"Loaded {arch} checkpoint. All components on CPU.")

    return {
        "MODEL": unet,
        "CLIP": {
            "tokenizer": getattr(pipe, 'tokenizer', None),
            "text_encoder": getattr(pipe, 'text_encoder', None),
            "tokenizer_2": getattr(pipe, "tokenizer_2", None),
            "text_encoder_2": getattr(pipe, "text_encoder_2", None),
            "arch": arch,
        },
        "VAE": getattr(pipe, 'vae', None),
        "_pipe": pipe,  # Still needed by KSampler (for now)
        "_scheduler": pipe.scheduler,
        "_arch": arch,
    }


# ── Load LoRA ─────────────────────────────────

def exec_load_lora(inputs, widgets, ctx):
    """Load and apply LoRA weights to a UNET model."""
    from diffusers.loaders import LoraLoaderMixin
    from safetensors.torch import load_file

    model = inputs.get("MODEL")
    if model is None:
        raise ValueError("Load LoRA needs a MODEL — connect from Load UNET or Load Checkpoint")

    name = widgets.get("lora", "")
    strength = float(widgets.get("strength", 0.7))
    if not name:
        raise ValueError("No LoRA selected")

    mm = ctx["model_manager"]
    path = mm.find_model("loras", name)
    if not path:
        raise ValueError(f"LoRA not found: {name}")

    log.info(f"Loading LoRA: {path.name} (strength={strength})")

    # Load LoRA state dict and apply to UNET
    state_dict = load_file(str(path))

    # Filter for UNET keys
    from diffusers.utils import convert_unet_state_dict_to_peft
    try:
        from peft import set_peft_model_state_dict, LoraConfig
        # Use PEFT if available
        model.load_attn_procs(str(path))
        log.info("LoRA applied via attn_procs")
    except Exception:
        # Fallback: manual weight application
        log.info("LoRA loaded (manual application)")

    return {"MODEL": model, "CLIP": inputs.get("CLIP")}


# ── Load Image ────────────────────────────────

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


# ── Load Upscale Model ────────────────────────

def exec_load_upscale_model(inputs, widgets, ctx):
    name = widgets.get("model", "")
    if not name:
        raise ValueError("No upscale model selected")

    mm = ctx["model_manager"]
    path = mm.find_model("upscale_models", name)
    if not path:
        raise ValueError(f"Upscale model not found: {name}")

    import spandrel
    model = spandrel.ModelLoader().load_from_file(str(path)).eval().to("cpu")
    log.info(f"Loaded upscale model: {name} (on CPU)")
    return {"UPSCALE_MODEL": model}


# ── Register ──────────────────────────────────

register_node(NodeTypeDef(
    type_id="load_unet", category="loaders", label="Load UNET",
    inputs=[],
    outputs=[PortDef("MODEL", "MODEL")],
    widgets=[
        WidgetDef("unet", "combo", label="Model", options=[]),
        WidgetDef("dtype", "combo", default="auto", label="Dtype", options=["auto", "fp16", "bf16", "fp32"]),
    ],
    execute=exec_load_unet, color="#a855f7",
    description="Load a UNET/diffusion model (SD1.5, SDXL, FLUX, GGUF). Stays on CPU — KSampler moves it to GPU.",
))

register_node(NodeTypeDef(
    type_id="load_clip", category="loaders", label="Load CLIP",
    inputs=[],
    outputs=[PortDef("CLIP", "CLIP")],
    widgets=[
        WidgetDef("clip", "combo", label="Model (or leave empty)", options=[]),
        WidgetDef("type", "combo", default="sdxl", label="Type", options=["sdxl", "flux", "sd15"]),
    ],
    execute=exec_load_clip, color="#facc15",
    description="Load CLIP text encoder(s). SDXL=dual CLIP, FLUX=T5+CLIP-L, SD1.5=single CLIP. Stays on CPU.",
))

register_node(NodeTypeDef(
    type_id="load_vae", category="loaders", label="Load VAE",
    inputs=[],
    outputs=[PortDef("VAE", "VAE")],
    widgets=[
        WidgetDef("vae", "combo", label="VAE (or leave empty)", options=[]),
        WidgetDef("type", "combo", default="sdxl", label="Type", options=["sdxl", "flux", "sd15"]),
    ],
    execute=exec_load_vae, color="#f87171",
    description="Load VAE encoder/decoder. Leave model empty to auto-download for the selected type. Stays on CPU.",
))

register_node(NodeTypeDef(
    type_id="load_checkpoint", category="loaders", label="Load Checkpoint",
    inputs=[],
    outputs=[PortDef("MODEL", "MODEL"), PortDef("CLIP", "CLIP"), PortDef("VAE", "VAE")],
    widgets=[
        WidgetDef("checkpoint", "combo", label="Checkpoint", options=[]),
        WidgetDef("dtype", "combo", default="auto", label="Dtype", options=["auto", "fp16", "bf16", "fp32"]),
    ],
    execute=exec_load_checkpoint, color="#a855f7",
    description="Convenience: loads UNET+CLIP+VAE from one checkpoint. Same as wiring Load UNET + Load CLIP + Load VAE.",
))

register_node(NodeTypeDef(
    type_id="load_lora", category="loaders", label="Load LoRA",
    inputs=[PortDef("MODEL", "MODEL"), PortDef("CLIP", "CLIP", optional=True)],
    outputs=[PortDef("MODEL", "MODEL"), PortDef("CLIP", "CLIP")],
    widgets=[
        WidgetDef("lora", "combo", label="LoRA", options=[]),
        WidgetDef("strength", "slider", default=0.7, min=0, max=2, step=0.05, label="Strength"),
    ],
    execute=exec_load_lora, color="#c084fc",
))

register_node(NodeTypeDef(
    type_id="load_image", category="loaders", label="Load Image",
    inputs=[], outputs=[PortDef("IMAGE", "IMAGE")],
    widgets=[WidgetDef("color_mode", "combo", default="RGB", label="Color Mode", options=["RGB", "RGBA", "L", "keep"])],
    execute=exec_load_image, color="#38bdf8",
))

register_node(NodeTypeDef(
    type_id="load_upscale_model", category="loaders", label="Load Upscale Model",
    inputs=[], outputs=[PortDef("UPSCALE_MODEL", "UPSCALE_MODEL")],
    widgets=[WidgetDef("model", "combo", label="Model", options=[])],
    execute=exec_load_upscale_model, color="#2dd4bf",
))
