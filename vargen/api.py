"""FastAPI backend — serves the pipeline engine as an API."""

import asyncio
import logging
import os
import time
import uuid
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, UploadFile, File, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from PIL import Image
import io
import json

from .schema import load_pipeline, dump_pipeline
from .engine import create_engine

log = logging.getLogger(__name__)

PIPELINES_DIR = Path(__file__).parent.parent / "pipelines"
OUTPUT_DIR = Path(__file__).parent.parent / "outputs"
UPLOAD_DIR = Path(__file__).parent.parent / "uploads"
OUTPUT_DIR.mkdir(exist_ok=True)
UPLOAD_DIR.mkdir(exist_ok=True)

# Global engine instance
_engine = None


def get_engine():
    global _engine
    if _engine is None:
        search_paths = []
        comfy = Path.home() / "ComfyUI" / "models"
        if comfy.exists():
            search_paths.append(str(comfy))
        _engine = create_engine(search_paths=search_paths)
    return _engine


app = FastAPI(title="vargen", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Pipelines ──────────────────────────────────────────────────

@app.get("/api/pipelines")
async def list_pipelines():
    """List available pipeline definitions."""
    pipelines = []
    if PIPELINES_DIR.exists():
        for f in sorted(PIPELINES_DIR.glob("*.yaml")):
            try:
                p = load_pipeline(f)
                pipelines.append({
                    "id": f.stem,
                    "name": p.name,
                    "description": p.description,
                    "tags": p.tags,
                    "steps": len(p.steps),
                    "models": len(p.models),
                })
            except Exception as e:
                pipelines.append({"id": f.stem, "name": f.stem, "error": str(e)})
    return pipelines


@app.get("/api/pipelines/{pipeline_id}")
async def get_pipeline(pipeline_id: str):
    """Get a pipeline's YAML content."""
    path = PIPELINES_DIR / f"{pipeline_id}.yaml"
    if not path.exists():
        raise HTTPException(404, f"Pipeline '{pipeline_id}' not found")
    return {"id": pipeline_id, "yaml": path.read_text()}


class SavePipelineRequest(BaseModel):
    yaml: str


@app.put("/api/pipelines/{pipeline_id}")
async def save_pipeline(pipeline_id: str, req: SavePipelineRequest):
    """Save/update a pipeline YAML."""
    import yaml as pyyaml
    try:
        pyyaml.safe_load(req.yaml)  # validate
    except Exception as e:
        raise HTTPException(400, f"Invalid YAML: {e}")

    path = PIPELINES_DIR / f"{pipeline_id}.yaml"
    path.write_text(req.yaml)
    return {"status": "saved", "id": pipeline_id}


@app.delete("/api/pipelines/{pipeline_id}")
async def delete_pipeline(pipeline_id: str):
    path = PIPELINES_DIR / f"{pipeline_id}.yaml"
    if not path.exists():
        raise HTTPException(404)
    path.unlink()
    return {"status": "deleted"}


# ── Models ─────────────────────────────────────────────────────

@app.get("/api/models/status")
async def model_status():
    """Get model manager status and VRAM info."""
    engine = get_engine()
    return engine.mm.status()


@app.post("/api/models/check")
async def check_models(req: SavePipelineRequest):
    """Check which models a pipeline needs and which are cached."""
    import tempfile
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        f.write(req.yaml)
        tmp = f.name
    try:
        pipeline = load_pipeline(tmp)
    finally:
        os.unlink(tmp)

    engine = get_engine()
    results = []
    for ref in pipeline.required_models():
        results.append({
            "name": ref.name,
            "repo": ref.repo,
            "file": ref.file,
            "cached": engine.mm.is_cached(ref),
            "vram_mb": ref.vram_mb,
            "gated": ref.gated,
        })
    return results


# ── Upload ─────────────────────────────────────────────────────

@app.post("/api/upload")
async def upload_image(file: UploadFile = File(...)):
    """Upload a reference image."""
    contents = await file.read()
    ext = Path(file.filename).suffix or ".png"
    filename = f"{uuid.uuid4().hex[:12]}{ext}"
    filepath = UPLOAD_DIR / filename

    # Validate it's an image
    try:
        img = Image.open(io.BytesIO(contents))
        img.verify()
    except Exception:
        raise HTTPException(400, "Invalid image file")

    with open(filepath, "wb") as f:
        f.write(contents)

    return {"filename": filename, "path": str(filepath), "url": f"/api/uploads/{filename}"}


@app.get("/api/uploads/{filename}")
async def serve_upload(filename: str):
    path = UPLOAD_DIR / filename
    if not path.exists():
        raise HTTPException(404)
    return FileResponse(path)


# ── Outputs ────────────────────────────────────────────────────

@app.get("/api/outputs")
async def list_outputs(limit: int = 50):
    """List generated output images."""
    outputs = []
    if OUTPUT_DIR.exists():
        for f in sorted(OUTPUT_DIR.glob("*.png"), reverse=True)[:limit]:
            outputs.append({
                "filename": f.name,
                "url": f"/api/outputs/{f.name}",
                "size": f.stat().st_size,
                "created": f.stat().st_mtime,
            })
    return outputs


@app.get("/api/outputs/{filename}")
async def serve_output(filename: str):
    path = OUTPUT_DIR / filename
    if not path.exists():
        raise HTTPException(404)
    return FileResponse(path)


# ── Run Pipeline ───────────────────────────────────────────────

class RunRequest(BaseModel):
    pipeline_id: Optional[str] = None
    pipeline_yaml: Optional[str] = None
    image_filename: Optional[str] = None
    overrides: Optional[dict] = None


@app.post("/api/run")
async def run_pipeline_sync(req: RunRequest):
    """Run a pipeline synchronously. For short pipelines."""
    engine = get_engine()

    # Load pipeline
    if req.pipeline_yaml:
        import tempfile
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(req.pipeline_yaml)
            tmp = f.name
        try:
            pipeline = load_pipeline(tmp)
        finally:
            os.unlink(tmp)
    elif req.pipeline_id:
        path = PIPELINES_DIR / f"{req.pipeline_id}.yaml"
        if not path.exists():
            raise HTTPException(404, f"Pipeline '{req.pipeline_id}' not found")
        pipeline = load_pipeline(path)
    else:
        raise HTTPException(400, "Provide pipeline_id or pipeline_yaml")

    # Load input image
    input_image = None
    if req.image_filename:
        img_path = UPLOAD_DIR / req.image_filename
        if img_path.exists():
            input_image = Image.open(img_path).convert("RGB")

    # Run
    results = engine.run(pipeline, input_image=input_image, overrides=req.overrides)

    # Save outputs and build response
    response = {"steps": {}}
    for name, result in results.items():
        step_data = {
            "type": result.output_type,
            "duration": result.duration,
        }
        if result.output_type == "image":
            ts = int(time.time())
            out_path = OUTPUT_DIR / f"{name}_{ts}.png"
            result.output.save(out_path)
            step_data["url"] = f"/api/outputs/{out_path.name}"
        elif result.output_type == "images":
            step_data["urls"] = []
            for idx, img in enumerate(result.output):
                ts = int(time.time())
                out_path = OUTPUT_DIR / f"{name}_{ts}_{idx:03d}.png"
                img.save(out_path)
                step_data["urls"].append(f"/api/outputs/{out_path.name}")
        elif result.output_type == "text":
            step_data["text"] = str(result.output)
        response["steps"][name] = step_data

    return response


# ── WebSocket for live progress ────────────────────────────────

@app.websocket("/api/ws/run")
async def run_pipeline_ws(ws: WebSocket):
    """Run a pipeline with live progress via WebSocket.

    Client sends: {"pipeline_id": "...", "image_filename": "...", "overrides": {...}}
    Server sends: {"event": "step_start"|"step_done"|"batch_progress"|"complete"|"error", ...}
    """
    await ws.accept()

    try:
        data = await ws.receive_json()
    except WebSocketDisconnect:
        return

    engine = get_engine()

    # Load pipeline
    try:
        if "pipeline_yaml" in data:
            import tempfile
            with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
                f.write(data["pipeline_yaml"])
                tmp = f.name
            pipeline = load_pipeline(tmp)
            os.unlink(tmp)
        else:
            path = PIPELINES_DIR / f"{data['pipeline_id']}.yaml"
            pipeline = load_pipeline(path)
    except Exception as e:
        await ws.send_json({"event": "error", "message": str(e)})
        await ws.close()
        return

    # Load input image
    input_image = None
    if data.get("image_filename"):
        img_path = UPLOAD_DIR / data["image_filename"]
        if img_path.exists():
            input_image = Image.open(img_path).convert("RGB")

    loop = asyncio.get_event_loop()

    async def send(msg):
        try:
            await ws.send_json(msg)
        except Exception:
            pass

    def on_step_start(name, idx, total):
        asyncio.run_coroutine_threadsafe(
            send({"event": "step_start", "step": name, "index": idx, "total": total}),
            loop,
        )

    def on_step_done(name, result):
        msg = {"event": "step_done", "step": name, "type": result.output_type, "duration": result.duration}
        if result.output_type == "image":
            ts = int(time.time())
            out_path = OUTPUT_DIR / f"{name}_{ts}.png"
            result.output.save(out_path)
            msg["url"] = f"/api/outputs/{out_path.name}"
        elif result.output_type == "images":
            msg["urls"] = []
            for idx, img in enumerate(result.output):
                ts = int(time.time())
                out_path = OUTPUT_DIR / f"{name}_{ts}_{idx:03d}.png"
                img.save(out_path)
                msg["urls"].append(f"/api/outputs/{out_path.name}")
        elif result.output_type == "text":
            msg["text"] = str(result.output)[:500]
        asyncio.run_coroutine_threadsafe(send(msg), loop)

    def on_batch(name, idx, total):
        asyncio.run_coroutine_threadsafe(
            send({"event": "batch_progress", "step": name, "index": idx, "total": total}),
            loop,
        )

    # Run in thread to not block the event loop
    try:
        results = await loop.run_in_executor(
            None,
            lambda: engine.run(
                pipeline,
                input_image=input_image,
                overrides=data.get("overrides"),
                on_step_start=on_step_start,
                on_step_done=on_step_done,
                on_batch_progress=on_batch,
            ),
        )
        await ws.send_json({"event": "complete"})
    except Exception as e:
        await ws.send_json({"event": "error", "message": str(e)})

    await ws.close()


# ── Step types info ────────────────────────────────────────────

@app.get("/api/step-types")
async def list_step_types():
    """List available step types for pipeline authoring."""
    engine = get_engine()
    return engine.list_step_types()


# ── Serve frontend in production ───────────────────────────────

FRONTEND_DIR = Path(__file__).parent.parent / "frontend" / ".output" / "public"


def create_app():
    """Create the app with optional frontend static serving."""
    if FRONTEND_DIR.exists():
        app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")
    return app
