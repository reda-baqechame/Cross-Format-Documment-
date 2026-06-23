"""Tesseract-backed OCR & structure service.

Turns a scanned image into *positioned* text — word-level :class:`RunNode`s carrying a bounding
box and a confidence score — rather than a flat string. Low-confidence words are tagged
(``attrs["ocr_review"]``) so they're flagged for review, never silently trusted. Reading order is
inferred geometrically (top-to-bottom, then left-to-right).

Scanned-grid tables are detected conservatively (:func:`build_table_nodes`): a :class:`TableNode`
subtree is emitted only when the words form a clear, full-page grid (≥2 rows × ≥2 aligned columns
where most words participate), so prose is never mangled into a garbled table.

Engine-agnostic and best-effort: it uses ``pytesseract.image_to_data`` when available and degrades
to ``[]`` when no Tesseract engine / language data is present, so callers can always fall back.
"""

from __future__ import annotations

import io
from dataclasses import dataclass

from docos.model.geometry import BBox
from docos.model.ids import new_node_id
from docos.model.nodes import (
    BaseNode,
    RunNode,
    TableCellNode,
    TableNode,
    TableRowNode,
)
from docos.services.ocr.interface import OcrStructureService

# Below this Tesseract confidence (0–100) a word is tagged for human review.
_REVIEW_BELOW = 60.0
# Reading-order row bucketing tolerance (px) so words on the same line group together.
_ROW_TOLERANCE = 12.0
# A grid is only emitted when at least this fraction of recognised words land in it — the guard
# that keeps prose pages (which form one ragged column) from being misread as tables.
_GRID_COVERAGE = 0.7


@dataclass
class _Word:
    text: str
    conf: float
    x0: float
    y0: float
    x1: float
    y1: float

    @property
    def cy(self) -> float:
        return (self.y0 + self.y1) / 2


def _image_to_words(image: bytes, languages: str) -> list[_Word]:
    """Recognise words with boxes + confidence. ``[]`` when no Tesseract engine is available."""
    try:
        import pytesseract
        from PIL import Image

        pytesseract.get_tesseract_version()  # raises if the binary is missing
    except Exception:  # noqa: BLE001 - OCR is optional; degrade to no structured output
        return []
    try:
        img = Image.open(io.BytesIO(image))
        data = pytesseract.image_to_data(img, lang=languages, output_type=pytesseract.Output.DICT)
    except Exception:  # noqa: BLE001 - a recognition failure is non-fatal
        return []

    words: list[_Word] = []
    for i, text in enumerate(data.get("text", [])):
        word = (text or "").strip()
        if not word:
            continue
        try:
            conf = float(data["conf"][i])
        except (KeyError, ValueError, IndexError):
            conf = -1.0
        if conf < 0:  # Tesseract emits -1 for non-text regions
            continue
        x, y = float(data["left"][i]), float(data["top"][i])
        w, h = float(data["width"][i]), float(data["height"][i])
        words.append(_Word(word, conf, x, y, x + w, y + h))
    return words


def _cluster_rows(words: list[_Word]) -> list[list[_Word]]:
    """Group words into visual rows by vertical position."""
    rows: list[list[_Word]] = []
    for w in sorted(words, key=lambda w: w.cy):
        if rows and abs(w.cy - rows[-1][0].cy) <= _ROW_TOLERANCE:
            rows[-1].append(w)
        else:
            rows.append([w])
    return rows


