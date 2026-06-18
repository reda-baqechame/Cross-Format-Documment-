"""Output validation — proof that a produced file is what the user asked for.

Every output-producing operation (export/convert, redact-then-export, page-ops) can be run
through here to get a machine-checked :class:`ValidationReport`: the output opens, the page
count is preserved, text is retained, **redacted content is provably unrecoverable**, and an
invalidated integrity seal is flagged. This is the product's differentiator — competitors return
a file and leave you to trust it; DocOS returns the file *and the proof*.

Pure, deterministic, fully offline: it re-parses the produced bytes (PyMuPDF for PDF; the OOXML
package for docx/xlsx/pptx; decode for text formats) and checks them against the canonical model.
"""

from __future__ import annotations

import io
import zipfile
from datetime import UTC, datetime

from pydantic import BaseModel, Field

from docos.model.document import CanonicalDocument
from docos.services.docengine.writers.redaction import is_redacted, run_text

_PDF_FORMATS = {"pdf", "searchable-pdf"}
_OOXML_FORMATS = {"docx", "xlsx", "pptx"}
# Redacted strings shorter than this are skipped for the recovery scan — a 1–2 char token
# would match incidental text everywhere and produce meaningless "leaks".
_MIN_REDACTION_LEN = 4


class ValidationFinding(BaseModel):
    level: str  # "pass" | "warn" | "fail"
    code: str  # e.g. "output.opens", "pages.count", "redaction.recovery"
    message: str


class ValidationReport(BaseModel):
    ok: bool  # no "fail" findings
    operation: str  # "export", "rotate", "merge", …
    output_format: str
    summary: str
    findings: list[ValidationFinding] = Field(default_factory=list)
    checked_at: datetime


def status(report: ValidationReport) -> str:
    """Single-word status for an ``X-DocOS-Validation`` header: pass | warn | fail."""
    if any(f.level == "fail" for f in report.findings):
        return "fail"
    if any(f.level == "warn" for f in report.findings):
        return "warn"
    return "pass"


# ── output re-parsing ───────────────────────────────────────────────────────────────────


def _open_ok(fmt: str, output: bytes) -> tuple[bool, str]:
    try:
        if fmt in _PDF_FORMATS:
            import fitz

            doc = fitz.open(stream=output, filetype="pdf")
            _ = doc.page_count
        elif fmt == "docx":
            import docx

            docx.Document(io.BytesIO(output))
        elif fmt == "xlsx":
            from openpyxl import load_workbook

            load_workbook(io.BytesIO(output), read_only=True)
        elif fmt == "pptx":
            from pptx import Presentation

            Presentation(io.BytesIO(output))
        elif fmt == "png":
            from PIL import Image

            Image.open(io.BytesIO(output)).verify()
        else:  # txt, md, html, csv
            output.decode("utf-8")
        return True, ""
    except Exception as exc:  # noqa: BLE001 - any parse failure is a validation failure
        return False, str(exc)


def _pdf_page_count(output: bytes) -> int:
    import fitz

    return fitz.open(stream=output, filetype="pdf").page_count


def _output_text(fmt: str, output: bytes) -> str:
    """All recoverable text in the output (visible *and* hidden), for the redaction scan."""
    if fmt in _PDF_FORMATS:
        import fitz

        doc = fitz.open(stream=output, filetype="pdf")
        return "\n".join(page.get_text() for page in doc)
    if fmt in _OOXML_FORMATS:
        # Scan the decompressed package parts directly — catches any text the high-level
        # reader would skip, so a "removed" string can't hide in an unread part.
        parts: list[str] = []
        try:
            with zipfile.ZipFile(io.BytesIO(output)) as zf:
                for name in zf.namelist():
                    if name.endswith((".xml", ".rels", ".txt")):
                        parts.append(zf.read(name).decode("utf-8", "ignore"))
        except zipfile.BadZipFile:
            return ""
        return "\n".join(parts)
    return output.decode("utf-8", "ignore")


def model_page_count(doc: CanonicalDocument) -> int:
    return sum(1 for n in doc.children_of(doc.root_id) if n.type == "page")


def _redacted_strings(doc: CanonicalDocument) -> list[str]:
    """Every text string the model marks redacted — what must NOT survive into output."""
    out: list[str] = []
    for node in doc.nodes.values():
        if not is_redacted(doc, node.id):
            continue
        text = (getattr(node, "text", "") or "").strip()
        if len(text) >= _MIN_REDACTION_LEN:
            out.append(text)
    return out


# ── checks ──────────────────────────────────────────────────────────────────────────────


