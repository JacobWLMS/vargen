"""Pipeline YAML schema — the contract between AI authors and the engine."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional
import yaml


@dataclass
class ModelRef:
    """A model reference with source for automatic retrieval."""
    name: str
    repo: str                          # e.g. "black-forest-labs/FLUX.1-dev"
    file: Optional[str] = None         # e.g. "flux1-dev.safetensors" (None = whole repo)
    source: str = "huggingface"        # "huggingface", "url", "civitai", "local"
    quantize: Optional[str] = None     # "nf4", "fp8", "int8" — applied on load
    format: Optional[str] = None       # "safetensors", "gguf", "bin" — auto-detected if None
    vram_mb: Optional[int] = None      # estimated VRAM usage
    gated: bool = False                # requires HF login
    subfolder: Optional[str] = None    # subfolder within repo

    def cache_id(self) -> str:
        parts = [self.repo.replace("/", "--")]
        if self.file:
            parts.append(self.file.replace("/", "--"))
        if self.quantize:
            parts.append(self.quantize)
        return "_".join(parts)


@dataclass
class IPAdapterConfig:
    """IP-Adapter modifier for generation steps."""
    model: str               # key into pipeline.models
    reference: str           # "{input}" or "{step_name}" — the identity reference image
    weight: float = 0.8
    weight_type: str = "linear"      # "linear", "ease_out", "style_transfer"
    start: float = 0.0
    end: float = 1.0


@dataclass
class ControlNetConfig:
    """ControlNet modifier for generation steps."""
    model: str               # key into pipeline.models
    image: Optional[str] = None      # control image source, None = auto-detect from input
    strength: float = 0.8
    start: float = 0.0
    end: float = 1.0
    preprocessor: Optional[str] = None  # "openpose", "canny", "depth", None = pre-processed


@dataclass
class LoRAConfig:
    """LoRA modifier for generation steps."""
    model: str               # key into pipeline.models
    weight: float = 0.7


@dataclass
class StepConfig:
    """A single pipeline step."""
    name: str
    type: str                          # "vision-llm", "txt2img", "img2img", "pixel-upscale", etc.
    model: str                         # key into pipeline.models
    params: dict = field(default_factory=dict)
    batch_count: int = 1               # run this step N times with different seeds
    ip_adapter: Optional[IPAdapterConfig] = None
    controlnet: Optional[ControlNetConfig] = None
    loras: list[LoRAConfig] = field(default_factory=list)
    condition: Optional[str] = None    # skip step if condition is false (future)

    def resolve_refs(self, outputs: dict[str, any]) -> dict:
        """Replace {step_name} references in params with actual outputs."""
        resolved = {}
        for key, val in self.params.items():
            if isinstance(val, str) and "{" in val and "}" in val:
                # Handle {ref} substitution
                ref = val.strip("{}")
                if ref == "input":
                    resolved[key] = val  # handled by engine
                elif ref in outputs:
                    resolved[key] = outputs[ref]
                else:
                    resolved[key] = val
            else:
                resolved[key] = val
        return resolved


@dataclass
class Pipeline:
    """A complete generation pipeline."""
    name: str
    description: str
    version: int
    models: dict[str, ModelRef]
    steps: list[StepConfig]
    author: Optional[str] = None
    tags: list[str] = field(default_factory=list)

    def required_models(self) -> list[ModelRef]:
        """All models needed by this pipeline."""
        used = set()
        for step in self.steps:
            used.add(step.model)
            if step.ip_adapter:
                used.add(step.ip_adapter.model)
            if step.controlnet:
                used.add(step.controlnet.model)
            for lora in step.loras:
                used.add(lora.model)
            for key in ("text_encoder", "clip", "vae", "upscale_model", "clip_vision"):
                if key in step.params:
                    used.add(step.params[key])
        return [self.models[k] for k in used if k in self.models]


def load_pipeline(path: str | Path) -> Pipeline:
    """Load a pipeline from YAML."""
    with open(path) as f:
        raw = yaml.safe_load(f)

    models = {}
    for key, mdef in raw.get("models", {}).items():
        models[key] = ModelRef(
            name=key,
            repo=mdef["repo"],
            file=mdef.get("file"),
            source=mdef.get("source", "huggingface"),
            quantize=mdef.get("quantize"),
            format=mdef.get("format"),
            vram_mb=mdef.get("vram_mb"),
            gated=mdef.get("gated", False),
            subfolder=mdef.get("subfolder"),
        )

    steps = []
    for sdef in raw.get("steps", []):
        sdef = dict(sdef)  # copy
        name = sdef.pop("name")
        step_type = sdef.pop("type")
        model = sdef.pop("model")
        batch_count = sdef.pop("batch_count", 1)
        condition = sdef.pop("condition", None)

        # Parse IP-Adapter config
        ip_adapter = None
        if "ip_adapter" in sdef:
            ipa = sdef.pop("ip_adapter")
            ip_adapter = IPAdapterConfig(
                model=ipa["model"],
                reference=ipa.get("reference", "{input}"),
                weight=ipa.get("weight", 0.8),
                weight_type=ipa.get("weight_type", "linear"),
                start=ipa.get("start", 0.0),
                end=ipa.get("end", 1.0),
            )

        # Parse ControlNet config
        controlnet = None
        if "controlnet" in sdef:
            cn = sdef.pop("controlnet")
            controlnet = ControlNetConfig(
                model=cn["model"],
                image=cn.get("image"),
                strength=cn.get("strength", 0.8),
                start=cn.get("start", 0.0),
                end=cn.get("end", 1.0),
                preprocessor=cn.get("preprocessor"),
            )

        # Parse LoRA configs
        loras = []
        if "loras" in sdef:
            for ldef in sdef.pop("loras"):
                loras.append(LoRAConfig(
                    model=ldef["model"],
                    weight=ldef.get("weight", 0.7),
                ))

        steps.append(StepConfig(
            name=name, type=step_type, model=model,
            params=sdef, batch_count=batch_count,
            ip_adapter=ip_adapter, controlnet=controlnet,
            loras=loras, condition=condition,
        ))

    return Pipeline(
        name=raw.get("name", "Untitled"),
        description=raw.get("description", ""),
        version=raw.get("version", 1),
        author=raw.get("author"),
        tags=raw.get("tags", []),
        models=models,
        steps=steps,
    )


def dump_pipeline(pipeline: Pipeline) -> str:
    """Serialize a pipeline back to YAML."""
    data = {
        "name": pipeline.name,
        "description": pipeline.description,
        "version": pipeline.version,
    }
    if pipeline.author:
        data["author"] = pipeline.author
    if pipeline.tags:
        data["tags"] = pipeline.tags

    data["models"] = {}
    for key, model in pipeline.models.items():
        mdef = {"repo": model.repo}
        if model.file:
            mdef["file"] = model.file
        if model.source != "huggingface":
            mdef["source"] = model.source
        if model.quantize:
            mdef["quantize"] = model.quantize
        if model.format:
            mdef["format"] = model.format
        if model.vram_mb:
            mdef["vram_mb"] = model.vram_mb
        if model.gated:
            mdef["gated"] = True
        if model.subfolder:
            mdef["subfolder"] = model.subfolder
        data["models"][key] = mdef

    data["steps"] = []
    for step in pipeline.steps:
        sdef = {"name": step.name, "type": step.type, "model": step.model}
        if step.batch_count > 1:
            sdef["batch_count"] = step.batch_count
        if step.ip_adapter:
            sdef["ip_adapter"] = {
                "model": step.ip_adapter.model,
                "reference": step.ip_adapter.reference,
                "weight": step.ip_adapter.weight,
            }
            if step.ip_adapter.weight_type != "linear":
                sdef["ip_adapter"]["weight_type"] = step.ip_adapter.weight_type
        if step.controlnet:
            sdef["controlnet"] = {
                "model": step.controlnet.model,
                "strength": step.controlnet.strength,
            }
            if step.controlnet.preprocessor:
                sdef["controlnet"]["preprocessor"] = step.controlnet.preprocessor
        if step.loras:
            sdef["loras"] = [{"model": l.model, "weight": l.weight} for l in step.loras]
        sdef.update(step.params)
        data["steps"].append(sdef)

    return yaml.dump(data, default_flow_style=False, sort_keys=False, allow_unicode=True)
