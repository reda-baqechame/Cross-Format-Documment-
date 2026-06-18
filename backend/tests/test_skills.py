"""Unit tests for the Document Skills framework + Autopilot."""

from __future__ import annotations

from docos.services.docengine.registry import default_registry
from docos.services.semantic.skills.autopilot import analyze
from docos.services.semantic.skills.invoice import InvoiceSkill
from docos.services.semantic.skills.registry import select_skill
from docos.services.semantic.skills.resume import ResumeSkill
from docos.services.semantic.skills.taxonomy import CATEGORY_LABELS, classify_purpose


def _doc(text: str):
    return default_registry().resolve("text/plain").parse(text.encode())


INVOICE = (
    "ACME Supplies\n\n"
    "Invoice Number: INV-1042\n"
    "Invoice Date: 2026-01-15\n"
    "Due Date: 2026-02-15\n"
    "Bill To: Globex Inc\n\n"
    "Subtotal: $1,000.00\n"
    "Tax: $100.00\n"
    "Total Due: $1,100.00\n"
)

INVOICE_BAD_TOTALS = INVOICE.replace("Total Due: $1,100.00", "Total Due: $9,999.00")

RESUME = (
    "Jane Doe\njane@example.com\n(415) 555-1212\n\n"
    "Experience\nSenior Engineer\n\nEducation\nBSc Computer Science\n\nSkills\nPython, Go\n"
)

CONTRACT = (
    "Service Agreement\n\n"
    "This agreement is by and between Acme and Globex. The parties hereby agree.\n"
    "This contract shall automatically renew for successive one-year terms.\n"
)


def test_taxonomy_loads_15_categories_and_classifies():
    assert len(CATEGORY_LABELS) == 15
    dt, conf, signals = classify_purpose(INVOICE.lower())
    assert dt is not None and dt.category == "financial"
    assert conf > 0 and signals


def test_invoice_skill_selected_and_extracts():
    doc = _doc(INVOICE)
    skill, dt, conf, _ = select_skill(doc)
    assert isinstance(skill, InvoiceSkill)
    assert dt is not None and dt.id == "invoice"
    by_name = {f.name: f for f in skill.extract(doc)}
    assert by_name["invoice_number"].value == "INV-1042"
    assert by_name["total"].status == "found"


def test_invoice_totals_mismatch_fails():
    report = analyze(_doc(INVOICE_BAD_TOTALS))
    assert report.type_id == "invoice"
    assert any(f.code == "totals.mismatch" and f.level == "fail" for f in report.findings)
    assert report.needs_review is True
    # Recommends exporting to Excel — the AP next action.
    assert any(a.kind == "export" and a.params.get("format") == "xlsx" for a in report.actions)


def test_invoice_totals_match_passes():
    report = analyze(_doc(INVOICE))
    assert any(f.code == "totals.match" and f.level == "pass" for f in report.findings)


def test_resume_skill():
    doc = _doc(RESUME)
    skill, dt, _, _ = select_skill(doc)
    assert isinstance(skill, ResumeSkill)
    by_name = {f.name: f for f in skill.extract(doc)}
    assert by_name["email"].value == "jane@example.com"


def test_contract_auto_renewal_warning():
    report = analyze(_doc(CONTRACT))
    assert report.type_id in {"contract", "nda", "employment_agreement", "lease"}
    assert any(f.code == "contract.auto_renewal" for f in report.findings)


def test_generic_fallback_for_recognized_but_undeep_type():
    sow = (
        "Statement of Work\n\nMilestones and deliverables are described below.\n"
        "Acceptance criteria apply.\n"
    )
    report = analyze(_doc(sow))
    assert report.deep is True
    assert report.category == "Sales"
    assert report.type == "Statement of work"
    assert any(f.code == "deliverables.present" for f in report.findings)
    assert any(f.code == "acceptance.present" for f in report.findings)
    assert report.actions


def test_autopilot_recognizes_pasted_form_and_visual_subtypes():
    incident = analyze(
        _doc(
            "Incident Form\n"
            "Date of incident: 2026-06-18\n"
            "Location: Warehouse B\n"
            "Reported by: Jane\n"
        )
    )
    assert incident.category == "Forms"
    assert incident.type_id == "incident_form"
    assert incident.type == "Incident form"

    dashboard = analyze(
        _doc("Operations Dashboard\nKPI: cycle time\nMetric: 82%\nTrend: up this quarter\n")
    )
    assert dashboard.category == "Presentation"
    assert dashboard.type_id == "dashboard"
    assert dashboard.type == "Dashboard"


def test_unrecognized_document_is_still_usable():
    report = analyze(_doc("zzzz qqqq wwww\n\nnothing matches here\n"))
    assert report.deep is False
    assert report.actions  # universal actions always present
    assert report.needs_review is False