def _column_anchors(words: list[_Word]) -> list[float]:
    """Cluster word left-edges into column anchors (a new column when the x-gap is large)."""
    if not words:
        return []
    widths = sorted(w.x1 - w.x0 for w in words)
    med_w = widths[len(widths) // 2] or 1.0
    gap = med_w * 1.5  # generous horizontal gap between distinct columns
    lefts = sorted(w.x0 for w in words)
    anchors: list[float] = []
    cluster = [lefts[0]]
    for left in lefts[1:]:
        if left - cluster[-1] > gap:
            anchors.append(sum(cluster) / len(cluster))
            cluster = [left]
        else:
            cluster.append(left)
    anchors.append(sum(cluster) / len(cluster))
    return anchors


def build_table_nodes(image: bytes, *, parent_id: str, languages: str = "eng") -> list[BaseNode]:
    """Detect a tabular grid and return its flat node subtree (table → rows → cells → runs).

    Returns ``[]`` unless the words form a confident, full-page grid: ≥2 rows, ≥2 aligned columns,
    every column populated across ≥2 rows, most rows spanning ≥2 columns, and ≥70% of all words
    participating. The flat list is ready to add straight into a document.
    """
    words = _image_to_words(image, languages)
    if len(words) < 4:
        return []
    rows = _cluster_rows(words)
    anchors = _column_anchors(words)
    if len(rows) < 2 or len(anchors) < 2:
        return []

    def col_of(w: _Word) -> int:
        return min(range(len(anchors)), key=lambda c: abs(w.x0 - anchors[c]))

    grid: dict[tuple[int, int], list[_Word]] = {}
    for ri, row in enumerate(rows):
        for w in row:
            grid.setdefault((ri, col_of(w)), []).append(w)

    # Consistency guards against ragged prose masquerading as a grid.
    cols_in_two_rows = sum(
        1 for ci in range(len(anchors)) if len({ri for (ri, c) in grid if c == ci}) >= 2
    )
    rows_multi_col = sum(
        1 for ri in range(len(rows)) if len({ci for (r, ci) in grid if r == ri}) >= 2
    )
    if cols_in_two_rows < len(anchors):
        return []
    if rows_multi_col < max(2, int(len(rows) * 0.6)):
        return []
    in_grid = sum(len(ws) for ws in grid.values())
    if in_grid < _GRID_COVERAGE * len(words):
        return []

    table = TableNode(
        id=new_node_id(), parent_id=parent_id, rows=len(rows), cols=len(anchors), reading_order=1
    )
    out: list[BaseNode] = [table]
    for ri in range(len(rows)):
        rnode = TableRowNode(id=new_node_id(), parent_id=table.id, row=ri, reading_order=ri)
        table.children.append(rnode.id)
        out.append(rnode)
        for ci in range(len(anchors)):
            cell_words = sorted(grid.get((ri, ci), []), key=lambda w: w.x0)
            text = " ".join(w.text for w in cell_words)
            conf = min((w.conf for w in cell_words), default=100.0)
            cnode = TableCellNode(id=new_node_id(), parent_id=rnode.id, row=ri, col=ci)
            xs = [w.x0 for w in cell_words] + [w.x1 for w in cell_words]
            ys = [w.y0 for w in cell_words] + [w.y1 for w in cell_words]
            run = RunNode(
                id=new_node_id(),
                parent_id=cnode.id,
                text=text,
                bbox=BBox(x0=min(xs), y0=min(ys), x1=max(xs), y1=max(ys)) if cell_words else None,
                attrs={"confidence": round(conf, 1), "ocr_review": conf < _REVIEW_BELOW},
            )
            cnode.children.append(run.id)
            rnode.children.append(cnode.id)
            out.extend([cnode, run])
    return out


class TesseractOcr(OcrStructureService):
    def __init__(self, languages: str = "eng") -> None:
        self.languages = languages

    def cleanup(self, image: bytes) -> bytes:
        """Grayscale + autocontrast to improve recognition; returns PNG bytes."""
        from PIL import Image, ImageOps

        img = Image.open(io.BytesIO(image))
        img = ImageOps.autocontrast(ImageOps.grayscale(img))
        out = io.BytesIO()
        img.save(out, format="PNG")
        return out.getvalue()

    def recognize(self, image: bytes) -> list[RunNode]:
        """Recognise word-level text spans with bounding boxes + confidence.

        Returns ``[]`` when no Tesseract engine is available (callers fall back to flat text or to
        ingesting the image without recovered text).
        """
        runs: list[RunNode] = []
        for w in _image_to_words(image, self.languages):
            runs.append(
                RunNode(
                    id=new_node_id(),
                    text=w.text,
                    bbox=BBox(x0=w.x0, y0=w.y0, x1=w.x1, y1=w.y1),
                    attrs={"confidence": round(w.conf, 1), "ocr_review": w.conf < _REVIEW_BELOW},
                )
            )
        return runs

    def extract_tables(self, image: bytes) -> list[TableNode]:
        """Conservative scanned-grid detection (see :func:`build_table_nodes`).

        Returns the detected :class:`TableNode` roots; the full subtree (rows/cells/runs) is built
        by ``build_table_nodes`` and consumed directly by the image adapter.
        """
        return [n for n in build_table_nodes(image, parent_id="") if isinstance(n, TableNode)]

    def infer_reading_order(self, nodes: list[BaseNode]) -> list[str]:
        """Top-to-bottom, then left-to-right, bucketing words onto rows by y position."""

        def key(node: BaseNode) -> tuple[float, float]:
            box = getattr(node, "bbox", None)
            if box is None:
                return (0.0, 0.0)
            return (round(box.y0 / _ROW_TOLERANCE), box.x0)

        return [n.id for n in sorted(nodes, key=key)]
