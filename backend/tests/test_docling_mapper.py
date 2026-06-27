"""Unit tests for the Docling → canonical mapper (no native Docling dependency required).

The mapper consumes the stable ``DoclingDocument.export_to_dict()`` shape, so we exercise it against
a recorded payload to lock down headings, paragraphs, real table structure, reading order, and the
``parsed_by=docling`` provenance marker — all without installing Docling.
"""

from __future__ import annotations

from docos.services.docengine.adapters.docling import (
    docling_available,
    docling_dict_to_canonical,
    parse_with_docling,
)

_SAMPLE = {
    "name": "Quarterly Report",
    "texts": [
        {"self_ref": "#/texts/0", "label": "title", "text": "Quarterly Report"},
        {"self_ref": "#/texts/1", "label": "paragraph", "text": "Revenue grew this quarter."},
        {"self_ref": "#/texts/2", "label": "list_item", "text": "North region up 12%"},
    ],
    "tables": [
        {
            "self_ref": "#/tables/0",
            "data": {
                "num_rows": 2,
                "num_cols": 2,
                "table_cells": [
                    {"text": "Item", "start_row_offset_idx": 0, "start_col_offset_idx": 0,
                     "column_header": True},
                    {"text": "Qty", "start_row_offset_idx": 0, "start_col_offset_idx": 1,
                     "column_header": True},
                    {"text": "Widget", "start_row_offset_idx": 1, "start_col_offset_idx": 0},
                    {"text": "10", "start_row_offset_idx": 1, "start_col_offset_idx": 1},
                ],
            },
        }
    ],
    "pictures": [{"self_ref": "#/pictures/0"}],
    "body": {
        "children": [
            {"$ref": "#/texts/0"},
            {"$ref": "#/texts/1"},
            {"$ref": "#/texts/2"},
            {"$ref": "#/tables/0"},
            {"$ref": "#/pictures/0"},
        ]
    },
}


def test_maps_headings_paragraphs_and_provenance():
    doc = docling_dict_to_canonical(_SAMPLE, source_format="pdf", source_mime="application/pdf")
    assert doc.meta.source_format == "pdf"
    assert doc.meta.source_mime == "application/pdf"
    assert doc.meta.custom["parsed_by"] == "docling"

    headings = [n for n in doc.nodes.values() if n.type == "heading"]
    assert len(headings) == 1 and headings[0].level == 1
    runs = {n.text for n in doc.nodes.values() if n.type == "run"}
    assert "Quarterly Report" in runs
    assert "Revenue grew this quarter." in runs

    # The list_item text becomes a tagged paragraph.
    paras = [n for n in doc.nodes.values() if n.type == "paragraph"]
    assert any("list_item" in p.tags for p in paras)


def test_maps_real_table_structure():
    doc = docling_dict_to_canonical(_SAMPLE, source_format="pdf", source_mime="application/pdf")
    tables = [n for n in doc.nodes.values() if n.type == "table"]
    assert len(tables) == 1
    table = tables[0]
    assert (table.rows, table.cols) == (2, 2)

    cells = [n for n in doc.nodes.values() if n.type == "table_cell"]
    assert len(cells) == 4
    headers = [c for c in cells if c.header]
    assert len(headers) == 2  # the two column-header cells
    cell_texts = {
        n.text for n in doc.nodes.values() if n.type == "run" and n.text in {"Item", "Qty", "10"}
    }
    assert {"Item", "Qty", "10"}.issubset(cell_texts)


def test_reading_order_follows_body():
    doc = docling_dict_to_canonical(_SAMPLE, source_format="pdf", source_mime="application/pdf")
    top_level = [doc.nodes[cid] for cid in doc.nodes[doc.root_id].children]
    orders = [n.reading_order for n in top_level]
    assert orders == sorted(orders)  # monotonic in document order
    # An image placeholder is kept for the picture so layout slots are preserved.
    assert any(n.type == "image" for n in top_level)


def test_parse_with_docling_uses_injected_converter():
    doc = parse_with_docling(
        b"ignored-bytes",
        source_format="docx",
        source_mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        convert_fn=lambda _data: _SAMPLE,
    )
    assert doc.meta.source_format == "docx"
    assert any(n.type == "table" for n in doc.nodes.values())


def test_docling_absent_by_default():
    # Docling is an optional extra; it is not part of the default/CI environment.
    assert docling_available() is False
