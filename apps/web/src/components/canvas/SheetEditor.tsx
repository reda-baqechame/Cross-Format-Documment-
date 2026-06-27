"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Table2 } from "lucide-react";
import type { CanonicalDocument, DocNode } from "@docos/shared-types";

import { setTableCell } from "@/lib/api";

/**
 * Spreadsheet editing surface over the canonical model.
 *
 * Renders every TableNode in the document as an editable grid and commits cell edits back through
 * the existing reversible patch API (`setTableCell`), so changes are versioned and undoable like
 * any other edit — no new mutation path. This is the seam where a full canvas/formula engine
 * (Univer) drops in later: the model→grid mapping and the `onCommit → setTableCell` save-back stay
 * the same; only the rendering surface changes.
 */

const MAX_ROWS = 500; // guardrail so a pathological sheet can't blow up the DOM

function cellText(doc: CanonicalDocument, node: DocNode): string {
  return node.children
    .map((cid) => doc.nodes[cid])
    .filter((c): c is DocNode => Boolean(c))
    .map((c) => (c.type === "run" ? (c.text ?? "") : cellText(doc, c)))
    .join("");
}

type Grid = { cellId: string; text: string; header: boolean }[][];

function buildGrid(doc: CanonicalDocument, table: DocNode): Grid {
  const rows = table.children
    .map((cid) => doc.nodes[cid])
    .filter((n): n is DocNode => Boolean(n) && n.type === "table_row")
    .sort((a, b) => (a.row ?? 0) - (b.row ?? 0))
    .slice(0, MAX_ROWS);
  return rows.map((row) =>
    row.children
      .map((cid) => doc.nodes[cid])
      .filter((c): c is DocNode => Boolean(c) && c.type === "table_cell")
      .sort((a, b) => (a.col ?? 0) - (b.col ?? 0))
      .map((c) => ({ cellId: c.id, text: cellText(doc, c), header: Boolean(c.header) })),
  );
}

function sheetLabel(doc: CanonicalDocument, table: DocNode, index: number): string {
  // Spreadsheet adapters map each worksheet to a heading immediately before its table.
  const siblings = doc.nodes[table.parent_id ?? doc.root_id]?.children ?? [];
  const pos = siblings.indexOf(table.id);
  for (let i = pos - 1; i >= 0; i -= 1) {
    const prev = doc.nodes[siblings[i]];
    if (prev?.type === "heading") return cellText(doc, prev) || `Sheet ${index + 1}`;
    if (prev?.type === "table") break;
  }
  return `Sheet ${index + 1}`;
}

export function SheetEditor({ doc, docId }: { doc: CanonicalDocument; docId: string }) {
  const queryClient = useQueryClient();
  const tables = Object.values(doc.nodes).filter((n) => n.type === "table");

  const commit = useMutation({
    mutationFn: ({ cellId, text }: { cellId: string; text: string }) =>
      setTableCell(docId, cellId, { text }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["model", docId] });
      queryClient.invalidateQueries({ queryKey: ["health", docId] });
    },
  });

  if (tables.length === 0) {
    return (
      <div className="mx-auto max-w-[816px] rounded-lg border border-slate-200 bg-white p-8 text-center text-sm text-slate-500">
        No tabular data detected in this spreadsheet.
      </div>
    );
  }

  return (
    <div className="mx-auto w-full max-w-[1100px] space-y-6">
      {tables.map((table, ti) => {
        const grid = buildGrid(doc, table);
        return (
          <section key={table.id} className="rounded-lg border border-slate-200 bg-white shadow-sm">
            <header className="flex items-center gap-2 border-b border-slate-200 px-4 py-2.5">
              <Table2 className="h-4 w-4 text-emerald-600" />
              <h3 className="text-sm font-semibold text-ink">{sheetLabel(doc, table, ti)}</h3>
              <span className="ml-auto text-xs text-slate-400">
                {table.rows ?? grid.length} × {table.cols ?? (grid[0]?.length ?? 0)}
              </span>
            </header>
            <div className="overflow-auto">
              <table className="w-full border-collapse text-sm">
                <tbody>
                  {grid.map((row, ri) => (
                    <tr key={ri}>
                      <td className="sticky left-0 z-10 select-none border border-slate-200 bg-slate-50 px-2 text-center text-xs text-slate-400">
                        {ri + 1}
                      </td>
                      {row.map((cell) => (
                        <td key={cell.cellId} className="border border-slate-200 p-0">
                          <input
                            // Remount when the server value changes so the input reflects truth.
                            key={`${cell.cellId}:${cell.text}`}
                            defaultValue={cell.text}
                            aria-label={`cell ${cell.cellId}`}
                            className={`w-full min-w-[7rem] bg-transparent px-2 py-1.5 outline-none focus:bg-emerald-50 focus:ring-1 focus:ring-emerald-400 ${
                              cell.header ? "font-semibold text-ink" : "text-slate-700"
                            }`}
                            onKeyDown={(e) => {
                              if (e.key === "Enter") (e.target as HTMLInputElement).blur();
                            }}
                            onBlur={(e) => {
                              const next = e.target.value;
                              if (next !== cell.text) commit.mutate({ cellId: cell.cellId, text: next });
                            }}
                          />
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        );
      })}
      {commit.isError && (
        <p className="text-sm text-red-600">Could not save the cell. Please try again.</p>
      )}
    </div>
  );
}
