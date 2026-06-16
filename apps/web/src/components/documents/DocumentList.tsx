"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";

import { deleteDocument, listDocuments } from "@/lib/api";

/** Recent documents with open + delete — the workspace's home shelf. */
export function DocumentList() {
  const queryClient = useQueryClient();
  const docs = useQuery({ queryKey: ["documents"], queryFn: listDocuments });
  const remove = useMutation({
    mutationFn: (docId: string) => deleteDocument(docId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["documents"] }),
  });

  if (docs.isLoading) return <p className="text-sm text-slate-500">Loading documents…</p>;
  const documents = docs.data?.documents ?? [];
  if (documents.length === 0) return null;

  return (
    <section className="space-y-2">
      <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-500">
        Recent documents
      </h2>
      <ul className="divide-y divide-slate-200 rounded-lg border border-slate-200 bg-white">
        {documents.map((d) => (
          <li key={d.doc_id} className="flex items-center justify-between px-4 py-3">
            <Link href={`/documents/${d.doc_id}`} className="flex items-center gap-3 hover:underline">
              <span className="rounded bg-slate-100 px-2 py-0.5 text-xs uppercase text-slate-500">
                {d.source_format}
              </span>
              <span className="text-sm">{d.title ?? `Document ${d.doc_id.slice(0, 10)}…`}</span>
            </Link>
            <button
              onClick={() => remove.mutate(d.doc_id)}
              disabled={remove.isPending}
              className="text-xs text-slate-400 hover:text-red-600"
            >
              Delete
            </button>
          </li>
        ))}
      </ul>
    </section>
  );
}
