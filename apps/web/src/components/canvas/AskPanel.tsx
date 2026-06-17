"use client";

import { useMutation } from "@tanstack/react-query";
import { useState } from "react";

import { askDocument, fetchSummary, type AskResponse, type SummaryResponse } from "@/lib/api";
import { useWorkspace } from "@/lib/store";
import { friendlyApiError } from "@/lib/upload";

/**
 * Ask-the-document panel. Questions and summaries are answered from the document's own
 * text, over the canonical model, with node-level citations — and run fully offline
 * (the "Offline" badge) unless an LLM provider is configured.
 */
export function AskPanel({ docId }: { docId: string }) {
  const [question, setQuestion] = useState("");
  const select = useWorkspace((s) => s.select);

  const ask = useMutation<AskResponse, Error, string>({
    mutationFn: (q: string) => askDocument(docId, q),
  });
  const summary = useMutation<SummaryResponse, Error, void>({
    mutationFn: () => fetchSummary(docId),
  });

  const result = ask.data ?? summary.data;
  const pending = ask.isPending || summary.isPending;
  const error = ask.error ?? summary.error;

  return (
    <section className="mb-6 rounded-lg border border-slate-200 bg-white p-4" aria-label="Ask this document">
      <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
        <input
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && question.trim() && ask.mutate(question)}
          placeholder="Ask this document… (e.g. “what is the refund policy?”)"
          aria-label="Question about this document"
          className="min-h-[44px] flex-1 rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-brand-400 focus:outline-none"
        />
        <div className="flex gap-2">
          <button
            type="button"
            onClick={() => ask.mutate(question)}
            disabled={pending || !question.trim()}
            aria-label="Ask question"
            className="min-h-[44px] flex-1 rounded-md bg-brand-600 px-3 py-2 text-sm font-medium text-white hover:bg-brand-500 disabled:opacity-40 sm:flex-none"
          >
            {ask.isPending ? "Asking…" : "Ask"}
          </button>
          <button
            type="button"
            onClick={() => summary.mutate()}
            disabled={pending}
            aria-label="Summarize document"
            className="min-h-[44px] flex-1 rounded-md border border-slate-300 px-3 py-2 text-sm hover:bg-slate-50 disabled:opacity-40 sm:flex-none"
          >
            {summary.isPending ? "Summarizing…" : "Summarize"}
          </button>
        </div>
      </div>

      {error && (
        <p role="alert" className="mt-2 text-sm text-red-600">
          {friendlyApiError(error, "Could not answer from this document.")}
        </p>
      )}

      {result && (
        <div className="mt-3 border-t border-slate-100 pt-3">
          <div className="flex items-start gap-2">
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
                <li key={c.node_id}>
                  <button
                    type="button"
                    onClick={() => select(c.node_id)}
                    className="w-full rounded px-1 py-1 text-left text-xs text-slate-600 hover:bg-yellow-50"
                  >
                    <span className="font-mono text-slate-400">{c.node_id.slice(0, 8)}</span>{" "}
                    {c.excerpt}
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </section>
  );
}
