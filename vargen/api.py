"""FastAPI backend — pipeline engine API with settings, model browsing, cancel, queue."""

import asyncio
import logging
import os
import time
import uuid
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, UploadFile, File, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from PIL import Image
import torch
import gc
import io

from .schema import load_pipeline
from .config import Config, browse_models
from .engine import create_engine, CancelledError
from .nodes import get_all_node_types, get_node_types_by_category
from .nodes.executor import GraphExecutor, CancelledError as GraphCancelledError

# Import node modules to trigger registration
from .nodes import loaders, conditioning, sampling, latent as latent_nodes, image as image_nodes
from .nodes import controlnet as controlnet_nodes, ipadapter as ipadapter_nodes
from .nodes import inpaint as inpaint_nodes, flux as flux_nodes
from .nodes import model_utils as model_utils_nodes

log = logging.getLogger(__name__)

PIPELINES_DIR = Path(__file__).parent.parent / "pipelines"
OUTPUT_DIR = Path(__file__).parent.parent / "outputs"
UPLOAD_DIR = Path(__file__).parent.parent / "uploads"
OUTPUT_DIR.mkdir(exist_ok=True)
UPLOAD_DIR.mkdir(exist_ok=True)

# Global state
_config = Config()
_engine = create_engine(config=_config)

