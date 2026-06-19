"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useState } from "react";

import {
  type AutopilotAction,
  type AutopilotField,
  type AutopilotFinding,
  downloadExport,
  type ExportFormat,
  fetchAutopilot,
  redactSensitive,
  signDocument,
} from "@/lib/api";
import { PromptModal } from "@/components/ui/Modal";
import { useToast } from "@/components/ui/Toast";
import { friendlyApiError, friendlyLoadError } from "@/lib/upload";

const ACTION_SUCCESS: Record<string, string> = {
  export: "Export downloaded.",
  redact: "Sensitive content redacted.",
  sign: "Integrity seal applied.",
};

/**
 * Document Autopilot — the "what should happen next" surface. It turns the open document into a
 * typed object: detected purpose, the key facts that matter for that purpose (flagging anything
 * uncertain for review), validation findings, and one-click recommended actions.
 */
export function AutopilotPanel({ docId }: { docId: string }) {
  const router = useRouter();
  const queryClient = useQueryClient();
  const toast = useToast();
  const [signOpen, setSignOpen] = useState(false);

  const autopilot = useQuery({
    queryKey: ["autopilot", docId],
    queryFn: () => fetchAutopilot(docId),
    enabled: Boolean(docId),
  });

  const run = useMutation({
    mutationFn: async (action: AutopilotAction) => {
      if (action.kind === "export") {
        return downloadExport(docId, (action.params.format ?? "docx") as ExportFormat);
      }
      if (action.kind === "redact") return redactSensitive(docId);
      if (action.kind === "navigate" && action.params.href) router.push(action.params.href);
      return null;
    },
    onSuccess: (_data, action) => {
      if (ACTION_SUCCESS[action.kind]) toast.success(ACTION_SUCCESS[action.kind]);
      queryClient.invalidateQueries({ queryKey: ["model", docId] });
      queryClient.invalidateQueries({ queryKey: ["health", docId] });
      queryClient.invalidateQueries({ queryKey: ["autopilot", docId] });
    },
    onError: (err) => toast.error(friendlyApiError(err, "That action couldn't be completed.")),
  });

  const sign = useMutation({
    mutationFn: (signer: string) => signDocument(docId, signer),
    onSuccess: () => {
      toast.success(ACTION_SUCCESS.sign);
      queryClient.invalidateQueries({ queryKey: ["model", docId] });
      queryClient.invalidateQueries({ queryKey: ["health", docId] });
      queryClient.invalidateQueries({ queryKey: ["autopilot", docId] });
    },
    onError: (err) => toast.error(friendlyApiError(err, "Couldn't seal the document.")),
  });

  const onAction = (action: AutopilotAction) => {
    if (action.kind === "sign") setSignOpen(true);
    else run.mutate(action);
  };

  return (
    <aside className="flex w-full shrink-0 flex-col gap-4 border-l border-slate-200 bg-white p-5 lg:w-96">
      <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-500">Autopilot</h2>

      {autopilot.isLoading && (
        <p className="text-sm text-slate-500" aria-live="polite">
          Analyzing document…
        </p>
      )}
      {autopilot.isError && (
        <p role="alert" className="text-sm text-red-600">
          {friendlyLoadError(autopilot.error)}
        </p>
      )}

      {autopilot.data && (
        <>
          {/* Detected type */}
          <div className="rounded-lg bg-slate-50 p-3">
            <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">
              Detected
            </p>
            <p className="mt-1 text-sm font-medium text-ink">
              {autopilot.data.category} · {autopilot.data.type}
              {autopilot.data.type_confidence > 0 && (
                <span className="ml-1 text-xs text-slate-500">
                  ({Math.round(autopilot.data.type_confidence * 100)}%)
                </span>
              )}
            </p>
            {autopilot.data.needs_review && (
              <p className="mt-1 text-xs font-medium text-amber-700">⚠ Needs review</p>
            )}
          </div>

          {/* Key facts */}
          {autopilot.data.fields.length > 0 && (
            <div>
              <h3 className="mb-2 text-xs font-semibold uppercase text-slate-400">Key facts</h3>
              <ul className="space-y-1">
                {autopilot.data.fields.map((f) => (
                  <FactRow key={f.name} field={f} />
                ))}
              </ul>
            </div>
          )}

          {/* Findings */}
          {autopilot.data.findings.length > 0 && (
            <div>
              <h3 className="mb-2 text-xs font-semibold uppercase text-slate-400">Checks</h3>
              <ul className="space-y-2">
                {autopilot.data.findings.map((f, i) => (
                  <FindingRow key={`${f.code}-${i}`} finding={f} />
                ))}
              </ul>
            </div>
          )}

          {/* Recommended actions */}
          {autopilot.data.actions.length > 0 && (
            <div className="flex flex-col gap-2">
              <h3 className="text-xs font-semibold uppercase text-slate-400">Recommended</h3>
              {autopilot.data.actions.map((a) => (
                <button
                  key={a.id}
                  type="button"
                  onClick={() => onAction(a)}
                  disabled={run.isPending || sign.isPending}
                  className="rounded-xl border border-line px-3 py-2 text-left text-sm font-medium text-slate-700 transition-colors hover:border-brand-200 hover:bg-brand-50/40 disabled:opacity-40"
                >
                  {a.label}
                </button>
              ))}
            </div>
          )}
        </>
      )}

      <PromptModal
        open={signOpen}
        title="Apply integrity seal"
        label="Seal as (your name)"
        placeholder="e.g. Jordan Lee"
        confirmLabel="Seal document"
        onConfirm={(signer) => sign.mutate(signer)}
        onClose={() => setSignOpen(false)}
      />
    </aside>
  );
}

function FactRow({ field }: { field: AutopilotField }) {
  const tone =
    field.status === "missing"
      ? "text-slate-400"
      : field.status === "low_confidence"
        ? "text-amber-700"
        : "text-slate-800";
  return (
    <li className="flex items-baseline justify-between gap-2 text-sm">
      <span className="text-slate-600">{field.label}</span>
      <span className={`text-right font-medium ${tone}`}>
        {field.status === "missing" ? "—" : field.value}
        {field.status === "low_confidence" && <span className="ml-1 text-xs">⚠</span>}
      </span>
    </li>
  );
}

function FindingRow({ finding }: { finding: AutopilotFinding }) {
  const mark = finding.level === "fail" ? "✕" : finding.level === "warn" ? "⚠" : "✓";
  const tone =
    finding.level === "fail"
      ? "border-red-200 bg-red-50 text-red-800"
      : finding.level === "warn"
        ? "border-amber-200 bg-amber-50 text-amber-800"
        : "border-emerald-200 bg-emerald-50 text-emerald-800";
  return (
    <li className={`rounded-lg border px-2 py-2 text-xs ${tone}`}>
      <span className="font-medium">{mark}</span> {finding.message}
    </li>
  );
}
