"use client";

import { useMutation } from "@tanstack/react-query";
import { useState } from "react";

import { askDocument, fetchSummary, type AskResponse, type SummaryResponse } from "@/lib/api";

/**
 * Ask-the-document panel. Questions and summaries are answered from the document's own
 * text, over the canonical model, with node-level citations — and run fully offline
 * (the "Offline" badge) unless an LLM provider is configured.
 */
export function AskPanel({ docId }: { docId: string }) {
  const [question, setQuestion] = useState("");

  const ask = useMutation<AskResponse, Error, string>({
    mutationFn: (q: string) => askDocument(docId, q),
  });
  const summary = useMutation<SummaryResponse, Error, void>({
    mutationFn: () => fetchSummary(docId),
  });

  const result = ask.data ?? summary.data;
  const pending = ask.isPending || summary.isPending;

  return (
    <section className="mb-6 rounded-lg border border-slate-200 bg-white p-4">
      <div className="flex items-center gap-2">
        <input
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && question.trim() && ask.mutate(question)}
          placeholder="Ask this document… (e.g. “what is the refund policy?”)"
          className="flex-1 rounded-md border border-slate-300 px-3 py-1.5 text-sm focus:border-blue-400 focus:outline-none"
        />
        <button
          onClick={() => ask.mutate(question)}
          disabled={pending || !question.trim()}
          className="rounded-md bg-blue-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-blue-500 disabled:opacity-40"
        >
          {ask.isPending ? "Asking…" : "Ask"}
        </button>
        <button
          onClick={() => summary.mutate()}
          disabled={pending}
          className="rounded-md border border-slate-300 px-3 py-1.5 text-sm hover:bg-slate-50 disabled:opacity-40"
        >
          {summary.isPending ? "Summarizing…" : "Summarize"}
        </button>
      </div>

      {result && (
        <div className="mt-3 border-t border-slate-100 pt-3">
          <div className="flex items-center gap-2">
            <p className="whitespace-pre-wrap text-sm text-slate-800">
              {"answer" in result ? result.answer : result.summary}
            </p>
            <span
              className="shrink-0 rounded bg-slate-100 px-1.5 py-0.5 text-[10px] uppercase text-slate-500"
              title={result.used_llm ? "Phrased by the configured LLM" : "Computed locally, no data egress"}
            >
              {result.used_llm ? "AI" : "Offline"}
            </span>
          </div>
          {result.citations.length > 0 && (
            <ul className="mt-2 space-y-1">
              {result.citations.map((c) => (
                <li key={c.node_id} className="text-xs text-slate-500">
                  <span className="font-mono text-slate-400">{c.node_id.slice(0, 8)}</span>{" "}
                  {c.excerpt}
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </section>
  );
}
