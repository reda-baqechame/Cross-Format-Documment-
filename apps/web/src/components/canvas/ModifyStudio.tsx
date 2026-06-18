"use client";

import type { CanonicalDocument, DocNode } from "@docos/shared-types";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";

import {
  addTextBlock,
  createField,
  deleteNode,
  deleteTableCol,
  deleteTableRow,
  detectFields,
  duplicateNode,
  duplicatePage,
  insertImage,
  insertLink,
  insertTableCol,
  insertTableRow,
  moveNode,
  replaceImage,
  setImageAttrs,
  setListAttrs,
  setPageAttrs,
  setTableCell,
  uploadDocumentAsset,
} from "@/lib/api";
import { useWorkspace } from "@/lib/store";
import { friendlyApiError } from "@/lib/upload";

const FIELD_TYPES = ["text", "date", "signature", "checkbox", "dropdown", "email", "phone"];

function ancestor(doc: CanonicalDocument, node: DocNode | undefined, type: string): DocNode | null {
  let current: string | null | undefined = node?.id;
  while (current) {
    const n: DocNode | undefined = doc.nodes[current];
    if (!n) return null;
    if (n.type === type) return n;
    current = n.parent_id;
  }
  return null;
}

function firstPage(doc: CanonicalDocument): DocNode | null {
  return Object.values(doc.nodes).find((n) => n.type === "page") ?? null;
}

function orderedPages(doc: CanonicalDocument): DocNode[] {
  const root = doc.nodes[doc.root_id];
  const rootPages =
    root?.children
      .map((id) => doc.nodes[id])
      .filter((n): n is DocNode => Boolean(n) && n.type === "page") ?? [];
  if (rootPages.length) return rootPages;
  return Object.values(doc.nodes)
    .filter((n) => n.type === "page")
    .sort((a, b) => (a.page_number ?? 0) - (b.page_number ?? 0));
}

function selectedLabel(node: DocNode | undefined): string {
  if (!node) return "Nothing selected";
  if (node.type === "run") return `Text: ${(node.text ?? "").slice(0, 40) || "blank"}`;
  if (node.type === "field") return `Field: ${node.field_name ?? "Field"}`;
  return node.type.replace("_", " ");
}

function parentForInsert(doc: CanonicalDocument, node: DocNode | undefined): string {
  if (!node) return doc.root_id;
  if (node.type === "run" && node.parent_id) return node.parent_id;
  if (["paragraph", "heading", "page", "root", "table_cell"].includes(node.type)) return node.id;
  return node.parent_id ?? doc.root_id;
}

