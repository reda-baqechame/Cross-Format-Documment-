"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";

import { deleteDocument, listDocuments } from "@/lib/api";
import { friendlyLoadError } from "@/lib/upload";

/** Recent documents with open + delete — the workspace's home shelf. */
export function DocumentList() {
  const queryClient = useQueryClient();
  const docs = useQuery({ queryKey: ["documents"], queryFn: listDocuments });
  const remove = useMutation({
    mutationFn: (docId: string) => deleteDocument(docId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["documents"] }),
  });

  if (docs.isLoading) return <p className="text-sm text-slate-500">Loading documents…</p>;
  if (docs.isError) {
    return (
      <p role="alert" className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
        Couldn&apos;t load your library: {friendlyLoadError(docs.error)}
      </p>
    );
  }
  const documents = docs.data?.documents ?? [];
  if (documents.length === 0) {
    return (
      <div className="rounded-lg border border-dashed border-slate-300 bg-white px-4 py-8 text-center text-sm text-slate-500">
        No documents yet. Drop your first file above to get started.
      </div>
    );
  }

  return (
    <section className="space-y-2">
      <ul className="divide-y divide-slate-200 rounded-lg border border-slate-200 bg-white">
        {documents.map((d) => (
          <li key={d.doc_id} className="flex items-center justify-between px-4 py-3">
            <Link href={`/documents/${d.doc_id}`} className="flex min-h-[44px] flex-1 items-center gap-3 py-2 hover:underline">
              <span className="rounded bg-slate-100 px-2 py-0.5 text-xs uppercase text-slate-500">
                {d.source_format}
              </span>
              <span className="text-sm">{d.title ?? `Document ${d.doc_id.slice(0, 10)}…`}</span>
            </Link>
            <button
              type="button"
              onClick={() => {
                const label = d.title ?? `Document ${d.doc_id.slice(0, 8)}…`;
                if (
                  window.confirm(
                    `Delete "${label}"? This removes the document and cannot be undone.`,
                  )
                ) {
                  remove.mutate(d.doc_id);
                }
              }}
              disabled={remove.isPending}
              aria-label={`Delete ${d.title ?? d.doc_id}`}
              className="min-h-[44px] min-w-[44px] px-2 text-xs text-slate-400 hover:text-red-600"
            >
              Delete
            </button>
          </li>
        ))}
      </ul>
    </section>
  );
}
