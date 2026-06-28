"use client";

import { useMutation } from "@tanstack/react-query";
import { useState } from "react";

import { runAgent, type AgentRun } from "@/lib/api";
import { friendlyApiError } from "@/lib/upload";

/**
 * The AI Helper — the conversational surface for the document agent. Type a goal; the agent plans,
 * runs read tools (classify/extract/intelligence), and *proposes* reversible edits with a preview.
 * It never commits: proposed edits are applied through the Edit/Modify tab after review. Read
 * analysis works offline (the "Offline" badge); edit proposals need a configured AI provider.
 */
const SUGGESTIONS = [
  "Summarize this and flag risks",
  "Extract all key fields",
  "Find and redact personal information",
  "Change the payment term to Net 30",
];

function StatusDot({ status }: { status: string }) {
  const color =
    status === "done"
      ? "bg-emerald-500"
      : status === "proposed"
        ? "bg-amber-500"
        : status === "requires_approval"
          ? "bg-orange-500"
          : "bg-slate-300";
  return <span className={`mt-1.5 inline-block h-2 w-2 shrink-0 rounded-full ${color}`} />;
}

export function AiHelperPanel({ docId }: { docId: string }) {
  const [goal, setGoal] = useState("");

  const agent = useMutation<AgentRun, Error, string>({
    mutationFn: (g: string) => runAgent(docId, g),
  });
  const run = agent.data;

  return (
    <section
      className="flex h-full flex-col gap-3 overflow-auto p-4"
      aria-label="AI document helper"
    >
      <div>
        <h2 className="text-sm font-semibold text-slate-800">AI Helper</h2>
        <p className="text-xs text-slate-500">
          Tell the agent what to do. It plans, analyzes, and proposes reversible edits — nothing is
          changed until you approve it in the Edit tab.
        </p>
      </div>

      <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
        <input
          value={goal}
          onChange={(e) => setGoal(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && goal.trim() && agent.mutate(goal)}
          placeholder="What do you want done with this document?"
          aria-label="Document goal"
          className="min-h-[44px] flex-1 rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-brand-400 focus:outline-none"
        />
        <button
          type="button"
          onClick={() => agent.mutate(goal)}
          disabled={agent.isPending || !goal.trim()}
          className="min-h-[44px] rounded-md bg-brand-600 px-4 py-2 text-sm font-medium text-white hover:bg-brand-500 disabled:opacity-40"
        >
          {agent.isPending ? "Working…" : "Run"}
        </button>
      </div>

      {!run && !agent.isPending && (
        <div className="flex flex-wrap gap-2">
          {SUGGESTIONS.map((s) => (
            <button
              key={s}
              type="button"
              onClick={() => {
                setGoal(s);
                agent.mutate(s);
              }}
              className="rounded-full border border-slate-200 px-3 py-1 text-xs text-slate-600 hover:bg-slate-50"
            >
              {s}
            </button>
          ))}
        </div>
      )}

      {agent.error && (
        <p role="alert" className="text-sm text-red-600">
          {friendlyApiError(agent.error, "The agent could not complete that.")}
        </p>
      )}

      {run && (
        <div className="flex flex-col gap-3">
          <div className="flex items-center gap-2 text-xs">
            <span className="rounded bg-slate-100 px-2 py-0.5 font-medium text-slate-700">
              {run.classification}
            </span>
            <span
              className="rounded bg-slate-100 px-1.5 py-0.5 uppercase text-slate-500"
              title={run.used_llm ? "Edits proposed by the configured LLM" : "No data egress"}
            >
              {run.used_llm ? "AI" : "Offline"}
            </span>
          </div>

          <ol className="space-y-2">
            {run.steps.map((step, i) => (
              <li key={i} className="flex gap-2 rounded-md border border-slate-100 p-2">
                <StatusDot status={step.status} />
                <div className="min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-medium text-slate-800">{step.label}</span>
                    {step.requires_approval && (
                      <span className="rounded bg-orange-50 px-1.5 py-0.5 text-[10px] uppercase text-orange-600">
                        approval
                      </span>
                    )}
                  </div>
                  <p className="text-xs text-slate-600">{step.summary}</p>
                </div>
              </li>
            ))}
          </ol>

          {run.proposed_patch && run.proposed_patch.change_count > 0 && (
            <div className="rounded-md border border-amber-200 bg-amber-50 p-3">
              <p className="text-sm font-medium text-amber-800">
                {run.proposed_patch.change_count} proposed change(s) — review &amp; apply in the Edit
                tab.
              </p>
              <ul className="mt-2 space-y-1">
                {(run.proposed_patch.changes ?? []).slice(0, 8).map((c, i) => (
                  <li key={i} className="text-xs">
                    {c.before && <span className="text-red-600 line-through">{c.before}</span>}{" "}
                    {c.after && <span className="text-emerald-700">{c.after}</span>}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {run.recommended_actions.length > 0 && (
            <div>
              <p className="text-xs font-medium text-slate-500">Recommended next</p>
              <div className="mt-1 flex flex-wrap gap-2">
                {run.recommended_actions.map((a, i) => (
                  <span
                    key={i}
                    className="rounded-full border border-slate-200 px-3 py-1 text-xs text-slate-600"
                  >
                    {a.label}
                  </span>
                ))}
              </div>
            </div>
          )}

          {run.warnings.length > 0 && (
            <ul className="space-y-1">
              {run.warnings.map((w, i) => (
                <li key={i} className="text-xs text-amber-700">
                  ⚠ {w}
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </section>
  );
}
