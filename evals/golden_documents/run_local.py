"""Golden single-document fixture eval (L2) — readiness + expert findings.

Runs checked-in text fixtures under ``evals/golden_documents/case_*/`` and asserts
expected verdicts, blocking checks, and evidence-bound findings.

Run: ``python evals/golden_documents/run_local.py``
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
from docos.services.expert.readiness_bridge import readiness_to_expert_findings  # noqa: E402
from docos.services.provenance import readiness  # noqa: E402


def _doc_from_txt(doc_id: str, text: str, *, meta: dict | None = None) -> CanonicalDocument:
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
    custom = (meta or {}).get("custom", {})
    doc = CanonicalDocument(
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
            custom=custom,
        ),
    )
    if meta and meta.get("metadata_sanitized"):
        doc.redaction.metadata_sanitized = True
    if meta and meta.get("pending"):
        doc.redaction.pending = meta["pending"]
    return doc


def _score_case(name: str, report, findings, expected: dict) -> list[str]:
    errors: list[str] = []
    if report.verdict != expected["expected_verdict"]:
        errors.append(f"{name}: verdict {report.verdict} != {expected['expected_verdict']}")
    check_ids = {c.id for c in report.checks if c.status != "pass"}
    for check_id in expected.get("expected_checks", []):
        if check_id not in check_ids:
            errors.append(f"{name}: missing failing check {check_id}")
    for f in findings:
        if f.severity in ("blocking", "warning") and not f.evidence and not f.human_review_required:
            errors.append(f"{name}: unfounded finding {f.rule_code or f.id}")
    return errors


def main() -> int:
    base = Path(__file__).resolve().parent
    errors: list[str] = []
    ran = 0
    for case_dir in sorted(base.glob("case_*")):
        expected_path = case_dir / "expected" / "verdict.json"
        doc_path = case_dir / "document.txt"
        if not expected_path.exists() or not doc_path.exists():
            continue
        expected = json.loads(expected_path.read_text(encoding="utf-8"))
        meta_path = case_dir / "meta.json"
        meta = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.exists() else None
        doc_id = case_dir.name
        doc = _doc_from_txt(doc_id, doc_path.read_text(encoding="utf-8"), meta=meta)
        report = readiness.build_report(doc)
        findings = readiness_to_expert_findings(doc_id, doc, report)
        errors.extend(_score_case(case_dir.name, report, findings, expected))
        ran += 1
    if ran < 10:
        errors.append(f"expected >=10 golden document cases, found {ran}")
    if errors:
        print("GOLDEN DOCUMENT FIXTURE EVAL FAILED")
        for e in errors:
            print(" ", e)
        return 1
    print(f"golden_documents: {ran} case(s) passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
