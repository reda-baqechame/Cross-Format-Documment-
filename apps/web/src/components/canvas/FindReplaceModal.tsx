"use client";

import type { CanonicalDocument } from "@docos/shared-types";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { ChevronDown, ChevronUp, X } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { replaceText } from "@/lib/api";
import { useWorkspace } from "@/lib/store";
import { useDismissOnOutside } from "@/lib/useDismiss";
import { friendlyApiError } from "@/lib/upload";

/** True if a node or any ancestor is redacted — mirrors the backend so the match
 *  count shown here matches what "Replace all" will actually touch. */
function isRedacted(doc: CanonicalDocument, nodeId: string | null): boolean {
  const ids = doc.redaction?.redacted_node_ids;
  if (!ids || ids.length === 0) return false;
  const seen = new Set<string>();
  let current = nodeId;
  while (current && !seen.has(current)) {
    if (ids.includes(current)) return true;
    seen.add(current);
    current = doc.nodes[current]?.parent_id ?? null;
  }
  return false;
}

function buildRegex(find: string, matchCase: boolean, wholeWord: boolean): RegExp | null {
  if (!find) return null;
  const escaped = find.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  const pattern = wholeWord ? `\\b${escaped}\\b` : escaped;
  try {
    return new RegExp(pattern, matchCase ? "g" : "gi");
  } catch {
    return null;
  }
}

/**
 * Find & replace dialog. Find/Prev/Next navigate matches client-side over the loaded
 * model (reusing the canvas selection highlight); Replace all issues one reversible,
 * audited edit via POST /documents/{id}/replace and refreshes the document.
 */
export function FindReplaceModal({
  doc,
  docId,
  onClose,
}: {
  doc: CanonicalDocument;
  docId: string;
  onClose: () => void;
}) {
  const [find, setFind] = useState("");
  const [replace, setReplace] = useState("");
  const [matchCase, setMatchCase] = useState(false);
  const [wholeWord, setWholeWord] = useState(false);
  const [active, setActive] = useState(0);
  const [status, setStatus] = useState<string | null>(null);

  const select = useWorkspace((s) => s.select);
  const queryClient = useQueryClient();
  const ref = useDismissOnOutside(true, onClose);

  // Run nodes (skipping redacted ones, like the backend) that contain the term.
  const matches = useMemo(() => {
    const rx = buildRegex(find, matchCase, wholeWord);
    if (!rx) return [] as { nodeId: string; count: number }[];
    const out: { nodeId: string; count: number }[] = [];
    for (const node of Object.values(doc.nodes)) {
      if (node.type !== "run" || !node.text || isRedacted(doc, node.id)) continue;
      const found = node.text.match(rx);
      if (found && found.length) out.push({ nodeId: node.id, count: found.length });
    }
    return out;
  }, [doc, find, matchCase, wholeWord]);

  const total = matches.reduce((n, m) => n + m.count, 0);

  useEffect(() => {
    setActive(0);
  }, [find, matchCase, wholeWord]);

  const goTo = (dir: 1 | -1) => {
    if (matches.length === 0) return;
    const next = (active + dir + matches.length) % matches.length;
    setActive(next);
    const id = matches[next].nodeId;
    select(id);
    document.getElementById(`node-${id}`)?.scrollIntoView({ block: "center", behavior: "smooth" });
  };

  const replaceAll = useMutation({
    mutationFn: () =>
      replaceText(docId, { find, replace, match_case: matchCase, whole_word: wholeWord }),
    onSuccess: (res) => {
      void queryClient.invalidateQueries({ queryKey: ["model", docId] });
      void queryClient.invalidateQueries({ queryKey: ["health", docId] });
      setStatus(
        res.applied
          ? `Replaced ${res.occurrences} occurrence${res.occurrences === 1 ? "" : "s"}.`
          : "No matches found.",
      );
    },
    onError: (e) => setStatus(friendlyApiError(e, "Replace failed.")),
  });

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center bg-slate-900/30 p-4 pt-24">
      <div
        ref={ref}
        role="dialog"
        aria-label="Find and replace"
        className="w-full max-w-md rounded-xl border border-slate-200 bg-white p-4 shadow-xl"
      >
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-sm font-semibold text-slate-900">Find &amp; replace</h2>
          <button type="button" className="icon-btn" aria-label="Close" onClick={onClose}>
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="space-y-2">
          <div className="flex items-center gap-2">
            <input
              autoFocus
              value={find}
              onChange={(e) => setFind(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") goTo(e.shiftKey ? -1 : 1);
              }}
              placeholder="Find"
              aria-label="Find"
              className="min-h-[40px] flex-1 rounded-lg border border-slate-300 px-3 text-sm"
            />
            <span className="w-20 shrink-0 text-right text-xs text-slate-500" aria-live="polite">
              {find ? (total ? `${active + 1}/${matches.length}` : "0 matches") : ""}
            </span>
            <button
              type="button"
              className="icon-btn"
              aria-label="Previous match"
              disabled={matches.length === 0}
              onClick={() => goTo(-1)}
            >
              <ChevronUp className="h-4 w-4" />
            </button>
            <button
              type="button"
              className="icon-btn"
              aria-label="Next match"
              disabled={matches.length === 0}
              onClick={() => goTo(1)}
            >
              <ChevronDown className="h-4 w-4" />
            </button>
          </div>

          <input
            value={replace}
            onChange={(e) => setReplace(e.target.value)}
            placeholder="Replace with"
            aria-label="Replace with"
            className="min-h-[40px] w-full rounded-lg border border-slate-300 px-3 text-sm"
          />

          <div className="flex flex-wrap items-center gap-4 text-sm text-slate-600">
            <label className="flex items-center gap-1.5">
              <input
                type="checkbox"
                checked={matchCase}
                onChange={(e) => setMatchCase(e.target.checked)}
              />
              Match case
            </label>
            <label className="flex items-center gap-1.5">
              <input
                type="checkbox"
                checked={wholeWord}
                onChange={(e) => setWholeWord(e.target.checked)}
              />
              Whole word
            </label>
          </div>
        </div>

        <div className="mt-4 flex items-center justify-between gap-2">
          <span
            role={status && status.toLowerCase().includes("fail") ? "alert" : "status"}
            className="text-xs text-slate-500"
            aria-live="polite"
          >
            {replaceAll.isPending ? "Replacing…" : status}
          </span>
          <button
            type="button"
            className="studio-btn"
            disabled={!find || total === 0 || replaceAll.isPending}
            onClick={() => replaceAll.mutate()}
          >
            Replace all{total ? ` (${total})` : ""}
          </button>
        </div>
      </div>
    </div>
  );
}
