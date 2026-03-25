"""Node type registry — granular operations with typed ports."""

from dataclasses import dataclass, field
from typing import Any, Callable, Optional


@dataclass
class PortDef:
    """Definition of a node input or output port."""
    name: str
    type: str  # MODEL, CLIP, VAE, CONDITIONING, LATENT, IMAGE, MASK, STRING, INT, FLOAT
    label: Optional[str] = None
    optional: bool = False


@dataclass
class WidgetDef:
    """Definition of a configurable widget on a node."""
    name: str
    type: str  # "combo", "text", "number", "slider", "toggle", "textarea"
    default: Any = None
    options: list[str] | None = None  # for combo type
    min: float | None = None          # for slider/number
    max: float | None = None
    step: float | None = None
    label: Optional[str] = None


@dataclass
class NodeTypeDef:
    """Complete definition of a node type."""
    type_id: str                    # e.g. "load_checkpoint"
    category: str                   # e.g. "loaders", "sampling", "conditioning"
    label: str                      # display name
    inputs: list[PortDef]           # typed input ports
    outputs: list[PortDef]          # typed output ports
    widgets: list[WidgetDef]        # configurable parameters
    execute: Callable               # function(inputs, widgets) -> outputs
    color: str = "#666"             # accent color for UI
    description: str = ""


# Global registry
_registry: dict[str, NodeTypeDef] = {}


def register_node(node_def: NodeTypeDef):
    """Register a node type."""
    _registry[node_def.type_id] = node_def


def get_node_type(type_id: str) -> Optional[NodeTypeDef]:
    return _registry.get(type_id)


def get_all_node_types() -> dict[str, NodeTypeDef]:
    return dict(_registry)


def get_node_types_by_category() -> dict[str, list[NodeTypeDef]]:
    result: dict[str, list[NodeTypeDef]] = {}
    for node_def in _registry.values():
        result.setdefault(node_def.category, []).append(node_def)
    return result
