"use client";

import {
  AlertTriangle,
  CheckCircle2,
  Circle,
  FileCheck2,
  LockKeyhole,
  Play,
  Send,
  ShieldCheck,
} from "lucide-react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useMemo, useState } from "react";

import {
  executeWorkflow,
  previewWorkflow,
  type WorkflowExecuteResponse,
  type WorkflowPreset,
  type WorkflowStep,
} from "@/lib/api";
import { getWorkflow, WORKFLOWS } from "@/lib/workflows";
import { friendlyApiError } from "@/lib/upload";
import { RecipeManagerPanel } from "@/components/workflows/RecipeManagerPanel";

export function WorkflowRunnerPanel({
  docId,
  initialPreset = "contract_packet",
}: {
  docId: string;
  initialPreset?: WorkflowPreset;
}) {
  const queryClient = useQueryClient();
  const [mode, setMode] = useState<"guided" | "recipes">("guided");
  const [preset, setPreset] = useState<WorkflowPreset>(initialPreset);
  const workflow = getWorkflow(preset);
  const [approved, setApproved] = useState<string[]>([]);
  const [confirmDestructive, setConfirmDestructive] = useState(false);
  const [approvers, setApprovers] = useState(workflow.defaultApprovers.join(", "));
  const [recipients, setRecipients] = useState(workflow.defaultRecipients.join(", "));
  const [result, setResult] = useState<WorkflowExecuteResponse | null>(null);

  const preview = useQuery({
    queryKey: ["workflow-preview", docId, preset],
    queryFn: () => previewWorkflow(docId, preset),
  });

  const execute = useMutation({
    mutationFn: () =>
      executeWorkflow(docId, {
        preset,
        approved_step_ids: approved,
        confirm_destructive: confirmDestructive,
        approvers: splitList(approvers),
        recipients: splitList(recipients),
      }),
    onSuccess: (data) => {
      setResult(data);
      void queryClient.invalidateQueries({ queryKey: ["approvals", docId] });
      void queryClient.invalidateQueries({ queryKey: ["bulk-send", docId] });
      void queryClient.invalidateQueries({ queryKey: ["health", docId] });
      void queryClient.invalidateQueries({ queryKey: ["model", docId] });
    },
  });

  const steps = useMemo(() => preview.data?.steps ?? [], [preview.data?.steps]);
  const approvalSteps = useMemo(
    () => steps.filter((step) => step.requires_approval || step.destructive),
    [steps],
  );

  function switchPreset(next: WorkflowPreset) {
    const nextWorkflow = getWorkflow(next);
    setPreset(next);
    setApproved([]);
    setConfirmDestructive(false);
    setApprovers(nextWorkflow.defaultApprovers.join(", "));
    setRecipients(nextWorkflow.defaultRecipients.join(", "));
    setResult(null);
  }

  return (
    <div className="flex h-full flex-col bg-white">
      <div className="border-b border-slate-200 px-5 py-4">
        <div className="flex items-center justify-between gap-3">
          <div>
            <h2 className="text-sm font-semibold text-slate-950">DocumentOps Agent</h2>
            <p className="mt-1 text-xs leading-5 text-slate-500">
              Preview, approve, and run revenue workflows without losing audit control.
            </p>
          </div>
          <span className="rounded-full border border-teal-200 bg-teal-50 px-2.5 py-1 text-xs font-medium text-teal-700">
            Guarded
          </span>
        </div>
        <div className="mt-3 grid grid-cols-2 rounded-lg bg-slate-100 p-1" aria-label="Workflow mode">
          <button
            type="button"
            onClick={() => setMode("guided")}
            className={[
              "min-h-[34px] rounded-md text-xs font-semibold",
              mode === "guided" ? "bg-white text-slate-900 shadow-sm" : "text-slate-500",
            ].join(" ")}
          >
            Guided workflows
          </button>
          <button
            type="button"
            onClick={() => setMode("recipes")}
            className={[
              "min-h-[34px] rounded-md text-xs font-semibold",
              mode === "recipes" ? "bg-white text-slate-900 shadow-sm" : "text-slate-500",
            ].join(" ")}
          >
            Saved recipes
          </button>
        </div>
      </div>

      {mode === "recipes" ? (
        <RecipeManagerPanel docId={docId} />
      ) : (
        <div className="space-y-5 overflow-auto p-5">
        <label className="block text-xs font-semibold uppercase tracking-wide text-slate-500">
          Workflow
        </label>
        <select
          value={preset}
          onChange={(event) => switchPreset(event.target.value as WorkflowPreset)}
          className="studio-input"
        >
          {WORKFLOWS.map((item) => (
            <option key={item.preset} value={item.preset}>
              {item.title}
            </option>
          ))}
        </select>

        <section className="rounded-lg border border-slate-200 bg-slate-50 p-3">
          <p className="text-sm font-semibold text-slate-900">{workflow.title}</p>
          <p className="mt-1 text-sm leading-5 text-slate-600">{workflow.blurb}</p>
          <p className="mt-3 text-xs font-medium text-teal-700">{workflow.revenueSignal}</p>
        </section>

        {preview.isLoading && <p className="text-sm text-slate-500">Building workflow preview...</p>}
        {preview.isError && (
          <p role="alert" className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700">
            {friendlyApiError(preview.error, "Could not preview this workflow.")}
          </p>
        )}

        {preview.data && (
          <>
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                Detected document
              </span>
              <span className="rounded-full bg-slate-100 px-2.5 py-1 text-xs font-medium text-slate-700">
                {preview.data.classification}
              </span>
            </div>

            {preview.data.warnings.map((warning) => (
              <div
                key={warning}
                className="flex gap-2 rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-800"
              >
                <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
                <p>{warning}</p>
              </div>
            ))}

            <ol className="space-y-2">
              {steps.map((step, index) => (
                <StepCard
                  key={step.id}
                  step={step}
                  index={index}
                  checked={approved.includes(step.id)}
                  onToggle={() =>
                    setApproved((current) =>
                      current.includes(step.id)
                        ? current.filter((id) => id !== step.id)
                        : [...current, step.id],
                    )
                  }
                />
              ))}
            </ol>

            {approvalSteps.length > 0 && (
              <section className="space-y-3 border-t border-slate-200 pt-4">
                <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                  Approval inputs
                </h3>
                <label className="block text-sm text-slate-700">
                  Approvers
                  <input
                    value={approvers}
                    onChange={(event) => setApprovers(event.target.value)}
                    className="studio-input mt-1"
                    placeholder="Legal Review, Finance Approval"
                  />
                </label>
                {preset === "bulk_send_template" && (
                  <label className="block text-sm text-slate-700">
                    Recipients
                    <input
                      value={recipients}
                      onChange={(event) => setRecipients(event.target.value)}
                      className="studio-input mt-1"
                      placeholder="alpha@example.com, bravo@example.com"
                    />
                  </label>
                )}
                <label className="flex items-start gap-2 rounded-lg border border-slate-200 p-3 text-sm text-slate-700">
                  <input
                    type="checkbox"
                    checked={confirmDestructive}
                    onChange={(event) => setConfirmDestructive(event.target.checked)}
                    className="mt-1"
                  />
                  <span>
                    Confirm destructive/send actions. Required before bulk packet creation or
                    other irreversible workflow side effects.
                  </span>
                </label>
              </section>
            )}

            <button
              type="button"
              onClick={() => execute.mutate()}
              disabled={execute.isPending}
              className="flex min-h-[42px] w-full items-center justify-center gap-2 rounded-lg bg-blue-600 px-4 text-sm font-semibold text-white shadow-sm hover:bg-blue-700 disabled:opacity-50"
            >
              <Play className="h-4 w-4" />
              {execute.isPending ? "Running workflow..." : "Run approved workflow"}
            </button>
          </>
        )}

        {execute.isError && (
          <p role="alert" className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700">
            {friendlyApiError(execute.error, "Workflow execution failed.")}
          </p>
        )}

        {result && (
          <section className="space-y-3 rounded-lg border border-slate-200 bg-white p-3">
            <h3 className="text-sm font-semibold text-slate-900">Execution result</h3>
            <ResultList label="Completed" steps={result.executed_steps} />
            <ResultList label="Needs approval" steps={result.skipped_steps} />
          </section>
        )}
        </div>
      )}
    </div>
  );
}

