"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { fetchBackendHealth, instructEdit, undoDocument } from "@/lib/api";
import { friendlyApiError } from "@/lib/upload";

/**
 * Natural-language editing bar. The instruction is interpreted by the LLM into concrete
 * patch ops server-side. AI is only real when a provider is configured, so we check the
 * backend's `ai_enabled` flag and show an honest disabled state instead of accepting an
 * instruction that would silently do nothing. Undo always works (it's not an AI feature).
 */
export function AiEditBar({ docId }: { docId: string }) {
  const [instruction, setInstruction] = useState("");
  const queryClient = useQueryClient();
  const health = useQuery({ queryKey: ["health"], queryFn: fetchBackendHealth, retry: false });
  const aiEnabled = health.data?.ai_enabled ?? false;

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
        onKeyDown={(e) => e.key === "Enter" && aiEnabled && instruction.trim() && edit.mutate()}
        placeholder={aiEnabled ? "Ask AI to edit…" : "AI editing not connected"}
        aria-label="Natural language edit instruction"
        disabled={!aiEnabled}
        className="min-h-[44px] min-w-0 flex-1 rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-brand-400 focus:outline-none disabled:cursor-not-allowed disabled:bg-slate-50 disabled:text-slate-400"
      />
      <div className="flex shrink-0 gap-2">
        <button
          type="button"
          onClick={() => edit.mutate()}
          disabled={!aiEnabled || edit.isPending || !instruction.trim()}
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
      {!aiEnabled && !health.isLoading && (
        <span className="text-xs text-slate-400 sm:ml-1" title="Set LLM_PROVIDER=anthropic + ANTHROPIC_API_KEY">
          AI off — edit text directly by double-clicking it
        </span>
      )}
      {error && (
        <p role="alert" className="text-xs text-red-600 sm:basis-full">
          {friendlyApiError(error, "Edit failed.")}
        </p>
      )}
    </div>
  );
}
