"use client";

import { useMutation } from "@tanstack/react-query";
import type { ExpertFinding } from "@/lib/api";
import { redactSensitive, sanitizeMetadata } from "@/lib/api";

export function DocumentFixesPanel({
  docId,
  findings,
  onFixed,
}: {
  docId: string;
  findings: ExpertFinding[];
  onFixed?: () => void;
}) {
  const fixable = findings.filter((f) => f.fix_available);

  const applyFix = useMutation({
    mutationFn: async () => {
      for (const f of fixable) {
        if (f.type === "metadata_risk") await sanitizeMetadata(docId);
        if (f.type === "redaction_risk") await redactSensitive(docId);
      }
    },
    onSuccess: () => onFixed?.(),
  });

  if (fixable.length === 0) {
    return (
      <p className="text-sm text-slate-500">
        No one-click fixes available. Use Clean before you send or fix issues manually.
      </p>
    );
  }

  return (
    <div className="card space-y-4 p-5">
      <p className="text-sm text-slate-600">
        {fixable.length} finding(s) can be fixed with reversible patches.
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
      <button
        type="button"
        className="btn-primary"
        onClick={() => applyFix.mutate()}
        disabled={applyFix.isPending}
      >
        {applyFix.isPending ? "Applying…" : `Apply ${fixable.length} fix(es)`}
      </button>
    </div>
  );
}
