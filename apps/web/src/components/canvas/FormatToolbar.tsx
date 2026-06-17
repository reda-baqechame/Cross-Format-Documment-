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
    mutationFn: (changes: {
      bold?: boolean;
      italic?: boolean;
      underline?: boolean;
      size?: number | null;
      color?: string | null;
    }) => formatRun(docId, selectedId!, changes),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["model", docId] });
      queryClient.invalidateQueries({ queryKey: ["health", docId] });
    },
  });

  const runSize = isRun ? (node as { size?: number | null }).size : undefined;
  const runColor = isRun ? (node as { color?: string | null }).color : undefined;

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

      <span className="mx-0.5 h-5 w-px bg-slate-200" aria-hidden />

      <input
        type="number"
        min={6}
        max={96}
        step={1}
        disabled={!isRun || toggle.isPending}
        value={runSize ?? ""}
        placeholder="pt"
        onChange={(e) => {
          const v = e.target.value.trim();
          toggle.mutate({ size: v === "" ? null : Number(v) });
        }}
        className="h-7 w-12 rounded border border-slate-300 px-1 text-center text-sm disabled:cursor-not-allowed disabled:opacity-40"
        title={isRun ? "Font size (points)" : "Select text to set its size"}
        aria-label="Font size"
      />
      <input
        type="color"
        disabled={!isRun || toggle.isPending}
        value={runColor ?? "#0f172a"}
        onChange={(e) => toggle.mutate({ color: e.target.value })}
        className="h-7 w-7 cursor-pointer rounded border border-slate-300 p-0.5 disabled:cursor-not-allowed disabled:opacity-40"
        title={isRun ? "Text color" : "Select text to set its color"}
        aria-label="Text color"
      />
    </div>
  );
}
