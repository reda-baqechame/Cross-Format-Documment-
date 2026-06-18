"""Document classification — a lightweight, deterministic document-type detector.

Keyword-signal scoring over the canonical model's text. Offline and explainable (it
returns the signals that fired), it covers the common business document types; an LLM
classifier can be layered on later for finer categories.
"""

from __future__ import annotations

from pydantic import BaseModel

from docos.model.document import CanonicalDocument
from docos.services.docengine.writers.redaction import is_redacted

# category -> signal keywords (lowercased, substring match on the document text)
_SIGNALS: dict[str, tuple[str, ...]] = {
    "invoice": ("invoice", "amount due", "total due", "subtotal", "bill to", "due date"),
    "receipt": ("receipt", "thank you for your", "cashier", "change due", "card ending"),
    "contract": ("agreement", "hereby", "the parties", "shall", "terms and conditions", "whereas"),
    "resume": ("experience", "education", "skills", "curriculum vitae", "résumé", "resume"),
    "proposal": ("proposal", "we propose", "deliverables", "scope", "pricing", "timeline"),
    "sow": ("statement of work", "sow", "milestones", "acceptance criteria", "deliverables"),
    "sop": ("standard operating procedure", "sop", "procedure", "purpose", "scope"),
    "financial_statement": (
        "balance sheet",
        "income statement",
        "cash flow",
        "assets",
        "liabilities",
    ),
    "shipping_document": ("bill of lading", "packing list", "customs", "certificate of origin"),
    "real_estate": ("purchase agreement", "lease", "property", "inspection", "closing"),
    "letter": ("dear ", "sincerely", "best regards", "yours truly"),
    "report": ("introduction", "summary", "conclusion", "methodology", "findings"),
    "application_form": ("application form", "applicant", "date of birth", "please complete"),
    "registration_form": ("registration form", "register", "attendee", "participant"),
    "contact_form": ("contact form", "name", "email", "phone", "message"),
    "order_form": ("order form", "quantity", "unit price", "ship to", "total"),
    "feedback_form": ("feedback form", "feedback", "rating", "comments"),
    "survey": ("survey", "questionnaire", "please rate", "strongly agree"),
    "consent_form": ("consent", "i agree", "i authorize", "i consent"),
    "intake_form": ("intake form", "patient", "client information", "emergency contact"),
    "booking_form": ("booking form", "reservation", "appointment", "preferred date"),
    "evaluation_form": ("evaluation form", "score", "rating", "criteria"),
    "inspection_form": ("inspection", "inspector", "condition", "pass", "fail"),
    "checklist": ("checklist", "checklist item", "completed", "done"),
    "timesheet": ("timesheet", "hours", "employee", "week ending"),
    "expense_form": ("expense", "reimbursement", "receipt attached", "amount"),
    "incident_form": ("incident", "date of incident", "location", "reported by"),
    "request_form": ("request form", "requested by", "request type", "reason"),
    "approval_form": ("approval", "approver", "approved by", "decision"),
    "form": ("please fill", "signature", "date of birth", "checkbox", "applicant"),
    "pitch_deck": ("pitch deck", "investor", "market size", "traction", "the ask", "raising"),
    "sales_presentation": (
        "sales presentation",
        "customer pain",
        "benefits",
        "pricing",
        "case study",
    ),
    "training_presentation": ("training", "learning objectives", "module", "quiz", "exercise"),
    "webinar_slides": ("webinar", "speaker", "agenda", "q&a", "call to action"),
    "infographic": ("infographic", "key statistic", "data source", "visual"),
    "poster": ("poster", "event", "date", "location", "call to action"),
    "flyer": ("flyer", "offer", "contact", "call to action"),
    "brochure": ("brochure", "features", "benefits", "contact", "about us"),
    "one_page_summary": ("one-page summary", "overview", "key points", "next steps"),
    "dashboard": ("dashboard", "kpi", "metric", "trend", "status"),
    "flowchart": ("flowchart", "start", "decision", "process", "end"),
    "mind_map": ("mind map", "topic", "branch", "idea"),
    "org_chart": ("organizational chart", "org chart", "reports to", "department"),
    "diagram": ("diagram", "legend", "component", "relationship"),
    "roadmap": ("roadmap", "milestone", "quarter", "timeline", "phase"),
    "timeline": ("timeline", "milestone", "date", "phase"),
    "presentation": ("agenda", "next steps", "thank you", "slide", "q&a", "our mission"),
}


class Classification(BaseModel):
    label: str
    confidence: float
    signals: list[str]


def _document_text(doc: CanonicalDocument) -> str:
    parts = [
        getattr(n, "text", "")
        for n in doc.walk()
        if getattr(n, "text", "") and not is_redacted(doc, n.id)
    ]
    return "\n".join(parts).lower()


def classify(doc: CanonicalDocument) -> Classification:
    text = _document_text(doc)
    scores: dict[str, list[str]] = {}
    for label, keywords in _SIGNALS.items():
        hits = [k for k in keywords if k in text]
        if hits:
            scores[label] = hits

    if not scores:
        return Classification(label="other", confidence=0.0, signals=[])

    best = max(scores, key=lambda k: len(scores[k]))
    matched = scores[best]
    confidence = round(len(matched) / len(_SIGNALS[best]), 2)
    return Classification(label=best, confidence=confidence, signals=matched)
