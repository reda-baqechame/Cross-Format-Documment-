"""Unit tests for BM25 retrieval + dry-run patch preview (deterministic, offline)."""

from __future__ import annotations

from datetime import UTC, datetime

from docos.model.document import CanonicalDocument, DocumentMeta
from docos.model.nodes import ParagraphNode, RootNode, RunNode
from docos.model.patch import Patch
from docos.services.semantic.preview import build_preview
from docos.services.semantic.retrieval import rank_nodes, select_digest_nodes


def _doc_with_runs(texts: list[str]) -> CanonicalDocument:
    now = datetime.now(UTC)
    root = RootNode(id="root", children=[])
    nodes: dict = {"root": root}
    for i, text in enumerate(texts):
        pid, rid = f"p{i}", f"r{i}"
        para = ParagraphNode(id=pid, parent_id="root", reading_order=i, children=[rid])
        nodes[pid] = para
        nodes[rid] = RunNode(id=rid, parent_id=pid, text=text)
        root.children.append(pid)
    return CanonicalDocument(
        doc_id="d",
        root_id="root",
        nodes=nodes,
        meta=DocumentMeta(source_format="txt", source_mime="text/plain", created_at=now,
                          modified_at=now),
    )


def test_rank_nodes_surfaces_the_relevant_run_first():
    doc = _doc_with_runs(
        ["The quick brown fox", "Termination clause and renewal terms", "Lorem ipsum dolor"]
    )
    ranked = rank_nodes(doc, "termination renewal")
    assert ranked, "expected at least one relevant node"
    assert ranked[0] == "r1"  # the clause run wins on BM25


def test_rank_nodes_empty_query_returns_document_order():
    doc = _doc_with_runs(["alpha", "beta", "gamma"])
    assert rank_nodes(doc, "   ") == ["r0", "r1", "r2"]


def test_select_digest_small_doc_returns_all_in_order():
    doc = _doc_with_runs(["one", "two", "three"])
    assert select_digest_nodes(doc, "anything", limit=400) == ["r0", "r1", "r2"]


def test_select_digest_large_doc_narrows_to_relevant_in_doc_order():
    # 10 filler runs + one that matches the query; limit forces narrowing.
    texts = [f"filler line number {i}" for i in range(10)]
    texts.insert(5, "indemnification liability cap")
    doc = _doc_with_runs(texts)
    selected = select_digest_nodes(doc, "indemnification liability", limit=3)
    assert "r5" in selected  # the relevant run is retained
    assert len(selected) <= 3
    # returned in document order (ascending run index)
    assert selected == sorted(selected, key=lambda nid: int(nid[1:]))


def test_build_preview_text_and_redaction_changes():
    doc = _doc_with_runs(["Contact finance@example.com", "Keep me"])
    ops = [
        Patch(op="set_text", target_id="r0", payload={"text": "Contact [redacted]"}),
        Patch(op="redact", target_id="r1"),
    ]
    preview = build_preview(doc, ops)
    assert preview.change_count == 2
    assert "2 changes" in preview.summary
    text_change = next(c for c in preview.changes if c.op == "set_text")
    assert text_change.before == "Contact finance@example.com"
    assert text_change.after == "Contact [redacted]"
    redaction = next(c for c in preview.changes if c.op == "redact")
    assert redaction.before == "Keep me"
    assert "removed" in (redaction.after or "")


def test_build_preview_empty_ops():
    doc = _doc_with_runs(["x"])
    preview = build_preview(doc, [])
    assert preview.change_count == 0
    assert "No changes" in preview.summary


def test_plan_endpoint_previews_without_committing(client):
    """POST /patches/plan returns a before/after preview and does NOT mutate the document."""
    files = {"file": ("n.txt", b"Hello world\n\nSecond.", "text/plain")}
    up = client.post("/documents", files=files)
    doc_id = up.json()["doc_id"]
    model = client.get(f"/documents/{doc_id}/model").json()["document"]
    run_id = next(n["id"] for n in model["nodes"].values() if n["type"] == "run")

    plan = client.post(
        f"/documents/{doc_id}/patches/plan",
        json={"ops": [{"op": "set_text", "target_id": run_id, "payload": {"text": "Changed!"}}]},
    )
    assert plan.status_code == 200, plan.text
    body = plan.json()
    assert body["preview"]["change_count"] == 1
    assert body["ops"][0]["target_id"] == run_id
    assert body["preview"]["changes"][0]["after"] == "Changed!"

    # The plan is a dry run: the stored document is unchanged.
    after = client.get(f"/documents/{doc_id}/model").json()["document"]
    assert after["nodes"][run_id]["text"] != "Changed!"


def test_plan_endpoint_rejects_unknown_target(client):
    up = client.post("/documents", files={"file": ("n.txt", b"Hi", "text/plain")})
    doc_id = up.json()["doc_id"]
    plan = client.post(
        f"/documents/{doc_id}/patches/plan",
        json={"ops": [{"op": "set_text", "target_id": "nope", "payload": {"text": "x"}}]},
    )
    assert plan.status_code == 422


def test_plan_instruction_requires_ai_provider_offline(client):
    up = client.post("/documents", files={"file": ("n.txt", b"Hi", "text/plain")})
    doc_id = up.json()["doc_id"]
    plan = client.post(f"/documents/{doc_id}/patches/plan", json={"instruction": "make it bold"})
    assert plan.status_code == 501  # no LLM provider configured offline
