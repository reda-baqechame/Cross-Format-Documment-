"use client";

import type { EvidenceRef } from "@/lib/api";

export function EvidenceDrawer({
  evidence,
  onClose,
}: {
  evidence: EvidenceRef[];
  onClose: () => void;
}) {
  return (
    <div
      className="fixed inset-0 z-40 flex justify-end bg-black/30"
      onClick={onClose}
      role="dialog"
      aria-label="Source citations"
    >
      <div
        className="h-full w-full max-w-md overflow-auto bg-white p-5 shadow-pop"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-semibold text-ink">Source citations</h3>
          <button type="button" className="icon-btn" onClick={onClose} aria-label="Close">
            ✕
          </button>
        </div>
        <ul className="mt-3 space-y-2">
          {evidence.map((e, i) => (
            <li key={i} className="rounded-lg border border-line p-3 text-xs">
              <div className="flex flex-wrap items-center gap-2">
                <span className="font-medium text-slate-700">
                  {e.document_type ?? e.document_id}
                </span>
                {e.page_number != null && (
                  <span className="text-slate-400">page {e.page_number}</span>
                )}
                {e.field_name && (
                  <span className="rounded bg-chrome px-1.5 py-0.5 text-[10px] text-slate-600">
                    {e.field_name}
                  </span>
                )}
              </div>
              <p className="mt-1 font-mono text-[11px] text-slate-700">“{e.raw_text}”</p>
              {e.normalized_value && (
                <p className="mt-1 text-slate-500">→ {e.normalized_value}</p>
              )}
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
