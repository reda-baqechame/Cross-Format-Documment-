"""Local redaction proof harness (deterministic, no model calls, no network).

Builds a document whose secret lives in a heading, paragraph, table cell, and image alt-text — all
redacted — exports it to every from-model format, and fails if the secret is recoverable anywhere in
the exported bytes (raw or inside decompressed OOXML parts). Also asserts a non-redacted control
marker survives, so a "clean" verdict can't come from accidentally dropping all content.

Run from the repo root:  ``python evals/redaction_proof/run_local.py``
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend" / "src"))
sys.path.insert(0, str(ROOT / "evals"))

from redaction_proof.harness import CONTROL, SECRET, run  # noqa: E402


def main() -> int:
    results = run()
    report = {
        "secret": SECRET,
        "control": CONTROL,
        "formats": {
            r.fmt: {
                "secret_recoverable_in": r.secret_locations,
                "control_present": r.control_present,
            }
            for r in results
        },
    }
    print(json.dumps(report, indent=2))

    leaks = [(r.fmt, r.secret_locations) for r in results if r.secret_locations]
    missing_control = [r.fmt for r in results if not r.control_present]

    if leaks:
        print("\nFAIL: redacted secret is recoverable in exported bytes:")
        for fmt, where in leaks:
            print(f"  - {fmt}: {where}")
        return 1
    if missing_control:
        print(
            f"\nFAIL: control marker missing in {missing_control} — the proof is not meaningful "
            "(content was dropped wholesale, not selectively redacted)."
        )
        return 1

    fmts = ", ".join(r.fmt for r in results)
    print(f"\nPASS: zero recoverable bytes of the redacted secret across {len(results)} formats "
          f"({fmts}); control marker survived in all.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
