"""Pack catalog — a discoverable registry of the installed business packs.

Each pack is a vertical bundle (document types + deterministic extraction + validation rules) on the
universal canonical core. This catalog makes them discoverable so the frontend can list what the
platform can do per industry, and so `/api/capabilities` and docs stay in sync with the code.
Read-only, deterministic, offline.
"""

from __future__ import annotations

from pydantic import BaseModel


class PackInfo(BaseModel):
    pack_id: str
    name: str
    description: str
    doc_types: list[str]
    endpoint: str
    capability: str


# The installed packs. Keep this in lockstep with services/packs/* and routes_packs.py.
CATALOG: tuple[PackInfo, ...] = (
    PackInfo(
        pack_id="import_export",
        name="Import / Export",
        description=(
            "Cross-document shipment-packet validation: currency/total/HS/origin consistency "
            "plus a customs document checklist."
        ),
        doc_types=[
            "commercial_invoice",
            "packing_list",
            "bill_of_lading",
            "certificate_of_origin",
            "purchase_order",
        ],
        endpoint="/packs/import-export/check",
        capability="pack_import_export",
    ),
    PackInfo(
        pack_id="finance",
        name="Finance / Accounts Payable",
        description=(
            "Invoice↔PO matching with total and currency comparison, plus duplicate-invoice "
            "detection to prevent double payment."
        ),
        doc_types=["invoice", "purchase_order"],
        endpoint="/packs/finance/ap-check",
        capability="pack_finance_ap",
    ),
    PackInfo(
        pack_id="contracts",
        name="Contracts / CLM",
        description=(
            "Clause extraction (parties, dates, term, governing law, renewal, termination, "
            "liability cap, payment terms) with a common-risk review."
        ),
        doc_types=["contract", "agreement"],
        endpoint="/packs/contracts/check",
        capability="pack_contracts",
    ),
    PackInfo(
        pack_id="hr",
        name="HR / Onboarding",
        description=(
            "Offer-letter extraction (role, start date, compensation, employment type, at-will) "
            "and onboarding-packet completeness checks."
        ),
        doc_types=[
            "offer_letter",
            "eligibility_form",
            "tax_withholding",
            "confidentiality_agreement",
        ],
        endpoint="/packs/hr/onboarding-check",
        capability="pack_hr_onboarding",
    ),
    PackInfo(
        pack_id="insurance",
        name="Insurance",
        description=(
            "Policy/declarations review (coverage limit, premium, deductible, effective/expiration "
            "dates) with expiry, missing-coverage, and claim-within-coverage-period checks."
        ),
        doc_types=["insurance_policy", "declarations", "insurance_claim"],
        endpoint="/packs/insurance/check",
        capability="pack_insurance",
    ),
)


def list_packs() -> list[PackInfo]:
    """Return the installed business packs (deterministic, offline)."""
    return list(CATALOG)
