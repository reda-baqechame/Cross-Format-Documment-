"""Expert vertical packs — the deep, evidence-bound rebuild of each business vertical.

Each module here exposes ``audit(packet_id, docs) -> ExpertReport`` with fully cited
findings. Contrast with ``docos.services.packs`` (the legacy, uncited deterministic packs),
which remain available unchanged for backward compatibility.
"""

from docos.services.expert.verticals import ap, contracts, hr, import_export, insurance

__all__ = ["ap", "contracts", "hr", "import_export", "insurance"]
