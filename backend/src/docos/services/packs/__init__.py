"""Business packs — vertical document workflows on the universal core.

A pack bundles document types + deterministic field extraction + cross-document validation rules for
one industry. The first is import/export: the sharpest wedge, where errors are expensive and fields
must agree across a shipment packet (commercial invoice, packing list, bill of lading, certificate
of origin, purchase order). Everything here is deterministic and offline.
"""

from docos.services.packs.import_export import PacketReport, check_packet

__all__ = ["PacketReport", "check_packet"]
