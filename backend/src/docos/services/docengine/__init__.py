"""Document engine: per-format adapters that parse into / export from the model."""

from docos.services.docengine.interface import FormatAdapter
from docos.services.docengine.registry import AdapterRegistry, default_registry

__all__ = ["AdapterRegistry", "FormatAdapter", "default_registry"]
