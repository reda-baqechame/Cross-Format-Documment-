"use client";

import { useQuery } from "@tanstack/react-query";

import { fetchIntelligence, type InsightCheck } from "@/lib/api";
import { useWorkspace } from "@/lib/store";
import { friendlyApiError } from "@/lib/upload";

const SEVERITY_STYLE: Record<InsightCheck["severity"], string> = {
  error: "bg-red-50 text-red-700 border-red-200",
  warn: "bg-amber-50 text-amber-700 border-amber-200",
  info: "bg-slate-50 text-slate-600 border-slate-200",
};

function CheckRow({ check }: { check: InsightCheck }) {
  const tone = check.passed
    ? "bg-emerald-50 text-emerald-700 border-emerald-200"
    : SEVERITY_STYLE[check.severity];
  const icon = check.passed ? "✓" : check.severity === "error" ? "✕" : "!";
  return (
    <li className={`rounded-lg border px-3 py-2 ${tone}`}>
      <div className="flex items-center gap-2">
        <span aria-hidden className="font-bold">
          {icon}
        </span>
        <span className="text-sm font-medium">{check.label}</span>
      </div>
      {!check.passed && check.detail && (
        <p className="mt-1 pl-6 text-xs opacity-90">{check.detail}</p>
      )}
    </li>
  );
}

/**
 * Document Intelligence — the typed, validated read for the detected document
 * kind. Beyond "here are some dates and dollars," it verifies the document does
 * its job: invoice totals reconcile, contracts carry key clauses, résumés have a
 * contact email an ATS can route.
 */
export function IntelligencePanel({ docId }: { docId: string }) {
  const select = useWorkspace((s) => s.select);
  const q = useQuery({
    queryKey: ["intelligence", docId],
    queryFn: () => fetchIntelligence(docId),
  });

  if (q.isLoading) {
    return <p className="p-6 text-sm text-slate-500">Analyzing document…</p>;
  }
  if (q.isError) {
    return (
      <p role="alert" className="p-6 text-sm text-red-600">
        {friendlyApiError(q.error, "Analysis failed.")}
      </p>
    );
  }

  const insight = q.data?.insight;
  if (!insight) return null;

  const problems = insight.checks.filter((c) => !c.passed && c.severity === "error").length;

  return (
    <div className="p-6">
      <div className="flex items-baseline justify-between gap-2">
        <h2 className="text-base font-semibold text-ink">Document intelligence</h2>
        <span className="rounded-full bg-brand-50 px-2 py-0.5 text-xs font-medium uppercase tracking-wide text-brand-700">
          {insight.doc_type}
        </span>
      </div>
      <p className="mt-1 text-sm text-slate-600">{insight.summary}</p>
      {problems > 0 && (
        <p className="mt-2 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
          {problems} issue{problems > 1 ? "s" : ""} that could cost you — review the red checks below.
        </p>
      )}

      <h3 className="mt-5 text-xs font-semibold uppercase tracking-wide text-slate-400">Checks</h3>
      <ul className="mt-2 space-y-2">
        {insight.checks.map((c) => (
          <CheckRow key={c.id} check={c} />
        ))}
      </ul>

      {insight.fields.length > 0 && (
        <>
          <h3 className="mt-6 text-xs font-semibold uppercase tracking-wide text-slate-400">
            Key fields
          </h3>
          <ul className="mt-2 space-y-1">
            {insight.fields.map((f) => (
              <li key={`${f.key}-${f.value}`}>
                <button
                  type="button"
                  onClick={() => f.node_id && select(f.node_id)}
                  disabled={!f.node_id}
                  className="flex w-full min-h-[44px] items-center justify-between rounded-lg px-2 py-1 text-left text-sm hover:bg-slate-50 disabled:cursor-default disabled:hover:bg-transparent"
                >
                  <span className="font-medium capitalize text-slate-700">
                    {f.key.replace(/_/g, " ")}
                  </span>
                  <span className="truncate pl-3 text-slate-600">{f.value}</span>
                </button>
              </li>
            ))}
          </ul>
        </>
      )}
    </div>
  );
}
