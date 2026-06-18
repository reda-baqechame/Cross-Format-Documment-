"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import {
  createEditorSession,
  planDocumentOps,
  saveEditorSession,
  type EditorSession,
  type OpsAgentPlan,
} from "@/lib/api";
import { friendlyApiError } from "@/lib/upload";

export function EditorSessionPanel({
  docId,
  sourceFormat,
}: {
  docId: string;
  sourceFormat?: string;
}) {
  const queryClient = useQueryClient();
  const [session, setSession] = useState<EditorSession | null>(null);
  const [goal, setGoal] = useState("Prepare this document for approval and export");
  const [plan, setPlan] = useState<OpsAgentPlan | null>(null);

  const start = useMutation({
    mutationFn: () => createEditorSession(docId),
    onSuccess: setSession,
  });
  const save = useMutation({
    mutationFn: () => {
      if (!session) throw new Error("No editor session is open.");
      return saveEditorSession(docId, session.session_id, "Saved from editor handoff panel");
    },
    onSuccess: (data) => {
      setSession(data);
      queryClient.invalidateQueries({ queryKey: ["model", docId] });
      queryClient.invalidateQueries({ queryKey: ["health", docId] });
    },
  });
  const planner = useMutation({
    mutationFn: () => planDocumentOps(docId, goal),
    onSuccess: setPlan,
  });

  const pending = start.isPending || save.isPending || planner.isPending;
  const error = start.error ?? save.error ?? planner.error;

  return (
    <div className="space-y-5 p-5">
      <div>
        <h2 className="text-base font-semibold text-ink">Editor Core</h2>
        <p className="mt-1 text-sm text-slate-500">
          {sourceFormat?.toUpperCase() ?? "Document"} editing with provider-aware handoff.
        </p>
      </div>

      <section className="space-y-3 border-t border-slate-200 pt-4">
        <button className="studio-btn w-full" disabled={pending} onClick={() => start.mutate()}>
          {session ? "Refresh editor session" : "Start editor session"}
        </button>
        {session && (
          <div className="space-y-3 rounded-lg border border-slate-200 bg-slate-50 p-3 text-sm">
            <div className="grid grid-cols-2 gap-2">
              <Metric label="Provider" value={session.provider} />
              <Metric label="Status" value={session.status} />
            </div>
            {session.warnings.length > 0 && (
              <div className="rounded-md border border-amber-200 bg-amber-50 p-2 text-amber-800">
                {session.warnings.map((warning) => (
                  <p key={warning}>{warning}</p>
                ))}
              </div>
            )}
            <div>
              <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                Capabilities
              </p>
              <div className="mt-2 flex flex-wrap gap-1">
                {session.capabilities.map((capability) => (
                  <span
                    key={capability}
                    className="rounded-full bg-white px-2 py-1 text-xs text-slate-600"
                  >
                    {capability.replaceAll("_", " ")}
                  </span>
                ))}
              </div>
            </div>
            <a className="studio-btn block text-center" href={session.editor_url}>
              Open editor surface
            </a>
            <button className="studio-btn w-full" disabled={pending} onClick={() => save.mutate()}>
              Mark editor session saved
            </button>
          </div>
        )}
      </section>

      <section className="space-y-3 border-t border-slate-200 pt-4">
        <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-500">
          DocumentOps Agent
        </h3>
        <textarea
          value={goal}
          onChange={(e) => setGoal(e.target.value)}
          className="studio-input min-h-[84px]"
        />
        <button
          className="studio-btn w-full"
          disabled={pending || !goal.trim()}
          onClick={() => planner.mutate()}
        >
          Plan safe workflow
        </button>
        {plan && (
          <div className="space-y-3 rounded-lg border border-slate-200 bg-white p-3 text-sm">
            <p className="font-medium text-slate-700">Detected: {plan.classification}</p>
            {plan.warnings.map((warning) => (
              <p key={warning} className="rounded-md border border-amber-200 bg-amber-50 p-2 text-amber-800">
                {warning}
              </p>
            ))}
            <ol className="space-y-2">
              {plan.actions.map((action) => (
                <li key={`${action.tool}-${action.label}`} className="rounded-md bg-slate-50 p-2">
                  <p className="font-medium text-slate-700">
                    {action.label}
                    {action.requires_approval ? " · approval required" : ""}
                  </p>
                  <p className="text-slate-500">{action.reason}</p>
                </li>
              ))}
            </ol>
          </div>
        )}
      </section>

      {error && (
        <p role="alert" className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
          {friendlyApiError(error, "The editor workflow could not run.")}
        </p>
      )}
    </div>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md bg-white p-2">
      <p className="text-[10px] font-semibold uppercase tracking-wide text-slate-400">{label}</p>
      <p className="mt-1 truncate font-medium text-slate-700">{value}</p>
    </div>
  );
}
