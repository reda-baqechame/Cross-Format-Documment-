"use client";

import { useQuery } from "@tanstack/react-query";

import { fetchExtract } from "@/lib/api";
import { useWorkspace } from "@/lib/store";
import { friendlyApiError } from "@/lib/upload";

/** Structured data extraction — dates, money, emails, label:value fields. */
export function ExtractPanel({ docId }: { docId: string }) {
  const select = useWorkspace((s) => s.select);
  const extract = useQuery({ queryKey: ["extract", docId], queryFn: () => fetchExtract(docId) });

  if (extract.isLoading) {
    return <p className="mb-4 text-sm text-slate-500">Extracting structured data…</p>;
  }
  if (extract.isError) {
    return (
      <p role="alert" className="mb-4 text-sm text-red-600">
        {friendlyApiError(extract.error, "Extraction failed.")}
      </p>
    );
  }

  const { entities, fields } = extract.data?.extraction ?? { entities: [], fields: [] };
  if (entities.length === 0 && fields.length === 0) {
    return (
      <p className="mb-4 text-sm text-slate-500">No structured entities detected in this document.</p>
    );
  }

  return (
    <section className="mb-6 rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
      <h3 className="text-sm font-semibold text-ink">Extracted data</h3>
      <p className="mt-1 text-xs text-slate-500">Tap a row to highlight the source in the document.</p>
      {entities.length > 0 && (
        <ul className="mt-3 space-y-1">
          {entities.slice(0, 20).map((e) => (
            <li key={`${e.node_id}-${e.value}`}>
              <button
                type="button"
                onClick={() => select(e.node_id)}
                className="flex w-full min-h-[44px] items-center justify-between rounded-lg px-2 py-1 text-left text-sm hover:bg-slate-50"
              >
                <span className="font-medium capitalize text-slate-700">{e.type}</span>
                <span className="truncate text-slate-600">{e.value}</span>
              </button>
            </li>
          ))}
        </ul>
      )}
      {fields.length > 0 && (
        <ul className="mt-2 space-y-1 border-t border-slate-100 pt-2">
          {fields.slice(0, 15).map((f) => (
            <li key={`${f.node_id}-${f.key}`}>
              <button
                type="button"
                onClick={() => select(f.node_id)}
                className="flex w-full min-h-[44px] items-center justify-between rounded-lg px-2 py-1 text-left text-sm hover:bg-slate-50"
              >
                <span className="font-medium text-slate-700">{f.key}</span>
                <span className="truncate text-slate-600">{f.value}</span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
