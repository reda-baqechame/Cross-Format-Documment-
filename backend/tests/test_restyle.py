"""Global restyle (Pillar C): bulk inline formatting compiled to reversible update_node ops."""

from __future__ import annotations

from datetime import UTC, datetime

from docos.model.document import CanonicalDocument, DocumentMeta
from docos.model.ids import new_doc_id, new_node_id
from docos.model.nodes import HeadingNode, ParagraphNode, RootNode, RunNode
from docos.services.semantic.restyle import RestyleStyle, build_restyle_patch


def _doc() -> CanonicalDocument:
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
    # A heading run and a body run.
    h = HeadingNode(id=new_node_id(), parent_id=root.id, level=1, reading_order=0)
    hr = RunNode(id=new_node_id(), parent_id=h.id, text="Title")
    h.children.append(hr.id)
    p = ParagraphNode(id=new_node_id(), parent_id=root.id, reading_order=1)
    pr = RunNode(id=new_node_id(), parent_id=p.id, text="body text TOTAL")
    p.children.append(pr.id)
    root.children.extend([h.id, p.id])
    for n in (h, hr, p, pr):
        doc.add_node(n)
    return doc, hr.id, pr.id


def test_restyle_headings_scope_targets_only_heading_runs():
    doc, hid, pid = _doc()
    patch = build_restyle_patch(doc, RestyleStyle(bold=True, size=18), scope="headings")
    targets = {p.target_id for p in patch.patches}
    assert hid in targets and pid not in targets


def test_restyle_matching_scope():
    doc, hid, pid = _doc()
    patch = build_restyle_patch(
        doc, RestyleStyle(italic=True), scope="matching", find="TOTAL"
    )
    assert {p.target_id for p in patch.patches} == {pid}


def test_restyle_skips_redacted_runs():
    doc, hid, pid = _doc()
    doc.redaction.redacted_node_ids.append(hid)
    patch = build_restyle_patch(doc, RestyleStyle(bold=True), scope="all")
    assert hid not in {p.target_id for p in patch.patches}


def test_restyle_requires_a_style_field():
    doc, _hid, _pid = _doc()
    try:
        build_restyle_patch(doc, RestyleStyle(), scope="all")
        raise AssertionError("expected ValueError")
    except ValueError:
        pass


def _upload(client, text):
    return client.post(
        "/documents", files={"file": ("d.txt", text.encode(), "text/plain")}
    ).json()["doc_id"]


def test_restyle_endpoint_applies_and_is_undoable(client):
    doc_id = _upload(client, "Heading line\n\nbody paragraph")
    res = client.post(
        f"/documents/{doc_id}/restyle", json={"scope": "all", "style": {"bold": True}}
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["applied"] is True and body["nodes_changed"] >= 1

    # Every run is now bold…
    model = client.get(f"/documents/{doc_id}/model").json()["document"]
    runs = [n for n in model["nodes"].values() if n.get("type") == "run"]
    assert runs and all(n.get("bold") for n in runs)

    # …and the bulk edit reverts in one undo (reversible).
    undo = client.post(f"/documents/{doc_id}/undo")
    assert undo.status_code == 200
    runs2 = [n for n in undo.json()["document"]["nodes"].values() if n.get("type") == "run"]
    assert not any(n.get("bold") for n in runs2)
