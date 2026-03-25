"""Graph executor — topologically sorts and executes node graphs with OOM protection."""

import gc
import logging
import time
import traceback
from typing import Callable, Optional

import torch
from PIL import Image

from . import get_node_type

log = logging.getLogger(__name__)


class CancelledError(Exception):
    pass


class GraphExecutor:
    """Execute a node graph with typed port connections and VRAM protection."""

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
        self._cancelled = False
        nodes = graph["nodes"]
        edges = graph.get("edges", [])

        # Build dependency graph
        deps: dict[str, set[str]] = {nid: set() for nid in nodes}
        for edge in edges:
            deps[edge["to_node"]].add(edge["from_node"])

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
            raise ValueError("Graph has cycles")

        outputs: dict[str, dict] = {}
        ctx = {"model_manager": self.mm, "input_image": input_image}

        for idx, nid in enumerate(order):
            if self._cancelled:
                self._cleanup()
                raise CancelledError("Cancelled")

            node_def_id = nodes[nid]["type"]
            node_type = get_node_type(node_def_id)
            if not node_type:
                raise ValueError(f"Unknown node type: {node_def_id}")

            if on_node_start:
                on_node_start(nid, nodes[nid], idx, len(order))

            # Collect inputs
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

            # Execute with OOM protection
            t0 = time.time()
            try:
                result = node_type.execute(node_inputs, widget_values, ctx)
            except torch.cuda.OutOfMemoryError:
                self._cleanup()
                error_msg = f"Out of VRAM on node {nid} ({node_def_id}). Try reducing resolution, batch size, or use a quantized model."
                log.error(error_msg)
                if on_node_done:
                    on_node_done(nid, nodes[nid], None, time.time() - t0, error_msg)
                raise RuntimeError(error_msg)
            except Exception as e:
                # Don't crash the server — log and report
                error_msg = f"{node_def_id}: {str(e)}"
                log.error(f"Node {nid} failed: {error_msg}")
                log.debug(traceback.format_exc())
                self._cleanup()
                if on_node_done:
                    on_node_done(nid, nodes[nid], None, time.time() - t0, error_msg)
                raise RuntimeError(error_msg)

            duration = time.time() - t0
            outputs[nid] = result
            log.info(f"  [{idx+1}/{len(order)}] {nid} ({node_def_id}): {duration:.1f}s")

            if on_node_done:
                on_node_done(nid, nodes[nid], result, duration, None)

        return outputs

    def _cleanup(self):
        """Emergency VRAM cleanup."""
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            torch.cuda.synchronize()
        log.info(f"Cleanup done. VRAM free: {self._vram_free()}MB")

    def _vram_free(self) -> int:
        if torch.cuda.is_available():
            free, _ = torch.cuda.mem_get_info()
            return int(free / 1024 / 1024)
        return 0
