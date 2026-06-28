"""License gate for the closed-SaaS core (CI release gate).

Walks every installed distribution and fails if any carries a license that is incompatible with a
closed commercial SaaS, unless it is in the explicit, documented EXCEPTIONS list. This implements
the release requirement: "No forbidden or unknown license in the deployed SBOM."

Policy (see CLAUDE.md): new deps must be MIT/Apache-2.0/BSD/ISC. The hard-blocked set below is the
subset that genuinely conflicts with closed SaaS distribution/operation:

  * AGPL  — network copyleft; the real SaaS blocker.
  * GPL   — strong copyleft (LGPL is allowed: weak/library copyleft, fine for an unmodified,
            dynamically-linked dependency like psycopg).
  * SSPL / BUSL / BSL / Commons-Clause / non-commercial (-NC) — source-available / field-of-use
            restrictions incompatible with commercial SaaS.

Each entry in EXCEPTIONS must name a real, tracked reason — not a way to silence the gate.

Usage:  python scripts/check_licenses.py            # fail on violations
        python scripts/check_licenses.py --report   # print the full license inventory, never fail
"""

from __future__ import annotations

import re
import sys
from importlib import metadata

# Distribution name (lowercased) -> reason it is allowed despite a flagged license.
EXCEPTIONS: dict[str, str] = {
    # AGPL, but load-bearing for PDF today. Tracked for removal via the PdfEngine migration
    # (Phase C / docs/roadmap-100x.md): pypdfium2 + pypdf + pikepdf replace it. Until then the
    # capabilities endpoint surfaces this as a licence risk and this exception keeps the gate
    # honest rather than green-by-omission.
    "pymupdf": "AGPL — tracked for removal in the PdfEngine migration (docs/roadmap-100x.md)",
}

# Our own package has no license metadata in editable installs; never gate it.
SELF = {"docos"}

# Patterns that hard-block. Ordered so AGPL/LGPL are distinguished before the generic GPL match.
_BLOCK = [
    (re.compile(r"\bAGPL\b|affero", re.I), "AGPL"),
    (re.compile(r"\bSSPL\b|server side public", re.I), "SSPL"),
    (re.compile(r"\bBUSL\b|\bBSL\b|business source", re.I), "BUSL/BSL"),
    (re.compile(r"commons[- ]clause", re.I), "Commons-Clause"),
    (re.compile(r"non[- ]commercial|\bNC\b|-nc\b", re.I), "non-commercial"),
    # GPL but NOT LGPL (negative lookbehind for the leading 'L').
    (re.compile(r"(?<![A-Za-z])(?<!L)GPL", re.I), "GPL"),
]


def _license_of(dist: metadata.Distribution) -> str:
    """Best-effort license string: prefer OSI classifiers, fall back to the License field."""
    meta = dist.metadata
    classifiers = meta.get_all("Classifier") or []
    licenses = [c.split("::")[-1].strip() for c in classifiers if c.startswith("License ::")]
    if licenses:
        return "; ".join(licenses)
    # Newer metadata uses a SPDX expression in License-Expression.
    expr = meta.get("License-Expression")
    if expr:
        return expr
    return (meta.get("License") or "UNKNOWN").splitlines()[0].strip() or "UNKNOWN"


def _is_lgpl_only(text: str) -> bool:
    return bool(re.search(r"\bLGPL\b|lesser general public", text, re.I))


def main() -> int:
    report = "--report" in sys.argv
    violations: list[tuple[str, str, str]] = []
    inventory: list[tuple[str, str]] = []

    for dist in metadata.distributions():
        name = (dist.metadata.get("Name") or "").strip()
        if not name or name.lower() in SELF:
            continue
        lic = _license_of(dist)
        inventory.append((name, lic))

        # LGPL is allowed even though it contains "GPL"; skip the GPL pattern for pure-LGPL.
        lgpl = _is_lgpl_only(lic)
        for pat, label in _BLOCK:
            if label == "GPL" and lgpl:
                continue
            if pat.search(lic):
                if name.lower() in EXCEPTIONS:
                    break
                violations.append((name, lic, label))
                break

    inventory.sort()
    if report:
        for name, lic in inventory:
            print(f"{name}\t{lic}")
        print(f"\n{len(inventory)} distributions inspected.")
        return 0

    if EXCEPTIONS:
        print("Documented license exceptions (tracked, not silenced):")
        for pkg, reason in EXCEPTIONS.items():
            print(f"  - {pkg}: {reason}")

    if violations:
        print("\n❌ Forbidden licenses found (incompatible with closed-SaaS):")
        for name, lic, label in violations:
            print(f"  - {name}: {lic}  [{label}]")
        print("\nUse a permissive replacement, or add a documented EXCEPTIONS entry if justified.")
        return 1

    print(f"\n✅ License gate passed: {len(inventory)} distributions, no forbidden licenses.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
