"""Seed a couple of sample documents for local development.

Run with ``make seed`` (requires the database to be migrated).
"""

from __future__ import annotations

from docos.db.base import session_scope
from docos.db.models import Document
from docos.services.docengine.adapters.txt import TxtAdapter
from docos.services.provenance.service import ProvenancePolicyServiceImpl

_SAMPLE_TXT = b"""Welcome to Cross-Format Document OS

This sample document was parsed into the canonical model and rendered from it.

Edit it, check its health panel, and watch the version history grow.
"""


def main() -> None:
    adapter = TxtAdapter()
    doc = adapter.parse(_SAMPLE_TXT)
    doc.meta.title = "Sample document"
    doc.accessibility.has_doc_title = True

    with session_scope() as session:
        provenance = ProvenancePolicyServiceImpl(session)
        record = Document(
            id=doc.doc_id,
            title=doc.meta.title,
            source_format="txt",
            source_mime="text/plain",
            blob_key="seed/sample.txt",
        )
        session.add(record)
        session.flush()
        version_id = provenance.commit_version(doc)
        record.current_version_id = version_id
        provenance.record_event(doc.doc_id, "document.seeded", actor="seed", detail={})
        print(f"seeded document {doc.doc_id} @ {version_id}")


if __name__ == "__main__":
    main()
