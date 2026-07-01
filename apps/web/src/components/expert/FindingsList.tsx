"use client";

import type { ExpertFinding, EvidenceRef } from "@/lib/api";
import { severityFor } from "./tone";

export function FindingsList({
  findings,
  onShowEvidence,
  emptyMessage = "No issues — document is clean.",
}: {
  findings: ExpertFinding[];
  onShowEvidence?: (evidence: EvidenceRef[]) => void;
  emptyMessage?: string;
}) {
  const order = ["blocking", "warning", "info"];
  const sorted = [...findings].sort(
    (a, b) => order.indexOf(a.severity) - order.indexOf(b.severity),
  );

  if (sorted.length === 0) {
    return <p className="text-sm text-slate-500">{emptyMessage}</p>;
  }

  return (
    <ul className="space-y-2">
      {sorted.map((f) => {
        const tone = severityFor(f.severity);
        return (
          <li
            key={f.id}
            className={`card border ${tone.badge.includes("red") ? "border-red-200" : "border-line"} p-4`}
          >
            <div className="flex items-center gap-2">
              <span className={`inline-block h-2 w-2 rounded-full ${tone.dot}`} />
              <span className="text-sm font-semibold text-ink">{f.title}</span>
              <span
                className={`ml-auto rounded-full px-2 py-0.5 text-[10px] font-medium ${tone.badge}`}
              >
                {f.severity}
              </span>
            </div>
            <p className="mt-2 text-xs text-slate-600">{f.explanation}</p>
            {f.business_impact && (
              <p className="mt-1 text-xs text-slate-500">Impact: {f.business_impact}</p>
            )}
            {f.recommended_action && (
              <p className="mt-1 text-xs text-slate-700">
                <span className="font-medium">Action:</span> {f.recommended_action}
              </p>
            )}
            <div className="mt-2 flex flex-wrap items-center gap-2">
              {f.evidence.length > 0 && onShowEvidence && (
                <button
                  type="button"
                  className="btn-ghost px-2 py-1 text-[11px]"
                  onClick={() => onShowEvidence(f.evidence)}
                >
                  View {f.evidence.length} source citation(s)
                </button>
              )}
              {f.human_review_required && (
                <span className="rounded-full bg-amber-50 px-2 py-0.5 text-[10px] text-amber-700">
                  needs human review
                </span>
              )}
              {f.fix_available && (
                <span className="rounded-full bg-trust-50 px-2 py-0.5 text-[10px] text-trust-800">
                  fix available
                </span>
              )}
              <span className="text-[10px] text-slate-400">
                {f.detection_method.replace("_", " ")} · {Math.round(f.confidence * 100)}%
              </span>
            </div>
          </li>
        );
      })}
    </ul>
  );
}
