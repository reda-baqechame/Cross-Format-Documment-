"""Golden packet fixture eval (L2) — file-backed cases with expected verdicts.

Runs checked-in document fixtures under ``evals/golden_packets/<pack>/case_*/`` and asserts
the same guarantees as ``evals/packet_audit/run_local.py``. Presence of
``expected/REVIEWED_BY`` marks a case as human-reviewed (rung 9).

Supports ``.txt`` and ``.pdf`` documents (PDF fixtures exercise the PDF adapter path).

Run: ``python evals/golden_packets/run_local.py``
"""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend" / "src"))

from docos.model.document import CanonicalDocument, DocumentMeta  # noqa: E402
from docos.model.nodes import PageNode, ParagraphNode, RootNode, RunNode  # noqa: E402
from docos.services.docengine.adapters.pdf import PdfAdapter  # noqa: E402
from docos.services.expert.verticals import (  # noqa: E402
    ap,
    contracts,
    hr,
    import_export,
    insurance,
)

VERTICALS = {
    "import_export": import_export,
    "ap": ap,
    "contracts": contracts,
    "hr": hr,
    "insurance": insurance,
}


def _pdf_bytes(lines: list[str]) -> bytes:
    import fitz

    pdf = fitz.open()
    page = pdf.new_page(width=595, height=842)
    for i, line in enumerate(lines):
        page.insert_text((72, 72 + i * 18), line, fontsize=11)
    data = pdf.tobytes()
    pdf.close()
    return data


def _doc_from_txt(doc_id: str, text: str) -> CanonicalDocument:
    lines = [ln for ln in text.splitlines() if ln.strip()]
    root = RootNode(id=f"{doc_id}_root", children=[f"{doc_id}_p1"])
    page = PageNode(id=f"{doc_id}_p1", parent_id=root.id, page_number=1, width=612, height=792)
    nodes = {root.id: root, page.id: page}
    for i, line in enumerate(lines):
        pid, rid = f"{doc_id}_para{i}", f"{doc_id}_run{i}"
        para = ParagraphNode(id=pid, parent_id=page.id)
        run = RunNode(id=rid, parent_id=pid, text=line)
        para.children = [rid]
        page.children.append(pid)
        nodes[pid] = para
        nodes[rid] = run
    now = datetime.now(tz=UTC)
    return CanonicalDocument(
        doc_id=doc_id,
        root_id=root.id,
        nodes=nodes,
        meta=DocumentMeta(
            title=doc_id,
            source_format="txt",
            source_mime="text/plain",
            created_at=now,
            modified_at=now,
            page_count=1,
        ),
    )


def _doc_from_pdf(doc_id: str, data: bytes) -> CanonicalDocument:
    doc = PdfAdapter().parse(data)
    doc.doc_id = doc_id
    doc.meta.title = doc_id
    return doc


def _load_document(path: Path, doc_id: str) -> CanonicalDocument:
    if path.suffix.lower() == ".pdf":
        data = path.read_bytes() if path.stat().st_size else _pdf_bytes([])
        if not path.stat().st_size:
            raise ValueError(f"empty pdf fixture: {path}")
        return _doc_from_pdf(doc_id, data)
    return _doc_from_txt(doc_id, path.read_text(encoding="utf-8"))


def _load_case(case_dir: Path) -> tuple[str, list[tuple[str, str, CanonicalDocument]], dict]:
    expected = json.loads((case_dir / "expected" / "verdict.json").read_text(encoding="utf-8"))
    pack = expected["pack"]
    docs: list[tuple[str, str, CanonicalDocument]] = []
    doc_dir = case_dir / "documents"
    for path in sorted(doc_dir.iterdir()):
        if path.suffix.lower() == ".txt" and path.name.endswith(".pdfsource.txt"):
            continue
        if path.suffix.lower() not in {".txt", ".pdf"}:
            continue
        doc_id = path.stem
        docs.append((doc_id, doc_id, _load_document(path, doc_id)))
    return pack, docs, expected


def _score_case(name: str, report, expected: dict) -> list[str]:
    errors: list[str] = []
    if report.verdict != expected["expected_verdict"]:
        errors.append(f"{name}: verdict {report.verdict} != {expected['expected_verdict']}")
    blocking_codes = {f.rule_code for f in report.findings if f.severity == "blocking"}
    for code in expected.get("expected_blocking", []):
        if code not in blocking_codes:
            errors.append(f"{name}: missing blocking rule {code}")
    for f in report.findings:
        if f.severity in ("blocking", "warning") and not f.evidence and not f.human_review_required:
            errors.append(f"{name}: unfounded finding {f.rule_code}")
    return errors


def _ensure_pdf_fixtures() -> None:
    """Materialize .pdf fixtures from sidecar *.pdfsource.txt when present."""
    base = Path(__file__).resolve().parent
    for src in base.glob("*/*/documents/*.pdfsource.txt"):
        pdf_name = src.name.replace(".pdfsource.txt", ".pdf")
        pdf_path = src.parent / pdf_name
        if pdf_path.exists() and pdf_path.stat().st_size > 0:
            continue
        lines = [ln for ln in src.read_text(encoding="utf-8").splitlines() if ln.strip()]
        pdf_path.write_bytes(_pdf_bytes(lines))


def main() -> int:
    _ensure_pdf_fixtures()
    base = Path(__file__).resolve().parent
    errors: list[str] = []
    reviewed = 0
    ran = 0
    per_pack: dict[str, int] = {}
    pdf_per_pack: dict[str, int] = {}
    for case_dir in sorted(base.glob("*/*")):
        if not case_dir.is_dir() or not (case_dir / "expected" / "verdict.json").exists():
            continue
        pack, docs, expected = _load_case(case_dir)
        vertical = VERTICALS[pack]
        report = vertical.audit(case_dir.name, docs)
        errors.extend(_score_case(str(case_dir.relative_to(base)), report, expected))
        ran += 1
        per_pack[pack] = per_pack.get(pack, 0) + 1
        if any(d[2].meta.source_format == "pdf" for d in docs):
            pdf_per_pack[pack] = pdf_per_pack.get(pack, 0) + 1
        if (case_dir / "expected" / "REVIEWED_BY").exists():
            reviewed += 1
    for pack, count in per_pack.items():
        if count < 3:
            errors.append(f"{pack}: expected >=3 cases, found {count}")
        if pdf_per_pack.get(pack, 0) < 1:
            errors.append(f"{pack}: expected >=1 PDF fixture case, found {pdf_per_pack.get(pack, 0)}")
    if ran == 0:
        print("No golden packet cases found.")
        return 1
    if errors:
        print("GOLDEN PACKET FIXTURE EVAL FAILED")
        for e in errors:
            print(" ", e)
        return 1
    print(f"golden_packets: {ran} case(s) passed ({reviewed} human-reviewed)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