app = FastAPI(title="vargen", version="0.1.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])


# ── Settings ───────────────────────────────────────────────────

@app.get("/api/settings")
async def get_settings():
    return _config.to_dict()


class SettingsUpdate(BaseModel):
    model_paths: Optional[list[str]] = None
    output_dir: Optional[str] = None
    vram_mode: Optional[str] = None
    defaults: Optional[dict] = None


@app.put("/api/settings")
async def update_settings(req: SettingsUpdate):
    updates = {k: v for k, v in req.model_dump().items() if v is not None}
    _config.update(updates)
    # Reinitialize model manager with new paths
    global _engine
    _engine = create_engine(config=_config)
    return {"status": "saved", "settings": _config.to_dict()}


# ── Pipelines ──────────────────────────────────────────────────

@app.get("/api/pipelines")
async def list_pipelines():
    pipelines = []
    if PIPELINES_DIR.exists():
        for f in sorted(PIPELINES_DIR.glob("*.yaml")):
            try:
                p = load_pipeline(f)
                pipelines.append({
                    "id": f.stem, "name": p.name, "description": p.description,
                    "tags": p.tags, "steps": len(p.steps), "models": len(p.models),
                })
            except Exception as e:
                pipelines.append({"id": f.stem, "name": f.stem, "error": str(e)})
    return pipelines


@app.get("/api/pipelines/{pipeline_id}")
async def get_pipeline(pipeline_id: str):
    path = PIPELINES_DIR / f"{pipeline_id}.yaml"
    if not path.exists():
        raise HTTPException(404, f"Pipeline '{pipeline_id}' not found")
    return {"id": pipeline_id, "yaml": path.read_text()}


class SavePipelineRequest(BaseModel):
    yaml: str


@app.put("/api/pipelines/{pipeline_id}")
async def save_pipeline(pipeline_id: str, req: SavePipelineRequest):
    import yaml
    try:
        yaml.safe_load(req.yaml)
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
    return _engine.mm.status()


@app.get("/api/models/browse")
async def browse_models_endpoint():
    """Browse all models across configured paths, organized by category."""
    return _engine.mm.browse()


@app.post("/api/models/check")
async def check_models(req: SavePipelineRequest):
    import tempfile
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        f.write(req.yaml)
        tmp = f.name
    try:
        pipeline = load_pipeline(tmp)
    finally:
        os.unlink(tmp)

    results = []
    for ref in pipeline.required_models():
        results.append({
            "name": ref.name, "repo": ref.repo, "file": ref.file,
            "cached": _engine.mm.is_cached(ref), "vram_mb": ref.vram_mb, "gated": ref.gated,
        })
    return results


@app.get("/api/models/downloads")
async def download_progress():
    """Get active download progress."""
    return _engine.mm.downloads.get_all()


# ── Workflows (graph format) ───────────────────────────────────

WORKFLOWS_DIR = Path(__file__).parent.parent / "workflows"
WORKFLOWS_DIR.mkdir(exist_ok=True)


@app.get("/api/workflows")
async def list_workflows():
    import json
    workflows = []
    for f in sorted(WORKFLOWS_DIR.glob("*.json")):
        try:
            data = json.loads(f.read_text())
            workflows.append({
                "id": f.stem,
                "name": data.get("name", f.stem),
                "description": data.get("description", ""),
                "nodes": len(data.get("nodes", {})),
                "edges": len(data.get("edges", [])),
            })
        except Exception:
            workflows.append({"id": f.stem, "name": f.stem, "error": "parse error"})
    return workflows


@app.get("/api/workflows/{workflow_id}")
async def get_workflow(workflow_id: str):
    import json
    path = WORKFLOWS_DIR / f"{workflow_id}.json"
    if not path.exists():
        raise HTTPException(404)
    return json.loads(path.read_text())


@app.put("/api/workflows/{workflow_id}")
async def save_workflow(workflow_id: str, data: dict):
    import json
    path = WORKFLOWS_DIR / f"{workflow_id}.json"
    path.write_text(json.dumps(data, indent=2))
    return {"status": "saved", "id": workflow_id}


@app.delete("/api/workflows/{workflow_id}")
async def delete_workflow(workflow_id: str):
    path = WORKFLOWS_DIR / f"{workflow_id}.json"
    if not path.exists():
        raise HTTPException(404)
    path.unlink()
    return {"status": "deleted"}


# ── Node Types ─────────────────────────────────────────────────

@app.get("/api/node-types")
async def list_node_types():
    """Return all registered node types with their port and widget definitions."""
    result = {}
    for type_id, node_def in get_all_node_types().items():
        result[type_id] = {
            "type_id": node_def.type_id,
            "category": node_def.category,
            "label": node_def.label,
            "description": node_def.description,
            "color": node_def.color,
            "inputs": [{"name": p.name, "type": p.type, "optional": p.optional} for p in node_def.inputs],
            "outputs": [{"name": p.name, "type": p.type} for p in node_def.outputs],
            "widgets": [{
                "name": w.name, "type": w.type, "default": w.default,
                "options": w.options, "min": w.min, "max": w.max, "step": w.step,
                "label": w.label or w.name,
            } for w in node_def.widgets],
        }
    return result


@app.get("/api/node-types/categories")
async def node_types_by_category():
    categories = {}
    for cat, nodes in get_node_types_by_category().items():
        categories[cat] = [{"type_id": n.type_id, "label": n.label, "color": n.color, "description": n.description} for n in nodes]
    return categories


# ── Graph Execution ────────────────────────────────────────────

_graph_executor: GraphExecutor | None = None

def get_graph_executor():
    global _graph_executor
    if _graph_executor is None:
        _graph_executor = GraphExecutor(_engine.mm)
    return _graph_executor


class GraphRunRequest(BaseModel):
    graph: dict
    image_filename: Optional[str] = None


@app.websocket("/api/ws/graph")
async def run_graph_ws(ws: WebSocket):
    """Execute a node graph with live progress."""
    await ws.accept()
    try:
        data = await ws.receive_json()
    except WebSocketDisconnect:
        return

    executor = get_graph_executor()
    input_image = _load_input_image(data.get("image_filename"))
    loop = asyncio.get_event_loop()

    async def send(msg):
        try: await ws.send_json(msg)
        except: pass

    def on_start(nid, node, idx, total):
        asyncio.run_coroutine_threadsafe(
            send({"event": "node_start", "node_id": nid, "type": node["type"], "index": idx, "total": total}), loop)

    def on_done(nid, node, result, duration, error):
        msg = {"event": "node_done", "node_id": nid, "type": node["type"], "duration": duration}
        if error:
            msg["error"] = error
        elif result:
            # Check for saved images
            if "_saved_url" in result:
                msg["image_url"] = result["_saved_url"]
            elif result.get("IMAGE") is not None and hasattr(result["IMAGE"], "save"):
                # Auto-save preview
                ts = int(time.time())
                path = OUTPUT_DIR / f"preview_{nid}_{ts}.png"
                result["IMAGE"].save(path)
                msg["image_url"] = f"/api/outputs/{path.name}"
        asyncio.run_coroutine_threadsafe(send(msg), loop)

    try:
        await loop.run_in_executor(None, lambda: executor.execute(
            data["graph"], input_image=input_image,
            on_node_start=on_start, on_node_done=on_done,
        ))
        await ws.send_json({"event": "complete"})
    except GraphCancelledError:
        await ws.send_json({"event": "cancelled"})
    except Exception as e:
        log.error(f"Graph execution error: {e}")
        try:
            await ws.send_json({"event": "error", "message": str(e)})
        except Exception:
            pass  # WebSocket might already be closed
    finally:
        # Always cleanup VRAM after execution
        import gc
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        try:
            await ws.close()
        except Exception:
            pass


# ── Upload ─────────────────────────────────────────────────────

@app.post("/api/upload")
async def upload_image(file: UploadFile = File(...)):
    contents = await file.read()
    ext = Path(file.filename).suffix or ".png"
    filename = f"{uuid.uuid4().hex[:12]}{ext}"
    filepath = UPLOAD_DIR / filename
    try:
        img = Image.open(io.BytesIO(contents))
        img.verify()
    except Exception:
        raise HTTPException(400, "Invalid image file")
    with open(filepath, "wb") as f:
        f.write(contents)
    return {"filename": filename, "url": f"/api/uploads/{filename}"}


@app.get("/api/uploads/{filename}")
async def serve_upload(filename: str):
    path = UPLOAD_DIR / filename
    if not path.exists():
        raise HTTPException(404)
    return FileResponse(path)


# ── Outputs ────────────────────────────────────────────────────

@app.get("/api/outputs")
async def list_outputs(limit: int = 50):
    outputs = []
    if OUTPUT_DIR.exists():
        for f in sorted(OUTPUT_DIR.glob("*.png"), reverse=True)[:limit]:
            outputs.append({
                "filename": f.name, "url": f"/api/outputs/{f.name}",
                "size": f.stat().st_size, "created": f.stat().st_mtime,
            })
    return outputs


@app.get("/api/outputs/{filename}")
async def serve_output(filename: str):
    path = OUTPUT_DIR / filename
    if not path.exists():
        raise HTTPException(404)
    return FileResponse(path)


@app.delete("/api/outputs/{filename}")
async def delete_output(filename: str):
    path = OUTPUT_DIR / filename
    if not path.exists():
        raise HTTPException(404)
    path.unlink()
    return {"status": "deleted"}


# ── Cancel ─────────────────────────────────────────────────────

@app.post("/api/cancel")
async def cancel_run():
    _engine.cancel()
    return {"status": "cancelling"}


# ── Run Pipeline ───────────────────────────────────────────────

class RunRequest(BaseModel):
    pipeline_id: Optional[str] = None
    pipeline_yaml: Optional[str] = None
    image_filename: Optional[str] = None
    overrides: Optional[dict] = None


@app.post("/api/run")
async def run_pipeline_sync(req: RunRequest):
    pipeline = _load_pipeline_from_req(req)
    input_image = _load_input_image(req.image_filename)

    try:
        results = _engine.run(pipeline, input_image=input_image, overrides=req.overrides)
    except CancelledError:
        return {"status": "cancelled"}

    return _format_results(results, pipeline)


# ── WebSocket for live progress ────────────────────────────────

@app.websocket("/api/ws/run")
async def run_pipeline_ws(ws: WebSocket):
    await ws.accept()
    try:
        data = await ws.receive_json()
    except WebSocketDisconnect:
        return

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

    input_image = _load_input_image(data.get("image_filename"))
    loop = asyncio.get_event_loop()

    async def send(msg):
        try:
            await ws.send_json(msg)
        except Exception:
            pass

    def on_step_start(name, idx, total):
        asyncio.run_coroutine_threadsafe(
            send({"event": "step_start", "step": name, "index": idx, "total": total}), loop)

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
            msg["text"] = str(result.output)[:1000]
        asyncio.run_coroutine_threadsafe(send(msg), loop)

    def on_batch(name, idx, total):
        asyncio.run_coroutine_threadsafe(
            send({"event": "batch_progress", "step": name, "index": idx, "total": total}), loop)

    try:
        await loop.run_in_executor(None, lambda: _engine.run(
            pipeline, input_image=input_image, overrides=data.get("overrides"),
            on_step_start=on_step_start, on_step_done=on_step_done, on_batch_progress=on_batch,
        ))
        await ws.send_json({"event": "complete"})
    except CancelledError:
        await ws.send_json({"event": "cancelled"})
    except Exception as e:
        await ws.send_json({"event": "error", "message": str(e)})
    await ws.close()


# ── Step types ─────────────────────────────────────────────────

@app.get("/api/step-types")
async def list_step_types():
    return _engine.list_step_types()


# ── Helpers ────────────────────────────────────────────────────

def _load_pipeline_from_req(req: RunRequest):
    if req.pipeline_yaml:
        import tempfile
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(req.pipeline_yaml)
            tmp = f.name
        try:
            return load_pipeline(tmp)
        finally:
            os.unlink(tmp)
    elif req.pipeline_id:
        path = PIPELINES_DIR / f"{req.pipeline_id}.yaml"
        if not path.exists():
            raise HTTPException(404, f"Pipeline '{req.pipeline_id}' not found")
        return load_pipeline(path)
    raise HTTPException(400, "Provide pipeline_id or pipeline_yaml")


def _load_input_image(filename: Optional[str]) -> Optional[Image.Image]:
    if not filename:
        return None
    img_path = UPLOAD_DIR / filename
    if img_path.exists():
        return Image.open(img_path).convert("RGB")
    return None


def _format_results(results, pipeline):
    response = {"steps": {}}
    for name, result in results.items():
        step_data = {"type": result.output_type, "duration": result.duration}
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


# ── Serve frontend ─────────────────────────────────────────────

FRONTEND_DIRS = [
    Path(__file__).parent.parent / "frontend" / ".output" / "public",
    Path(__file__).parent.parent / "frontend" / "dist",
]


@app.on_event("startup")
def mount_frontend():
    for d in FRONTEND_DIRS:
        if d.exists():
            app.mount("/", StaticFiles(directory=str(d), html=True), name="frontend")
            log.info(f"Serving frontend from {d}")
            break
    else:
        log.warning("No built frontend found. Run: cd frontend && npx nuxt generate")