export function ModifyStudio({ doc, docId }: { doc: CanonicalDocument; docId: string }) {
  const selectedId = useWorkspace((s) => s.selectedNodeId);
  const selectNode = useWorkspace((s) => s.select);
  const selected = selectedId ? doc.nodes[selectedId] : undefined;
  const queryClient = useQueryClient();

  const table = useMemo(() => ancestor(doc, selected, "table"), [doc, selected]);
  const row = useMemo(() => ancestor(doc, selected, "table_row"), [doc, selected]);
  const cell = useMemo(() => ancestor(doc, selected, "table_cell"), [doc, selected]);
  const list = useMemo(() => ancestor(doc, selected, "list"), [doc, selected]);
  const page = useMemo(() => ancestor(doc, selected, "page") ?? firstPage(doc), [doc, selected]);
  const image = selected?.type === "image" ? selected : null;
  const pages = useMemo(() => orderedPages(doc), [doc]);

  const [fieldName, setFieldName] = useState("New field");
  const [fieldKind, setFieldKind] = useState("text");
  const [fieldRequired, setFieldRequired] = useState(true);
  const [cellText, setCellText] = useState("");
  const [linkHref, setLinkHref] = useState("");
  const [altText, setAltText] = useState("");
  const [newText, setNewText] = useState("New text");
  const [pageRotation, setPageRotation] = useState("0");

  useEffect(() => {
    setCellText(cell ? collectText(doc, cell) : "");
    setAltText(image?.alt_text ?? "");
    setLinkHref(selected?.type === "run" ? (selected.link_href ?? "") : "");
    setPageRotation(String(page?.rotation ?? 0));
  }, [cell, doc, image, page, selected]);

  const refresh = () => {
    queryClient.invalidateQueries({ queryKey: ["model", docId] });
    queryClient.invalidateQueries({ queryKey: ["health", docId] });
    queryClient.invalidateQueries({ queryKey: ["fields", docId] });
    queryClient.invalidateQueries({ queryKey: ["intelligence", docId] });
    queryClient.invalidateQueries({ queryKey: ["autopilot", docId] });
  };

  const action = useMutation({
    mutationFn: (fn: () => Promise<unknown>) => fn(),
    onSuccess: refresh,
  });

  const run = (fn: () => Promise<unknown>) => action.mutate(fn);
  const selectedParent = parentForInsert(doc, selected);

  return (
    <div className="space-y-5 p-5">
      <div>
        <h2 className="text-base font-semibold text-ink">Modify Studio</h2>
        <p className="mt-1 text-sm text-slate-500">{selectedLabel(selected)}</p>
      </div>

      {pages.length > 0 && (
        <section className="space-y-2 border-t border-slate-200 pt-4">
          <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-500">Pages & slides</h3>
          <div className="max-h-72 space-y-2 overflow-y-auto pr-1">
            {pages.map((p, index) => {
              const parentId = p.parent_id ?? doc.root_id;
              const siblings = doc.nodes[parentId]?.children ?? [];
              const siblingIndex = siblings.indexOf(p.id);
              const selectedPage = p.id === page?.id;
              return (
                <div
                  key={p.id}
                  className={`grid grid-cols-[56px_1fr] gap-2 rounded-lg border p-2 ${
                    selectedPage ? "border-brand bg-brand/5" : "border-slate-200 bg-white"
                  }`}
                >
                  <button
                    type="button"
                    className="aspect-[4/3] rounded-md border border-slate-300 bg-slate-50 text-xs font-semibold text-slate-600"
                    onClick={() => selectNode(p.id)}
                  >
                    {index + 1}
                  </button>
                  <div className="min-w-0 space-y-2">
                    <button
                      type="button"
                      className="block w-full truncate text-left text-sm font-medium text-slate-700"
                      onClick={() => selectNode(p.id)}
                    >
                      {p.type === "page" ? "Page" : "Slide"} {p.page_number ?? index + 1}
                    </button>
                    <div className="grid grid-cols-4 gap-1">
                      <button
                        className="studio-btn px-2 py-1 text-xs"
                        disabled={action.isPending || siblingIndex <= 0}
                        onClick={() => run(() => moveNode(docId, p.id, parentId, siblingIndex - 1))}
                      >
                        Up
                      </button>
                      <button
                        className="studio-btn px-2 py-1 text-xs"
                        disabled={action.isPending || siblingIndex < 0 || siblingIndex >= siblings.length - 1}
                        onClick={() => run(() => moveNode(docId, p.id, parentId, siblingIndex + 1))}
                      >
                        Down
                      </button>
                      <button className="studio-btn px-2 py-1 text-xs" disabled={action.isPending} onClick={() => run(() => duplicatePage(docId, p.id))}>
                        Copy
                      </button>
                      <button
                        className="studio-btn px-2 py-1 text-xs"
                        disabled={action.isPending || pages.length <= 1}
                        onClick={() => run(() => deleteNode(docId, p.id))}
                      >
                        Del
                      </button>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </section>
      )}

      <section className="space-y-2 border-t border-slate-200 pt-4">
        <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-500">Structure</h3>
        <div className="grid grid-cols-2 gap-2">
          <button className="studio-btn" disabled={!selected || action.isPending} onClick={() => selected && run(() => duplicateNode(docId, selected.id))}>
            Duplicate
          </button>
          <button className="studio-btn" disabled={!selected || action.isPending} onClick={() => selected && run(() => deleteNode(docId, selected.id))}>
            Delete
          </button>
        </div>
        <div className="flex gap-2">
          <input value={newText} onChange={(e) => setNewText(e.target.value)} className="studio-input" />
          <button className="studio-btn shrink-0" disabled={action.isPending} onClick={() => run(() => addTextBlock(docId, selectedParent, newText))}>
            Add text
          </button>
        </div>
      </section>

      <section className="space-y-2 border-t border-slate-200 pt-4">
        <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-500">Forms</h3>
        <button className="studio-btn w-full" disabled={action.isPending} onClick={() => run(() => detectFields(docId))}>
          Detect blanks as fields
        </button>
        <div className="grid grid-cols-[1fr_auto] gap-2">
          <input value={fieldName} onChange={(e) => setFieldName(e.target.value)} className="studio-input" />
          <select value={fieldKind} onChange={(e) => setFieldKind(e.target.value)} className="studio-input">
            {FIELD_TYPES.map((kind) => (
              <option key={kind} value={kind}>{kind}</option>
            ))}
          </select>
        </div>
        <label className="flex items-center gap-2 text-sm text-slate-600">
          <input type="checkbox" checked={fieldRequired} onChange={(e) => setFieldRequired(e.target.checked)} />
          Required
        </label>
        <button
          className="studio-btn w-full"
          disabled={!fieldName.trim() || action.isPending}
          onClick={() =>
            run(() =>
              createField(docId, {
                field_name: fieldName.trim(),
                field_kind: fieldKind,
                parent_id: selectedParent,
                required: fieldRequired,
                placeholder: fieldName.trim(),
              }),
            )
          }
        >
          Add field here
        </button>
      </section>

      <section className="space-y-2 border-t border-slate-200 pt-4">
        <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-500">Tables</h3>
        {table ? (
          <>
            <div className="grid grid-cols-2 gap-2">
              <button className="studio-btn" disabled={action.isPending} onClick={() => run(() => insertTableRow(docId, table.id, row?.row))}>
                Add row
              </button>
              <button className="studio-btn" disabled={action.isPending} onClick={() => run(() => deleteTableRow(docId, table.id, row?.row, row?.id))}>
                Delete row
              </button>
              <button className="studio-btn" disabled={action.isPending} onClick={() => run(() => insertTableCol(docId, table.id, cell?.col))}>
                Add column
              </button>
              <button className="studio-btn" disabled={action.isPending} onClick={() => run(() => deleteTableCol(docId, table.id, cell?.col))}>
                Delete column
              </button>
            </div>
            {cell && (
              <div className="space-y-2">
                <textarea value={cellText} onChange={(e) => setCellText(e.target.value)} className="studio-input min-h-[72px]" />
                <button className="studio-btn w-full" disabled={action.isPending} onClick={() => run(() => setTableCell(docId, cell.id, { text: cellText }))}>
                  Save cell
                </button>
              </div>
            )}
          </>
        ) : (
          <p className="text-sm text-slate-500">Select a table or cell to edit rows and columns.</p>
        )}
      </section>

      <section className="space-y-2 border-t border-slate-200 pt-4">
        <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-500">Images</h3>
        <input value={altText} onChange={(e) => setAltText(e.target.value)} placeholder="Alt text" className="studio-input" />
        {image && (
          <button className="studio-btn w-full" disabled={action.isPending} onClick={() => run(() => setImageAttrs(docId, image.id, { alt_text: altText || null }))}>
            Save image alt
          </button>
        )}
        <label className="studio-btn block cursor-pointer text-center">
          {image ? "Replace image" : "Insert image"}
          <input
            type="file"
            accept="image/png,image/jpeg,image/tiff"
            className="hidden"
            disabled={action.isPending}
            onChange={(e) => {
              const file = e.target.files?.[0];
              e.target.value = "";
              if (!file) return;
              run(async () => {
                const asset = await uploadDocumentAsset(docId, file);
                if (image) return replaceImage(docId, image.id, asset, altText || file.name);
                return insertImage(docId, page?.id ?? doc.root_id, asset, altText || file.name);
              });
            }}
          />
        </label>
      </section>

      <section className="space-y-2 border-t border-slate-200 pt-4">
        <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-500">Links, Lists & Slides</h3>
        <div className="flex gap-2">
          <input value={linkHref} onChange={(e) => setLinkHref(e.target.value)} placeholder="https://..." className="studio-input" />
          <button className="studio-btn shrink-0" disabled={selected?.type !== "run" || action.isPending} onClick={() => selected && run(() => insertLink(docId, selected.id, linkHref))}>
            Link
          </button>
        </div>
        {list && (
          <button className="studio-btn w-full" disabled={action.isPending} onClick={() => run(() => setListAttrs(docId, list.id, !list.ordered))}>
            Switch to {list.ordered ? "bullets" : "numbers"}
          </button>
        )}
        {page && (
          <div className="grid grid-cols-[1fr_auto_auto] gap-2">
            <input value={pageRotation} onChange={(e) => setPageRotation(e.target.value)} className="studio-input" />
            <button className="studio-btn" disabled={action.isPending} onClick={() => run(() => setPageAttrs(docId, page.id, { rotation: Number(pageRotation) || 0 }))}>
              Rotate
            </button>
            <button className="studio-btn" disabled={action.isPending} onClick={() => run(() => duplicatePage(docId, page.id))}>
              Duplicate
            </button>
          </div>
        )}
      </section>

      {action.isError && (
        <p role="alert" className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
          {friendlyApiError(action.error, "Could not modify the document.")}
        </p>
      )}
    </div>
  );
}

function collectText(doc: CanonicalDocument, node: DocNode): string {
  return node.children
    .map((cid) => doc.nodes[cid])
    .filter((child): child is DocNode => Boolean(child))
    .map((child) => (child.type === "run" ? (child.text ?? "") : collectText(doc, child)))
    .join("");
}
