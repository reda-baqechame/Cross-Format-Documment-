"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { instructEdit, undoDocument } from "@/lib/api";
import { friendlyApiError } from "@/lib/upload";

/**
 * Natural-language editing bar. The instruction is interpreted by the LLM into
 * concrete patch ops server-side (a no-op offline, real edits when a provider is
 * configured); Undo rolls back one version through the persisted version DAG.
 */
export function AiEditBar({ docId }: { docId: string }) {
  const [instruction, setInstruction] = useState("");
  const queryClient = useQueryClient();
  const refresh = () => {
    queryClient.invalidateQueries({ queryKey: ["model", docId] });
    queryClient.invalidateQueries({ queryKey: ["health", docId] });
  };

  const edit = useMutation({
    mutationFn: () => instructEdit(docId, instruction),
    onSuccess: (res) => {
      refresh();
      if (res.applied) setInstruction("");
    },
  });
  const undo = useMutation({ mutationFn: () => undoDocument(docId), onSuccess: refresh });

  const error = edit.error ?? undo.error;

  return (
    <div className="flex min-w-0 flex-1 flex-col gap-1 sm:flex-row sm:items-center sm:gap-2">
      <input
        value={instruction}
        onChange={(e) => setInstruction(e.target.value)}
        onKeyDown={(e) => e.key === "Enter" && instruction.trim() && edit.mutate()}
        placeholder="Ask AI to edit…"
        aria-label="Natural language edit instruction"
        className="min-h-[44px] min-w-0 flex-1 rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-brand-400 focus:outline-none"
      />
      <div className="flex shrink-0 gap-2">
        <button
          type="button"
          onClick={() => edit.mutate()}
          disabled={edit.isPending || !instruction.trim()}
          aria-label="Apply AI edit"
          className="min-h-[44px] rounded-md bg-brand-600 px-3 py-2 text-sm font-medium text-white hover:bg-brand-500 disabled:opacity-40"
        >
          {edit.isPending ? "…" : "Edit"}
        </button>
        <button
          type="button"
          onClick={() => undo.mutate()}
          disabled={undo.isPending}
          aria-label="Undo last change"
          className="min-h-[44px] rounded-md border border-slate-300 px-3 py-2 text-sm hover:bg-slate-50 disabled:opacity-40"
          title="Undo the last change"
        >
          Undo
        </button>
      </div>
      {edit.data && !edit.data.applied && !edit.isPending && (
        <span className="text-xs text-slate-400 sm:ml-1">Configure an LLM for AI edits</span>
      )}
      {error && (
        <p role="alert" className="text-xs text-red-600 sm:basis-full">
          {friendlyApiError(error, "Edit failed.")}
        </p>
      )}
    </div>
  );
}
