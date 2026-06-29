"""Build a canonical document from a structured report, plus per-pack report adapters.

A ``GeneratedReport`` is a format-neutral description (title + sections of paragraphs and tables);
``build_document`` turns it into a node graph that any writer can render. Pack adapters
(``ap_reconciliation_report`` etc.) map a pack's findings DTO onto that neutral shape, so a single
synthesis path serves every vertical and every output format.
"""

from __future__ import annotations

from datetime import UTC, datetime

from pydantic import BaseModel, Field

from docos.model.document import CanonicalDocument, DocumentMeta
from docos.model.ids import new_doc_id, new_node_id
from docos.model.nodes import (
    HeadingNode,
    ParagraphNode,
    RootNode,
    RunNode,
    TableCellNode,
    TableNode,
    TableRowNode,
)
from docos.services.packs.contracts import ContractReport
from docos.services.packs.finance import APReport
from docos.services.packs.hr import HRReport
from docos.services.packs.import_export import PacketReport
from docos.services.packs.insurance import InsuranceReport


class ReportTable(BaseModel):
    title: str | None = None
    headers: list[str]
    rows: list[list[str]] = Field(default_factory=list)


class ReportSection(BaseModel):
    heading: str
    paragraphs: list[str] = Field(default_factory=list)
    tables: list[ReportTable] = Field(default_factory=list)


class GeneratedReport(BaseModel):
    title: str
    subtitle: str | None = None
    sections: list[ReportSection] = Field(default_factory=list)


def build_document(report: GeneratedReport) -> CanonicalDocument:
    """Render a ``GeneratedReport`` into a fresh, writer-ready :class:`CanonicalDocument`."""
    now = datetime.now(UTC)
    root = RootNode(id=new_node_id("root"))
    doc = CanonicalDocument(
        doc_id=new_doc_id(),
        root_id=root.id,
        meta=DocumentMeta(
            source_format="report",
            source_mime="application/octet-stream",
            created_at=now,
            modified_at=now,
            title=report.title,
        ),
    )
    doc.add_node(root)
    order = 0

    def _top(node) -> None:
        nonlocal order
        node.reading_order = order
        order += 1
        root.children.append(node.id)
        doc.add_node(node)

    def _text_block(node, text: str) -> None:
        run = RunNode(id=new_node_id(), parent_id=node.id, text=text)
        node.children.append(run.id)
        _top(node)
        doc.add_node(run)

    # Title + optional subtitle.
    _text_block(HeadingNode(id=new_node_id(), parent_id=root.id, level=1), report.title)
    if report.subtitle:
        _text_block(ParagraphNode(id=new_node_id(), parent_id=root.id), report.subtitle)

    for section in report.sections:
        _text_block(HeadingNode(id=new_node_id(), parent_id=root.id, level=2), section.heading)
        for para in section.paragraphs:
            _text_block(ParagraphNode(id=new_node_id(), parent_id=root.id), para)
        for table in section.tables:
            _build_table(doc, root, table, _top)

    return doc


def _build_table(doc: CanonicalDocument, root: RootNode, table: ReportTable, attach) -> None:
    """Append a table (header row + body rows) as canonical nodes."""
    grid = [table.headers, *table.rows]
    cols = max((len(r) for r in grid), default=0)
    tnode = TableNode(id=new_node_id(), parent_id=root.id, rows=len(grid), cols=cols)
    for r, cells in enumerate(grid):
        rownode = TableRowNode(id=new_node_id(), parent_id=tnode.id, row=r)
        for c in range(cols):
            value = cells[c] if c < len(cells) else ""
            cell = TableCellNode(
                id=new_node_id(), parent_id=rownode.id, row=r, col=c, header=(r == 0)
            )
            run = RunNode(id=new_node_id(), parent_id=cell.id, text=value, bold=(r == 0))
            cell.children.append(run.id)
            rownode.children.append(cell.id)
            doc.add_node(cell)
            doc.add_node(run)
        tnode.children.append(rownode.id)
        doc.add_node(rownode)
    attach(tnode)


def _findings_section(findings) -> ReportSection:
    """A severity-coded findings table (shared across all pack reports)."""
    rows = [[f.severity.upper(), f.code, f.message] for f in findings]
    if not rows:
        return ReportSection(
            heading="Findings", paragraphs=["No issues detected — the packet is consistent."]
        )
    errors = sum(1 for f in findings if f.severity == "error")
    warns = sum(1 for f in findings if f.severity == "warn")
    return ReportSection(
        heading="Findings",
        paragraphs=[f"{errors} blocking issue(s), {warns} warning(s)."],
        tables=[ReportTable(headers=["Severity", "Code", "Detail"], rows=rows)],
    )


def _money(value: float | None) -> str:
    return "" if value is None else f"{value:,.2f}"


