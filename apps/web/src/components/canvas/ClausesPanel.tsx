"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import {
  createClause,
  deleteClause,
  insertClause,
  listClauses,
  type Clause,
} from "@/lib/api";
import { useWorkspace } from "@/lib/store";
import { friendlyApiError } from "@/lib/upload";
import type { CanonicalDocument } from "@docos/shared-types";

/** Concatenate the text runs under a node (so a selected block can be saved as a clause). */
function nodeText(doc: CanonicalDocument, nodeId: string): string {
  const node = doc.nodes[nodeId];
  if (!node) return "";
  if (node.type === "run") return node.text ?? "";
  return (node.children ?? []).map((id) => nodeText(doc, id)).join(" ").trim();
}

export function ClausesPanel({ doc, docId }: { doc: CanonicalDocument; docId: string }) {
  const queryClient = useQueryClient();
  const selectedId = useWorkspace((s) => s.selectedNodeId);
  const clauses = useQuery({ queryKey: ["clauses"], queryFn: listClauses });
  const [title, setTitle] = useState("");
  const [body, setBody] = useState("");
  const [error, setError] = useState<string | null>(null);

  const refresh = () => queryClient.invalidateQueries({ queryKey: ["clauses"] });

  const save = useMutation({
    mutationFn: () => createClause({ title: title.trim(), body: body.trim() }),
    onSuccess: () => {
      setTitle("");
      setBody("");
      setError(null);
      refresh();
    },
    onError: (e) => setError(friendlyApiError(e, "Could not save the clause.")),
  });

  const insert = useMutation({
    mutationFn: (clause: Clause) => insertClause(docId, { clause_id: clause.id }),
    onSuccess: () => {
      setError(null);
      queryClient.invalidateQueries({ queryKey: ["model", docId] });
    },
    onError: (e) => setError(friendlyApiError(e, "Could not save the clause.")),
  });

  const remove = useMutation({ mutationFn: deleteClause, onSuccess: refresh });

  const useSelected = () => {
    if (!selectedId) return;
    const text = nodeText(doc, selectedId);
    if (text) setBody(text);
  };

  return (
    <div className="flex h-full flex-col gap-4 overflow-auto p-4">
      <div>
        <h2 className="text-sm font-semibold text-slate-900">Clause library</h2>
        <p className="mt-1 text-xs text-slate-500">
          Save reusable clauses and insert them into this contract. Inserts are versioned and
          undoable like every other edit.
        </p>
      </div>

      {error && (
        <p className="rounded border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-700">
          {error}
        </p>
      )}

      <section className="space-y-2 rounded-lg border border-slate-200 p-3">
        <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">New clause</p>
        <input
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          placeholder="Title (e.g. Confidentiality)"
          className="w-full rounded border border-slate-300 px-2 py-1 text-sm"
        />
        <textarea
          value={body}
          onChange={(e) => setBody(e.target.value)}
          placeholder="Clause text…"
          rows={4}
          className="w-full rounded border border-slate-300 px-2 py-1 text-sm"
        />
        <div className="flex items-center gap-2">
          <button
            type="button"
            disabled={!title.trim() || !body.trim() || save.isPending}
            onClick={() => save.mutate()}
            className="btn-primary px-3 py-1 text-xs disabled:opacity-40"
          >
            Save clause
          </button>
          <button
            type="button"
            disabled={!selectedId}
            onClick={useSelected}
            className="btn-secondary px-3 py-1 text-xs disabled:opacity-40"
            title={selectedId ? "Use the selected block's text" : "Select a block on the page"}
          >
            Use selected text
          </button>
        </div>
      </section>

      <section className="space-y-2">
        <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">
          Saved clauses
        </p>
        {clauses.isLoading && <p className="text-xs text-slate-500">Loading…</p>}
        {clauses.data?.length === 0 && (
          <p className="text-xs text-slate-500">No clauses saved yet.</p>
        )}
        {clauses.data?.map((clause) => (
          <div key={clause.id} className="rounded-lg border border-slate-200 p-3">
            <p className="text-sm font-medium text-slate-900">{clause.title}</p>
            <p className="mt-1 line-clamp-3 text-xs text-slate-500">{clause.body}</p>
            <div className="mt-2 flex items-center gap-2">
              <button
                type="button"
                disabled={insert.isPending}
                onClick={() => insert.mutate(clause)}
                className="btn-primary px-2.5 py-1 text-xs disabled:opacity-40"
              >
                Insert
              </button>
              <button
                type="button"
                onClick={() => remove.mutate(clause.id)}
                className="text-xs text-slate-500 hover:text-red-600"
              >
                Delete
              </button>
            </div>
          </div>
        ))}
      </section>
    </div>
  );
}
