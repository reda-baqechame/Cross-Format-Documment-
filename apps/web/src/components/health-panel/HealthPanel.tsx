"use client";

import type { DocumentHealth } from "@docos/shared-types";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { HealthBadge } from "@/components/health-panel/HealthBadge";
import {
  redactNode,
  redactSensitive,
  remediateAccessibility,
  sanitizeMetadata,
  scanSensitive,
  signDocument,
} from "@/lib/api";
import { useWorkspace } from "@/lib/store";

/**
 * The persistent "document health" panel — the product's signature surface. It puts
 * accessibility, metadata hygiene, redaction, and signature readiness in one place
 * instead of scattering them across separate editors, viewers, and signing tools.
 */
export function HealthPanel({ health, docId }: { health: DocumentHealth; docId: string }) {
  const pct = Math.round(health.accessibility_score * 100);
  const queryClient = useQueryClient();
  const selectedNodeId = useWorkspace((s) => s.selectedNodeId);

  const refresh = () => {
    queryClient.invalidateQueries({ queryKey: ["model", docId] });
    queryClient.invalidateQueries({ queryKey: ["health", docId] });
    queryClient.invalidateQueries({ queryKey: ["sensitive", docId] });
  };

  const sensitive = useQuery({
    queryKey: ["sensitive", docId],
    queryFn: () => scanSensitive(docId),
  });
  const sensitiveCount = sensitive.data?.node_count ?? 0;

  const cleanSensitive = useMutation({
    mutationFn: () => redactSensitive(docId),
    onSuccess: refresh,
  });

  const fixA11y = useMutation({
    mutationFn: () => remediateAccessibility(docId),
    onSuccess: refresh,
  });

  const sanitize = useMutation({ mutationFn: () => sanitizeMetadata(docId), onSuccess: refresh });
  const redact = useMutation({
    mutationFn: () => redactNode(docId, selectedNodeId as string),
    onSuccess: refresh,
  });
  const sign = useMutation({
    mutationFn: (signer: string) => signDocument(docId, signer),
    onSuccess: refresh,
  });

  return (
    <aside className="flex w-80 shrink-0 flex-col gap-4 border-l border-slate-200 bg-white p-5">
      <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-500">
        Document health
      </h2>

      <Stat label="Accessibility" value={`${pct}%`} ok={pct >= 75} />
      <Stat label="Metadata" value={health.metadata_risk ? "Needs review" : "Clean"} ok={!health.metadata_risk} />
      <Stat
        label="Redactions"
        value={health.has_pending_redactions ? "Pending" : "None pending"}
        ok={!health.has_pending_redactions}
      />
      <Stat
        label="Sensitive data"
        value={
          sensitive.isLoading
            ? "Scanning…"
            : sensitiveCount > 0
              ? `${sensitiveCount} to redact`
              : "Clean"
        }
        ok={!sensitive.isLoading && sensitiveCount === 0}
      />
      <Stat
        label="Signature"
        value={health.signed ? "Signed" : health.ready_for_signing ? "Ready" : "Not ready"}
        ok={health.signed || health.ready_for_signing}
      />

      <div className="flex flex-col gap-2">
        <h3 className="text-xs font-semibold uppercase text-slate-400">Trust actions</h3>
        <button
          onClick={() => sanitize.mutate()}
          disabled={sanitize.isPending || !health.metadata_risk}
          className="rounded-md border border-slate-300 px-3 py-2 text-sm hover:bg-slate-50 disabled:opacity-40"
        >
          {sanitize.isPending ? "Sanitizing…" : "Sanitize metadata"}
        </button>
        <button
          onClick={() => fixA11y.mutate()}
          disabled={fixA11y.isPending || pct >= 100}
          title="Auto-tag headings, set reading order, and add image alt text"
          className="rounded-md border border-slate-300 px-3 py-2 text-sm hover:bg-slate-50 disabled:opacity-40"
        >
          {fixA11y.isPending ? "Fixing…" : pct >= 100 ? "Accessibility ✓" : "Fix accessibility"}
        </button>
        <button
          onClick={() => redact.mutate()}
          disabled={redact.isPending || !selectedNodeId}
          title={selectedNodeId ? "Redact the selected text" : "Select text first"}
          className="rounded-md border border-slate-300 px-3 py-2 text-sm hover:bg-slate-50 disabled:opacity-40"
        >
          {redact.isPending ? "Redacting…" : "Redact selection"}
        </button>
        <button
          onClick={() => cleanSensitive.mutate()}
          disabled={cleanSensitive.isPending || sensitiveCount === 0}
          title={
            sensitiveCount > 0
              ? "Detect and redact PII/secrets before export"
              : "No sensitive data detected"
          }
          className="rounded-md border border-slate-300 px-3 py-2 text-sm hover:bg-slate-50 disabled:opacity-40"
        >
          {cleanSensitive.isPending
            ? "Cleaning…"
            : sensitiveCount > 0
              ? `Clean sensitive data (${sensitiveCount})`
              : "No sensitive data"}
        </button>
        <button
          onClick={() => {
            const signer = window.prompt("Sign as (your name):")?.trim();
            if (signer) sign.mutate(signer);
          }}
          disabled={sign.isPending || health.signed}
          title={health.signed ? "Already signed" : "Apply a tamper-evident signature"}
          className="rounded-md border border-slate-300 px-3 py-2 text-sm hover:bg-slate-50 disabled:opacity-40"
        >
          {health.signed ? "Signed ✓" : sign.isPending ? "Signing…" : "Sign document"}
        </button>
      </div>

      <div>
        <h3 className="mb-2 text-xs font-semibold uppercase text-slate-400">Findings</h3>
        <ul className="space-y-2">
          {health.findings.map((f, i) => (
            <HealthBadge key={`${f.code}-${i}`} finding={f} />
          ))}
        </ul>
      </div>
    </aside>
  );
}

function Stat({ label, value, ok }: { label: string; value: string; ok: boolean }) {
  return (
    <div className="flex items-center justify-between rounded-md bg-slate-50 px-3 py-2">
      <span className="text-sm text-slate-600">{label}</span>
      <span className={`text-sm font-medium ${ok ? "text-green-700" : "text-amber-700"}`}>
        {value}
      </span>
    </div>
  );
}
