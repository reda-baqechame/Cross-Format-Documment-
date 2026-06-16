"""PDF page operations: merge, split, reorder, rotate, delete."""

from __future__ import annotations

import fitz
import pytest

from docos.services.docengine import pageops


def _pdf(labels: list[str]) -> bytes:
    doc = fitz.open()
    for label in labels:
        page = doc.new_page(width=300, height=300)
        page.insert_text((50, 50), label, fontsize=20)
    data = doc.tobytes()
    doc.close()
    return data


def _texts(pdf: bytes) -> list[str]:
    doc = fitz.open(stream=pdf, filetype="pdf")
    try:
        return [p.get_text().strip() for p in doc]
    finally:
        doc.close()


def test_page_count():
    assert pageops.page_count(_pdf(["A", "B", "C"])) == 3


def test_reorder_and_subset():
    out = pageops.reorder_pages(_pdf(["A", "B", "C"]), [2, 0])
    assert _texts(out) == ["C", "A"]


def test_delete_pages():
    out = pageops.delete_pages(_pdf(["A", "B", "C"]), [1])
    assert _texts(out) == ["A", "C"]


def test_delete_all_pages_rejected():
    with pytest.raises(ValueError):
        pageops.delete_pages(_pdf(["A"]), [0])


def test_extract_pages():
    out = pageops.extract_pages(_pdf(["A", "B", "C", "D"]), [1, 3])
    assert _texts(out) == ["B", "D"]


def test_rotate_pages():
    out = pageops.rotate_pages(_pdf(["A", "B"]), [0], 90)
    doc = fitz.open(stream=out, filetype="pdf")
    try:
        assert doc[0].rotation == 90
        assert doc[1].rotation == 0
    finally:
        doc.close()


def test_rotate_invalid_degrees():
    with pytest.raises(ValueError):
        pageops.rotate_pages(_pdf(["A"]), [0], 45)


def test_merge():
    out = pageops.merge([_pdf(["A", "B"]), _pdf(["C"])])
    assert _texts(out) == ["A", "B", "C"]


def test_out_of_range_rejected():
    with pytest.raises(ValueError):
        pageops.reorder_pages(_pdf(["A"]), [5])
