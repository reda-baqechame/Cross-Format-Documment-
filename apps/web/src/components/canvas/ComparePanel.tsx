"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import { useState } from "react";

import { diffDocuments, listDocuments } from "@/lib/api";
import { friendlyApiError } from "@/lib/upload";

/** Cross-document redline — wired to the backend diff API. */
export function ComparePanel({ docId }: { docId: string }) {
  const [against, setAgainst] = useState("");
  const docs = useQuery({ queryKey: ["documents"], queryFn: listDocuments });

  const diff = useMutation({
    mutationFn: (otherId: string) => diffDocuments(docId, otherId),
  });

  const others = (docs.data?.documents ?? []).filter((d) => d.doc_id !== docId);

  return (
    <section className="mb-6 rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
      <h3 className="text-sm font-semibold text-ink">Compare with another document</h3>
      <p className="mt-1 text-xs text-slate-500">
        Block-level redline across formats — see what changed between two files.
      </p>
      <div className="mt-3 flex flex-col gap-2 sm:flex-row">
        <select
          value={against}
          onChange={(e) => setAgainst(e.target.value)}
          aria-label="Document to compare against"
          className="min-h-[44px] flex-1 rounded-lg border border-slate-300 px-3 text-sm"
        >
          <option value="">Choose a document…</option>
          {others.map((d) => (
            <option key={d.doc_id} value={d.doc_id}>
              {d.title ?? d.doc_id.slice(0, 12)} ({d.source_format})
            </option>
          ))}
        </select>
        <button
          type="button"
          disabled={!against || diff.isPending}
          onClick={() => diff.mutate(against)}
          className="min-h-[44px] rounded-lg bg-brand-600 px-4 text-sm font-medium text-white hover:bg-brand-500 disabled:opacity-40"
        >
          {diff.isPending ? "Comparing…" : "Compare"}
        </button>
      </div>

      {diff.isError && (
        <p role="alert" className="mt-2 text-sm text-red-600">
          {friendlyApiError(diff.error, "Compare failed.")}
        </p>
      )}

      {diff.data && (
        <div className="mt-4 space-y-2 border-t border-slate-100 pt-3">
          <p className="text-xs text-slate-500">
            +{diff.data.result.added} added · −{diff.data.result.removed} removed · ~
            {diff.data.result.changed} changed
          </p>
          <ul className="max-h-64 space-y-2 overflow-auto text-sm">
            {diff.data.result.segments.map((seg, i) => (
              <li
                key={i}
                className={[
                  "rounded-lg px-3 py-2",
                  seg.op === "delete" ? "bg-red-50 line-through text-red-800" : "",
                  seg.op === "insert" ? "bg-green-50 text-green-900" : "",
                  seg.op === "replace" ? "bg-amber-50 text-amber-900" : "",
                  seg.op === "equal" ? "text-slate-600" : "",
                ].join(" ")}
              >
                {seg.op === "delete" || seg.op === "replace" ? seg.a_text : null}
                {seg.op === "insert" || seg.op === "replace" ? seg.b_text : null}
                {seg.op === "equal" ? seg.a_text : null}
              </li>
            ))}
          </ul>
        </div>
      )}
    </section>
  );
}
