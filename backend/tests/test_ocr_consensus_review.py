"""Parser mesh + HITL: OCR consensus routing, source-engine provenance, and the review queue."""

from __future__ import annotations

from datetime import UTC, datetime

from docos.model.document import CanonicalDocument, DocumentMeta
from docos.model.geometry import BBox
from docos.model.ids import new_doc_id, new_node_id
from docos.model.nodes import ParagraphNode, RootNode, RunNode
from docos.services.ocr.consensus import ConsensusOcr
from docos.services.ocr.interface import OcrStructureService
from docos.services.semantic.review import build_review_queue


class _FakeEngine(OcrStructureService):
    """An engine that returns one word at a fixed confidence — for routing tests."""

    def __init__(self, text: str, conf: float) -> None:
        self._text, self._conf = text, conf

    def cleanup(self, image):
        return image

    def recognize(self, image):
        return [
            RunNode(
                id=new_node_id(),
                text=self._text,
                bbox=BBox(x0=0, y0=0, x1=10, y1=10),
                attrs={"confidence": self._conf, "source_engine": "fake"},
            )
        ]

    def extract_tables(self, image):
        return []

    def infer_reading_order(self, nodes):
        return [n.id for n in nodes]


def test_consensus_keeps_higher_confidence_engine():
    low = _FakeEngine("rnistake", 40.0)
    high = _FakeEngine("correct", 95.0)
    consensus = ConsensusOcr([low, high])
    runs = consensus.recognize(b"img")
    assert len(runs) == 1 and runs[0].text == "correct"


def test_consensus_single_engine_is_passthrough():
    only = _FakeEngine("hello", 88.0)
    assert ConsensusOcr([only]).recognize(b"img")[0].text == "hello"


def _doc_with_runs(*specs: tuple[str, dict]) -> CanonicalDocument:
    now = datetime.now(UTC)
    root = RootNode(id=new_node_id("root"))
    doc = CanonicalDocument(
        doc_id=new_doc_id(),
        root_id=root.id,
        meta=DocumentMeta(
            source_format="png", source_mime="image/png", created_at=now, modified_at=now
        ),
    )
    doc.add_node(root)
    for i, (text, attrs) in enumerate(specs):
        p = ParagraphNode(id=new_node_id(), parent_id=root.id, reading_order=i)
        r = RunNode(id=new_node_id(), parent_id=p.id, text=text, attrs=attrs)
        p.children.append(r.id)
        root.children.append(p.id)
        doc.add_node(p)
        doc.add_node(r)
    return doc


def test_review_queue_lists_low_confidence_ocr_only():
    doc = _doc_with_runs(
        ("blurry", {"confidence": 35.0, "ocr_review": True, "source_engine": "tesseract"}),
        ("crisp", {"confidence": 99.0, "ocr_review": False, "source_engine": "tesseract"}),
        ("not-ocr", {}),  # no confidence attr → not an OCR run, never queued
    )
    queue = build_review_queue(doc)
    ocr_items = [i for i in queue.items if i.kind == "ocr"]
    assert len(ocr_items) == 1
    assert ocr_items[0].value == "blurry"
    assert ocr_items[0].source_engine == "tesseract"


def test_review_queue_skips_redacted_low_confidence_text():
    doc = _doc_with_runs(
        ("secret", {"confidence": 20.0, "ocr_review": True, "source_engine": "tesseract"}),
    )
    secret_run = next(n.id for n in doc.nodes.values() if getattr(n, "text", "") == "secret")
    doc.redaction.redacted_node_ids.append(secret_run)
    assert [i for i in build_review_queue(doc).items if i.kind == "ocr"] == []


def test_review_items_endpoint_is_owner_scoped(client):
    doc_id = client.post(
        "/documents",
        files={"file": ("a.txt", b"Invoice number: INV-1\nTotal due: 9.00 USD", "text/plain")},
    ).json()["doc_id"]
    res = client.get(f"/documents/{doc_id}/review-items")
    assert res.status_code == 200
    body = res.json()
    assert body["doc_id"] == doc_id and "items" in body and "ocr_floor" in body
