"""Typed document intelligence — analyzers over the canonical model."""

from __future__ import annotations

from datetime import UTC, datetime

from docos.model.document import CanonicalDocument, DocumentMeta
from docos.model.nodes import (
    FieldNode,
    HeadingNode,
    PageNode,
    ParagraphNode,
    RootNode,
    RunNode,
)
from docos.services.semantic import intelligence


def _doc(texts: list[str]) -> CanonicalDocument:
    now = datetime.now(UTC)
    root = RootNode(id="root")
    d = CanonicalDocument(
        doc_id="d",
        root_id=root.id,
        meta=DocumentMeta(
            source_format="txt",
            source_mime="text/plain",
            created_at=now,
            modified_at=now,
            page_count=1,
        ),
    )
    d.add_node(root)
    for i, t in enumerate(texts):
        para = ParagraphNode(id=f"p{i}", parent_id=root.id, reading_order=i)
        run = RunNode(id=f"r{i}", parent_id=para.id, text=t)
        para.children.append(run.id)
        root.children.append(para.id)
        d.add_node(para)
        d.add_node(run)
    return d


def _doc_root() -> CanonicalDocument:
    now = datetime.now(UTC)
    root = RootNode(id="root")
    d = CanonicalDocument(
        doc_id="d",
        root_id=root.id,
        meta=DocumentMeta(
            source_format="txt",
            source_mime="text/plain",
            created_at=now,
            modified_at=now,
            page_count=1,
        ),
    )
    d.add_node(root)
    return d


def _check(insight, check_id):
    return next(c for c in insight.checks if c.id == check_id)


def test_invoice_totals_reconcile_passes_when_math_adds_up():
    doc = _doc(
        [
            "INVOICE",
            "Invoice Number: INV-2026-044",
            "Due Date: 2026-04-01",
            "Subtotal: $100.00",
            "Tax: $10.00",
            "Total Due: $110.00",
        ]
    )
    insight = intelligence.analyze(doc)
    assert insight.doc_type == "invoice"
    assert _check(insight, "totals_reconcile").passed is True
    assert _check(insight, "has_total").passed is True
    assert _check(insight, "has_invoice_number").passed is True


def test_invoice_totals_reconcile_flags_mismatch():
    doc = _doc(
        [
            "INVOICE",
            "Subtotal: $100.00",
            "Tax: $10.00",
            "Total Due: $200.00",  # wrong on purpose
        ]
    )
    insight = intelligence.analyze(doc)
    check = _check(insight, "totals_reconcile")
    assert check.passed is False
    assert check.severity == "error"
    assert "200.00" in check.detail


def test_invoice_redacted_total_fails_its_check():
    doc = _doc(["INVOICE", "Bill To: Acme", "Total Due: $110.00"])
    # redact the only monetary line — a redaction-aware reader must not see it
    doc.redaction.redacted_node_ids.append("r2")
    insight = intelligence.analyze(doc)
    assert _check(insight, "has_total").passed is False


def test_resume_missing_email_is_an_error():
    doc = _doc(
        [
            "Jane Doe",
            "Experience: Senior Engineer at Globex 2019-2024",
            "Education: B.Sc Computer Science",
            "Skills: Python, FastAPI",
        ]
    )
    insight = intelligence.analyze(doc)
    assert insight.doc_type == "resume"
    assert _check(insight, "has_email").passed is False
    assert _check(insight, "has_email").severity == "error"
    assert _check(insight, "section_experience").passed is True


def test_contract_missing_clause_is_flagged_and_risk_detected():
    doc = _doc(
        [
            "SERVICES AGREEMENT",
            "This agreement is made by and between Acme and Beta.",
            "The parties hereby agree to unlimited liability for all damages.",
            "Signature: ____________",
        ]
    )
    insight = intelligence.analyze(doc)
    assert insight.doc_type == "contract"
    # no confidentiality language present -> clause check fails
    assert _check(insight, "clause_confidentiality").passed is False
    # risky language present -> the "no unlimited liability" guard fails
    assert _check(insight, "no_unlimited_liability").passed is False
    assert _check(insight, "clause_signature").passed is True


