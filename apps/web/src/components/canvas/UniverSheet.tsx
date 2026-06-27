"use client";

import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef } from "react";
import type { CanonicalDocument, DocNode } from "@docos/shared-types";

// Univer's UI stylesheet — without it the toolbar/grid render unstyled.
import "@univerjs/presets/lib/styles/preset-sheets-core.css";

import { setTableCell } from "@/lib/api";

/**
 * Univer-backed spreadsheet surface (Apache-2.0): an Excel-grade grid with formulas, sorting and
 * filtering, seeded from the canonical `TableNode`s. Cell edits are committed back through the
 * existing reversible-patch path (`setTableCell`) — no new mutation path — so they stay versioned
 * and undoable. Univer is heavy and browser-only, so this component is always loaded via
 * `next/dynamic` with `ssr:false` (see the workspace page).
 */

const MAX_ROWS = 500;

function runText(doc: CanonicalDocument, node: DocNode): string {
  return node.children
    .map((cid) => doc.nodes[cid])
    .filter((c): c is DocNode => Boolean(c))
    .map((c) => (c.type === "run" ? (c.text ?? "") : runText(doc, c)))
    .join("");
}

type SheetSeed = {
  name: string;
  cellData: Record<number, Record<number, { v: string }>>;
  cellIds: Record<string, string>; // "row:col" -> canonical cell id
  rowCount: number;
  colCount: number;
};

function buildSeeds(doc: CanonicalDocument): SheetSeed[] {
  const tables = Object.values(doc.nodes).filter((n) => n.type === "table");
  return tables.map((table, ti) => {
    const cellData: Record<number, Record<number, { v: string }>> = {};
    const cellIds: Record<string, string> = {};
    let rowCount = 0;
    let colCount = 0;
    const rows = table.children
      .map((cid) => doc.nodes[cid])
      .filter((n): n is DocNode => Boolean(n) && n.type === "table_row")
      .sort((a, b) => (a.row ?? 0) - (b.row ?? 0))
      .slice(0, MAX_ROWS);
    rows.forEach((row, r) => {
      const cells = row.children
        .map((cid) => doc.nodes[cid])
        .filter((c): c is DocNode => Boolean(c) && c.type === "table_cell")
        .sort((a, b) => (a.col ?? 0) - (b.col ?? 0));
      cells.forEach((cell, c) => {
        cellData[r] = cellData[r] ?? {};
        cellData[r][c] = { v: runText(doc, cell) };
        cellIds[`${r}:${c}`] = cell.id;
        colCount = Math.max(colCount, c + 1);
      });
      rowCount = r + 1;
    });
    return { name: `Sheet ${ti + 1}`, cellData, cellIds, rowCount, colCount };
  });
}

export default function UniverSheet({ doc, docId }: { doc: CanonicalDocument; docId: string }) {
  const containerRef = useRef<HTMLDivElement>(null);
  const queryClient = useQueryClient();

  useEffect(() => {
    let disposed = false;
    let univer: { dispose?: () => void } | undefined;
    const seeds = buildSeeds(doc);
    // Flat "sheetIndex:row:col" -> cellId lookup for save-back.
    const idLookup: Record<string, string> = {};
    seeds.forEach((s, si) =>
      Object.entries(s.cellIds).forEach(([rc, id]) => {
        idLookup[`${si}:${rc}`] = id;
      }),
    );

    (async () => {
      const presets = await import("@univerjs/presets");
      const { UniverSheetsCorePreset } = await import("@univerjs/presets/preset-sheets-core");
      const enUS = (await import("@univerjs/presets/preset-sheets-core/locales/en-US")).default;
      if (disposed || !containerRef.current) return;

      const { createUniver, defaultTheme, LocaleType, merge } = presets;
      const created = createUniver({
        locale: LocaleType.EN_US,
        locales: { [LocaleType.EN_US]: merge({}, enUS) },
        theme: defaultTheme,
        presets: [UniverSheetsCorePreset({ container: containerRef.current })],
      });
      univer = created.univer;
      const univerAPI = created.univerAPI;

      const sheetOrder = seeds.map((_, i) => `s${i}`);
      type SheetData = {
        id: string;
        name: string;
        rowCount: number;
        columnCount: number;
        cellData: Record<number, Record<number, { v: string }>>;
      };
      const sheets: Record<string, SheetData> = {};
      seeds.forEach((s, i) => {
        sheets[`s${i}`] = {
          id: `s${i}`,
          name: s.name,
          rowCount: Math.max(s.rowCount + 5, 20),
          columnCount: Math.max(s.colCount + 3, 12),
          cellData: s.cellData,
        };
      });
      univerAPI.createWorkbook({
        id: docId,
        name: doc.meta.title ?? "Spreadsheet",
        sheetOrder,
        sheets,
      });

      // Commit cell edits back through the reversible-patch API. We match Univer's set-range-values
      // command and map each changed (sheet,row,col) to its canonical cell id. Defensive about the
      // exact param shape across Univer versions.
      univerAPI.onCommandExecuted?.((command: { id?: string; params?: unknown }) => {
        if (!command?.id || !/set-range-values/.test(command.id)) return;
        const params = (command.params ?? {}) as Record<string, unknown>;
        const subUnit = (params.subUnitId ?? params.sheetId ?? "s0") as string;
        const sheetIndex = sheetOrder.indexOf(subUnit);
        const si = sheetIndex < 0 ? 0 : sheetIndex;
        const grid = (params.cellValue ?? params.value ?? {}) as Record<
          string,
          Record<string, { v?: unknown }>
        >;
        for (const [r, cols] of Object.entries(grid)) {
          for (const [c, cell] of Object.entries(cols)) {
            const id = idLookup[`${si}:${r}:${c}`];
            if (!id) continue;
            const next = cell && typeof cell === "object" && "v" in cell ? String(cell.v ?? "") : "";
            void setTableCell(docId, id, { text: next }).then(() => {
              queryClient.invalidateQueries({ queryKey: ["health", docId] });
            });
          }
        }
      });
    })();

    return () => {
      disposed = true;
      try {
        univer?.dispose?.();
      } catch {
        /* best-effort teardown */
      }
    };
    // Re-init only when the document identity changes (not on every model refetch).
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [docId]);

  if (Object.values(doc.nodes).every((n) => n.type !== "table")) {
    return (
      <div className="mx-auto max-w-[816px] rounded-lg border border-slate-200 bg-white p-8 text-center text-sm text-slate-500">
        No tabular data detected in this spreadsheet.
      </div>
    );
  }

  return (
    <div className="overflow-hidden rounded-lg border border-slate-200 bg-white shadow-sm">
      <div ref={containerRef} className="h-[72vh] w-full" data-testid="univer-sheet" />
    </div>
  );
}
