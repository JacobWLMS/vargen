"""Graph executor — topologically sorts and executes node graphs with OOM protection."""

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

# Execution lock — only one graph can run at a time (single GPU)
_execution_lock = threading.Lock()


class CancelledError(Exception):
    pass


class GraphExecutor:
    """Execute a node graph with typed port connections, VRAM protection, and concurrency safety."""

    def __init__(self, model_manager):
        self.mm = model_manager
        self._cancelled = False

    def cancel(self):
        self._cancelled = True

    def execute(
        self,
        graph: dict,
        input_image: Optional[Image.Image] = None,
        on_node_start: Optional[Callable] = None,
        on_node_done: Optional[Callable] = None,
    ) -> dict:
        if not _execution_lock.acquire(blocking=False):
            raise RuntimeError("Another generation is already running. Wait for it to finish or cancel it.")

        try:
            return self._execute_locked(graph, input_image, on_node_start, on_node_done)
        finally:
            self._cleanup()
            _execution_lock.release()

    def _execute_locked(self, graph, input_image, on_node_start, on_node_done):
        self._cancelled = False
        nodes = graph.get("nodes", {})
        edges = graph.get("edges", [])

        if not nodes:
            raise ValueError("Graph has no nodes")

        # Validate node types exist
        for nid, ndef in nodes.items():
            if not get_node_type(ndef.get("type", "")):
                raise ValueError(f"Unknown node type '{ndef.get('type')}' on node '{nid}'")

        # Build dependency graph
        deps: dict[str, set[str]] = {nid: set() for nid in nodes}
        for edge in edges:
            from_node = edge.get("from_node", "")
            to_node = edge.get("to_node", "")
            if from_node not in nodes:
                raise ValueError(f"Edge references unknown source node: {from_node}")
            if to_node not in nodes:
                raise ValueError(f"Edge references unknown target node: {to_node}")
            deps[to_node].add(from_node)

        # Topological sort
        order = []
        in_degree = {nid: len(d) for nid, d in deps.items()}
        queue = [nid for nid, deg in in_degree.items() if deg == 0]

        while queue:
            nid = queue.pop(0)
            order.append(nid)
            for other_nid, other_deps in deps.items():
                if nid in other_deps:
                    in_degree[other_nid] -= 1
                    if in_degree[other_nid] == 0:
                        queue.append(other_nid)

        if len(order) != len(nodes):
            raise ValueError("Graph has cycles — cannot execute")

        # Execute in order
        outputs: dict[str, dict] = {}
        ctx = {"model_manager": self.mm, "input_image": input_image}

        for idx, nid in enumerate(order):
            if self._cancelled:
                raise CancelledError("Cancelled by user")

            node_def_id = nodes[nid]["type"]
            node_type = get_node_type(node_def_id)

            if on_node_start:
                on_node_start(nid, nodes[nid], idx, len(order))

            # Collect inputs from connected edges
            node_inputs = {}
            for edge in edges:
                if edge["to_node"] == nid:
                    src = outputs.get(edge["from_node"], {})
                    value = src.get(edge["from_port"])
                    node_inputs[edge["to_port"]] = value
                    # Pass through internal state
                    for key in ("_pipe", "_width", "_height", "_cn_image", "_cn_strength",
                                "_cn_start", "_cn_end", "_ip_adapter_image", "_ip_adapter_loaded", "_arch"):
                        if key in src:
                            node_inputs[key] = src[key]

            widget_values = nodes[nid].get("widgets", {})

            # Execute with error handling
            t0 = time.time()
            error_msg = None
            result = None

            try:
                result = node_type.execute(node_inputs, widget_values, ctx)
            except torch.cuda.OutOfMemoryError:
                self._cleanup()
                error_msg = f"Out of VRAM on '{node_def_id}'. Reduce resolution/batch or use a quantized model."
                log.error(error_msg)
            except CancelledError:
                raise
            except Exception as e:
                error_msg = f"{node_def_id}: {str(e)}"
                log.error(f"Node {nid} failed: {error_msg}")
                log.debug(traceback.format_exc())

            duration = time.time() - t0

            if error_msg:
                if on_node_done:
                    on_node_done(nid, nodes[nid], None, duration, error_msg)
                raise RuntimeError(error_msg)

            outputs[nid] = result or {}
            log.info(f"  [{idx+1}/{len(order)}] {nid} ({node_def_id}): {duration:.1f}s")

            if on_node_done:
                on_node_done(nid, nodes[nid], result, duration, None)

        return outputs

    def _cleanup(self):
        """Emergency VRAM cleanup."""
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            try:
                torch.cuda.synchronize()
            except Exception:
                pass
        log.info(f"Cleanup done. VRAM free: {self._vram_free()}MB")

    def _vram_free(self) -> int:
        if torch.cuda.is_available():
            free, _ = torch.cuda.mem_get_info()
            return int(free / 1024 / 1024)
        return 0
