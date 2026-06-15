"""Model → file writers.

These rebuild concrete files from the canonical model, independent of the adapter
that originally parsed the source — which is what lets any opened document export to
DOCX/TXT (e.g. a PDF-origin document downloads as a real .docx).
"""

from docos.services.docengine.writers.docx_writer import model_to_docx
from docos.services.docengine.writers.redaction import is_redacted, run_text

__all__ = ["model_to_docx", "is_redacted", "run_text"]