# ── Per-pack adapters ──────────────────────────────────────────────────────────────────────────


def ap_reconciliation_report(rep: APReport) -> GeneratedReport:
    match_rows = [
        [
            m.invoice_doc_id,
            m.po_number or "—",
            m.matched_po_doc_id or "(no PO matched)",
            {True: "yes", False: "NO", None: "n/a"}[m.total_matches],
            {True: "yes", False: "NO", None: "n/a"}[m.currency_matches],
        ]
        for m in rep.matches
    ]
    doc_rows = [
        [d.doc_id, d.invoice_number or "—", d.po_number or "—", d.currency or "—", _money(d.total)]
        for d in rep.documents
    ]
    return GeneratedReport(
        title="Accounts-Payable Reconciliation",
        subtitle=rep.summary,
        sections=[
            _findings_section(rep.findings),
            ReportSection(
                heading="Invoice ↔ PO matches",
                tables=[
                    ReportTable(
                        headers=["Invoice", "PO #", "Matched PO", "Total OK", "Currency OK"],
                        rows=match_rows,
                    )
                ],
            ),
            ReportSection(
                heading="Documents",
                tables=[
                    ReportTable(
                        headers=["Doc", "Invoice #", "PO #", "Currency", "Total"], rows=doc_rows
                    )
                ],
            ),
        ],
    )


def packet_exception_report(rep: PacketReport) -> GeneratedReport:
    doc_rows = [
        [
            d.doc_id,
            d.doc_type,
            d.currency or "—",
            _money(d.total),
            d.hs_code or "—",
            d.origin or "—",
        ]
        for d in rep.documents
    ]
    checklist_rows = [[c.label, "present" if c.present else "MISSING"] for c in rep.checklist]
    return GeneratedReport(
        title="Import/Export Packet — Exception Report",
        subtitle=rep.summary,
        sections=[
            _findings_section(rep.findings),
            ReportSection(
                heading="Required documents",
                tables=[ReportTable(headers=["Document", "Status"], rows=checklist_rows)],
            ),
            ReportSection(
                heading="Extracted shipment fields",
                tables=[
                    ReportTable(
                        headers=["Doc", "Type", "Currency", "Total", "HS code", "Origin"],
                        rows=doc_rows,
                    )
                ],
            ),
        ],
    )


def contract_risk_report(rep: ContractReport) -> GeneratedReport:
    doc_rows = [
        [
            d.doc_id,
            ", ".join(d.parties) or "—",
            d.governing_law or "—",
            "yes" if d.auto_renew else "no",
            "yes" if d.has_liability_cap else "no",
        ]
        for d in rep.documents
    ]
    return GeneratedReport(
        title="Contract Risk Review",
        subtitle=rep.summary,
        sections=[
            _findings_section(rep.findings),
            ReportSection(
                heading="Contract terms",
                tables=[
                    ReportTable(
                        headers=["Doc", "Parties", "Governing law", "Auto-renew", "Liability cap"],
                        rows=doc_rows,
                    )
                ],
            ),
        ],
    )


def hr_onboarding_report(rep: HRReport) -> GeneratedReport:
    offer_rows = [
        [
            o.doc_id,
            o.role or "—",
            o.start_date or "—",
            o.compensation or "—",
            o.employment_type or "—",
        ]
        for o in rep.offers
    ]
    checklist_rows = [[c.label, "present" if c.present else "MISSING"] for c in rep.checklist]
    return GeneratedReport(
        title="HR Onboarding — Completeness Report",
        subtitle=rep.summary,
        sections=[
            _findings_section(rep.findings),
            ReportSection(
                heading="Onboarding packet",
                tables=[ReportTable(headers=["Document", "Status"], rows=checklist_rows)],
            ),
            ReportSection(
                heading="Offer details",
                tables=[
                    ReportTable(
                        headers=["Doc", "Role", "Start", "Compensation", "Type"], rows=offer_rows
                    )
                ],
            ),
        ],
    )


def insurance_review_report(rep: InsuranceReport) -> GeneratedReport:
    doc_rows = [
        [
            d.doc_id,
            d.kind,
            d.policy_number or d.claim_number or "—",
            _money(d.coverage_limit),
            d.effective_date or "—",
            d.expiration_date or "—",
        ]
        for d in rep.documents
    ]
    return GeneratedReport(
        title="Insurance Policy / Claim Review",
        subtitle=rep.summary,
        sections=[
            _findings_section(rep.findings),
            ReportSection(
                heading="Policies & claims",
                tables=[
                    ReportTable(
                        headers=["Doc", "Kind", "Number", "Coverage", "Effective", "Expires"],
                        rows=doc_rows,
                    )
                ],
            ),
        ],
    )
