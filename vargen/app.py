"""Vargen web UI — pipeline editor + runner + gallery."""

import logging
import os
import sys
import time
from pathlib import Path
from typing import Optional

import gradio as gr
import yaml
from PIL import Image

from .schema import load_pipeline, dump_pipeline, Pipeline
from .engine import create_engine, PipelineEngine
from .models import ModelManager

log = logging.getLogger(__name__)

PIPELINES_DIR = Path(__file__).parent.parent / "pipelines"
OUTPUT_DIR = Path(__file__).parent.parent / "outputs"
OUTPUT_DIR.mkdir(exist_ok=True)


class VargenApp:
    """Main application state."""

    def __init__(self, cache_dir: Optional[str] = None, search_paths: list[str] | None = None):
        self.engine = create_engine(cache_dir=cache_dir, search_paths=search_paths)
        self.current_pipeline: Optional[Pipeline] = None
        self.last_results: dict = {}

    def list_pipelines(self) -> list[str]:
        """List available pipeline YAML files."""
        if not PIPELINES_DIR.exists():
            return []
        return [f.stem for f in sorted(PIPELINES_DIR.glob("*.yaml"))]

    def load_pipeline_yaml(self, name: str) -> str:
        """Load pipeline YAML as text."""
        path = PIPELINES_DIR / f"{name}.yaml"
        if not path.exists():
            return f"# Pipeline '{name}' not found"
        return path.read_text()

    def save_pipeline_yaml(self, name: str, content: str) -> str:
        """Save pipeline YAML from editor."""
        path = PIPELINES_DIR / f"{name}.yaml"
        try:
            # Validate it parses
            yaml.safe_load(content)
            path.write_text(content)
            return f"Saved: {path.name}"
        except Exception as e:
            return f"Error: {e}"

    def check_models(self, yaml_text: str) -> str:
        """Check which models are cached and which need downloading."""
        if not yaml_text:
            return "No pipeline loaded. Select one from the dropdown."
        try:
            import tempfile
            with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
                f.write(yaml_text)
                tmp = f.name

            pipeline = load_pipeline(tmp)
            os.unlink(tmp)

            lines = ["Model Status:", ""]
            for ref in pipeline.required_models():
                cached = self.engine.mm.is_cached(ref)
                icon = "[cached]" if cached else "[needs download]"
                size = f" ({ref.vram_mb}MB VRAM)" if ref.vram_mb else ""
                lines.append(f"  {icon} {ref.name}: {ref.repo}" +
                           (f"/{ref.file}" if ref.file else "") + size)

            lines.append("")
            lines.append(f"Total VRAM available: {self.engine.mm.total_vram_mb}MB")
            lines.append(f"Free VRAM: {self.engine.mm.available_vram_mb}MB")

            return "\n".join(lines)
        except Exception as e:
            return f"Error checking models: {e}"

    def run_pipeline(
        self,
        yaml_text: str,
        input_image: Optional[Image.Image],
        progress=gr.Progress(),
    ):
        """Run a pipeline and yield results progressively."""
        import tempfile

        if not yaml_text:
            yield None, [], "Error: Select a pipeline first"
            return
        if input_image is None:
            yield None, [], "Error: Upload an input image first"
            return

        import tempfile
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(yaml_text)
            tmp = f.name

        try:
            pipeline = load_pipeline(tmp)
        except Exception as e:
            yield None, [], f"Pipeline parse error: {e}"
            return
        finally:
            os.unlink(tmp)

        status_lines = []
        gallery_images = []

        def on_start(name, idx, total):
            msg = f"[{idx+1}/{total}] Running: {name}..."
            status_lines.append(msg)
            progress((idx) / total, desc=msg)

        def on_done(name, result):
            msg = f"  {name} done ({result.duration:.1f}s)"
            status_lines.append(msg)
            if result.output_type == "image":
                # Save to outputs
                ts = int(time.time())
                out_path = OUTPUT_DIR / f"{name}_{ts}.png"
                result.output.save(out_path)
                gallery_images.append(result.output)
            elif result.output_type == "text":
                status_lines.append(f"  Caption: {str(result.output)[:200]}...")

        try:
            results = self.engine.run(
                pipeline,
                input_image=input_image,
                on_step_start=on_start,
                on_step_done=on_done,
            )

            self.last_results = results
            status_lines.append("\nPipeline complete!")

            # Get final image
            final_image = None
            for step in reversed(pipeline.steps):
                if step.name in results and results[step.name].output_type == "image":
                    final_image = results[step.name].output
                    break

            yield final_image, gallery_images, "\n".join(status_lines)

        except Exception as e:
            log.exception("Pipeline failed")
            status_lines.append(f"\nError: {e}")
            yield None, gallery_images, "\n".join(status_lines)


