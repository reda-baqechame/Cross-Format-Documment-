"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { applyPlan, fetchBackendHealth, planEdit, undoDocument, type PatchPlan } from "@/lib/api";
import { friendlyApiError } from "@/lib/upload";

/**
 * Natural-language editing bar with a dry-run preview. The instruction is planned by the LLM into
 * concrete patch ops server-side (no commit); we show a before/after preview, and only commit those
 * ops when the user approves. AI is only real when a provider is configured, so we check the
 * backend's `ai_enabled` flag and show an honest disabled state. Undo always works.
 */
export function AiEditBar({ docId }: { docId: string }) {
  const [instruction, setInstruction] = useState("");
  const [plan, setPlan] = useState<PatchPlan | null>(null);
  const queryClient = useQueryClient();
  const health = useQuery({ queryKey: ["health"], queryFn: fetchBackendHealth, retry: false });
  const aiEnabled = health.data?.ai_enabled ?? false;

  const refresh = () => {
    queryClient.invalidateQueries({ queryKey: ["model", docId] });
    queryClient.invalidateQueries({ queryKey: ["health", docId] });
  };

  const preview = useMutation({
    mutationFn: () => planEdit(docId, { instruction }),
    onSuccess: (p) => setPlan(p),
  });
  const apply = useMutation({
    mutationFn: () => applyPlan(docId, plan as PatchPlan),
    onSuccess: () => {
      refresh();
      setPlan(null);
      setInstruction("");
    },
  });
  const undo = useMutation({ mutationFn: () => undoDocument(docId), onSuccess: refresh });

  const error = preview.error ?? apply.error ?? undo.error;

  return (
    <div className="flex min-w-0 flex-1 flex-col gap-1 sm:flex-row sm:items-center sm:gap-2">
      <input
        value={instruction}
        onChange={(e) => setInstruction(e.target.value)}
        onKeyDown={(e) =>
          e.key === "Enter" && aiEnabled && instruction.trim() && !preview.isPending && preview.mutate()
        }
        placeholder={aiEnabled ? "Ask AI to edit…" : "AI editing not connected"}
        aria-label="Natural language edit instruction"
        disabled={!aiEnabled}
        className="min-h-[44px] min-w-0 flex-1 rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-brand-400 focus:outline-none disabled:cursor-not-allowed disabled:bg-slate-50 disabled:text-slate-400"
      />
      <div className="flex shrink-0 gap-2">
        <button
          type="button"
          onClick={() => preview.mutate()}
          disabled={!aiEnabled || preview.isPending || !instruction.trim()}
          aria-label="Preview AI edit"
          className="min-h-[44px] rounded-md bg-brand-600 px-3 py-2 text-sm font-medium text-white hover:bg-brand-500 disabled:opacity-40"
        >
          {preview.isPending ? "…" : "Preview"}
        </button>
        <button
          type="button"
          onClick={() => undo.mutate()}
          disabled={undo.isPending}
          aria-label="Undo last change"
          className="min-h-[44px] rounded-md border border-slate-300 px-3 py-2 text-sm hover:bg-slate-50 disabled:opacity-40"
          title="Undo the last change"
        >
          Undo
        </button>
      </div>
      {!aiEnabled && !health.isLoading && (
        <span className="text-xs text-slate-400 sm:ml-1" title="Set LLM_PROVIDER=anthropic + ANTHROPIC_API_KEY">
          AI off — edit text directly by double-clicking it
        </span>
      )}
      {plan && (
        <div className="sm:basis-full rounded-md border border-brand-200 bg-brand-50 p-3 text-sm">
          <p className="font-medium text-ink">{plan.preview.summary}</p>
          {plan.preview.changes.length > 0 && (
            <ul className="mt-2 max-h-40 space-y-1 overflow-auto">
              {plan.preview.changes.slice(0, 20).map((c, i) => (
                <li key={i} className="text-xs text-slate-600">
                  <span className="font-semibold text-slate-500">{c.label}:</span>{" "}
                  {c.before ? <span className="line-through">{c.before}</span> : null}{" "}
                  {c.after ? <span className="text-emerald-700">{c.after}</span> : null}
                </li>
              ))}
            </ul>
          )}
          <div className="mt-3 flex gap-2">
            <button
              type="button"
              onClick={() => apply.mutate()}
              disabled={apply.isPending || plan.preview.change_count === 0}
              className="min-h-[36px] rounded-md bg-emerald-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-emerald-500 disabled:opacity-40"
            >
              {apply.isPending ? "Applying…" : "Apply changes"}
            </button>
            <button
              type="button"
              onClick={() => setPlan(null)}
              className="min-h-[36px] rounded-md border border-slate-300 px-3 py-1.5 text-sm hover:bg-slate-50"
            >
              Discard
            </button>
          </div>
        </div>
      )}
      {error && (
        <p role="alert" className="text-xs text-red-600 sm:basis-full">
          {friendlyApiError(error, "Edit failed.")}
        </p>
      )}
    </div>
  );
}
