"""Accessibility auto-remediation: ops generation, reversibility, and endpoint."""

from __future__ import annotations

import io
from datetime import UTC, datetime

from docos.model.document import CanonicalDocument, DocumentMeta
from docos.model.ids import new_patch_id
from docos.model.nodes import HeadingNode, ImageNode, ParagraphNode, RootNode, RunNode
from docos.model.patch import ReversiblePatch
from docos.services.provenance import accessibility
from docos.services.semantic.llm.noop import LocalNoopClient
from docos.services.semantic.orchestrator import SemanticOrchestratorImpl


def _needy_doc() -> CanonicalDocument:
    now = datetime.now(UTC)
    root = RootNode(id="root")
    doc = CanonicalDocument(
        doc_id="d",
        root_id=root.id,
        meta=DocumentMeta(
            source_format="pdf",
            source_mime="application/pdf",
            created_at=now,
            modified_at=now,
            page_count=1,
        ),
    )
    doc.add_node(root)
    heading = HeadingNode(id="h", parent_id=root.id, level=2)  # no H tag, no reading_order
    para = ParagraphNode(id="p", parent_id=root.id)
    run = RunNode(id="r", parent_id=para.id, text="body")
    image = ImageNode(id="img", parent_id=root.id, blob_ref="b")  # no alt_text
    para.children.append(run.id)
    root.children.extend([heading.id, para.id, image.id])
    for n in (heading, para, run, image):
        doc.add_node(n)
    return doc


def test_remediation_ops_cover_tags_reading_order_and_alt():
    ops = accessibility.remediation_ops(_needy_doc())
    assert any(o.op == "retag" and o.target_id == "h" for o in ops)
    assert any(o.op == "update_node" and "reading_order" in o.payload for o in ops)
    assert any(o.op == "update_node" and o.payload.get("alt_text") for o in ops)


def test_remediation_is_reversible():
    doc = _needy_doc()
    orch = SemanticOrchestratorImpl(LocalNoopClient())
    patch = ReversiblePatch(
        id=new_patch_id(),
        patches=accessibility.remediation_ops(doc),
        created_at=datetime.now(UTC),
    )
    applied = orch.apply(doc, patch)
    assert "H2" in applied.nodes["h"].tags
    assert applied.nodes["img"].alt_text
    reverted = orch.revert(applied, patch)
    assert reverted.nodes["h"].tags == []
    assert reverted.nodes["img"].alt_text is None


def test_remediate_endpoint_does_not_lower_score(client, sample_docx_bytes):
    docx_mime = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    doc_id = client.post(
        "/documents", files={"file": ("d.docx", io.BytesIO(sample_docx_bytes), docx_mime)}
    ).json()["doc_id"]
    before = client.get(f"/documents/{doc_id}/health").json()["health"]["accessibility_score"]
    assert client.post(f"/documents/{doc_id}/remediate-accessibility").status_code == 200
    after = client.get(f"/documents/{doc_id}/health").json()["health"]["accessibility_score"]
    assert after >= before
