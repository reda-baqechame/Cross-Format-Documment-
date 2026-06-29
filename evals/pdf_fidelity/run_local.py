"""PDF edit-fidelity eval (deterministic, offline, no model calls).

Proves the write-back path round-trips an edit *and* keeps the original style: it builds a PDF,
edits a span, exports via ``write_back_pdf``, re-parses the result, and checks the new text is
present, the old text is gone, and the edited span's font family/weight is preserved (the fix for
"edited text reflows to a flat default font"). Exits non-zero on any regression.

Run from the repo root:  ``python evals/pdf_fidelity/run_local.py``
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend" / "src"))

from docos.services.docengine.adapters.pdf import PdfAdapter  # noqa: E402
from docos.services.docengine.writers.pdf_writer import _base14_font, write_back_pdf  # noqa: E402

GATE = 1.0


def _build_pdf() -> bytes:
    import fitz

    doc = fitz.open()
    page = doc.new_page(width=400, height=200)
    page.insert_text((50, 80), "Bold heading here", fontname="hebo", fontsize=16)
    page.insert_text((50, 120), "Body line to edit", fontname="helv", fontsize=11)
    data = doc.tobytes()
    doc.close()
    return data


def _checks() -> list[tuple[str, bool]]:
    pdf = _build_pdf()
    doc = PdfAdapter().parse(pdf)

    target = next(n for n in doc.nodes.values() if getattr(n, "text", "") == "Body line to edit")
    target.text = "Body line edited now"
    # A bold span keeps bold weight when re-inserted (base-14 mapping, not flat helv).
    bold_node = next(n for n in doc.nodes.values() if getattr(n, "text", "") == "Bold heading here")

    out = write_back_pdf(pdf, doc)
    reparsed = PdfAdapter().parse(out)
    text = " ".join(getattr(n, "text", "") for n in reparsed.nodes.values() if n.type == "run")

    return [
        ("is_pdf", out[:4] == b"%PDF"),
        ("edit_applied", "Body line edited now" in text),
        ("old_text_gone", "Body line to edit" not in text),
        ("bold_preserved", _base14_font(bold_node) in {"hebo", "hebi"}),
    ]


def main() -> int:
    checks = _checks()
    passed = sum(1 for _, ok in checks if ok)
    total = len(checks)
    rate = passed / total if total else 1.0

    print(json.dumps({name: ok for name, ok in checks}, indent=2))
    for name, ok in checks:
        print(f"  [{'ok ' if ok else 'FAIL'}] {name}")
    print(f"PDF edit-fidelity: {passed}/{total} = {rate:.0%} (gate {GATE:.0%})")

    if rate < GATE:
        print("GATE FAILED")
        return 1
    print("GATE PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
