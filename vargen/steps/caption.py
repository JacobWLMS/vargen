"""Vision-LLM captioning step."""

import logging
import torch
from PIL import Image

log = logging.getLogger(__name__)


def run_caption(model_ref, params: dict, mm, pipeline) -> str:
    """Caption an image using a vision-language model.

    Params:
        input_image: PIL Image to caption
        prompt: instruction for the VLM (default: "Describe this image in detail")
        append: text to append to the caption output
        prepend: text to prepend to the caption output
        max_tokens: max generation tokens (default: 512)
    """
    from transformers import AutoProcessor, AutoModelForCausalLM

    image: Image.Image = params.get("input_image")
    if image is None:
        raise ValueError("caption step requires an input_image")

    prompt = params.get("prompt", "Describe this image in detail")
    append = params.get("append", "")
    prepend = params.get("prepend", "")
    max_tokens = params.get("max_tokens", 512)

    model_path = mm.model_path(model_ref)
    log.info(f"Loading caption model from {model_path}")

    # Load model with automatic device mapping for low VRAM
    model = AutoModelForCausalLM.from_pretrained(
        str(model_path),
        torch_dtype=torch.float16,
        device_map="auto",
        trust_remote_code=True,
    )
    processor = AutoProcessor.from_pretrained(
        str(model_path),
        trust_remote_code=True,
    )
    mm.register("caption_model", model)
    mm.register("caption_processor", processor)

    # Build conversation
    messages = [
        {
            "role": "user",
            "content": [
                {"type": "image", "image": image},
                {"type": "text", "text": prompt},
            ],
        }
    ]

    text = processor.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    inputs = processor(
        text=[text],
        images=[image],
        return_tensors="pt",
        padding=True,
    ).to(model.device)

    with torch.no_grad():
        output_ids = model.generate(
            **inputs,
            max_new_tokens=max_tokens,
            do_sample=False,
        )

    # Decode only the generated tokens
    generated = output_ids[0][inputs.input_ids.shape[1]:]
    caption = processor.decode(generated, skip_special_tokens=True).strip()

    # Apply prepend/append
    parts = []
    if prepend:
        parts.append(prepend)
    parts.append(caption)
    if append:
        parts.append(append)

    result = ", ".join(parts) if len(parts) > 1 else parts[0]
    log.info(f"Caption: {result[:200]}...")
    return result
