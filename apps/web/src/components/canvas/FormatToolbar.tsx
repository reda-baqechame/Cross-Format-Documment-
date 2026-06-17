"use client";

import type { CanonicalDocument } from "@docos/shared-types";
import { useMutation, useQueryClient } from "@tanstack/react-query";

import { formatRun } from "@/lib/api";
import { useWorkspace } from "@/lib/store";

/**
 * Rich-formatting toolbar. When a text run is selected on the canvas, toggling
 * B / I / U issues a reversible `update_node` patch — so formatting is versioned
 * and undoable like every other edit. Disabled until a run is selected.
 */
export function FormatToolbar({ doc, docId }: { doc: CanonicalDocument; docId: string }) {
  const selectedId = useWorkspace((s) => s.selectedNodeId);
  const queryClient = useQueryClient();
  const node = selectedId ? doc.nodes[selectedId] : undefined;
  const isRun = node?.type === "run";

  const toggle = useMutation({
    mutationFn: (changes: { bold?: boolean; italic?: boolean; underline?: boolean }) =>
      formatRun(docId, selectedId!, changes),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["model", docId] });
      queryClient.invalidateQueries({ queryKey: ["health", docId] });
    },
  });

  const btn = (active: boolean | undefined) =>
    [
      "h-7 w-7 rounded text-sm",
      active ? "bg-slate-900 text-white" : "text-slate-600 hover:bg-slate-100",
      !isRun ? "cursor-not-allowed opacity-40" : "",
    ].join(" ");

  return (
    <div
      className="flex items-center gap-1 rounded-md border border-slate-300 px-1 py-0.5"
      title={isRun ? "Format selected text" : "Select text on the page to format it"}
    >
      <button
        type="button"
        disabled={!isRun || toggle.isPending}
        onClick={() => toggle.mutate({ bold: !node?.bold })}
        className={`font-bold ${btn(node?.bold)}`}
        aria-pressed={!!node?.bold}
        aria-label="Bold"
      >
        B
      </button>
      <button
        type="button"
        disabled={!isRun || toggle.isPending}
        onClick={() => toggle.mutate({ italic: !node?.italic })}
        className={`italic ${btn(node?.italic)}`}
        aria-pressed={!!node?.italic}
        aria-label="Italic"
      >
        I
      </button>
      <button
        type="button"
        disabled={!isRun || toggle.isPending}
        onClick={() => toggle.mutate({ underline: !node?.underline })}
        className={`underline ${btn(node?.underline)}`}
        aria-pressed={!!node?.underline}
        aria-label="Underline"
      >
        U
      </button>
    </div>
  );
}
