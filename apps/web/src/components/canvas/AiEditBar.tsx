"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { instructEdit, undoDocument } from "@/lib/api";

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

  return (
    <div className="flex items-center gap-2">
      <input
        value={instruction}
        onChange={(e) => setInstruction(e.target.value)}
        onKeyDown={(e) => e.key === "Enter" && instruction.trim() && edit.mutate()}
        placeholder="Ask AI to edit… (e.g. “make the first heading bold”)"
        className="w-80 rounded-md border border-slate-300 px-3 py-1.5 text-sm focus:border-blue-400 focus:outline-none"
      />
      <button
        onClick={() => edit.mutate()}
        disabled={edit.isPending || !instruction.trim()}
        className="rounded-md bg-blue-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-blue-500 disabled:opacity-40"
      >
        {edit.isPending ? "Editing…" : "Edit"}
      </button>
      <button
        onClick={() => undo.mutate()}
        disabled={undo.isPending}
        className="rounded-md border border-slate-300 px-3 py-1.5 text-sm hover:bg-slate-50 disabled:opacity-40"
        title="Undo the last change"
      >
        Undo
      </button>
      {edit.data && !edit.data.applied && (
        <span className="text-xs text-slate-400">No change (configure an LLM provider)</span>
      )}
    </div>
  );
}
