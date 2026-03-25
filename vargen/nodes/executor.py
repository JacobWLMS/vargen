"""Graph executor — topologically sorts and executes node graphs."""

import gc
import logging
import time
from typing import Callable, Optional

import torch
from PIL import Image

from . import get_node_type

log = logging.getLogger(__name__)


class GraphExecutor:
    """Execute a node graph with typed port connections."""

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
        """Execute a node graph.

        graph format:
        {
            "nodes": {
                "node_id": {"type": "load_checkpoint", "widgets": {"checkpoint": "model.safetensors"}, "x": 0, "y": 0},
                ...
            },
            "edges": [
                {"from_node": "n1", "from_port": "MODEL", "to_node": "n2", "to_port": "MODEL"},
                ...
            ]
        }

        Returns dict of {node_id: {port_name: value}} for all executed nodes.
        """
        self._cancelled = False
        nodes = graph["nodes"]
        edges = graph.get("edges", [])

        # Build dependency graph
        deps: dict[str, set[str]] = {nid: set() for nid in nodes}
        for edge in edges:
            deps[edge["to_node"]].add(edge["from_node"])

        # Topological sort (Kahn's algorithm)
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
        ctx = {
            "model_manager": self.mm,
            "input_image": input_image,
        }

        for idx, nid in enumerate(order):
            if self._cancelled:
                self._cleanup()
                raise CancelledError("Execution cancelled")

            node_def_id = nodes[nid]["type"]
            node_type = get_node_type(node_def_id)
            if not node_type:
                raise ValueError(f"Unknown node type: {node_def_id}")

            if on_node_start:
                on_node_start(nid, nodes[nid], idx, len(order))

            # Collect inputs from connected edges
            node_inputs = {}
            for edge in edges:
                if edge["to_node"] == nid:
                    src_outputs = outputs.get(edge["from_node"], {})
                    value = src_outputs.get(edge["from_port"])
                    node_inputs[edge["to_port"]] = value
                    # Also pass through internal state like _pipe
                    if "_pipe" in src_outputs:
                        node_inputs["_pipe"] = src_outputs["_pipe"]
                    if "_width" in src_outputs:
                        node_inputs["_width"] = src_outputs["_width"]
                    if "_height" in src_outputs:
                        node_inputs["_height"] = src_outputs["_height"]

            # Get widget values
            widget_values = nodes[nid].get("widgets", {})

            # Execute
            t0 = time.time()
            try:
                result = node_type.execute(node_inputs, widget_values, ctx)
            except Exception as e:
                log.error(f"Node {nid} ({node_def_id}) failed: {e}")
                if on_node_done:
                    on_node_done(nid, nodes[nid], None, time.time() - t0, str(e))
                raise
            duration = time.time() - t0

            outputs[nid] = result
            log.info(f"  [{idx+1}/{len(order)}] {nid} ({node_def_id}): {duration:.1f}s")

            if on_node_done:
                on_node_done(nid, nodes[nid], result, duration, None)

        return outputs

    def _cleanup(self):
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()


class CancelledError(Exception):
    pass
