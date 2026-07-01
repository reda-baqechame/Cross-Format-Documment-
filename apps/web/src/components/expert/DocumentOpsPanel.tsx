"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { VerdictCard } from "@/components/expert/VerdictCard";
import { FindingsList } from "@/components/expert/FindingsList";
import {
  applyDocumentAutopilot,
  type AutopilotGoal,
  runDocumentAutopilot,
} from "@/lib/api";
import { useToast } from "@/components/ui/Toast";
import { friendlyApiError } from "@/lib/upload";

const GOALS: { id: AutopilotGoal; label: string }[] = [
  { id: "clean_before_send", label: "Clean before send" },
  { id: "review", label: "Review & verify" },
  { id: "export", label: "Export readiness" },
  { id: "compare", label: "Compare documents" },
];

/** DocumentOps Automate — outcome picker over the expert spine (run → apply loop). */
export function DocumentOpsPanel({ docId }: { docId: string }) {
  const toast = useToast();
  const queryClient = useQueryClient();
  const [goal, setGoal] = useState<AutopilotGoal>("clean_before_send");
  const [againstDocId, setAgainstDocId] = useState("");

  const run = useQuery({
    queryKey: ["document-ops", docId, goal, againstDocId],
    queryFn: () =>
      runDocumentAutopilot(docId, {
        goal,
        against_doc_id: goal === "compare" ? againstDocId || undefined : undefined,
      }),
    enabled: Boolean(docId),
  });

  const apply = useMutation({
    mutationFn: (findingIds: string[]) => applyDocumentAutopilot(docId, findingIds),
    onSuccess: () => {
      toast.success("Fixes applied — re-running verify.");
      queryClient.invalidateQueries({ queryKey: ["document-ops", docId] });
      queryClient.invalidateQueries({ queryKey: ["readiness", docId] });
      queryClient.invalidateQueries({ queryKey: ["model", docId] });
    },
    onError: (err) => toast.error(friendlyApiError(err, "Could not apply fixes.")),
  });

  const result = run.data?.result;
  const fixable = run.data?.fix_plans?.map((p) => p.finding_id) ?? [];

  return (
    <aside className="flex w-full shrink-0 flex-col gap-4 border-l border-slate-200 bg-white p-5 lg:w-96">
      <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-500">
        DocumentOps
      </h2>
      <p className="text-xs text-slate-500">
        Pick an outcome, run verify, then apply reversible fixes in one loop.
      </p>

      <div className="flex flex-wrap gap-2">
        {GOALS.map((g) => (
          <button
            key={g.id}
            type="button"
            onClick={() => setGoal(g.id)}
            className={`rounded-lg border px-2 py-1 text-xs font-medium ${
              goal === g.id
                ? "border-brand-500 bg-brand-50 text-brand-800"
                : "border-line text-slate-600 hover:bg-slate-50"
            }`}
          >
            {g.label}
          </button>
        ))}
      </div>

      {goal === "compare" && (
        <label className="text-xs text-slate-600">
          Reference document ID
          <input
            className="mt-1 w-full rounded border border-line px-2 py-1 text-sm"
            value={againstDocId}
            onChange={(e) => setAgainstDocId(e.target.value)}
            placeholder="Other doc ID"
          />
        </label>
      )}

      {run.isLoading && <p className="text-sm text-slate-500">Running…</p>}
      {run.isError && (
        <p className="text-sm text-red-600">{friendlyApiError(run.error, "Run failed.")}</p>
      )}

      {result && (
        <>
          <VerdictCard
            verdict={result.verdict}
            score={result.score != null ? result.score / 100 : undefined}
            summary={`${result.blocking_count ?? 0} blocking · ${result.warning_count ?? 0} warning`}
          />
          {run.data?.steps && run.data.steps.length > 0 && (
            <ol className="list-inside list-decimal text-xs text-slate-600">
              {run.data.steps.map((s) => (
                <li key={s}>{s}</li>
              ))}
            </ol>
          )}
          {run.data?.compare_summary && (
            <p className="text-xs text-slate-600">{run.data.compare_summary}</p>
          )}
          <FindingsList findings={result.findings} />
          {fixable.length > 0 && (
            <button
              type="button"
              disabled={apply.isPending}
              onClick={() => apply.mutate(fixable)}
              className="rounded-xl bg-brand-600 px-3 py-2 text-sm font-medium text-white hover:bg-brand-700 disabled:opacity-50"
            >
              Apply {fixable.length} fix(es)
            </button>
          )}
        </>
      )}
    </aside>
  );
}
