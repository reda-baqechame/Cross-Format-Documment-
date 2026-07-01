"use client";

import { useState } from "react";
import {
  applyPacketFixes,
  planPacketFixes,
  type ExpertFinding,
  type FixPlanView,
} from "@/lib/api";
import { useToast } from "@/components/ui/Toast";

export function PacketFixesPanel({
  packetId,
  findings,
  onApplied,
}: {
  packetId: string;
  findings: ExpertFinding[];
  onApplied: () => Promise<void>;
}) {
  const toast = useToast();
  const [plans, setPlans] = useState<FixPlanView[] | null>(null);
  const [busy, setBusy] = useState(false);
  const fixable = findings.filter((f) => f.fix_available);

  async function loadPlans() {
    setBusy(true);
    try {
      const res = await planPacketFixes(packetId);
      setPlans(res.plans);
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Could not load fix plans");
    } finally {
      setBusy(false);
    }
  }

  async function applyAll() {
    if (!plans?.length) return;
    setBusy(true);
    try {
      await applyPacketFixes(
        packetId,
        plans.map((p) => p.finding_id),
      );
      toast.success("Fixes applied — re-running audit");
      setPlans(null);
      await onApplied();
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Apply failed");
    } finally {
      setBusy(false);
    }
  }

  if (fixable.length === 0) {
    return (
      <p className="text-sm text-slate-500">
        No one-click fixes for this audit. Resolve blocking issues manually, then re-run.
      </p>
    );
  }

  return (
    <div className="card space-y-4 p-5">
      <p className="text-sm text-slate-600">
        {fixable.length} finding(s) can be fixed with reversible patches (metadata scrub or cited
        redaction).
      </p>
      <ul className="space-y-2 text-xs">
        {fixable.map((f) => (
          <li key={f.id} className="rounded-lg border border-line px-3 py-2">
            <span className="font-medium text-slate-800">{f.title}</span>
            {f.recommended_action && (
              <span className="ml-2 text-slate-500">{f.recommended_action}</span>
            )}
          </li>
        ))}
      </ul>
      <div className="flex flex-wrap gap-2">
        <button type="button" className="btn-secondary" onClick={loadPlans} disabled={busy}>
          {busy ? "Loading…" : "Preview fix plan"}
        </button>
        {plans && plans.length > 0 && (
          <button type="button" className="btn-primary" onClick={applyAll} disabled={busy}>
            Apply {plans.length} fix(es) & re-audit
          </button>
        )}
      </div>
      {plans && (
        <ul className="space-y-1 text-xs text-slate-600">
          {plans.map((p) => (
            <li key={p.finding_id}>
              {p.title} · {p.patch_count} patch(es) on {p.document_id}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
