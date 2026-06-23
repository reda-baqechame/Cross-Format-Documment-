"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import {
  cleanDocument,
  exportUrl,
  fetchReadiness,
  fetchRedactionAudit,
  redactSensitive,
  sanitizeMetadata,
  type CleanResponse,
  type ExportFormat,
  type ReadinessCheck,
} from "@/lib/api";

/**
 * The "Send-Ready Check" / Document X-Ray reveal — one verdict on whether a document is
 * safe and complete to send, with one-click fixes that reuse the existing trust ops. This
 * is the headline trust surface: the value (and the alarm) is visible at a glance.
 */
export function ReadinessPanel({ docId }: { docId: string }) {
  const queryClient = useQueryClient();
  const readiness = useQuery({
    queryKey: ["readiness", docId],
    queryFn: () => fetchReadiness(docId),
  });
  const audit = useQuery({
    queryKey: ["redaction-audit", docId],
    queryFn: () => fetchRedactionAudit(docId),
  });

  const refresh = () => {
    queryClient.invalidateQueries({ queryKey: ["readiness", docId] });
    queryClient.invalidateQueries({ queryKey: ["health", docId] });
    queryClient.invalidateQueries({ queryKey: ["sensitive", docId] });
    queryClient.invalidateQueries({ queryKey: ["model", docId] });
  };

  const fix = useMutation({
    mutationFn: (action: ReadinessCheck["fix_action"]) => {
      if (action === "redact_pii") return redactSensitive(docId);
      if (action === "sanitize_metadata") return sanitizeMetadata(docId);
      return Promise.reject(new Error("This check has no automatic fix."));
    },
    onSuccess: refresh,
  });

  const [cleaned, setCleaned] = useState<CleanResponse | null>(null);
  const clean = useMutation({
    mutationFn: () => cleanDocument(docId),
    onSuccess: (result) => {
      setCleaned(result);
      refresh();
    },
  });

  if (readiness.isLoading || !readiness.data) {
    return (
      <section className="border-b border-slate-200 p-5">
        <p className="text-sm text-slate-500">Running send-ready check…</p>
      </section>
    );
  }

  const report = readiness.data.report;
  const tone = VERDICT_TONE[report.verdict];

  return (
    <section className="flex flex-col gap-3 border-b border-slate-200 bg-white p-5">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-500">
          Send-Ready Check
        </h2>
        <button
          type="button"
          onClick={() => readiness.refetch()}
          className="text-xs text-slate-400 hover:text-slate-600"
        >
          Re-check
        </button>
      </div>

      <div className={`rounded-lg border px-4 py-3 ${tone.box}`}>
        <p className={`text-sm font-semibold ${tone.text}`}>{tone.label}</p>
        <p className="mt-0.5 text-xs text-slate-600">{report.summary}</p>
      </div>

      {audit.data?.audit.is_pdf && audit.data.audit.verdict === "leaky" && (
        <div className="rounded-lg border border-red-300 bg-red-50 px-4 py-3">
          <p className="text-sm font-semibold text-red-800">⚠ Un-Redact Test failed</p>
          <p className="mt-0.5 text-xs text-red-700">{audit.data.audit.summary}</p>
          <p className="mt-1 text-[11px] text-red-600">
            Those black boxes are cosmetic — the text underneath is still in the file. Clean
            this document to remove it for real.
          </p>
        </div>
      )}
      {audit.data?.audit.is_pdf && audit.data.audit.verdict === "safe" && (
        <p className="text-xs text-green-700">✓ Un-Redact Test passed — no text recoverable under any cover.</p>
      )}

      {report.verdict !== "ready" && (
        <button
          type="button"
          onClick={() => clean.mutate()}
          disabled={clean.isPending}
          className="rounded-md bg-slate-900 px-3 py-2 text-sm font-medium text-white hover:bg-slate-700 disabled:opacity-40"
        >
          {clean.isPending ? "Cleaning & verifying…" : "Clean before you send"}
        </button>
      )}

      {cleaned && cleaned.validation.ok && (
        <div className="rounded-lg border border-green-200 bg-green-50 px-4 py-3">
          <p className="text-sm font-semibold text-green-800">Verified clean copy ready</p>
          <p className="mt-0.5 text-xs text-green-700">
            Proof: {cleaned.validation.summary}. Redacted text is unrecoverable and embedded
            metadata is stripped.
          </p>
          <a
            href={exportUrl(docId, cleaned.validation.output_format as ExportFormat)}
            className="mt-2 inline-block rounded-md border border-green-300 bg-white px-3 py-1.5 text-xs font-medium text-green-800 hover:bg-green-100"
          >
            Download clean copy (.{cleaned.validation.output_format})
          </a>
        </div>
      )}

      <ul className="space-y-2">
        {report.checks.map((check) => (
          <li
            key={check.id}
            className="rounded-lg border border-slate-200 px-3 py-2 text-xs"
          >
            <div className="flex items-center justify-between gap-2">
              <span className="flex items-center gap-2 font-medium text-slate-800">
                <Dot status={check.status} />
                {check.label}
                {check.count > 0 && (
                  <span className="rounded-full bg-slate-100 px-1.5 py-0.5 text-[10px] text-slate-600">
                    {check.count}
                  </span>
                )}
              </span>
              {check.status !== "pass" &&
                check.fixable &&
                (check.fix_action === "redact_pii" ||
                  check.fix_action === "sanitize_metadata") && (
                  <button
                    type="button"
                    onClick={() => fix.mutate(check.fix_action)}
                    disabled={fix.isPending}
                    className="shrink-0 rounded-md border border-slate-300 px-2 py-1 text-[11px] hover:bg-slate-50 disabled:opacity-40"
                  >
                    {fix.isPending ? "Fixing…" : "Fix"}
                  </button>
                )}
            </div>
            <p className="mt-1 text-slate-500">{check.detail}</p>
          </li>
        ))}
      </ul>

      {(readiness.isError || fix.isError || clean.isError) && (
        <p role="alert" className="text-xs text-red-600">
          {[readiness.error, fix.error, clean.error]
            .filter(Boolean)
            .map((e) => (e instanceof Error ? e.message : String(e)))
            .join(" · ")}
        </p>
      )}
    </section>
  );
}

const VERDICT_TONE: Record<
  string,
  { label: string; box: string; text: string }
> = {
  ready: {
    label: "Ready to send",
    box: "border-green-200 bg-green-50",
    text: "text-green-800",
  },
  needs_fixes: {
    label: "Needs fixes before sending",
    box: "border-amber-200 bg-amber-50",
    text: "text-amber-800",
  },
  blocked: {
    label: "Blocked — hidden data can still leak",
    box: "border-red-200 bg-red-50",
    text: "text-red-800",
  },
};

function Dot({ status }: { status: ReadinessCheck["status"] }) {
  const color =
    status === "fail" ? "bg-red-500" : status === "warn" ? "bg-amber-500" : "bg-green-500";
  return <span className={`inline-block h-2 w-2 rounded-full ${color}`} aria-hidden />;
}