def test_generic_fallback_for_plain_text():
    doc = _doc(["Just a note.", "Meeting on 2026-05-01 about nothing in particular."])
    insight = intelligence.analyze(doc)
    # not one of the typed kinds; still returns a usable insight
    assert _check(insight, "found_date").passed is True


def test_form_flags_blank_fields():
    d = _doc_root()
    root = d.get("root")
    para = ParagraphNode(id="p0", parent_id="root", reading_order=0)
    run = RunNode(
        id="r0", parent_id="p0", text="Please fill this applicant form. Signature required."
    )
    para.children.append(run.id)
    root.children.append(para.id)
    d.add_node(para)
    d.add_node(run)
    f1 = FieldNode(
        id="f1", parent_id="root", reading_order=1, field_name="Full name", value="Jane Doe"
    )
    f2 = FieldNode(
        id="f2", parent_id="root", reading_order=2, field_name="Date of birth", value=None
    )
    root.children.extend([f1.id, f2.id])
    d.add_node(f1)
    d.add_node(f2)

    insight = intelligence.analyze(d)
    assert insight.doc_type == "form"
    assert _check(insight, "has_fields").passed is True
    assert _check(insight, "all_required_filled").passed is False
    assert "Date of birth" in _check(insight, "all_required_filled").detail


def test_form_redacted_field_value_not_leaked():
    d = _doc_root()
    root = d.get("root")
    para = ParagraphNode(id="p0", parent_id="root", reading_order=0)
    run = RunNode(id="r0", parent_id="p0", text="Applicant form — please fill and signature.")
    para.children.append(run.id)
    root.children.append(para.id)
    d.add_node(para)
    d.add_node(run)
    f1 = FieldNode(
        id="f1", parent_id="root", reading_order=1, field_name="SSN", value="123-45-6789"
    )
    root.children.append(f1.id)
    d.add_node(f1)
    d.redaction.redacted_node_ids.append("f1")

    insight = intelligence.analyze(d)
    assert all("123-45-6789" not in fld.value for fld in insight.fields)


def test_presentation_pitch_deck_checklist():
    d = _doc_root()
    root = d.get("root")

    def add_slide(i: int, title: str, body: str) -> None:
        page = PageNode(
            id=f"pg{i}", parent_id="root", reading_order=i, page_number=i, width=720, height=540
        )
        h = HeadingNode(id=f"h{i}", parent_id=page.id, reading_order=0, level=1)
        hr = RunNode(id=f"hr{i}", parent_id=h.id, text=title)
        h.children.append(hr.id)
        p = ParagraphNode(id=f"pp{i}", parent_id=page.id, reading_order=1)
        pr = RunNode(id=f"ppr{i}", parent_id=p.id, text=body)
        p.children.append(pr.id)
        page.children.extend([h.id, p.id])
        root.children.append(page.id)
        for n in (page, h, hr, p, pr):
            d.add_node(n)

    add_slide(0, "Acme — Investor Pitch", "Seed round, raising $2M. TAM is huge.")
    add_slide(1, "Agenda", "What we'll cover today.")
    add_slide(2, "Problem", "Customers waste hours.")
    add_slide(3, "Solution", "Our product fixes it.")
    add_slide(4, "Team", "Founders ex-Google.")
    add_slide(5, "Thank you", "Q&A")

    insight = intelligence.analyze(d)
    assert insight.doc_type == "presentation"
    assert _check(insight, "has_title_slide").passed is True
    assert _check(insight, "has_agenda_or_closing").passed is True
    # pitch language present -> deck checklist is scored
    assert _check(insight, "deck_has_problem").passed is True
    assert _check(insight, "deck_has_market").passed is True  # "tam"
    assert _check(insight, "deck_has_ask").passed is True  # "raising"
    # no business-model/pricing content -> that check fails
    assert _check(insight, "deck_has_model").passed is False
