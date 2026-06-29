"""Document synthesis — generate a NEW canonical document (a deliverable) from structured data.

Packs produce findings (``APReport``, ``PacketReport``, …); this turns those findings into a real
document a user can download (exception report, AP reconciliation, customs summary). The synthesized
document is an ordinary :class:`CanonicalDocument`, so it flows through every existing writer
(PDF/XLSX/DOCX/HTML/MD) with no new exporter. Deterministic and offline.
"""

from docos.services.synthesis.report_builder import (
    GeneratedReport,
    ReportSection,
    ReportTable,
    ap_reconciliation_report,
    build_document,
    contract_risk_report,
    hr_onboarding_report,
    insurance_review_report,
    packet_exception_report,
)

__all__ = [
    "GeneratedReport",
    "ReportSection",
    "ReportTable",
    "ap_reconciliation_report",
    "build_document",
    "contract_risk_report",
    "hr_onboarding_report",
    "insurance_review_report",
    "packet_exception_report",
]
