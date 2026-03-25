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
    source: str = "huggingface"        # "huggingface", "url", "civitai"
    quantize: Optional[str] = None     # "nf4", "fp8", "int8" — applied on load
    format: Optional[str] = None       # "safetensors", "gguf", "bin" — auto-detected if None
    vram_mb: Optional[int] = None      # estimated VRAM usage
    gated: bool = False                # requires HF login
    subfolder: Optional[str] = None    # subfolder within repo

    def cache_id(self) -> str:
        """Unique cache key for this model."""
        parts = [self.repo.replace("/", "--")]
        if self.file:
            parts.append(self.file.replace("/", "--"))
        if self.quantize:
            parts.append(self.quantize)
        return "_".join(parts)


@dataclass
class StepConfig:
    """A single pipeline step."""
    name: str
    type: str                          # "vision-llm", "txt2img", "img2img", "pixel-upscale", "refine", "ip-adapter"
    model: str                         # key into pipeline.models
    params: dict = field(default_factory=dict)  # step-type-specific params

    def resolve_refs(self, outputs: dict[str, any]) -> dict:
        """Replace {step_name} references in params with actual outputs."""
        resolved = {}
        for key, val in self.params.items():
            if isinstance(val, str) and val.startswith("{") and val.endswith("}"):
                ref = val[1:-1]
                if ref in outputs:
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
            # Some step types reference additional models in params
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
        name = sdef.pop("name")
        step_type = sdef.pop("type")
        model = sdef.pop("model")
        steps.append(StepConfig(name=name, type=step_type, model=model, params=sdef))

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
        sdef.update(step.params)
        data["steps"].append(sdef)

    return yaml.dump(data, default_flow_style=False, sort_keys=False, allow_unicode=True)
