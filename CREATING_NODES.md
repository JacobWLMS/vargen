# Creating Nodes for vargen

Nodes are the building blocks of vargen workflows. Each node performs one operation with typed inputs, outputs, and configurable widgets.

## Quick Start

Create a new `.py` file in `vargen/nodes/` and register your node:

```python
# vargen/nodes/my_nodes.py

import torch
from . import register_node, NodeTypeDef, PortDef, WidgetDef

def exec_my_node(inputs, widgets, ctx):
    """
    inputs:  dict of connected port values (keyed by port name)
    widgets: dict of widget values (keyed by widget name)
    ctx:     dict with 'model_manager', 'input_image'

    Returns: dict of output port values (keyed by port name)
    """
    image = inputs.get("IMAGE")
    strength = widgets.get("strength", 1.0)

    # Do your processing here
    result = process(image, strength)

    return {"IMAGE": result}

register_node(NodeTypeDef(
    type_id="my_node",          # unique identifier
    category="image",           # groups in the asset panel
    label="My Node",            # display name
    inputs=[
        PortDef("IMAGE", "IMAGE"),
    ],
    outputs=[
        PortDef("IMAGE", "IMAGE"),
    ],
    widgets=[
        WidgetDef("strength", "slider", default=1.0, min=0, max=2, step=0.1, label="Strength"),
    ],
    execute=exec_my_node,
    color="#60a0ff",             # node accent color (hex)
    description="Does something to an image",
))
```

Then import it in `vargen/nodes/__init__.py` or `vargen/api.py`.

## Port Types

| Type | Color | What it carries |
|------|-------|----------------|
| `MODEL` | `#b380ff` (purple) | UNET model |
| `CLIP` | `#ffd500` (yellow) | Tokenizer + text encoder bundle |
| `VAE` | `#ff6060` (red) | VAE encoder/decoder |
| `CONDITIONING` | `#ffa040` (orange) | Encoded text embeddings (prompt_embeds + pooled) |
| `LATENT` | `#ff80c0` (pink) | Latent tensor (BxCxHxW) |
| `IMAGE` | `#60a0ff` (blue) | PIL Image |
| `MASK` | `#40ff40` (green) | Mask tensor |
| `UPSCALE_MODEL` | `#60a0ff` (blue) | Spandrel upscale model |
| `STRING` | `#80ff80` (green) | Text string |
| `INT` | `#60d060` (green) | Integer |
| `FLOAT` | `#60d060` (green) | Float |

## Widget Types

| Type | Renders as | Properties |
|------|-----------|------------|
| `combo` | `<select>` dropdown | `options: ["a", "b", "c"]` |
| `text` | `<input>` single line | |
| `textarea` | `<textarea>` multi-line | |
| `number` | `<input type="number">` | `min`, `max`, `step` |
| `slider` | `<input type="range">` | `min`, `max`, `step` |
| `toggle` | checkbox | `default: true/false` |

## Combo Options for Models

For widgets that select models, use these special `name` values — the frontend auto-populates them from the model inventory:

| Widget name | Populates from |
|-------------|---------------|
| `checkpoint` | `checkpoints/` + `diffusion_models/` |
| `lora` | `loras/` |
| `model` (on `load_upscale_model`) | `upscale_models/` |

## The `ctx` Object

Every execute function receives a `ctx` dict:

```python
ctx = {
    "model_manager": ModelManager,  # .find_model(category, filename) → Path
    "input_image": Image | None,    # uploaded reference image
}
```

## The `inputs` Object

Connected port values arrive in `inputs`, keyed by port name:

```python
inputs = {
    "MODEL": unet_model,           # from Load Checkpoint
    "CLIP": {                       # from Load Checkpoint
        "tokenizer": ...,
        "text_encoder": ...,
        "tokenizer_2": ...,        # SDXL only
        "text_encoder_2": ...,     # SDXL only
        "arch": "sdxl" | "sd15",
    },
    "VAE": vae_model,              # from Load Checkpoint
    "CONDITIONING": {              # from CLIP Text Encode
        "prompt_embeds": tensor,
        "pooled_prompt_embeds": tensor,  # SDXL only
        "text": "original text",
        "arch": "sdxl",
    },
    "LATENT": tensor,              # shape: [B, 4, H//8, W//8]
    "IMAGE": PIL.Image,
    "_pipe": pipeline,             # the full diffusers pipeline (internal)
    "_width": int,                 # from Empty Latent
    "_height": int,
}
```

## Internal Pass-through Values

Values prefixed with `_` are internal state passed between nodes:

| Key | Source | Purpose |
|-----|--------|---------|
| `_pipe` | Load Checkpoint | Full diffusers pipeline — KSampler needs this |
| `_width` | Empty Latent | Image dimensions for KSampler |
| `_height` | Empty Latent | Image dimensions for KSampler |

The graph executor automatically passes `_` prefixed values through connected edges.

## Example: Standard txt2img Pipeline

```
Load Checkpoint ──MODEL──→ KSampler ──LATENT──→ VAE Decode ──IMAGE──→ Save Image
       │──CLIP──→ CLIP Text Encode (positive) ──CONDITIONING──→ KSampler
       │──CLIP──→ CLIP Text Encode (negative) ──CONDITIONING──→ KSampler
       │──VAE──→ VAE Decode
Empty Latent ──LATENT──→ KSampler
```

## Categories

Use these for the `category` field:

| Category | For |
|----------|-----|
| `loaders` | Load Checkpoint, Load LoRA, Load Image, Load Upscale Model |
| `conditioning` | CLIP Text Encode, Conditioning Combine |
| `sampling` | KSampler |
| `latent` | Empty Latent, VAE Encode, VAE Decode |
| `image` | Save Image, Image Scale, Image Crop, Upscale with Model |
| `mask` | Mask operations |

## Plugin Nodes

Drop a `.py` file in `~/.vargen/plugins/` with:

```python
STEP_TYPE = "my_custom_node"

def run(model_ref, params, mm, pipeline):
    # This is the OLD step-based API, not the node API
    pass
```

For the new node API, add files to `vargen/nodes/` and import them in `api.py`.
