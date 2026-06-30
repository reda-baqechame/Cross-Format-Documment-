"""Expert vertical packs — the deep, evidence-bound rebuild of each business vertical.

Each module here exposes ``audit(packet_id, docs) -> ExpertReport`` with fully cited
findings. Contrast with ``docos.services.packs`` (the legacy, uncited deterministic packs),
which remain available unchanged for backward compatibility.
"""

from docos.services.expert.verticals import import_export

__all__ = ["import_export"]
