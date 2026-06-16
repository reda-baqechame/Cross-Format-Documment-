"use client";

import { useMutation } from "@tanstack/react-query";
import Link from "next/link";
import { useState } from "react";

import { searchDocuments, type SearchResponse } from "@/lib/api";

/** Full-text search across every document (redaction-aware), over the canonical model. */
export function SearchBar() {
  const [q, setQ] = useState("");
  const search = useMutation<SearchResponse, Error, string>({
    mutationFn: (query: string) => searchDocuments(query),
  });

  return (
    <div className="space-y-3">
      <div className="flex gap-2">
        <input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && q.trim() && search.mutate(q)}
          placeholder="Search across all documents…"
          className="flex-1 rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-blue-400 focus:outline-none"
        />
        <button
          onClick={() => search.mutate(q)}
          disabled={search.isPending || !q.trim()}
          className="rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-700 disabled:opacity-40"
        >
          Search
        </button>
      </div>
      {search.data && (
        <ul className="space-y-2">
          {search.data.hits.length === 0 && (
            <li className="text-sm text-slate-500">No matches.</li>
          )}
          {search.data.hits.map((h) => (
            <li key={h.doc_id} className="rounded-md border border-slate-200 p-3 text-sm">
              <Link href={`/documents/${h.doc_id}`} className="font-medium hover:underline">
                {h.title ?? h.doc_id.slice(0, 12)}
              </Link>
              <p className="text-slate-500">{h.snippet}</p>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
