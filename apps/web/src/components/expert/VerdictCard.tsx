"use client";

import { toneFor, normalizeVerdict } from "./tone";

export function VerdictCard({
  verdict,
  score,
  summary,
  action,
}: {
  verdict: string;
  score?: number;
  summary: string;
  action?: React.ReactNode;
}) {
  const tone = toneFor(normalizeVerdict(verdict));
  return (
    <div className={`card border ${tone.box} p-5`}>
      <div className="flex flex-wrap items-center gap-3">
        <span
          className={`inline-flex items-center gap-2 rounded-full px-3 py-1 text-sm font-semibold ${tone.badge}`}
        >
          <span className={`inline-block h-2 w-2 rounded-full ${tone.dot}`} />
          {tone.label.toUpperCase()}
        </span>
        {score != null && (
          <span className="text-sm text-slate-500">Readiness {Math.round(score * 100)}%</span>
        )}
        {action && <div className="ml-auto">{action}</div>}
      </div>
      <p className="mt-3 text-sm text-slate-700">{summary}</p>
    </div>
  );
}
