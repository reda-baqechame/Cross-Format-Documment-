"use client";

import { useMutation } from "@tanstack/react-query";
import Link from "next/link";
import { useState } from "react";

import { notebookAsk, type NotebookResponse } from "@/lib/api";

/**
 * Multi-document notebook: ask one question across the whole library and get an answer
 * backed by citations that link to the exact source document. Runs offline by default.
 */
export function NotebookPanel() {
  const [question, setQuestion] = useState("");
  const ask = useMutation<NotebookResponse, Error, string>({
    mutationFn: (q: string) => notebookAsk(q),
  });

  const run = () => question.trim() && ask.mutate(question);

  return (
    <div className="space-y-3 rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
      <div>
        <h3 className="text-base font-semibold text-ink">Ask across all your documents</h3>
        <p className="text-sm text-slate-500">
          Get one answer drawn from your whole library, with links to the sources.
        </p>
      </div>
      <div className="flex flex-wrap gap-2">
        <input
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && run()}
          placeholder="e.g. What is our refund window?"
          className="min-h-[44px] min-w-0 flex-1 rounded-lg border border-slate-300 px-3 py-2 text-base focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-200 sm:text-sm"
        />
        <button
          onClick={run}
          disabled={ask.isPending || !question.trim()}
          className="min-h-[44px] rounded-lg bg-brand-600 px-4 py-2 text-sm font-medium text-white hover:bg-brand-500 disabled:opacity-40"
        >
          {ask.isPending ? "Thinking…" : "Ask"}
        </button>
      </div>

      {ask.isError && <p className="text-sm text-red-600">Couldn’t answer — please try again.</p>}

      {ask.data && (
        <div className="space-y-3">
          <p className="rounded-lg bg-slate-50 p-3 text-sm text-slate-800">{ask.data.answer}</p>
          {ask.data.citations.length > 0 && (
            <div className="space-y-1">
              <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">
                Sources
              </p>
              <ul className="space-y-1">
                {ask.data.citations.map((c) => (
                  <li key={`${c.doc_id}-${c.node_id}`} className="text-sm">
                    <Link
                      href={`/documents/${c.doc_id}`}
                      className="font-medium text-blue-600 hover:underline"
                    >
                      {c.title ?? c.doc_id.slice(0, 12)}
                    </Link>
                    <span className="text-slate-500"> — {c.excerpt}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
          <p className="text-xs text-slate-400">
            Searched {ask.data.document_count} document
            {ask.data.document_count === 1 ? "" : "s"}
            {ask.data.used_llm ? " · phrased by AI" : " · offline answer"}
          </p>
        </div>
      )}
    </div>
  );
}
