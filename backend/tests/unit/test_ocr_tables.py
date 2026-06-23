"""Conservative scanned-grid table OCR.

The geometry (row/column clustering + the anti-prose guards) is tested engine-free via the pure
helpers; the end-to-end image→table path is gated on a real Tesseract engine.
"""

from __future__ import annotations

import io

from PIL import Image, ImageDraw

from docos.model.nodes import TableNode
from docos.services.docengine.adapters.image import ocr_available
from docos.services.ocr.tesseract import (
    _cluster_rows,
    _column_anchors,
    _Word,
    build_table_nodes,
)


def test_row_clustering_groups_by_line():
    words = [
        _Word("a", 90, 0, 0, 20, 12),
        _Word("b", 90, 100, 2, 120, 14),  # same row as a
        _Word("c", 90, 0, 60, 20, 72),  # next row
        _Word("d", 90, 100, 62, 120, 74),
    ]
    rows = _cluster_rows(words)
    assert len(rows) == 2
    assert {w.text for w in rows[0]} == {"a", "b"}


def test_column_anchors_finds_two_columns():
    words = [
        _Word("a", 90, 0, 0, 20, 12),
        _Word("b", 90, 200, 0, 220, 12),
        _Word("c", 90, 2, 40, 22, 52),
        _Word("d", 90, 202, 40, 222, 52),
    ]
    anchors = _column_anchors(words)
    assert len(anchors) == 2
    assert anchors[0] < 50 and anchors[1] > 150


def test_build_table_nodes_degrades_without_engine_or_emits_table():
    img = Image.new("RGB", (400, 200), "white")
    draw = ImageDraw.Draw(img)
    for r, row in enumerate([("Name", "Age"), ("Alice", "30"), ("Bob", "41")]):
        for c, cell in enumerate(row):
            draw.text((20 + c * 200, 20 + r * 50), cell, fill="black")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    nodes = build_table_nodes(buf.getvalue(), parent_id="page-1")

    if not ocr_available():
        assert nodes == []  # no engine → clean no-op, never a faked table
        return

    tables = [n for n in nodes if isinstance(n, TableNode)]
    assert tables, "expected a table from a clear 3x2 grid"
    assert tables[0].parent_id == "page-1"
    assert tables[0].cols == 2


def test_prose_does_not_become_a_table():
    img = Image.new("RGB", (600, 120), "white")
    ImageDraw.Draw(img).text(
        (10, 40), "This is an ordinary sentence of running prose text.", fill="black"
    )
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    # Either no engine (→ []) or an engine that correctly declines to grid prose.
    assert build_table_nodes(buf.getvalue(), parent_id="page-1") == []
