"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import {
  getApprovals,
  startApprovals,
  type WorkflowStatus,
} from "@/lib/api";

const STATE_STYLE: Record<WorkflowStatus["state"], string> = {
  none: "bg-slate-100 text-slate-500",
  in_progress: "bg-amber-100 text-amber-700",
  approved: "bg-green-100 text-green-700",
  rejected: "bg-red-100 text-red-700",
};

const STEP_ICON = { pending: "○", approved: "✓", rejected: "✗" } as const;

/**
 * Approval / multi-party signing workflow. Route a document to an ordered (or parallel)
 * list of approvers; each approves or rejects in turn. State is tracked server-side and
 * every transition is audited. A rejection halts the workflow.
 */
export function ApprovalsPanel({ docId }: { docId: string }) {
  const queryClient = useQueryClient();
  const [names, setNames] = useState("");
  const [ordered, setOrdered] = useState(true);
  const [showNewForm, setShowNewForm] = useState(false);

  const workflow = useQuery({ queryKey: ["approvals", docId], queryFn: () => getApprovals(docId) });
  const set = (w: WorkflowStatus) => queryClient.setQueryData(["approvals", docId], w);

  const start = useMutation({
    mutationFn: () =>
      startApprovals(
        docId,
        names.split(",").map((n) => n.trim()).filter(Boolean),
        ordered,
      ),
    onSuccess: (w) => {
      set(w);
      setNames("");
      setShowNewForm(false);
    },
  });

  const w = workflow.data;
  const finished = w && (w.state === "approved" || w.state === "rejected");
  const active = w && w.state !== "none" && !(finished && showNewForm);

  return (
    <aside className="w-full shrink-0 space-y-4 overflow-auto border-l border-slate-200 bg-white p-4 lg:w-80">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-semibold text-slate-800">Approvals</h2>
        {w && (
          <span className={`rounded px-2 py-0.5 text-xs font-medium ${STATE_STYLE[w.state]}`}>
            {w.state.replace("_", " ")}
          </span>
        )}
      </div>

      {!active && (
        <div className="space-y-2">
          <p className="text-xs text-slate-500">
            Route this document for sign-off. Enter approvers (comma-separated).
          </p>
          <input
            value={names}
            onChange={(e) => setNames(e.target.value)}
            placeholder="alice, bob, carol"
            className="w-full rounded-md border border-slate-300 px-2 py-1.5 text-sm focus:border-blue-400 focus:outline-none"
          />
          <label className="flex items-center gap-2 text-xs text-slate-600">
            <input
              type="checkbox"
              checked={ordered}
              onChange={(e) => setOrdered(e.target.checked)}
            />
            In order (each waits for the previous)
          </label>
          <button
            onClick={() => start.mutate()}
            disabled={start.isPending || !names.trim()}
            className="w-full rounded-md bg-blue-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-blue-500 disabled:opacity-40"
          >
            Start workflow
          </button>
        </div>
      )}

      {w && active && (
        <div className="space-y-3">
          <ol className="space-y-1">
            {w.steps.map((s) => {
              const isCurrent = w.current_approvers.includes(s.approver);
              return (
                <li
                  key={`${s.approver}-${s.order_index}`}
                  className={`flex items-center justify-between rounded-md border px-2 py-1.5 text-sm ${
                    isCurrent ? "border-amber-300 bg-amber-50" : "border-slate-200"
                  }`}
                >
                  <span className="flex items-center gap-2">
                    <span
                      className={
                        s.status === "approved"
                          ? "text-green-600"
                          : s.status === "rejected"
                            ? "text-red-600"
                            : "text-slate-400"
                      }
                    >
                      {STEP_ICON[s.status]}
                    </span>
                    {w.ordered && <span className="text-xs text-slate-400">{s.order_index + 1}.</span>}
                    {s.approver}
                  </span>
                  {isCurrent && (
                    <span className="text-xs text-amber-700">Recipient action required</span>
                  )}
                </li>
              );
            })}
          </ol>

          {finished && (
            <button
              type="button"
              onClick={() => setShowNewForm(true)}
              className="text-xs text-brand-600 hover:underline"
            >
              Start a new workflow
            </button>
          )}
          {w.state === "in_progress" && (
            <p className="text-xs text-slate-500">
              Waiting on: {w.current_approvers.join(", ") || "—"}
            </p>
          )}
        </div>
      )}

      {start.isError && (
        <p role="alert" className="text-xs text-red-600">
          {start.error instanceof Error ? start.error.message : String(start.error)}
        </p>
      )}
    </aside>
  );
}
