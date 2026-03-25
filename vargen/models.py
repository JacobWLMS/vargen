"""Model manager — download with progress, cache, load, and unload models."""

import gc
import logging
import threading
from pathlib import Path
from typing import Optional, Callable

import torch
from huggingface_hub import hf_hub_download, snapshot_download

from .schema import ModelRef
from .config import Config, browse_models, MODEL_CATEGORIES

log = logging.getLogger(__name__)

DEFAULT_CACHE_DIR = Path.home() / ".vargen" / "models"


class DownloadProgress:
    """Tracks download progress for active downloads."""

    def __init__(self):
        self._active: dict[str, dict] = {}
        self._lock = threading.Lock()

    def start(self, model_name: str, total_bytes: int = 0):
        with self._lock:
            self._active[model_name] = {
                "status": "downloading",
                "downloaded": 0,
                "total": total_bytes,
                "percent": 0.0,
            }

    def update(self, model_name: str, downloaded: int, total: int):
        with self._lock:
            if model_name in self._active:
                self._active[model_name].update({
                    "downloaded": downloaded,
                    "total": total,
                    "percent": (downloaded / total * 100) if total > 0 else 0,
                })

    def complete(self, model_name: str):
        with self._lock:
            if model_name in self._active:
                self._active[model_name]["status"] = "complete"
                self._active[model_name]["percent"] = 100.0

    def fail(self, model_name: str, error: str):
        with self._lock:
            if model_name in self._active:
                self._active[model_name]["status"] = "failed"
                self._active[model_name]["error"] = error

    def get_all(self) -> dict[str, dict]:
        with self._lock:
            return dict(self._active)

    def clear_completed(self):
        with self._lock:
            self._active = {
                k: v for k, v in self._active.items()
                if v["status"] not in ("complete", "failed")
            }


class ModelManager:
    """Manages model lifecycle: resolve, download with progress, load, unload."""

    def __init__(self, config: Optional[Config] = None, cache_dir: Optional[str | Path] = None):
        self.config = config or Config()
        self.cache_dir = Path(cache_dir or DEFAULT_CACHE_DIR)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._loaded: dict[str, any] = {}
        self.downloads = DownloadProgress()

        # Build search paths from config
        self.search_paths = [Path(p) for p in self.config.model_paths]
        log.info(f"Model search paths: {self.search_paths}")

    @property
    def available_vram_mb(self) -> int:
        if torch.cuda.is_available():
            free, _ = torch.cuda.mem_get_info()
            return int(free / 1024 / 1024)
        return 0

    @property
    def total_vram_mb(self) -> int:
        if torch.cuda.is_available():
            _, total = torch.cuda.mem_get_info()
            return int(total / 1024 / 1024)
        return 0

    def is_cached(self, ref: ModelRef) -> bool:
        local = self._local_path(ref)
        if local is None:
            return False
        if ref.file:
            return local.is_file()
        return local.is_dir() and any(local.iterdir())

    def ensure(self, ref: ModelRef) -> Path:
        """Download model if not cached, return local path."""
        local = self._local_path(ref)
        if local and local.exists() and (local.is_file() or (local.is_dir() and any(local.iterdir()))):
            return local

        log.info(f"Downloading '{ref.name}' from {ref.source}://{ref.repo}")
        return self._download(ref)

    def ensure_all(self, refs: list[ModelRef], on_progress: Optional[Callable] = None) -> dict[str, Path]:
        paths = {}
        for i, ref in enumerate(refs):
            if on_progress:
                on_progress(ref.name, i, len(refs), self.is_cached(ref))
            paths[ref.name] = self.ensure(ref)
        return paths

    def unload_all(self):
        for name in list(self._loaded.keys()):
            self.unload(name)
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            torch.cuda.synchronize()

    def unload(self, name: str):
        if name in self._loaded:
            obj = self._loaded.pop(name)
            del obj
            gc.collect()
            if torch.cuda.is_available():
                torch.cuda.empty_cache()

    def get(self, name: str):
        return self._loaded.get(name)

    def register(self, name: str, obj: any):
        self._loaded[name] = obj

    def model_path(self, ref: ModelRef) -> Path:
        return self.ensure(ref)

    def browse(self) -> dict[str, list[dict]]:
        """Browse all models across configured paths."""
        return browse_models(self.config.model_paths)

    def status(self) -> dict:
        return {
            "cache_dir": str(self.cache_dir),
            "model_paths": self.config.model_paths,
            "loaded_models": list(self._loaded.keys()),
            "vram_total_mb": self.total_vram_mb,
            "vram_free_mb": self.available_vram_mb,
            "downloads": self.downloads.get_all(),
        }

    # ── internal ──────────────────────────────────────────────

    def _local_path(self, ref: ModelRef) -> Optional[Path]:
        """Find model locally: search configured paths first, then cache."""
        if ref.file:
            filename = ref.file.split("/")[-1]
            # Search all configured model paths
            for sp in self.search_paths:
                for match in sp.rglob(filename):
                    if match.is_file():
                        return match
            # Check absolute path
            abs_path = Path(ref.file)
            if abs_path.is_absolute() and abs_path.exists():
                return abs_path

        # Fall back to cache dir
        repo_dir = self.cache_dir / ref.repo.replace("/", "--")
        if ref.file:
            return repo_dir / ref.file
        return repo_dir

    def _download(self, ref: ModelRef) -> Path:
        if ref.source in ("huggingface", "local"):
            return self._download_hf(ref)
        elif ref.source == "url":
            return self._download_url(ref)
        raise ValueError(f"Unknown source: {ref.source}")

    def _download_hf(self, ref: ModelRef) -> Path:
        repo_dir = self.cache_dir / ref.repo.replace("/", "--")
        repo_dir.mkdir(parents=True, exist_ok=True)

        self.downloads.start(ref.name)

        try:
            if ref.file:
                # Single file download with progress
                local = hf_hub_download(
                    repo_id=ref.repo,
                    filename=ref.file,
                    local_dir=repo_dir,
                    subfolder=ref.subfolder,
                )
                self.downloads.complete(ref.name)
                return Path(local)
            else:
                local = snapshot_download(
                    repo_id=ref.repo,
                    local_dir=repo_dir,
                )
                self.downloads.complete(ref.name)
                return Path(local)
        except Exception as e:
            self.downloads.fail(ref.name, str(e))
            raise

    def _download_url(self, ref: ModelRef) -> Path:
        import urllib.request
        repo_dir = self.cache_dir / ref.repo.replace("/", "--")
        repo_dir.mkdir(parents=True, exist_ok=True)
        filename = ref.file or ref.repo.split("/")[-1]
        dest = repo_dir / filename
        if not dest.exists():
            self.downloads.start(ref.name)
            try:
                urllib.request.urlretrieve(ref.repo, dest)
                self.downloads.complete(ref.name)
            except Exception as e:
                self.downloads.fail(ref.name, str(e))
                raise
        return dest