def build_ui(app: VargenApp) -> gr.Blocks:
    """Build the Gradio interface."""

    css = """
    .pipeline-editor textarea { font-family: monospace !important; font-size: 13px !important; }
    .step-card { border: 1px solid #333; border-radius: 8px; padding: 12px; margin: 4px 0; }
    .status-box textarea { font-family: monospace !important; font-size: 12px !important; }
    """

    with gr.Blocks(
        title="vargen",
        theme=gr.themes.Base(
            primary_hue="orange",
            neutral_hue="gray",
            font=gr.themes.GoogleFont("Inter"),
        ),
        css=css,
    ) as ui:
        gr.Markdown("# vargen\n*AI-native image generation pipelines*")

        with gr.Tabs():
            # ── TAB 1: RUN ──────────────────────────────────────
            with gr.Tab("Run"):
                with gr.Row():
                    with gr.Column(scale=1):
                        input_image = gr.Image(
                            label="Reference Image",
                            type="pil",
                            height=400,
                        )
                        pipeline_dropdown = gr.Dropdown(
                            choices=app.list_pipelines(),
                            label="Pipeline",
                            value=app.list_pipelines()[0] if app.list_pipelines() else None,
                        )
                        run_btn = gr.Button("Generate", variant="primary", size="lg")

                    with gr.Column(scale=2):
                        output_image = gr.Image(label="Result", height=400)
                        gallery = gr.Gallery(
                            label="All Steps",
                            columns=4,
                            height=200,
                        )
                        status = gr.Textbox(
                            label="Status",
                            lines=8,
                            interactive=False,
                            elem_classes=["status-box"],
                        )

                # Load pipeline YAML when dropdown changes — preload first pipeline
                initial_pipeline = app.list_pipelines()[0] if app.list_pipelines() else ""
                initial_yaml = app.load_pipeline_yaml(initial_pipeline) if initial_pipeline else ""
                pipeline_yaml_hidden = gr.State(initial_yaml)

                def on_pipeline_select(name):
                    if name:
                        return app.load_pipeline_yaml(name)
                    return ""

                pipeline_dropdown.change(
                    on_pipeline_select,
                    inputs=[pipeline_dropdown],
                    outputs=[pipeline_yaml_hidden],
                )

                def on_run(yaml_text, image):
                    if not yaml_text:
                        yield None, [], "Select a pipeline first"
                        return
                    yield from app.run_pipeline(yaml_text, image)

                run_btn.click(
                    on_run,
                    inputs=[pipeline_yaml_hidden, input_image],
                    outputs=[output_image, gallery, status],
                )

            # ── TAB 2: PIPELINE EDITOR ──────────────────────────
            with gr.Tab("Pipeline Editor"):
                with gr.Row():
                    with gr.Column(scale=1):
                        editor_pipeline = gr.Dropdown(
                            choices=app.list_pipelines(),
                            label="Load Pipeline",
                        )
                        new_name = gr.Textbox(label="Save As", placeholder="my_pipeline")
                        save_btn = gr.Button("Save Pipeline")
                        check_btn = gr.Button("Check Models")
                        model_status = gr.Textbox(
                            label="Model Status",
                            lines=10,
                            interactive=False,
                            elem_classes=["status-box"],
                        )

                    with gr.Column(scale=3):
                        editor = gr.Code(
                            label="Pipeline YAML",
                            language="yaml",
                            lines=35,
                            elem_classes=["pipeline-editor"],
                        )
                        save_status = gr.Textbox(label="", interactive=False, visible=True)

                def on_load_editor(name):
                    if name:
                        return app.load_pipeline_yaml(name), name
                    return "", ""

                editor_pipeline.change(
                    on_load_editor,
                    inputs=[editor_pipeline],
                    outputs=[editor, new_name],
                )

                save_btn.click(
                    lambda name, content: app.save_pipeline_yaml(name, content),
                    inputs=[new_name, editor],
                    outputs=[save_status],
                )

                check_btn.click(
                    app.check_models,
                    inputs=[editor],
                    outputs=[model_status],
                )

            # ── TAB 3: MODELS ───────────────────────────────────
            with gr.Tab("Models"):
                gr.Markdown("### Model Cache")
                refresh_btn = gr.Button("Refresh")
                model_info = gr.JSON(label="Status")

                refresh_btn.click(
                    lambda: app.engine.mm.status(),
                    outputs=[model_info],
                )

            # ── TAB 4: GALLERY ──────────────────────────────────
            with gr.Tab("Gallery"):
                gr.Markdown("### Generated Images")
                gallery_refresh = gr.Button("Refresh")
                output_gallery = gr.Gallery(
                    label="Outputs",
                    columns=4,
                    height=600,
                )

                def load_gallery():
                    images = []
                    if OUTPUT_DIR.exists():
                        for f in sorted(OUTPUT_DIR.glob("*.png"), reverse=True)[:50]:
                            images.append(str(f))
                    return images

                gallery_refresh.click(load_gallery, outputs=[output_gallery])

    return ui


def main():
    """Launch vargen."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(message)s",
        datefmt="%H:%M:%S",
    )

    import argparse
    parser = argparse.ArgumentParser(description="vargen - AI image pipeline engine")
    parser.add_argument("--port", type=int, default=8188)
    parser.add_argument("--host", type=str, default="0.0.0.0")
    parser.add_argument("--cache-dir", type=str, default=None)
    parser.add_argument("--models-dir", type=str, action="append", default=None,
                       help="Extra model search paths (e.g. ~/ComfyUI/models)")
    parser.add_argument("--share", action="store_true", help="Create public Gradio link")
    args = parser.parse_args()

    # Auto-detect ComfyUI models dir
    search_paths = args.models_dir or []
    comfy_models = Path.home() / "ComfyUI" / "models"
    if comfy_models.exists() and str(comfy_models) not in search_paths:
        search_paths.append(str(comfy_models))
        log.info(f"Found ComfyUI models at {comfy_models}")

    app = VargenApp(cache_dir=args.cache_dir, search_paths=search_paths)
    ui = build_ui(app)
    ui.launch(
        server_name=args.host,
        server_port=args.port,
        share=args.share,
    )


if __name__ == "__main__":
    main()