function StepCard({
  step,
  index,
  checked,
  onToggle,
}: {
  step: WorkflowStep;
  index: number;
  checked: boolean;
  onToggle: () => void;
}) {
  const needsChoice = step.requires_approval || step.destructive;
  return (
    <li className="rounded-lg border border-slate-200 bg-white p-3">
      <div className="flex items-start gap-3">
        <div className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-slate-100 text-xs font-semibold text-slate-600">
          {index + 1}
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex items-center justify-between gap-2">
            <p className="text-sm font-semibold text-slate-900">{step.label}</p>
            <ToolIcon tool={step.tool} />
          </div>
          <p className="mt-1 text-xs leading-5 text-slate-500">{step.reason}</p>
          {needsChoice && (
            <button
              type="button"
              onClick={onToggle}
              className={[
                "mt-3 flex min-h-[34px] w-full items-center justify-center gap-2 rounded-md border px-3 text-xs font-semibold",
                checked
                  ? "border-blue-600 bg-blue-50 text-blue-700"
                  : "border-slate-200 text-slate-600 hover:bg-slate-50",
              ].join(" ")}
            >
              {checked ? <CheckCircle2 className="h-4 w-4" /> : <Circle className="h-4 w-4" />}
              Approve this step
            </button>
          )}
        </div>
      </div>
    </li>
  );
}

function ToolIcon({ tool }: { tool: string }) {
  const className = "h-4 w-4 text-slate-500";
  if (tool === "approvals") return <ShieldCheck className={className} />;
  if (tool === "bulk_send") return <Send className={className} />;
  if (tool === "health") return <LockKeyhole className={className} />;
  return <FileCheck2 className={className} />;
}

function ResultList({ label, steps }: { label: string; steps: WorkflowStep[] }) {
  if (steps.length === 0) return null;
  return (
    <div>
      <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">{label}</p>
      <ul className="mt-2 space-y-2">
        {steps.map((step) => (
          <li key={`${label}-${step.id}`} className="rounded-md bg-slate-50 p-2 text-xs text-slate-600">
            <span className="font-medium text-slate-800">{step.label}</span>
            {step.result ? ` - ${step.result}` : null}
          </li>
        ))}
      </ul>
    </div>
  );
}

function splitList(value: string): string[] {
  return value
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}
