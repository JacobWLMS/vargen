"""Settings & configuration management."""

import logging
from pathlib import Path
from typing import Optional
import yaml

log = logging.getLogger(__name__)

DEFAULT_CONFIG_PATH = Path.home() / ".vargen" / "config.yaml"

DEFAULT_CONFIG = {
    "model_paths": [],
    "output_dir": None,  # defaults to <project>/outputs
    "defaults": {
        "steps": 20,
        "guidance": 3.5,
        "width": 1024,
        "height": 1024,
        "seed": -1,
    },
    "vram_mode": "balanced",  # "aggressive", "balanced", "keep_loaded"
}

# ComfyUI-compatible model subdirectories
MODEL_CATEGORIES = {
    "checkpoints": ["*.safetensors", "*.ckpt"],
    "diffusion_models": ["*.safetensors", "*.gguf"],
    "loras": ["*.safetensors"],
    "controlnet": ["*.safetensors", "*.pth"],
    "clip": ["*.safetensors"],
    "clip_vision": ["*.safetensors", "*.bin"],
    "text_encoders": ["*.safetensors"],
    "vae": ["*.safetensors"],
    "upscale_models": ["*.safetensors", "*.pth"],
    "embeddings": ["*.safetensors", "*.pt", "*.bin"],
    "ipadapter": ["*.safetensors", "*.bin"],
}


class Config:
    """Application configuration backed by YAML file."""

    def __init__(self, path: Optional[str | Path] = None):
        self.path = Path(path or DEFAULT_CONFIG_PATH)
        self._data: dict = {}
        self.load()

    def load(self):
        if self.path.exists():
            with open(self.path) as f:
                self._data = yaml.safe_load(f) or {}
            log.info(f"Loaded config from {self.path}")
        else:
            self._data = {}
            log.info(f"No config at {self.path}, using defaults")

        # Merge with defaults
        for key, val in DEFAULT_CONFIG.items():
            if key not in self._data:
                self._data[key] = val

        # Auto-detect common model paths
        self._auto_detect_paths()

    def save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.path, "w") as f:
            yaml.dump(self._data, f, default_flow_style=False, sort_keys=False)
        log.info(f"Saved config to {self.path}")

    def _auto_detect_paths(self):
        """Auto-detect ComfyUI and other common model directories."""
        auto_paths = [
            Path.home() / "ComfyUI" / "models",
            Path.home() / "stable-diffusion-webui" / "models",
            Path("/workspace/ComfyUI/models"),  # RunPod
        ]
        for p in auto_paths:
            if p.exists() and str(p) not in self.model_paths:
                self._data.setdefault("model_paths", []).append(str(p))
                log.info(f"Auto-detected model path: {p}")

    @property
    def model_paths(self) -> list[str]:
        return self._data.get("model_paths", [])

    @model_paths.setter
    def model_paths(self, paths: list[str]):
        self._data["model_paths"] = paths

    @property
    def output_dir(self) -> str | None:
        return self._data.get("output_dir")

    @property
    def defaults(self) -> dict:
        return self._data.get("defaults", DEFAULT_CONFIG["defaults"])

    @property
    def vram_mode(self) -> str:
        return self._data.get("vram_mode", "balanced")

    def to_dict(self) -> dict:
        return dict(self._data)

    def update(self, data: dict):
        self._data.update(data)
        self.save()


def browse_models(model_paths: list[str]) -> dict[str, list[dict]]:
    """Scan all model paths and return categorized inventory."""
    inventory: dict[str, list[dict]] = {cat: [] for cat in MODEL_CATEGORIES}

    for base_path_str in model_paths:
        base_path = Path(base_path_str)
        if not base_path.exists():
            continue

        for category, patterns in MODEL_CATEGORIES.items():
            cat_dir = base_path / category
            if not cat_dir.exists():
                continue

            for pattern in patterns:
                for model_file in cat_dir.rglob(pattern):
                    if model_file.is_file():
                        inventory[category].append({
                            "name": model_file.name,
                            "path": str(model_file),
                            "size_mb": round(model_file.stat().st_size / 1024 / 1024, 1),
                            "format": model_file.suffix.lstrip("."),
                            "source_dir": str(base_path),
                            "relative": str(model_file.relative_to(base_path)),
                        })

    # Deduplicate by filename within each category
    for cat in inventory:
        seen = set()
        deduped = []
        for m in inventory[cat]:
            if m["name"] not in seen:
                seen.add(m["name"])
                deduped.append(m)
        inventory[cat] = sorted(deduped, key=lambda x: x["name"])

    return inventory
