"""Local document-fidelity eval harness (deterministic, no model calls, no network).

Builds a representative canonical document (heading + paragraph with a secret + a 2x2 table with
OCR-confidence-tagged cells), runs every fidelity metric, prints a report, and exits non-zero if any
metric regresses below its threshold. Mirrors ``evals/document_ops/run_local.py`` and is safe to run
in CI. Drop real corpus files under ``samples/`` to extend coverage beyond the synthetic sample.

Run from the repo root:  ``python evals/document_fidelity/run_local.py``
"""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BACKEND_SRC = ROOT / "backend" / "src"
sys.path.insert(0, str(BACKEND_SRC))
sys.path.insert(0, str(ROOT / "evals"))

from docos.model.document import CanonicalDocument, DocumentMeta  # noqa: E402
from docos.model.nodes import (  # noqa: E402
    HeadingNode,
    ParagraphNode,
    RootNode,
    RunNode,
    TableCellNode,
    TableNode,
    TableRowNode,
)
from docos.services.docengine.registry import default_registry  # noqa: E402
from document_fidelity.metrics import (  # noqa: E402
    export_score,
    layout_score,
    ocr_score,
    redaction_score,
    table_score,
)

SECRET = "finance@example.com"

# Per-metric regression gates. The synthetic sample is constructed to clear these comfortably; a
# drop below them means the fidelity plumbing changed and should be looked at.
THRESHOLDS = {
    "layout_score": 0.99,
    "ocr_score": 0.80,
    "table_score": 0.99,
    "export_text_retention": 0.95,
    "redaction_score": 1.0,
}


def _sample_doc() -> CanonicalDocument:
    now = datetime.now(UTC)
    root = RootNode(id="root", children=["h1", "p1", "tbl1"])
    heading = HeadingNode(id="h1", parent_id="root", level=1, reading_order=0, children=["hr"])
    hrun = RunNode(id="hr", parent_id="h1", text="Quarterly Report")
    para = ParagraphNode(id="p1", parent_id="root", reading_order=1, children=["pr"])
    prun = RunNode(id="pr", parent_id="p1", text=f"Contact {SECRET} for details.")

    table = TableNode(id="tbl1", parent_id="root", rows=2, cols=2, reading_order=2,
                      children=["r0", "r1"])
    nodes: dict = {
        "root": root, "h1": heading, "hr": hrun, "p1": para, "pr": prun, "tbl1": table,
    }
    values = [["Item", "Qty"], ["Widget", "10"]]
    for ri in range(2):
        row = TableRowNode(id=f"r{ri}", parent_id="tbl1", row=ri, reading_order=ri)
        cell_ids = []
        for ci in range(2):
            cid, runid = f"c{ri}{ci}", f"cr{ri}{ci}"
            cell = TableCellNode(id=cid, parent_id=row.id, row=ri, col=ci, header=(ri == 0),
                                 children=[runid])
            run = RunNode(id=runid, parent_id=cid, text=values[ri][ci],
                          attrs={"confidence": 92.0, "ocr_review": False})
            nodes[cid] = cell
            nodes[runid] = run
            cell_ids.append(cid)
        row.children = cell_ids
        nodes[row.id] = row

    return CanonicalDocument(
        doc_id="fidelity_sample",
        root_id="root",
        nodes=nodes,
        meta=DocumentMeta(
            title="Quarterly Report",
            source_format="docx",
            source_mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            created_at=now,
            modified_at=now,
            page_count=1,
        ),
    )


def main() -> int:
    doc = _sample_doc()
    registry = default_registry()
    exp = export_score(doc, registry)
    scores = {
        "layout_score": layout_score(doc),
        "ocr_score": ocr_score(doc),
        "table_score": table_score(doc, expected_cells=4),
        "export_openable": exp["openable"],
        "export_text_retention": exp["text_retention"],
        "redaction_score": redaction_score(doc, registry, secret=SECRET),
    }
    print(json.dumps({"scores": scores, "thresholds": THRESHOLDS}, indent=2))

    failures = []
    if not scores["export_openable"]:
        failures.append("export_openable is False")
    for key, floor in THRESHOLDS.items():
        if scores.get(key, 0.0) < floor:
            failures.append(f"{key}={scores.get(key)} < {floor}")

    if failures:
        print("\nFIDELITY REGRESSIONS:")
        for f in failures:
            print(f"  - {f}")
        return 1
    print("\nAll fidelity metrics passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
