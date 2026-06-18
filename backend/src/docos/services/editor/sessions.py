"""Embedded editor provider selection.

This module intentionally does not fake native editing. It returns a configured
provider session only when the corresponding provider URL is present; otherwise it
falls back to the current safe local editor and explains the fidelity limit.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from docos.model.document import CanonicalDocument
from docos.settings import Settings

_OFFICE_FORMATS = {"docx", "xlsx", "pptx"}


@dataclass(frozen=True)
class EditorProviderSession:
    provider: str
    editor_url: str
    config: dict
    capabilities: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def build_editor_session(
    doc: CanonicalDocument, settings: Settings, *, requested_provider: str | None = None
) -> EditorProviderSession:
    source_format = doc.meta.source_format.lower()
    local_url = f"/documents/{doc.doc_id}?tab=modify"

    if source_format in _OFFICE_FORMATS:
        wants_onlyoffice = requested_provider == "onlyoffice" or (
            requested_provider is None and settings.office_editor_provider == "onlyoffice"
        )
        if wants_onlyoffice and settings.onlyoffice_document_server_url:
            return EditorProviderSession(
                provider="onlyoffice",
                editor_url=settings.onlyoffice_document_server_url.rstrip("/"),
                config={
                    "document": {
                        "fileType": source_format,
                        "title": doc.meta.title or f"Document {doc.doc_id[:8]}",
                        "key": doc.content_hash,
                    },
                    "editorConfig": {"mode": "edit"},
                },
                capabilities=[
                    "native_text_layout",
                    "native_tables",
                    "native_spreadsheets",
                    "native_presentations",
                    "collaborative_provider_ready",
                ],
            )
        return EditorProviderSession(
            provider="local_basic",
            editor_url=local_url,
            config={"tab": "modify"},
            capabilities=[
                "canonical_text_edit",
                "forms",
                "tables_basic",
                "images_basic",
                "audited_patches",
            ],
            warnings=[
                "Native Office layout editing is not active. Configure "
                "ONLYOFFICE_DOCUMENT_SERVER_URL and OFFICE_EDITOR_PROVIDER=onlyoffice for "
                "full DOCX/XLSX/PPTX sessions."
            ],
        )

    if source_format == "pdf":
        wants_external_pdf = requested_provider == "external_pdf" or (
            requested_provider is None and settings.pdf_editor_provider == "external"
        )
        if wants_external_pdf and settings.pdf_editor_url:
            return EditorProviderSession(
                provider="external_pdf",
                editor_url=settings.pdf_editor_url.rstrip("/"),
                config={"documentId": doc.doc_id, "mode": "edit"},
                capabilities=["native_pdf_text", "native_pdf_images", "native_pdf_forms"],
            )
        return EditorProviderSession(
            provider="basic_pdf",
            editor_url=local_url,
            config={"tab": "modify"},
            capabilities=[
                "canonical_text_edit",
                "redaction",
                "page_ops",
                "audited_patches",
            ],
            warnings=[
                "PDF editing is currently the safe basic editor, not Acrobat-level native PDF "
                "editing. Configure PDF_EDITOR_PROVIDER=external and PDF_EDITOR_URL to enable "
                "a licensed PDF SDK."
            ],
        )

    return EditorProviderSession(
        provider="local_basic",
        editor_url=local_url,
        config={"tab": "modify"},
        capabilities=[
            "canonical_text_edit",
            "forms",
            "tables_basic",
            "images_basic",
            "audited_patches",
        ],
        warnings=[
            "This format opens in the canonical editor. Native provider editing is available "
            "first for DOCX, XLSX, PPTX, and PDF."
        ],
    )
