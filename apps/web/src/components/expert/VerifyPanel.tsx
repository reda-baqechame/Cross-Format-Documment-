"use client";

import Link from "next/link";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { DocumentExportProofPanel } from "@/components/expert/ExportProofPanel";
import { DocumentFixesPanel } from "@/components/expert/DocumentFixesPanel";
import { EvidenceDrawer } from "@/components/expert/EvidenceDrawer";
import { FindingsList } from "@/components/expert/FindingsList";
import { VerdictCard } from "@/components/expert/VerdictCard";
import {
  cleanDocument,
  exportUrl,
  fetchReadiness,
  fetchRedactionAudit,
  type CleanResponse,
  type EvidenceRef,
  type ExportFormat,
} from "@/lib/api";

type VerifyTab = "overview" | "issues" | "fixes" | "export";

const TABS: { id: VerifyTab; label: string }[] = [
  { id: "overview", label: "Overview" },
  { id: "issues", label: "Issues" },
  { id: "fixes", label: "Fixes" },
  { id: "export", label: "Clean export" },
];

/** Unified Verify surface — same expert spine as Command Center, for single documents. */
export function VerifyPanel({ docId }: { docId: string }) {
  const queryClient = useQueryClient();
  const [tab, setTab] = useState<VerifyTab>("overview");
  const [activeEvidence, setActiveEvidence] = useState<EvidenceRef[] | null>(null);
  const [cleaned, setCleaned] = useState<CleanResponse | null>(null);

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
    queryClient.invalidateQueries({ queryKey: ["model", docId] });
  };

  const clean = useMutation({
    mutationFn: () => cleanDocument(docId),
    onSuccess: (result) => {
      setCleaned(result);
      refresh();
    },
  });

  if (readiness.isLoading || !readiness.data) {
    return <p className="p-5 text-sm text-slate-500">Running send-ready check…</p>;
  }

  const report = readiness.data.report;
  const findings = readiness.data.expert_findings ?? [];
  const result = readiness.data.result;
  const score = result?.score != null ? result.score / 100 : undefined;
  const hasCleanable =
    report.verdict !== "ready" &&
    report.checks.some(
      (c) =>
        c.status !== "pass" &&
        (c.fix_action === "redact_pii" || c.fix_action === "sanitize_metadata"),
    );

  return (
    <div className="flex flex-col gap-4 p-4">
      <VerdictCard
        verdict={report.verdict}
        score={score}
        summary={report.summary}
        action={
          <button
            type="button"
            className="btn-secondary text-xs"
            onClick={() => readiness.refetch()}
          >
            Re-check
          </button>
        }
      />

      {audit.data?.audit.is_pdf && audit.data.audit.verdict === "leaky" && (
        <div className="rounded-lg border border-red-300 bg-red-50 px-4 py-3 text-xs text-red-700">
          Un-Redact Test failed — text may still be recoverable under black boxes. Clean this
          document to remove it for real.
        </div>
      )}

      {hasCleanable && (
        <button
          type="button"
          className="btn-primary"
          onClick={() => clean.mutate()}
          disabled={clean.isPending}
        >
          {clean.isPending ? "Cleaning & verifying…" : "Clean before you send"}
        </button>
      )}

      {cleaned?.validation.ok && (
        <div className="rounded-lg border border-trust-200 bg-trust-50 px-4 py-3 text-xs text-trust-800">
          Verified clean copy ready. Proof: {cleaned.validation.summary}
          <a
            href={exportUrl(docId, cleaned.validation.output_format as ExportFormat)}
            className="ml-2 underline"
          >
            Download (.{cleaned.validation.output_format})
          </a>
        </div>
      )}

      <div className="flex gap-1 border-b border-line">
        {TABS.map((t) => (
          <button
            key={t.id}
            type="button"
            className={`mode-tab ${tab === t.id ? "mode-tab-active" : ""}`}
            onClick={() => setTab(t.id)}
          >
            {t.label}
            {t.id === "issues" && findings.length > 0 && (
              <span className="ml-1 rounded-full bg-slate-100 px-1.5 text-[10px]">
                {findings.length}
              </span>
            )}
          </button>
        ))}
      </div>

      {tab === "overview" && (
        <div className="space-y-3 text-xs text-slate-600">
          <p>
            Evidence-bound Clean Before Send — same expert spine as{" "}
            <Link href="/packets" className="text-brand-600 hover:underline">
              Command Center
            </Link>{" "}
            for multi-document packets.
          </p>
          {result && (
            <ul className="space-y-1">
              <li>
                Blocking:{" "}
                {findings.filter((f) => f.severity === "blocking").length}
              </li>
              <li>
                Warnings:{" "}
                {findings.filter((f) => f.severity === "warning").length}
              </li>
              <li>Fix plans available: {result.fix_plans_available ?? 0}</li>
            </ul>
          )}
        </div>
      )}

      {tab === "issues" && (
        <FindingsList findings={findings} onShowEvidence={setActiveEvidence} />
      )}

      {tab === "fixes" && (
        <DocumentFixesPanel docId={docId} findings={findings} onFixed={refresh} />
      )}

      {tab === "export" && (
        <DocumentExportProofPanel
          docId={docId}
          validationSummary={cleaned?.validation.summary}
          outputFormat={cleaned?.validation.output_format}
        />
      )}

      {activeEvidence && (
        <EvidenceDrawer evidence={activeEvidence} onClose={() => setActiveEvidence(null)} />
      )}
    </div>
  );
}
