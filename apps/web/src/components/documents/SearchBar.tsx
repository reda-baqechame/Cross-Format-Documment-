"use client";

import { useMutation } from "@tanstack/react-query";
import Link from "next/link";
import { useState } from "react";

import { searchDocuments, semanticSearch } from "@/lib/api";

type Mode = "keyword" | "semantic";
interface Hit {
  doc_id: string;
  title: string | null;
  snippet: string;
  score?: number;
}

/**
 * Search across every document. Keyword mode does redaction-aware substring matching;
 * semantic mode ranks whole documents by TF-IDF relevance, so a topic matches even
 * without the exact word.
 */
export function SearchBar() {
  const [q, setQ] = useState("");
  const [mode, setMode] = useState<Mode>("keyword");

  const search = useMutation<Hit[], Error, { query: string; mode: Mode }>({
    mutationFn: async ({ query, mode }) => {
      if (mode === "semantic") return semanticSearch(query);
      const res = await searchDocuments(query);
      return res.hits;
    },
  });

  const run = () => q.trim() && search.mutate({ query: q, mode });

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap gap-2">
        <input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && run()}
          placeholder={
            mode === "semantic"
              ? "Find documents by topic…"
              : "Search for exact words across all documents…"
          }
          className="min-w-[12rem] flex-1 rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-blue-400 focus:outline-none"
        />
        <div className="inline-flex overflow-hidden rounded-md border border-slate-300 text-sm">
          {(["keyword", "semantic"] as Mode[]).map((m) => (
            <button
              key={m}
              onClick={() => setMode(m)}
              className={
                mode === m ? "bg-slate-900 px-3 py-2 text-white" : "px-3 py-2 hover:bg-slate-50"
              }
            >
              {m === "keyword" ? "Keyword" : "Semantic"}
            </button>
          ))}
        </div>
        <button
          onClick={run}
          disabled={search.isPending || !q.trim()}
          className="rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-500 disabled:opacity-40"
        >
          {search.isPending ? "Searching…" : "Search"}
        </button>
      </div>

      {search.data && (
        <ul className="space-y-2">
          {search.data.length === 0 && <li className="text-sm text-slate-500">No matches.</li>}
          {search.data.map((h) => (
            <li key={h.doc_id} className="rounded-md border border-slate-200 p-3 text-sm">
              <div className="flex items-center justify-between">
                <Link href={`/documents/${h.doc_id}`} className="font-medium hover:underline">
                  {h.title ?? h.doc_id.slice(0, 12)}
                </Link>
                {typeof h.score === "number" && (
                  <span className="rounded bg-slate-100 px-2 py-0.5 text-xs text-slate-500">
                    {Math.round(h.score * 100)}% match
                  </span>
                )}
              </div>
              <p className="text-slate-500">{h.snippet}</p>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
