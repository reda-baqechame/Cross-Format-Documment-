"""Document-purpose taxonomy — the breadth layer.

Maps the ~15 document *categories* (financial, legal, sales, HR, …) to the highest-demand
purposes with detection keywords, so classification spans the real document landscape instead of
a handful of hardcoded types. This is data, not code: adding a purpose is one tuple. Deep skills
(invoice/contract/résumé) build on top; everything else is recognized and handled by the generic
skill, so no recognized document is ever a dead end.
"""

from __future__ import annotations

from dataclasses import dataclass

CATEGORY_LABELS: dict[str, str] = {
    "financial": "Financial",
    "legal": "Legal",
    "sales": "Sales",
    "hr": "HR",
    "business": "Business",
    "marketing": "Marketing",
    "academic": "Academic",
    "technical": "Technical",
    "government": "Government",
    "medical": "Medical",
    "real_estate": "Real estate",
    "logistics": "Logistics & trade",
    "personal": "Personal",
    "forms": "Forms",
    "presentation": "Presentation",
}


@dataclass(frozen=True)
class DocType:
    id: str
    label: str
    category: str
    keywords: tuple[str, ...]


# Ordered roughly by commercial demand. Keywords are lowercased substrings matched on doc text.
DOC_TYPES: tuple[DocType, ...] = (
    # ── financial ────────────────────────────────────────────────────────────
    DocType(
        "invoice",
        "Invoice",
        "financial",
        ("invoice", "amount due", "bill to", "subtotal", "total due", "invoice number"),
    ),
    DocType(
        "receipt",
        "Receipt",
        "financial",
        ("receipt", "amount paid", "change due", "thank you for your purchase", "cash", "card"),
    ),
    DocType(
        "purchase_order",
        "Purchase order",
        "financial",
        ("purchase order", "po number", "p.o.", "ship to", "order date"),
    ),
    DocType(
        "bank_statement",
        "Bank statement",
        "financial",
        ("statement", "opening balance", "closing balance", "account number"),
    ),
    DocType(
        "expense_report",
        "Expense report",
        "financial",
        ("expense report", "reimbursement", "mileage", "expense"),
    ),
    DocType(
        "balance_sheet",
        "Balance sheet",
        "financial",
        ("balance sheet", "assets", "liabilities", "equity"),
    ),
    DocType(
        "income_statement",
        "Income statement",
        "financial",
        ("income statement", "profit and loss", "net income", "cost of goods", "revenue"),
    ),
    DocType(
        "tax_return",
        "Tax return",
        "financial",
        ("tax return", "taxable income", "form 1040", "w-2", "deduction"),
    ),
    DocType("budget", "Budget", "financial", ("budget", "forecast", "projected", "variance")),
    # ── legal ────────────────────────────────────────────────────────────────
    DocType(
        "contract",
        "Contract",
        "legal",
        ("agreement", "hereby", "the parties", "whereas", "shall", "terms and conditions"),
    ),
    DocType(
        "nda",
        "NDA",
        "legal",
        ("non-disclosure", "confidential information", "nda", "shall not disclose"),
    ),
    DocType(
        "lease", "Lease", "legal", ("lease", "lessor", "lessee", "tenant", "landlord", "premises")
    ),
    DocType(
        "employment_agreement",
        "Employment agreement",
        "legal",
        ("employment agreement", "at-will", "employer", "compensation"),
    ),
    DocType(
        "terms_of_service",
        "Terms of service",
        "legal",
        ("terms of service", "acceptable use", "by using this"),
    ),
    DocType(
        "privacy_policy",
        "Privacy policy",
        "legal",
        ("privacy policy", "personal data", "we collect", "cookies", "gdpr"),
    ),
    DocType(
        "power_of_attorney",
        "Power of attorney",
        "legal",
        ("power of attorney", "attorney-in-fact", "on my behalf"),
    ),
    DocType("will", "Will", "legal", ("last will", "testament", "bequeath", "executor")),
    # ── sales ────────────────────────────────────────────────────────────────
    DocType("proposal", "Proposal", "sales", ("proposal", "we propose", "deliverables", "scope")),
    DocType(
        "quote", "Quote", "sales", ("quote", "quotation", "estimate", "valid until", "unit price")
    ),
    DocType(
        "sow",
        "Statement of work",
        "sales",
        ("statement of work", "sow", "milestones", "acceptance criteria"),
    ),
    DocType(
        "pitch_deck",
        "Pitch deck",
        "presentation",
        ("the ask", "market size", "traction", "our solution", "problem"),
    ),
    # ── hr ───────────────────────────────────────────────────────────────────
    DocType(
        "resume",
        "Résumé",
        "hr",
        (
            "experience",
            "education",
            "skills",
            "curriculum vitae",
            "résumé",
            "resume",
            "work history",
        ),
    ),
    DocType(
        "cover_letter",
        "Cover letter",
        "hr",
        ("dear hiring", "cover letter", "i am writing to apply", "the position"),
    ),
    DocType(
        "job_description",
        "Job description",
        "hr",
        ("job description", "responsibilities", "qualifications", "reports to"),
    ),
    DocType(
        "offer_letter",
        "Offer letter",
        "hr",
        ("offer letter", "pleased to offer", "start date", "annual salary"),
    ),
    DocType(
        "performance_review",
        "Performance review",
        "hr",
        ("performance review", "review period", "rating", "goals"),
    ),
    # ── business ───────────────────────────────────────────────────────────────
    DocType(
        "business_plan",
        "Business plan",
        "business",
        ("business plan", "executive summary", "market analysis", "financial projections"),
    ),
    DocType(
        "report",
        "Report",
        "business",
        ("introduction", "summary", "conclusion", "methodology", "findings"),
    ),
    DocType(
        "meeting_minutes",
        "Meeting minutes",
        "business",
        ("minutes", "attendees", "agenda", "action items"),
    ),
    DocType(
        "sop",
        "SOP",
        "business",
        ("standard operating procedure", "sop", "procedure", "purpose", "scope"),
    ),
    DocType("memo", "Memo", "business", ("memorandum", "memo", "re:")),
    # ── marketing ──────────────────────────────────────────────────────────────
    DocType(
        "press_release",
        "Press release",
        "marketing",
        ("press release", "for immediate release", "media contact", "announced today"),
    ),
    DocType(
        "white_paper", "White paper", "marketing", ("white paper", "abstract", "executive summary")
    ),
    DocType(
        "marketing_plan",
        "Marketing plan",
        "marketing",
        ("marketing plan", "target audience", "campaign", "channels"),
    ),
    # ── academic ─────────────────────────────────────────────────────────────
    DocType(
        "research_paper",
        "Research paper",
        "academic",
        ("abstract", "methodology", "references", "et al", "hypothesis"),
    ),
    DocType(
        "thesis", "Thesis", "academic", ("thesis", "dissertation", "literature review", "chapter")
    ),
    DocType(
        "syllabus", "Syllabus", "academic", ("syllabus", "grading", "office hours", "prerequisites")
    ),
    DocType("transcript", "Transcript", "academic", ("transcript", "gpa", "credits", "semester")),
    DocType(
        "certificate",
        "Certificate",
        "academic",
        ("certificate", "awarded to", "this certifies", "completion"),
    ),
    # ── technical ──────────────────────────────────────────────────────────────
    DocType(
        "prd",
        "Product requirements",
        "technical",
        ("product requirements", "prd", "user stories", "acceptance criteria"),
    ),
    DocType(
        "srs",
        "Software requirements",
        "technical",
        ("software requirements", "srs", "functional requirements", "non-functional"),
    ),
    DocType(
        "api_doc",
        "API documentation",
        "technical",
        ("endpoint", "request", "response", "authentication", "parameters"),
    ),
    DocType(
        "user_manual",
        "User manual",
        "technical",
        ("user manual", "getting started", "installation", "troubleshooting"),
    ),
    DocType("readme", "README", "technical", ("readme", "installation", "usage", "contributing")),
    DocType(
        "release_notes",
        "Release notes",
        "technical",
        ("release notes", "changelog", "bug fixes", "new features"),
    ),
    # ── government ─────────────────────────────────────────────────────────────
    DocType(
        "passport",
        "Passport",
        "government",
        ("passport", "nationality", "place of birth", "passport no"),
    ),
    DocType(
        "drivers_license",
        "Driver's licence",
        "government",
        ("driver", "licence", "license", "class", "restrictions"),
    ),
    DocType(
        "birth_certificate",
        "Birth certificate",
        "government",
        ("certificate of birth", "place of birth", "registrar"),
    ),
    DocType(
        "permit", "Permit", "government", ("permit", "license number", "issued by", "authority")
    ),
    # ── medical ────────────────────────────────────────────────────────────────
    DocType(
        "medical_record",
        "Medical record",
        "medical",
        ("patient", "diagnosis", "medical record", "mrn"),
    ),
    DocType(
        "prescription",
        "Prescription",
        "medical",
        ("prescription", "rx", "dosage", "refills", "pharmacy"),
    ),
    DocType(
        "lab_report",
        "Lab report",
        "medical",
        ("laboratory", "specimen", "reference range", "result"),
    ),
    DocType(
        "discharge_summary",
        "Discharge summary",
        "medical",
        ("discharge", "admission", "hospital course"),
    ),
    # ── real estate ──────────────────────────────────────────────────────────
    DocType(
        "purchase_agreement",
        "Purchase agreement",
        "real_estate",
        ("purchase agreement", "buyer", "seller", "closing", "earnest money"),
    ),
    DocType(
        "inspection_report",
        "Inspection report",
        "real_estate",
        ("inspection", "condition", "inspector", "findings"),
    ),
    DocType(
        "appraisal",
        "Appraisal",
        "real_estate",
        ("appraisal", "market value", "comparable", "subject property"),
    ),
    # ── logistics & trade ──────────────────────────────────────────────────────
    DocType(
        "bill_of_lading",
        "Bill of lading",
        "logistics",
        ("bill of lading", "shipper", "consignee", "carrier", "port of loading"),
    ),
    DocType(
        "packing_list",
        "Packing list",
        "logistics",
        ("packing list", "net weight", "gross weight", "carton"),
    ),
    DocType(
        "commercial_invoice",
        "Commercial invoice",
        "logistics",
        ("commercial invoice", "country of origin", "hs code", "incoterms", "exporter"),
    ),
    DocType(
        "certificate_of_origin",
        "Certificate of origin",
        "logistics",
        ("certificate of origin", "country of origin", "chamber of commerce"),
    ),
    DocType(
        "customs_declaration",
        "Customs declaration",
        "logistics",
        ("customs", "declaration", "duty", "tariff"),
    ),
    DocType(
        "air_waybill", "Air waybill", "logistics", ("air waybill", "awb", "airport of departure")
    ),
    # ── personal ───────────────────────────────────────────────────────────────
    DocType("letter", "Letter", "personal", ("dear ", "sincerely", "best regards", "yours truly")),
    DocType(
        "itinerary",
        "Travel itinerary",
        "personal",
        ("itinerary", "departure", "arrival", "confirmation number"),
    ),
    # ── forms ──────────────────────────────────────────────────────────────────
    DocType(
        "form",
        "Form",
        "forms",
        ("please fill", "please complete", "applicant", "checkbox", "date of birth"),
    ),
    DocType(
        "application_form",
        "Application form",
        "forms",
        ("application form", "applicant", "date of birth", "please complete"),
    ),
    DocType(
        "registration_form",
        "Registration form",
        "forms",
        ("registration form", "register", "attendee", "participant"),
    ),
    DocType("contact_form", "Contact form", "forms", ("contact form", "name", "email", "phone")),
    DocType(
        "order_form", "Order form", "forms", ("order form", "quantity", "unit price", "ship to")
    ),
    DocType("feedback_form", "Feedback form", "forms", ("feedback form", "feedback", "rating")),
    DocType(
        "consent_form", "Consent form", "forms", ("consent", "i agree", "i authorize", "i consent")
    ),
    DocType(
        "survey", "Survey", "forms", ("survey", "questionnaire", "please rate", "strongly agree")
    ),
    DocType(
        "questionnaire", "Questionnaire", "forms", ("questionnaire", "questions", "respondent")
    ),
    DocType(
        "intake_form",
        "Intake form",
        "forms",
        ("intake form", "patient", "client information", "emergency contact"),
    ),
    DocType(
        "booking_form",
        "Booking form",
        "forms",
        ("booking form", "reservation", "appointment", "preferred date"),
    ),
    DocType("evaluation_form", "Evaluation form", "forms", ("evaluation form", "score", "rating")),
    DocType(
        "inspection_form", "Inspection form", "forms", ("inspection", "inspector", "condition")
    ),
    DocType("checklist", "Checklist", "forms", ("checklist", "completed", "done")),
    DocType("timesheet", "Timesheet", "forms", ("timesheet", "hours", "employee", "week ending")),
    DocType(
        "expense_form", "Expense form", "forms", ("expense", "reimbursement", "receipt attached")
    ),
    DocType(
        "incident_form", "Incident form", "forms", ("incident", "date of incident", "location")
    ),
    DocType("request_form", "Request form", "forms", ("request form", "requested by", "reason")),
    DocType("approval_form", "Approval form", "forms", ("approval", "approver", "approved by")),
    # ── presentation ─────────────────────────────────────────────────────────
    DocType(
        "sales_presentation",
        "Sales presentation",
        "presentation",
        ("sales presentation", "customer pain", "benefits", "pricing", "case study"),
    ),
    DocType(
        "training_presentation",
        "Training presentation",
        "presentation",
        ("training", "learning objectives", "module", "quiz", "exercise"),
    ),
    DocType("webinar_slides", "Webinar slides", "presentation", ("webinar", "speaker", "q&a")),
    DocType(
        "infographic",
        "Infographic",
        "presentation",
        ("infographic", "key statistic", "data source"),
    ),
    DocType("poster", "Poster", "presentation", ("poster", "event", "date", "location")),
    DocType("flyer", "Flyer", "presentation", ("flyer", "offer", "contact", "call to action")),
    DocType(
        "brochure", "Brochure", "presentation", ("brochure", "features", "benefits", "contact")
    ),
    DocType(
        "one_page_summary",
        "One-page summary",
        "presentation",
        ("one-page summary", "overview", "key points", "next steps"),
    ),
    DocType("dashboard", "Dashboard", "presentation", ("dashboard", "kpi", "metric", "trend")),
    DocType("flowchart", "Flowchart", "presentation", ("flowchart", "decision", "process")),
    DocType("mind_map", "Mind map", "presentation", ("mind map", "topic", "branch")),
    DocType(
        "org_chart",
        "Organizational chart",
        "presentation",
        ("org chart", "reports to", "department"),
    ),
    DocType("diagram", "Diagram", "presentation", ("diagram", "legend", "component")),
    DocType("roadmap", "Roadmap", "presentation", ("roadmap", "milestone", "quarter")),
    DocType("timeline", "Timeline", "presentation", ("timeline", "milestone", "date")),
    DocType(
        "slide_deck",
        "Slide deck",
        "presentation",
        ("agenda", "next steps", "overview", "thank you"),
    ),
)


def classify_purpose(text: str) -> tuple[DocType | None, float, list[str]]:
    """Best-matching document purpose by keyword score → (DocType|None, confidence, signals)."""
    best: DocType | None = None
    best_hits: list[str] = []
    best_score = 0.0
    for dt in DOC_TYPES:
        hits = [k for k in dt.keywords if k in text]
        if not hits:
            continue
        score = len(hits) / len(dt.keywords)
        # Prefer higher ratio; break ties by more raw hits.
        if score > best_score or (score == best_score and len(hits) > len(best_hits)):
            best, best_hits, best_score = dt, hits, score
    if best is None:
        return None, 0.0, []
    return best, round(best_score, 2), best_hits
