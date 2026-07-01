"""Printable HTML expert packet report."""

from __future__ import annotations

from html import escape

from docos.services.expert.schemas import ExpertReport

_VERDICT = {
    "ready": "Ready to send",
    "needs_review": "Needs review",
    "blocked": "Blocked — do not send",
}


def render_expert_report_html(
    *,
    title: str,
    packet_id: str,
    report: ExpertReport,
) -> str:
    rows = []
    for f in report.findings:
        sev = escape(f.severity)
        rows.append(
            f"<tr class='{sev}'>"
            f"<td><strong>{escape(f.title)}</strong></td>"
            f"<td>{escape(sev)}</td>"
            f"<td>{escape(f.explanation)}</td>"
            f"<td>{escape(f.recommended_action or '—')}</td>"
            "</tr>"
        )
    actions = (
        "".join(f"<li>{escape(a.detail)}</li>" for a in report.recommended_actions)
        or "<li>No actions required.</li>"
    )
    docs = ", ".join(escape(d.title or d.document_id) for d in report.documents_detected)
    score = f"{report.readiness_score:.0%}"
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8"/>
  <title>{escape(title)} — Expert Packet Report</title>
  <style>
    body {{ font-family: system-ui, sans-serif; margin: 2rem; color: #0f172a; }}
    h1 {{ font-size: 1.5rem; }}
    .verdict {{ font-size: 1.1rem; font-weight: 600; margin: 1rem 0; }}
    table {{ border-collapse: collapse; width: 100%; margin-top: 1rem; }}
    th, td {{ border: 1px solid #e2e8f0; padding: 0.5rem; text-align: left; vertical-align: top; }}
    th {{ background: #f8fafc; }}
    .blocking {{ background: #fef2f2; }}
    .warning {{ background: #fffbeb; }}
    .info {{ background: #f0f9ff; }}
  </style>
</head>
<body>
  <h1>Expert Packet Audit Report</h1>
  <p class="verdict">{escape(_VERDICT.get(report.verdict, report.verdict))} · Score {score}</p>
  <p><strong>Packet:</strong> {escape(title)} ({escape(packet_id)})</p>
  <p><strong>Pack:</strong> {escape(report.pack)}</p>
  <p><strong>Documents:</strong> {docs}</p>
  <p>{escape(report.executive_summary)}</p>
  <h2>Findings</h2>
  <table>
    <thead><tr><th>Issue</th><th>Severity</th><th>Detail</th><th>Action</th></tr></thead>
    <tbody>{"".join(rows) if rows else '<tr><td colspan="4">No findings.</td></tr>'}</tbody>
  </table>
  <h2>Recommended next steps</h2>
  <ul>{actions}</ul>
  <p><small>Generated {escape(report.generated_at)} · DocOS expert spine</small></p>
</body>
</html>"""
