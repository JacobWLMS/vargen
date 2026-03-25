"""Pipeline execution engine — runs steps sequentially with VRAM management."""

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
        self.output = output          # Image, str, or other
        self.output_type = output_type  # "image", "text", "latent"
        self.duration = duration


class PipelineEngine:
    """Execute pipelines with surgical VRAM management."""

    def __init__(self, model_manager: ModelManager):
        self.mm = model_manager
        self._step_handlers: dict[str, Callable] = {}
        self._register_builtins()

    def register_step(self, step_type: str, handler: Callable):
        """Register a custom step handler."""
        self._step_handlers[step_type] = handler

    def run(
        self,
        pipeline: Pipeline | str | Path,
        input_image: Optional[Image.Image] = None,
        overrides: Optional[dict[str, dict]] = None,
        on_step_start: Optional[Callable] = None,
        on_step_done: Optional[Callable] = None,
    ) -> dict[str, StepResult]:
        """Run a pipeline end-to-end.

        Args:
            pipeline: Pipeline object or path to YAML
            input_image: Input image for the pipeline
            overrides: {step_name: {param: value}} to override step params
            on_step_start: callback(step_name, step_index, total_steps)
            on_step_done: callback(step_name, result)

        Returns:
            {step_name: StepResult} for all completed steps
        """
        if isinstance(pipeline, (str, Path)):
            pipeline = load_pipeline(pipeline)

        overrides = overrides or {}
        outputs: dict[str, StepResult] = {}

        log.info(f"Running pipeline: {pipeline.name} ({len(pipeline.steps)} steps)")
        log.info(f"VRAM: {self.mm.total_vram_mb}MB total, {self.mm.available_vram_mb}MB free")

        # Ensure all models are downloaded first
        log.info("Checking models...")
        all_refs = pipeline.required_models()
        self.mm.ensure_all(all_refs)

        for i, step in enumerate(pipeline.steps):
            step_name = step.name
            if on_step_start:
                on_step_start(step_name, i, len(pipeline.steps))

            log.info(f"[{i+1}/{len(pipeline.steps)}] Running step: {step_name} (type: {step.type})")

            # Resolve {ref} params with previous outputs
            output_values = {}
            for k, v in outputs.items():
                output_values[k] = v.output
            params = step.resolve_refs(output_values)

            # Apply user overrides
            if step_name in overrides:
                params.update(overrides[step_name])

            # Inject input image
            if input_image is not None and "input_image" not in params:
                params["input_image"] = input_image

            # Get model ref
            model_ref = pipeline.models.get(step.model)
            if not model_ref:
                raise ValueError(f"Step '{step_name}' references unknown model '{step.model}'")

            # Get handler
            handler = self._step_handlers.get(step.type)
            if not handler:
                raise ValueError(f"Unknown step type: '{step.type}'. "
                                f"Available: {list(self._step_handlers.keys())}")

            # Clear VRAM before loading new model
            self.mm.unload_all()

            # Execute step
            t0 = time.time()
            result = handler(model_ref, params, self.mm, pipeline)
            duration = time.time() - t0

            # Wrap result
            if isinstance(result, Image.Image):
                output_type = "image"
            elif isinstance(result, str):
                output_type = "text"
            else:
                output_type = "other"

            step_result = StepResult(step_name, result, output_type, duration)
            outputs[step_name] = step_result

            # Unload after step
            self.mm.unload_all()

            log.info(f"  Done in {duration:.1f}s → {output_type}")

            if on_step_done:
                on_step_done(step_name, step_result)

        return outputs

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
                "model_cached": self.mm.is_cached(model_ref) if model_ref else False,
                "vram_mb": model_ref.vram_mb if model_ref else None,
                "handler_available": step.type in self._step_handlers,
            })
        return info

    def _register_builtins(self):
        """Register built-in step handlers."""
        from .steps.caption import run_caption
        from .steps.generate import run_txt2img
        from .steps.refine import run_img2img
        from .steps.upscale import run_upscale

        self._step_handlers["vision-llm"] = run_caption
        self._step_handlers["txt2img"] = run_txt2img
        self._step_handlers["img2img"] = run_img2img
        self._step_handlers["refine"] = run_img2img  # same handler, different params
        self._step_handlers["pixel-upscale"] = run_upscale


def create_engine(cache_dir: str | Path | None = None, search_paths: list[str] | None = None) -> PipelineEngine:
    """Create a ready-to-use engine."""
    mm = ModelManager(cache_dir=cache_dir, search_paths=search_paths)
    return PipelineEngine(mm)
