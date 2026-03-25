"""Graph executor — sequential execution with per-node VRAM management.

Key design: only ONE model component is in VRAM at a time.
After each node finishes, its models are moved to CPU.
This is how ComfyUI handles 8GB GPUs.
"""

import gc
import logging
import time
import threading
import traceback
from typing import Callable, Optional

import torch
from PIL import Image

from . import get_node_type

log = logging.getLogger(__name__)

_execution_lock = threading.Lock()


class CancelledError(Exception):
    pass


def vram_free_mb() -> int:
    if torch.cuda.is_available():
        return torch.cuda.mem_get_info()[0] // (1024 * 1024)
    return 0


def flush_vram():
    """Aggressively free VRAM — call between nodes."""
    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
        try:
            torch.cuda.synchronize()
        except Exception:
            pass


def offload_to_cpu(obj):
    """Move a model/pipeline/tensor to CPU to free VRAM."""
    if obj is None:
        return
    if isinstance(obj, torch.Tensor):
        return obj.cpu()
    if hasattr(obj, 'to'):
        try:
            obj.to('cpu')
        except Exception:
            pass
    # For dicts (like our CLIP bundle), recurse
    if isinstance(obj, dict):
        for v in obj.values():
            offload_to_cpu(v)


class GraphExecutor:
    """Execute a node graph. Only one model in VRAM at a time."""

    def __init__(self, model_manager):
        self.mm = model_manager
        self._cancelled = False

    def cancel(self):
        self._cancelled = True

    def execute(self, graph, input_image=None, on_node_start=None, on_node_done=None):
        if not _execution_lock.acquire(blocking=False):
            raise RuntimeError("Another generation is running. Cancel it first.")

        try:
            return self._execute(graph, input_image, on_node_start, on_node_done)
        finally:
            flush_vram()
            _execution_lock.release()

    def _execute(self, graph, input_image, on_node_start, on_node_done):
        self._cancelled = False
        nodes = graph.get("nodes", {})
        edges = graph.get("edges", [])

        if not nodes:
            raise ValueError("Graph has no nodes")

        # Validate
        for nid, ndef in nodes.items():
            if not get_node_type(ndef.get("type", "")):
                raise ValueError(f"Unknown node type '{ndef.get('type')}' on node '{nid}'")

        # Build dependency graph
        deps = {nid: set() for nid in nodes}
        for edge in edges:
            if edge["from_node"] not in nodes:
                raise ValueError(f"Edge references unknown node: {edge['from_node']}")
            if edge["to_node"] not in nodes:
                raise ValueError(f"Edge references unknown node: {edge['to_node']}")
            deps[edge["to_node"]].add(edge["from_node"])

        # Topological sort
        order = []
        in_degree = {nid: len(d) for nid, d in deps.items()}
        queue = [nid for nid, deg in in_degree.items() if deg == 0]
        while queue:
            nid = queue.pop(0)
            order.append(nid)
            for other, other_deps in deps.items():
                if nid in other_deps:
                    in_degree[other] -= 1
                    if in_degree[other] == 0:
                        queue.append(other)

        if len(order) != len(nodes):
            raise ValueError("Graph has cycles")

        # Execute
        outputs = {}
        ctx = {"model_manager": self.mm, "input_image": input_image}

        for idx, nid in enumerate(order):
            if self._cancelled:
                raise CancelledError("Cancelled")

            node_type = get_node_type(nodes[nid]["type"])
            if on_node_start:
                on_node_start(nid, nodes[nid], idx, len(order))

            # ── BEFORE NODE: flush VRAM from previous node ──
            # Move all previous node outputs' model objects to CPU
            # Keep only lightweight data (tensors, images, text)
            self._offload_previous_outputs(outputs, nid, edges)
            flush_vram()
            log.info(f"  VRAM before {nodes[nid]['type']}: {vram_free_mb()}MB free")

            # Collect inputs from edges
            node_inputs = self._collect_inputs(nid, edges, outputs, nodes)
            widget_values = nodes[nid].get("widgets", {})

            # Execute with error handling
            t0 = time.time()
            error_msg = None
            result = None

            try:
                result = node_type.execute(node_inputs, widget_values, ctx)
            except torch.cuda.OutOfMemoryError:
                flush_vram()
                error_msg = (f"Out of VRAM on '{nodes[nid]['type']}' ({vram_free_mb()}MB free). "
                           f"Reduce resolution, use smaller model, or set offload to sequential_cpu.")
                log.error(error_msg)
            except CancelledError:
                raise
            except Exception as e:
                error_msg = f"{nodes[nid]['type']}: {str(e)}"
                log.error(f"Node {nid} failed: {error_msg}")
                log.debug(traceback.format_exc())

            duration = time.time() - t0

            if error_msg:
                flush_vram()
                if on_node_done:
                    on_node_done(nid, nodes[nid], None, duration, error_msg)
                raise RuntimeError(error_msg)

            # ── AFTER NODE: offload this node's models to CPU ──
            if result:
                self._offload_models_in_result(result)

            outputs[nid] = result or {}
            log.info(f"  [{idx+1}/{len(order)}] {nid} ({nodes[nid]['type']}): {duration:.1f}s | VRAM: {vram_free_mb()}MB free")

            if on_node_done:
                on_node_done(nid, nodes[nid], result, duration, None)

        return outputs

    def _collect_inputs(self, nid, edges, outputs, nodes):
        """Gather inputs for a node from connected edges."""
        node_inputs = {}
        for edge in edges:
            if edge["to_node"] == nid:
                src = outputs.get(edge["from_node"], {})
                node_inputs[edge["to_port"]] = src.get(edge["from_port"])
                # Pass through internal state
                for key in ("_pipe", "_width", "_height", "_cn_image", "_cn_strength",
                            "_cn_start", "_cn_end", "_ip_adapter_image", "_ip_adapter_loaded", "_arch"):
                    if key in src:
                        node_inputs[key] = src[key]
        return node_inputs

    def _offload_previous_outputs(self, outputs, current_nid, edges):
        """Move model objects from previous nodes to CPU.

        We keep: lightweight data (PIL Images, strings, small tensors, latents)
        We offload: model objects (_pipe, MODEL, CLIP, VAE, UPSCALE_MODEL, CONTROLNET)
        """
        model_keys = {"MODEL", "CLIP", "VAE", "UPSCALE_MODEL", "CONTROLNET", "_pipe"}

        # Find which nodes' outputs are still needed by future nodes
        # (nodes that haven't executed yet)
        needed_by_future = set()
        for edge in edges:
            if edge["to_node"] != current_nid and edge["to_node"] not in outputs:
                needed_by_future.add(edge["from_node"])

        for out_nid, out_data in outputs.items():
            if out_nid in needed_by_future:
                continue  # Still needed, don't offload
            for key in list(out_data.keys()):
                if key in model_keys:
                    offload_to_cpu(out_data[key])

    def _offload_models_in_result(self, result):
        """After a node runs, move its model outputs to CPU immediately.

        We keep the reference (so downstream nodes can .to('cuda') when needed)
        but free the VRAM now.
        """
        model_keys = {"MODEL", "UPSCALE_MODEL", "CONTROLNET"}
        for key in model_keys:
            if key in result:
                offload_to_cpu(result[key])

        # For _pipe: move all components to CPU
        pipe = result.get("_pipe")
        if pipe and hasattr(pipe, 'components'):
            for name, component in pipe.components.items():
                if hasattr(component, 'to'):
                    try:
                        component.to('cpu')
                    except Exception:
                        pass
        elif pipe and hasattr(pipe, 'to'):
            try:
                pipe.to('cpu')
            except Exception:
                pass

        flush_vram()
