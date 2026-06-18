"""Local eval harness for the DocumentOpsAgent planning contract."""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
BACKEND_SRC = ROOT / "backend" / "src"
sys.path.insert(0, str(BACKEND_SRC))

from docos.model.document import CanonicalDocument, DocumentMeta  # noqa: E402
from docos.model.nodes import ParagraphNode, RootNode, RunNode  # noqa: E402
from docos.services.semantic.agents.document_ops import plan_document_ops  # noqa: E402


def _sample_doc() -> CanonicalDocument:
    now = datetime.now(UTC)
    root = RootNode(id="root", children=["p1"])
    paragraph = ParagraphNode(id="p1", parent_id="root", children=["r1"])
    run = RunNode(
        id="r1",
        parent_id="p1",
        text="Vendor agreement for ACME. Email: finance@example.com. Signature: ______",
    )
    return CanonicalDocument(
        doc_id="eval_doc",
        root_id=root.id,
        nodes={root.id: root, paragraph.id: paragraph, run.id: run},
        meta=DocumentMeta(
            title="Vendor agreement",
            source_format="docx",
            source_mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            created_at=now,
            modified_at=now,
            page_count=1,
        ),
    )


def _load_cases() -> list[dict[str, Any]]:
    path = Path(__file__).with_name("cases.jsonl")
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def _assert_case(case: dict[str, Any]) -> None:
    plan = plan_document_ops(_sample_doc(), case["goal"], allow_destructive=False)
    tools = {action.tool for action in plan.actions}
    missing = set(case["required_tools"]) - tools
    if missing:
        raise AssertionError(f"{case['name']} missing tools: {sorted(missing)}")

    approval_tools = {action.tool for action in plan.actions if action.requires_approval}
    expected_approval = set(case["approval_tools"])
    if not expected_approval.issubset(approval_tools):
        raise AssertionError(
            f"{case['name']} missing approval gates: {sorted(expected_approval - approval_tools)}"
        )

    for action in plan.actions:
        if not action.reason.strip():
            raise AssertionError(f"{case['name']} action {action.tool} has no reason")

    required_warning = case.get("required_warning")
    if required_warning and not any(required_warning in warning for warning in plan.warnings):
        raise AssertionError(f"{case['name']} missing warning: {required_warning}")


def main() -> None:
    cases = _load_cases()
    for case in cases:
        _assert_case(case)
    print(f"DocumentOpsAgent local eval passed {len(cases)} cases")


if __name__ == "__main__":
    main()
