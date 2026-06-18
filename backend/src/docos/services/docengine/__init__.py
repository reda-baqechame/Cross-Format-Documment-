"""Document engine: per-format adapters that parse into / export from the model."""

from docos.services.docengine.interface import FormatAdapter

__all__ = ["AdapterRegistry", "FormatAdapter", "default_registry"]


def __getattr__(name: str):
    if name in {"AdapterRegistry", "default_registry"}:
        from docos.services.docengine.registry import AdapterRegistry, default_registry

        return {"AdapterRegistry": AdapterRegistry, "default_registry": default_registry}[name]
    raise AttributeError(name)
