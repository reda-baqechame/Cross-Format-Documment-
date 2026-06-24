"""Block-level document comparison."""

from __future__ import annotations

from datetime import UTC, datetime

from docos.model.document import CanonicalDocument, DocumentMeta
from docos.model.nodes import ParagraphNode, RootNode, RunNode
from docos.services.provenance import diff


def _doc(texts: list[str]) -> CanonicalDocument:
    now = datetime.now(UTC)
    root = RootNode(id="root")
    d = CanonicalDocument(
        doc_id="d",
        root_id=root.id,
        meta=DocumentMeta(
            source_format="txt",
            source_mime="text/plain",
            created_at=now,
            modified_at=now,
            page_count=1,
        ),
    )
    d.add_node(root)
    for i, t in enumerate(texts):
        para = ParagraphNode(id=f"p{i}", parent_id=root.id, reading_order=i)
        run = RunNode(id=f"r{i}", parent_id=para.id, text=t)
        para.children.append(run.id)
        root.children.append(para.id)
        d.add_node(para)
        d.add_node(run)
    return d


def test_identical_documents_all_equal():
    res = diff.diff_documents(_doc(["one", "two"]), _doc(["one", "two"]))
    assert res.added == res.removed == res.changed == 0
    assert res.unchanged == 2


def test_insert_and_delete_and_replace():
    base = _doc(["intro", "middle", "end"])
    other = _doc(["intro", "MIDDLE EDITED", "end", "new tail"])
    res = diff.diff_documents(base, other)
    ops = {s.op for s in res.segments}
    assert "equal" in ops and "replace" in ops and "insert" in ops
    assert res.added == 1  # "new tail"
    assert res.changed == 1  # middle replaced
    # the replace segment pairs both sides
    repl = next(s for s in res.segments if s.op == "replace")
    assert repl.a_text == "middle" and repl.b_text == "MIDDLE EDITED"


def test_pure_deletion():
    res = diff.diff_documents(_doc(["a", "b"]), _doc(["a"]))
    assert res.removed == 1 and res.added == 0
