"""Redaction enforcement shared by every writer.

The product promise is that redaction *removes* content, not merely hides it. Every
export path runs run text through :func:`run_text`, so redacted text never reaches
the exported bytes — a node is redacted if it (or any ancestor) is marked redacted.
"""

from __future__ import annotations

from urllib.parse import urlparse

from docos.model.document import CanonicalDocument
from docos.model.nodes import AnyNode

# Leading chars a spreadsheet may treat as a formula. Includes tab and CR (OWASP CSV-injection
# vectors that some apps strip before evaluating the next char).
_SPREADSHEET_FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")
_SAFE_LINK_SCHEMES = {"http", "https", "mailto", "tel"}


def is_redacted(doc: CanonicalDocument, node_id: str | None) -> bool:
    """True if ``node_id`` or any of its ancestors is in the redaction set."""
    redacted = doc.redaction.redacted_node_ids
    if not redacted:
        return False
    seen: set[str] = set()
    current = node_id
    while current and current not in seen:
        if current in redacted:
            return True
        seen.add(current)
        node = doc.nodes.get(current)
        current = node.parent_id if node else None
    return False


def run_text(doc: CanonicalDocument, node: AnyNode) -> str:
    """The exportable text of a run — empty when redacted (true removal)."""
    if is_redacted(doc, node.id):
        return ""
    return getattr(node, "text", "")


def node_text(doc: CanonicalDocument, node: AnyNode) -> str:
    """Exportable text for any text-bearing node, honoring redaction."""
    if is_redacted(doc, node.id):
        return ""
    if node.type == "field":
        return getattr(node, "value", None) or ""
    if node.type == "image":
        return getattr(node, "alt_text", None) or ""
    return getattr(node, "text", "")


def spreadsheet_text(value: str) -> str:
    """Neutralize spreadsheet formulas in exported CSV/XLSX cells."""
    if value and value[0] in _SPREADSHEET_FORMULA_PREFIXES:
        return "'" + value
    return value


def safe_link_href(href: str | None) -> str | None:
    """Return a link href only when its scheme is safe for exported files."""
    if href is None:
        return None
    cleaned = href.strip()
    if not cleaned:
        return None
    if cleaned.startswith(("#", "/", "./", "../")):
        return cleaned
    parsed = urlparse(cleaned)
    if parsed.scheme.lower() in _SAFE_LINK_SCHEMES:
        return cleaned
    return None
