"""Model manager — download, cache, load, and unload models."""

import gc
import os
import logging
from pathlib import Path
from typing import Optional

import torch
from huggingface_hub import hf_hub_download, snapshot_download, HfApi

from .schema import ModelRef

log = logging.getLogger(__name__)

DEFAULT_CACHE_DIR = Path.home() / ".vargen" / "models"


class ModelManager:
    """Manages model lifecycle: resolve → download → load → unload."""

    def __init__(self, cache_dir: str | Path | None = None, search_paths: list[str | Path] | None = None):
        self.cache_dir = Path(cache_dir or DEFAULT_CACHE_DIR)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._loaded: dict[str, any] = {}    # name → loaded model object
        self._vram_used: int = 0             # estimated MB in use
        # Additional paths to search for local models (e.g. ComfyUI models dir)
        self.search_paths = [Path(p) for p in (search_paths or [])]

    @property
    def available_vram_mb(self) -> int:
        if torch.cuda.is_available():
            free, total = torch.cuda.mem_get_info()
            return int(free / 1024 / 1024)
        return 0

    @property
    def total_vram_mb(self) -> int:
        if torch.cuda.is_available():
            _, total = torch.cuda.mem_get_info()
            return int(total / 1024 / 1024)
        return 0

    def is_cached(self, ref: ModelRef) -> bool:
        """Check if a model is already downloaded."""
        local = self._local_path(ref)
        if local is None:
            return False
        if ref.file:
            return local.is_file()
        return local.is_dir()

    def ensure(self, ref: ModelRef) -> Path:
        """Download model if not cached, return local path."""
        local = self._local_path(ref)
        if local and local.exists():
            log.info(f"Model '{ref.name}' already cached at {local}")
            return local

        log.info(f"Downloading '{ref.name}' from {ref.source}://{ref.repo}")
        return self._download(ref)

    def ensure_all(self, refs: list[ModelRef], on_progress=None) -> dict[str, Path]:
        """Download all missing models. Returns {name: path} mapping."""
        paths = {}
        for i, ref in enumerate(refs):
            if on_progress:
                on_progress(ref.name, i, len(refs), self.is_cached(ref))
            paths[ref.name] = self.ensure(ref)
        return paths

    def unload_all(self):
        """Unload all models and free VRAM."""
        for name in list(self._loaded.keys()):
            self.unload(name)
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            torch.cuda.synchronize()
        self._vram_used = 0
        log.info(f"All models unloaded. Free VRAM: {self.available_vram_mb}MB")

    def unload(self, name: str):
        """Unload a specific model."""
        if name in self._loaded:
            obj = self._loaded.pop(name)
            del obj
            gc.collect()
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
            log.info(f"Unloaded '{name}'")

    def get(self, name: str):
        """Get a loaded model by name."""
        return self._loaded.get(name)

    def register(self, name: str, obj: any):
        """Register a loaded model object for lifecycle management."""
        self._loaded[name] = obj

    def model_path(self, ref: ModelRef) -> Path:
        """Get local path for a model ref (download if needed)."""
        return self.ensure(ref)

    def status(self) -> dict:
        """Current model manager status."""
        return {
            "cache_dir": str(self.cache_dir),
            "loaded_models": list(self._loaded.keys()),
            "vram_total_mb": self.total_vram_mb,
            "vram_free_mb": self.available_vram_mb,
        }

    def list_cached(self) -> list[str]:
        """List all cached model directories/files."""
        if not self.cache_dir.exists():
            return []
        return [p.name for p in self.cache_dir.iterdir()]

    # ── internal ──────────────────────────────────────────────

    def _local_path(self, ref: ModelRef) -> Optional[Path]:
        """Compute local cache path for a model ref.

        Checks: search_paths first (for existing ComfyUI models etc),
        then the vargen cache dir.
        """
        # Check search paths for the file (e.g. ComfyUI/models/**)
        if ref.file:
            for sp in self.search_paths:
                # Search recursively for the filename
                for match in sp.rglob(ref.file.split("/")[-1]):
                    if match.is_file():
                        return match
            # Also check if ref.file is an absolute path
            abs_path = Path(ref.file)
            if abs_path.is_absolute() and abs_path.exists():
                return abs_path

        # Fall back to cache dir
        repo_dir = self.cache_dir / ref.repo.replace("/", "--")
        if ref.file:
            return repo_dir / ref.file
        return repo_dir

    def _download(self, ref: ModelRef) -> Path:
        """Download a model from its source."""
        if ref.source == "huggingface":
            return self._download_hf(ref)
        elif ref.source == "url":
            return self._download_url(ref)
        else:
            raise ValueError(f"Unknown source: {ref.source}")

    def _download_hf(self, ref: ModelRef) -> Path:
        """Download from HuggingFace Hub."""
        repo_dir = self.cache_dir / ref.repo.replace("/", "--")
        repo_dir.mkdir(parents=True, exist_ok=True)

        if ref.file:
            # Download single file
            local = hf_hub_download(
                repo_id=ref.repo,
                filename=ref.file,
                local_dir=repo_dir,
                subfolder=ref.subfolder,
            )
            return Path(local)
        else:
            # Download entire repo
            local = snapshot_download(
                repo_id=ref.repo,
                local_dir=repo_dir,
            )
            return Path(local)

    def _download_url(self, ref: ModelRef) -> Path:
        """Download from direct URL."""
        import urllib.request
        repo_dir = self.cache_dir / ref.repo.replace("/", "--")
        repo_dir.mkdir(parents=True, exist_ok=True)
        filename = ref.file or ref.repo.split("/")[-1]
        dest = repo_dir / filename
        if not dest.exists():
            log.info(f"Downloading {ref.repo} → {dest}")
            urllib.request.urlretrieve(ref.repo, dest)
        return dest