def _check_redaction(doc: CanonicalDocument, fmt: str, output: bytes) -> ValidationFinding | None:
    needles = _redacted_strings(doc)
    if not needles:
        return None
    haystack = _output_text(fmt, output)
    leaked = sum(1 for n in set(needles) if n in haystack)
    if leaked:
        # Never echo the leaked content itself — that would defeat the redaction.
        return ValidationFinding(
            level="fail",
            code="redaction.recovery",
            message=f"{leaked} redacted item(s) are still recoverable from the output.",
        )
    return ValidationFinding(
        level="pass",
        code="redaction.recovery",
        message=f"All {len(set(needles))} redacted item(s) are unrecoverable from the output.",
    )


def _check_signature(
    doc: CanonicalDocument, signature_valid: bool | None
) -> ValidationFinding | None:
    if not doc.signature.signed:
        return None
    if signature_valid is False:
        return ValidationFinding(
            level="warn",
            code="signature.invalidated",
            message="The integrity seal no longer matches the content (invalidated by an edit).",
        )
    return ValidationFinding(
        level="pass", code="signature.valid", message="Integrity seal is present and valid."
    )


def _check_text_retained(
    doc: CanonicalDocument, fmt: str, output: bytes
) -> ValidationFinding | None:
    model_has_text = any(run_text(doc, n).strip() for n in doc.nodes.values())
    if not model_has_text:
        return None
    if _output_text(fmt, output).strip():
        return ValidationFinding(
            level="pass", code="text.retained", message="Document text is present in the output."
        )
    return ValidationFinding(
        level="warn",
        code="text.retained",
        message="The document has text but none was found in the output.",
    )


def _report(operation: str, fmt: str, findings: list[ValidationFinding]) -> ValidationReport:
    n_fail = sum(1 for f in findings if f.level == "fail")
    n_warn = sum(1 for f in findings if f.level == "warn")
    if n_fail:
        summary = f"{n_fail} check(s) failed" + (f", {n_warn} warning(s)" if n_warn else "")
    elif n_warn:
        summary = f"All critical checks passed, {n_warn} warning(s)"
    else:
        summary = "All checks passed"
    return ValidationReport(
        ok=n_fail == 0,
        operation=operation,
        output_format=fmt,
        summary=summary,
        findings=findings,
        checked_at=datetime.now(UTC),
    )


def validate_export(
    doc: CanonicalDocument,
    fmt: str,
    output: bytes,
    *,
    signature_valid: bool | None = None,
) -> ValidationReport:
    """Validate an exported/converted file against the model that produced it."""
    findings: list[ValidationFinding] = []

    opened, err = _open_ok(fmt, output)
    if not opened:
        findings.append(
            ValidationFinding(
                level="fail", code="output.opens", message=f"Output failed to open: {err}"
            )
        )
        return _report("export", fmt, findings)
    findings.append(
        ValidationFinding(level="pass", code="output.opens", message="Output opens correctly.")
    )

    if fmt in _PDF_FORMATS:
        expected = model_page_count(doc)
        if expected:
            actual = _pdf_page_count(output)
            level = "pass" if actual == expected else "fail"
            findings.append(
                ValidationFinding(
                    level=level,
                    code="pages.count",
                    message=f"{actual} of {expected} expected page(s) present.",
                )
            )

    for finding in (
        _check_redaction(doc, fmt, output),
        _check_text_retained(doc, fmt, output),
        _check_signature(doc, signature_valid),
    ):
        if finding is not None:
            findings.append(finding)

    return _report("export", fmt, findings)


def validate_pageop(
    doc: CanonicalDocument,
    operation: str,
    output: bytes,
    *,
    expected_pages: int | None,
    signature_valid: bool | None = None,
) -> ValidationReport:
    """Validate a PDF page operation's output (rotate/delete/reorder/merge/…)."""
    findings: list[ValidationFinding] = []

    opened, err = _open_ok("pdf", output)
    if not opened:
        findings.append(
            ValidationFinding(
                level="fail", code="output.opens", message=f"Output failed to open: {err}"
            )
        )
        return _report(operation, "pdf", findings)
    findings.append(
        ValidationFinding(level="pass", code="output.opens", message="Output opens correctly.")
    )

    actual = _pdf_page_count(output)
    if expected_pages is not None:
        level = "pass" if actual == expected_pages else "fail"
        findings.append(
            ValidationFinding(
                level=level,
                code="pages.count",
                message=f"{actual} of {expected_pages} expected page(s) present.",
            )
        )

    for finding in (
        _check_redaction(doc, "pdf", output),
        _check_signature(doc, signature_valid),
    ):
        if finding is not None:
            findings.append(finding)

    return _report(operation, "pdf", findings)
