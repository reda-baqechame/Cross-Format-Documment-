"use client";

import type { DocumentHealth } from "@docos/shared-types";

import { HealthBadge } from "@/components/health-panel/HealthBadge";

/**
 * The persistent "document health" panel — the product's signature surface. It puts
 * accessibility, metadata hygiene, redaction, and signature readiness in one place
 * instead of scattering them across separate editors, viewers, and signing tools.
 */
export function HealthPanel({ health }: { health: DocumentHealth }) {
  const pct = Math.round(health.accessibility_score * 100);
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
        label="Signature"
        value={health.signed ? "Signed" : health.ready_for_signing ? "Ready" : "Not ready"}
        ok={health.signed || health.ready_for_signing}
      />

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
