"use client";

import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  downloadPacketExport,
  downloadPacketReportHtml,
  getPacketReport,
  runPacketAudit,
  type EvidenceRef,
  type ExpertReport,
} from "@/lib/api";
import { EvidenceDrawer } from "@/components/expert/EvidenceDrawer";
import { PacketExportProofPanel } from "@/components/expert/ExportProofPanel";
import { FindingsList } from "@/components/expert/FindingsList";
import { PacketFixesPanel } from "@/components/expert/PacketFixesPanel";
import { VerdictCard } from "@/components/expert/VerdictCard";
import { useToast } from "@/components/ui/Toast";

type Tab = "verdict" | "findings" | "facts" | "evidence" | "fixes" | "export";

const TABS: { id: Tab; label: string }[] = [
  { id: "verdict", label: "Verdict" },
  { id: "findings", label: "Issues" },
  { id: "fixes", label: "Fixes" },
  { id: "export", label: "Clean export" },
  { id: "facts", label: "Extracted facts" },
  { id: "evidence", label: "Evidence" },
];

export function PacketWorkspace({ packetId }: { packetId: string }) {
  const qc = useQueryClient();
  const toast = useToast();
  const [tab, setTab] = useState<Tab>("verdict");
  const [activeEvidence, setActiveEvidence] = useState<EvidenceRef[] | null>(null);

  const report = useQuery({
    queryKey: ["packet-report", packetId],
    queryFn: () => getPacketReport(packetId),
    enabled: Boolean(packetId),
  });

  const audit = useQuery({
    queryKey: ["packet-audit", packetId],
    queryFn: () => runPacketAudit(packetId),
    enabled: false,
  });

  async function runAudit() {
    try {
      const r = await audit.refetch();
      if (r.data) {
        toast.success(`Audit complete: ${r.data.verdict.replace("_", " ")}`);
        qc.invalidateQueries({ queryKey: ["packet-report", packetId] });
        qc.invalidateQueries({ queryKey: ["packets"] });
        setTab("verdict");
      }
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Audit failed");
    }
  }

  if (report.isLoading) {
    return <p className="text-slate-500">Loading packet…</p>;
  }
  if (report.isError) {
    return (
      <div className="card p-6">
        <p className="text-sm text-slate-600">
          No audit run yet for this packet. Add documents and run the audit to get an
          evidence-bound verdict.
        </p>
        <button type="button" className="btn-primary mt-4" onClick={runAudit}>
          Run audit now
        </button>
      </div>
    );
  }

  const r = report.data;
  if (!r) {
    return (
      <div className="card p-6">
        <p className="text-sm text-slate-600">No audit report available.</p>
        <button type="button" className="btn-primary mt-4" onClick={runAudit}>
          Run audit
        </button>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <VerdictCard
        verdict={r.verdict}
        score={r.readiness_score}
        summary={r.executive_summary}
        action={
          <button
            type="button"
            className="btn-secondary"
            onClick={runAudit}
            disabled={audit.isFetching}
          >
            {audit.isFetching ? "Auditing…" : "Re-run audit"}
          </button>
        }
      />

      <div className="flex gap-1 border-b border-line">
        {TABS.map((t) => (
          <button
            key={t.id}
            type="button"
            className={`mode-tab ${tab === t.id ? "mode-tab-active" : ""}`}
            onClick={() => setTab(t.id)}
          >
            {t.label}
            {t.id === "findings" && r.findings.length > 0 && (
              <span className="ml-1 rounded-full bg-slate-100 px-1.5 text-[10px] text-slate-600">
                {r.findings.length}
              </span>
            )}
          </button>
        ))}
      </div>

      {tab === "verdict" && <VerdictTab report={r} />}
      {tab === "findings" && (
        <FindingsList findings={r.findings} onShowEvidence={setActiveEvidence} />
      )}
      {tab === "fixes" && (
        <PacketFixesPanel packetId={packetId} findings={r.findings} onApplied={runAudit} />
      )}
      {tab === "export" && (
        <PacketExportProofPanel
          packetId={packetId}
          documentCount={r.documents_detected.length}
          onDownloadZip={() => downloadPacketExport(packetId, "zip")}
          onDownloadReport={() => downloadPacketReportHtml(packetId)}
        />
      )}
      {tab === "facts" && <FactsTab report={r} />}
      {tab === "evidence" && <EvidenceTab findings={r.findings} onShowEvidence={setActiveEvidence} />}

      {activeEvidence && (
        <EvidenceDrawer evidence={activeEvidence} onClose={() => setActiveEvidence(null)} />
      )}
    </div>
  );
}

function VerdictTab({ report }: { report: ExpertReport }) {
  return (
    <div className="grid gap-4 md:grid-cols-2">
      <section className="card p-5">
        <h3 className="text-sm font-semibold text-ink">Documents detected</h3>
        <ul className="mt-3 space-y-2">
          {report.documents_detected.map((d) => (
            <li key={d.document_id} className="rounded-lg border border-line px-3 py-2 text-xs">
              <span className="font-medium text-slate-800">{d.document_type ?? "other"}</span>
              <span className="ml-2 text-slate-500">{d.title ?? d.document_id}</span>
              <span className="ml-2 text-slate-400">{Math.round(d.confidence * 100)}%</span>
            </li>
          ))}
          {report.documents_detected.length === 0 && (
            <li className="text-xs text-slate-500">No documents yet.</li>
          )}
        </ul>
      </section>
      <section className="card p-5">
        <h3 className="text-sm font-semibold text-ink">Missing documents</h3>
        <ul className="mt-3 space-y-2">
          {report.missing_documents.map((m) => (
            <li key={m.document_type} className="rounded-lg border border-line px-3 py-2 text-xs">
              <span className="font-medium text-slate-800">{m.label}</span>
              <span className="ml-2 text-slate-500">{m.why_required}</span>
            </li>
          ))}
          {report.missing_documents.length === 0 && (
            <li className="text-xs text-slate-500">None — the packet is complete.</li>
          )}
        </ul>
      </section>
      {report.recommended_actions.length > 0 && (
        <section className="card p-5 md:col-span-2">
          <h3 className="text-sm font-semibold text-ink">Recommended actions</h3>
          <ul className="mt-3 space-y-2">
            {report.recommended_actions.map((a, i) => (
              <li key={i} className="rounded-lg border border-line px-3 py-2 text-xs">
                <span className="font-medium text-slate-800">{a.title}</span>
                <span className="ml-2 text-slate-600">{a.detail}</span>
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}

function FactsTab({ report }: { report: ExpertReport }) {
  if (report.extracted_fields.length === 0) {
    return <p className="text-sm text-slate-500">No fields extracted yet.</p>;
  }
  return (
    <div className="card overflow-hidden">
      <table className="w-full text-left text-xs">
        <thead className="bg-chrome text-slate-600">
          <tr>
            <th className="px-3 py-2 font-medium">Field</th>
            <th className="px-3 py-2 font-medium">Value</th>
            <th className="px-3 py-2 font-medium">Document</th>
            <th className="px-3 py-2 font-medium">Confidence</th>
          </tr>
        </thead>
        <tbody>
          {report.extracted_fields.map((f, i) => (
            <tr key={i} className="border-t border-line">
              <td className="px-3 py-2 font-medium text-slate-700">{f.name}</td>
              <td className="px-3 py-2 text-slate-800">{f.value}</td>
              <td className="px-3 py-2 text-slate-500">{f.document_type ?? f.document_id}</td>
              <td className="px-3 py-2 text-slate-500">{Math.round(f.confidence * 100)}%</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function EvidenceTab({
  findings,
  onShowEvidence,
}: {
  findings: ExpertReport["findings"];
  onShowEvidence: (e: EvidenceRef[]) => void;
}) {
  const all: EvidenceRef[] = findings.flatMap((f) => f.evidence);
  const seen = new Map<string, EvidenceRef>();
  for (const e of all) {
    seen.set(`${e.document_id}|${e.node_id ?? ""}|${e.raw_text}`, e);
  }
  if (seen.size === 0) {
    return (
      <p className="text-sm text-slate-500">
        No cited evidence yet. Absence-based findings escalate to human review.
      </p>
    );
  }
  return (
    <ul className="space-y-2">
      {Array.from(seen.values()).map((e, i) => (
        <li key={i} className="card border border-line p-3 text-xs">
          <div className="flex items-center gap-2">
            <span className="font-medium text-slate-700">{e.document_type ?? e.document_id}</span>
            {e.page_number != null && <span className="text-slate-400">page {e.page_number}</span>}
          </div>
          <p className="mt-1 font-mono text-[11px] text-slate-700">“{e.raw_text}”</p>
          <button
            type="button"
            className="btn-ghost mt-2 px-2 py-1 text-[11px]"
            onClick={() => onShowEvidence([e])}
          >
            Open citation
          </button>
        </li>
      ))}
    </ul>
  );
}
