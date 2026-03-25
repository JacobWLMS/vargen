"""Pipeline execution engine — runs steps with batch support and VRAM management."""

import logging
import time
from pathlib import Path
from typing import Callable, Optional

from PIL import Image

from .schema import Pipeline, StepConfig, ModelRef, load_pipeline
from .models import ModelManager

log = logging.getLogger(__name__)


class StepResult:
    """Output of a pipeline step."""
    def __init__(self, name: str, output: any, output_type: str, duration: float):
        self.name = name
        self.output = output          # Image, str, list[Image], or other
        self.output_type = output_type  # "image", "text", "images", "other"
        self.duration = duration


class CancelledError(Exception):
    pass


class PipelineEngine:
    """Execute pipelines with batch support, cancel, and surgical VRAM management."""

    def __init__(self, model_manager: ModelManager):
        self.mm = model_manager
        self._step_handlers: dict[str, Callable] = {}
        self._cancelled = False
        self._register_builtins()

    def cancel(self):
        """Cancel the currently running pipeline."""
        self._cancelled = True
        log.info("Pipeline cancellation requested")

    def register_step(self, step_type: str, handler: Callable):
        """Register a custom step handler. Drop a .py in steps/ and call this."""
        self._step_handlers[step_type] = handler

    def run(
        self,
        pipeline: Pipeline | str | Path,
        input_image: Optional[Image.Image] = None,
        overrides: Optional[dict[str, dict]] = None,
        on_step_start: Optional[Callable] = None,
        on_step_done: Optional[Callable] = None,
        on_batch_progress: Optional[Callable] = None,
    ) -> dict[str, StepResult]:
        """Run a pipeline end-to-end with batch support."""
        if isinstance(pipeline, (str, Path)):
            pipeline = load_pipeline(pipeline)

        overrides = overrides or {}
        outputs: dict[str, StepResult] = {}

        log.info(f"Pipeline: {pipeline.name} ({len(pipeline.steps)} steps)")
        log.info(f"VRAM: {self.mm.total_vram_mb}MB total, {self.mm.available_vram_mb}MB free")

        # Ensure all models are downloaded
        log.info("Checking models...")
        self.mm.ensure_all(pipeline.required_models())

        self._cancelled = False

        for i, step in enumerate(pipeline.steps):
            if self._cancelled:
                self.mm.unload_all()
                raise CancelledError("Pipeline cancelled by user")

            if on_step_start:
                on_step_start(step.name, i, len(pipeline.steps))

            log.info(f"[{i+1}/{len(pipeline.steps)}] {step.name} (type: {step.type})")

            # Resolve {ref} params
            output_values = {k: v.output for k, v in outputs.items()}
            params = step.resolve_refs(output_values)

            # Apply overrides
            if step.name in overrides:
                params.update(overrides[step.name])

            # Inject input image
            if input_image is not None:
                params.setdefault("input_image", input_image)
                # Also resolve {input} references in params
                for key, val in list(params.items()):
                    if val == "{input}":
                        params[key] = input_image

            # Inject modifier configs for generation steps
            if step.ip_adapter:
                params["_ip_adapter"] = step.ip_adapter
                # Resolve IP-Adapter reference image
                ref_key = step.ip_adapter.reference.strip("{}")
                if ref_key == "input":
                    params["_ip_ref_image"] = input_image
                elif ref_key in output_values:
                    params["_ip_ref_image"] = output_values[ref_key]
            if step.controlnet:
                params["_controlnet"] = step.controlnet
            if step.loras:
                params["_loras"] = step.loras

            # Get model ref and handler
            model_ref = pipeline.models.get(step.model)
            if not model_ref:
                raise ValueError(f"Unknown model '{step.model}' in step '{step.name}'")

            handler = self._step_handlers.get(step.type)
            if not handler:
                raise ValueError(f"Unknown step type: '{step.type}'")

            # Clear VRAM
            self.mm.unload_all()

            # Execute — with batch support
            t0 = time.time()
            if step.batch_count > 1:
                result = self._run_batch(
                    handler, model_ref, params, step, pipeline,
                    on_batch_progress,
                )
            else:
                result = handler(model_ref, params, self.mm, pipeline)

            duration = time.time() - t0

            # Wrap result
            if isinstance(result, list):
                output_type = "images"
            elif isinstance(result, Image.Image):
                output_type = "image"
            elif isinstance(result, str):
                output_type = "text"
            else:
                output_type = "other"

            step_result = StepResult(step.name, result, output_type, duration)
            outputs[step.name] = step_result

            self.mm.unload_all()
            log.info(f"  Done in {duration:.1f}s → {output_type}")

            if on_step_done:
                on_step_done(step.name, step_result)

        return outputs

    def _run_batch(self, handler, model_ref, params, step, pipeline, on_progress):
        """Run a step N times, collecting results."""
        results = []
        for batch_idx in range(step.batch_count):
            log.info(f"  Batch {batch_idx+1}/{step.batch_count}")
            if on_progress:
                on_progress(step.name, batch_idx, step.batch_count)

            batch_params = dict(params)
            batch_params["_batch_index"] = batch_idx

            # For batch, reload model each time to reset state
            # (LoRAs, IP-Adapter state, etc.)
            if batch_idx > 0:
                self.mm.unload_all()

            result = handler(model_ref, batch_params, self.mm, pipeline)
            results.append(result)

        return results

    def list_step_types(self) -> dict[str, str]:
        """List available step types and their descriptions."""
        types = {}
        for name, handler in self._step_handlers.items():
            doc = handler.__doc__ or "No description"
            types[name] = doc.split("\n")[0].strip()
        return types

    def dry_run(self, pipeline: Pipeline | str | Path) -> list[dict]:
        """Check what a pipeline would do without running it."""
        if isinstance(pipeline, (str, Path)):
            pipeline = load_pipeline(pipeline)

        info = []
        for step in pipeline.steps:
            model_ref = pipeline.models.get(step.model)
            info.append({
                "step": step.name,
                "type": step.type,
                "model": step.model,
                "batch_count": step.batch_count,
                "has_ip_adapter": step.ip_adapter is not None,
                "has_controlnet": step.controlnet is not None,
                "lora_count": len(step.loras),
                "model_cached": self.mm.is_cached(model_ref) if model_ref else False,
                "vram_mb": model_ref.vram_mb if model_ref else None,
                "handler_available": step.type in self._step_handlers,
            })
        return info

    def _register_builtins(self):
        from .steps.caption import run_caption
        from .steps.generate import run_txt2img
        from .steps.refine import run_img2img
        from .steps.upscale import run_upscale
        self._step_handlers["vision-llm"] = run_caption
        self._step_handlers["txt2img"] = run_txt2img
        self._step_handlers["img2img"] = run_img2img
        self._step_handlers["refine"] = run_img2img
        self._step_handlers["pixel-upscale"] = run_upscale

    def load_plugins(self, plugin_dir: str | Path):
        """Load custom step handlers from a directory of .py files."""
        import importlib.util
        plugin_dir = Path(plugin_dir)
        if not plugin_dir.exists():
            return

        for py_file in plugin_dir.glob("*.py"):
            if py_file.name.startswith("_"):
                continue
            spec = importlib.util.spec_from_file_location(py_file.stem, py_file)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)

            # Convention: module defines STEP_TYPE and run()
            if hasattr(mod, "STEP_TYPE") and hasattr(mod, "run"):
                self._step_handlers[mod.STEP_TYPE] = mod.run
                log.info(f"Loaded plugin: {mod.STEP_TYPE} from {py_file.name}")


def create_engine(cache_dir: str | Path | None = None, config: 'Config | None' = None) -> PipelineEngine:
    """Create a ready-to-use engine."""
    from .config import Config
    cfg = config or Config()
    mm = ModelManager(config=cfg, cache_dir=cache_dir)
    engine = PipelineEngine(mm)

    # Auto-load plugins from ~/.vargen/plugins/
    plugin_dir = Path.home() / ".vargen" / "plugins"
    engine.load_plugins(plugin_dir)

    return engine
