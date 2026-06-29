"""Killer demo: import/export packet validation → generated deliverables + audit (offline).

The end-to-end "real result": feed a shipment packet (commercial invoice, packing list, bill of
lading — with a deliberate currency mismatch and a missing certificate of origin), validate it, and
*generate* the deliverables a broker actually needs — an exception report (PDF) and a reconciliation
workbook (XLSX) — plus a printed audit trail. No model, no network, no cloud key.

Run from the repo root:  ``python evals/demo_import_export/run_local.py``
"""

from __future__ import annotations

import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend" / "src"))

from docos.model.document import CanonicalDocument, DocumentMeta  # noqa: E402
from docos.model.ids import new_doc_id, new_node_id  # noqa: E402
from docos.model.nodes import ParagraphNode, RootNode, RunNode  # noqa: E402
from docos.services import synthesis  # noqa: E402
from docos.services.docengine.writers.searchable_pdf import model_to_searchable_pdf  # noqa: E402
from docos.services.docengine.writers.xlsx_writer import model_to_xlsx  # noqa: E402
from docos.services.packs import check_packet  # noqa: E402


def _doc(*lines: str) -> CanonicalDocument:
    now = datetime.now(UTC)
    root = RootNode(id=new_node_id("root"))
    doc = CanonicalDocument(
        doc_id=new_doc_id(),
        root_id=root.id,
        meta=DocumentMeta(
            source_format="txt", source_mime="text/plain", created_at=now, modified_at=now
        ),
    )
    doc.add_node(root)
    for i, line in enumerate(lines):
        p = ParagraphNode(id=new_node_id(), parent_id=root.id, reading_order=i)
        r = RunNode(id=new_node_id(), parent_id=p.id, text=line)
        p.children.append(r.id)
        root.children.append(p.id)
        doc.add_node(p)
        doc.add_node(r)
    return doc


def _packet() -> list[tuple[str, str, CanonicalDocument]]:
    return [
        (
            "ci",
            "Commercial Invoice",
            _doc(
                "Commercial Invoice",
                "Invoice number: INV-7788",
                "Total due: 24500.00 USD",
                "Country of origin: Vietnam",
                "HS code 610910",
            ),
        ),
        (
            "pl",
            "Packing List",
            _doc("Packing List", "Total: 24500.00 EUR", "Cartons: 120"),  # currency mismatch
        ),
        (
            "bol",
            "Bill of Lading",
            _doc("Bill of Lading", "Vessel: Ever Given", "Port of loading: Haiphong"),
        ),
        # (no certificate of origin → the checklist should flag it missing)
    ]


def main() -> int:
    packet = _packet()
    report = check_packet(packet)

    out_dir = Path(tempfile.mkdtemp(prefix="docos_demo_"))
    doc = synthesis.build_document(synthesis.packet_exception_report(report))
    pdf_path = out_dir / "exception_report.pdf"
    xlsx_path = out_dir / "reconciliation.xlsx"
    pdf_path.write_bytes(model_to_searchable_pdf(doc))
    xlsx_path.write_bytes(model_to_xlsx(doc))

    print("=== Import/Export DocumentOps demo ===")
    print(f"Documents in packet: {report.document_count}")
    print(f"Summary: {report.summary}\n")
    print("Audit trail (findings):")
    for f in report.findings:
        print(f"  - [{f.severity.upper()}] {f.code}: {f.message}")
    print("\nRequired-document checklist:")
    for item in report.checklist:
        print(f"  - {item.label}: {'present' if item.present else 'MISSING'}")
    print("\nGenerated deliverables:")
    print(f"  - exception report (PDF): {pdf_path}  [{pdf_path.stat().st_size} bytes]")
    print(f"  - reconciliation (XLSX):  {xlsx_path}  [{xlsx_path.stat().st_size} bytes]")

    # The demo must actually surface the planted issues, else it isn't proving anything.
    codes = {f.code for f in report.findings}
    assert "currency_mismatch" in codes, "expected the planted currency mismatch to be flagged"
    assert "document_missing" in codes, "expected the missing certificate of origin to be flagged"
    assert pdf_path.read_bytes()[:4] == b"%PDF" and xlsx_path.read_bytes()[:2] == b"PK"
    print("\nOK: issues flagged and deliverables generated.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
