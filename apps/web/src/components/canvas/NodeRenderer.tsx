"use client";

import type { CanonicalDocument, DocNode } from "@docos/shared-types";
import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";

import { addPositionedText, deleteNode, moveNode, previewUrl, setRunText } from "@/lib/api";
import { useWorkspace } from "@/lib/store";

// Matches the backend PdfAdapter.render_preview_bytes default so overlay coordinates
// (PDF points) line up with the rasterised page image.
const PDF_SCALE = 1.5;

/** A page/image preview that degrades to a labelled placeholder instead of a broken-image
 * icon when the backend preview can't be produced (e.g. transient error, page out of range). */
function PreviewImage({
  src,
  alt,
  width,
  height,
  className,
  onClick,
}: {
  src: string;
  alt: string;
  width?: number;
  height?: number;
  className?: string;
  onClick?: () => void;
}) {
  const [failed, setFailed] = useState(false);
  if (failed) {
    return (
      <div
        onClick={onClick}
        style={width && height ? { width, height } : undefined}
        className={[
          "flex items-center justify-center bg-slate-50 text-center text-xs text-slate-500",
          className ?? "",
        ].join(" ")}
      >
        <span className="px-3">Preview unavailable — the document text is still editable below.</span>
      </div>
    );
  }
  return (
    // eslint-disable-next-line @next/next/no-img-element
    <img
      src={src}
      alt={alt}
      width={width}
      height={height}
      onClick={onClick}
      onError={() => setFailed(true)}
      className={className}
    />
  );
}

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

function collectRuns(doc: CanonicalDocument, nodeId: string): DocNode[] {
  const out: DocNode[] = [];
  const stack = [...(doc.nodes[nodeId]?.children ?? [])];
  while (stack.length) {
    const node = doc.nodes[stack.pop()!];
    if (!node) continue;
    if (node.type === "run") out.push(node);
    else stack.push(...node.children);
  }
  return out;
}

/**
 * Renders a node by walking its children in the canonical model. The model — not the
 * raw file — is the source of truth, which is the core architectural bet.
 */
export function NodeRenderer({
  doc,
  nodeId,
  docId,
}: {
  doc: CanonicalDocument;
  nodeId: string;
  docId: string;
}) {
  const node = doc.nodes[nodeId];
  if (!node) return null;
  const children = node.children.map((cid) => (
    <NodeRenderer key={cid} doc={doc} nodeId={cid} docId={docId} />
  ));

  switch (node.type) {
    case "root": {
      // Born-digital docs get block-level structure actions (move/delete); PDF pages
      // keep their faithful overlay and are edited via text/redaction instead.
      const structural = doc.meta.source_format !== "pdf" && (doc.permissions?.can_edit ?? true);
      return (
        <div className="space-y-3">
          {node.children.map((cid, i) =>
            structural ? (
              <BlockWrap
                key={cid}
                doc={doc}
                docId={docId}
                parentId={node.id}
                nodeId={cid}
                index={i}
                count={node.children.length}
              >
                <NodeRenderer doc={doc} nodeId={cid} docId={docId} />
              </BlockWrap>
            ) : (
              <NodeRenderer key={cid} doc={doc} nodeId={cid} docId={docId} />
            ),
          )}
        </div>
      );
    }
    case "page":
      return <PageView doc={doc} node={node} docId={docId}>{children}</PageView>;
    case "heading":
      return <Heading node={node}>{children}</Heading>;
    case "paragraph":
      return <p className="leading-relaxed">{children}</p>;
    case "run":
      return <RunSpan doc={doc} node={node} docId={docId} />;
    case "list":
      return node.ordered ? (
        <ol className="list-decimal space-y-1 pl-6">{children}</ol>
      ) : (
        <ul className="list-disc space-y-1 pl-6">{children}</ul>
      );
    case "list_item":
      return <li className="leading-relaxed">{children}</li>;
    case "image":
      return <ImageNode doc={doc} node={node} docId={docId} />;
    case "field":
      return <FieldNode node={node} />;
    case "table":
      return <SelectableTable node={node}>{children}</SelectableTable>;
    case "table_row":
      return <tr>{children}</tr>;
    case "table_cell":
      return <SelectableCell node={node}>{children}</SelectableCell>;
    default:
      return <div data-node-type={node.type}>{children}</div>;
  }
}

function Heading({ node, children }: { node: DocNode; children: React.ReactNode }) {
  const level = Math.min(Math.max(node.level ?? 1, 1), 6);
  const Tag = `h${level}` as keyof JSX.IntrinsicElements;
  const sizes: Record<number, string> = {
    1: "text-2xl",
    2: "text-xl",
    3: "text-lg",
    4: "text-base",
    5: "text-sm",
    6: "text-sm",
  };
  return <Tag className={`font-semibold ${sizes[level]}`}>{children}</Tag>;
}

/** Inline-editable, redaction-aware text run (used in normal document flow). */
function RunSpan({
  doc,
  node,
  docId,
}: {
  doc: CanonicalDocument;
  node: DocNode;
  docId: string;
}) {
  const select = useWorkspace((s) => s.select);
  const selected = useWorkspace((s) => s.selectedNodeId === node.id);
  const editingNodeId = useWorkspace((s) => s.editingNodeId);
  const setEditing = useWorkspace((s) => s.setEditing);
  const queryClient = useQueryClient();
  const redacted = isRedacted(doc, node.id);
  const canEdit = doc.permissions?.can_edit ?? true;
  const editing = editingNodeId === node.id;
  const longPressRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const clearLongPress = () => {
    if (longPressRef.current) {
      clearTimeout(longPressRef.current);
      longPressRef.current = null;
    }
  };

  const startLongPress = () => {
    if (!canEdit) return;
    clearLongPress();
    longPressRef.current = setTimeout(() => setEditing(node.id), 450);
  };

  if (redacted) {
    return (
      <span
        onClick={() => select(node.id)}
        title="Redacted — removed from exports"
        className="cursor-pointer rounded bg-slate-900 px-2 align-middle text-slate-900 select-none"
      >
        {"█".repeat(Math.max(node.text?.length ?? 3, 3))}
      </span>
    );
  }

  if (editing) {
    return (
      <InlineEditor
        initial={node.text ?? ""}
        onCommit={async (text) => {
          setEditing(null);
          if (text !== (node.text ?? "")) {
            await setRunText(docId, node.id, text);
            queryClient.invalidateQueries({ queryKey: ["model", docId] });
            queryClient.invalidateQueries({ queryKey: ["health", docId] });
          }
        }}
        onCancel={() => setEditing(null)}
      />
    );
  }

  return (
    <span
      id={`node-${node.id}`}
      onClick={() => select(node.id)}
      onDoubleClick={() => canEdit && setEditing(node.id)}
      onTouchStart={startLongPress}
      onTouchEnd={clearLongPress}
      onTouchMove={clearLongPress}
      onContextMenu={(e) => {
        if (canEdit) {
          e.preventDefault();
          setEditing(node.id);
        }
      }}
      className={[
        node.bold ? "font-bold" : "",
        node.italic ? "italic" : "",
        node.underline ? "underline" : "",
        selected ? "bg-yellow-100" : "",
        canEdit ? "cursor-text" : "cursor-default",
      ].join(" ")}
      style={{
        // Color and size are first-class run fields — render them so the format
        // toolbar's changes are visible on the canvas, not just stored in the model.
        color: node.color ?? undefined,
        fontSize: typeof node.size === "number" ? `${node.size}px` : undefined,
        fontFamily: node.font ?? undefined,
        whiteSpace: "pre-wrap",
      }}
      title={canEdit ? "Double-click or long-press to edit" : undefined}
    >
      {node.text}
    </span>
  );
}

function InlineEditor({
  initial,
  onCommit,
  onCancel,
}: {
  initial: string;
  onCommit: (text: string) => void;
  onCancel: () => void;
}) {
  const [value, setValue] = useState(initial);
  const ref = useRef<HTMLTextAreaElement>(null);
  useEffect(() => {
    const textarea = ref.current;
    if (!textarea) return;
    textarea.focus();
    textarea.setSelectionRange(textarea.value.length, textarea.value.length);
  }, []);
  return (
    <textarea
      ref={ref}
      value={value}
      onChange={(e) => setValue(e.target.value)}
      onBlur={() => onCommit(value)}
      onKeyDown={(e) => {
        if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) onCommit(value);
        if (e.key === "Escape") onCancel();
      }}
      rows={Math.max(value.split("\n").length, 1)}
      className="min-h-[32px] min-w-[12ch] resize rounded border border-blue-400 bg-blue-50 px-2 py-1 align-top leading-relaxed outline-none"
      style={{
        width: `${Math.min(
          Math.max(...value.split("\n").map((line) => line.length), 12) + 2,
          72,
        )}ch`,
      }}
      aria-label="Inline document text editor"
    />
  );
}

/** PDF page: faithful rasterised backdrop with a selectable/redactable text overlay. */
function PageView({
  doc,
  node,
  docId,
  children,
}: {
  doc: CanonicalDocument;
  node: DocNode;
  docId: string;
  children: React.ReactNode;
}) {
  const select = useWorkspace((s) => s.select);
  const selected = useWorkspace((s) => s.selectedNodeId === node.id);
  const addTextMode = useWorkspace((s) => s.addTextMode);
  const setAddText = useWorkspace((s) => s.setAddText);
  const queryClient = useQueryClient();
  // Pending click position (in PDF points) where a new text box will be placed.
  const [pending, setPending] = useState<{ x: number; y: number } | null>(null);
  const isPdf = doc.meta.source_format === "pdf";
  if (!isPdf || !node.width || !node.height) {
    return (
      <div
        onClick={(e) => {
          if (e.target === e.currentTarget) select(node.id);
        }}
        className={[
          "my-4 rounded bg-white p-8 shadow-sm",
          selected ? "outline outline-2 outline-brand-300" : "",
        ].join(" ")}
      >
        {children}
      </div>
    );
  }
  const w = node.width * PDF_SCALE;
  const h = node.height * PDF_SCALE;
  const runs = collectRuns(doc, node.id).filter((r) => r.bbox);

  const placeText = async (text: string) => {
    const point = pending;
    setPending(null);
    setAddText(false);
    if (!point || !text.trim()) return;
    const size = 12;
    await addPositionedText(
      docId,
      node.id,
      { x0: point.x, y0: point.y, x1: point.x + 240, y1: point.y + size * 1.5 },
      text,
      { size },
    );
    queryClient.invalidateQueries({ queryKey: ["model", docId] });
  };

  return (
    <div
      className={[
        "relative mx-auto my-4 bg-white shadow",
        selected ? "outline outline-2 outline-brand-300" : "",
        addTextMode ? "cursor-crosshair" : "",
      ].join(" ")}
      style={{ width: w, height: h }}
      onClick={(e) => {
        if (addTextMode) {
          const rect = e.currentTarget.getBoundingClientRect();
          setPending({
            x: (e.clientX - rect.left) / PDF_SCALE,
            y: (e.clientY - rect.top) / PDF_SCALE,
          });
          return;
        }
        if (e.target === e.currentTarget) select(node.id);
      }}
    >
      <PreviewImage
        src={previewUrl(docId, (node.page_number ?? 1) - 1)}
        alt={`Page ${node.page_number ?? 1}`}
        width={w}
        height={h}
        className="block select-none"
      />
      {runs.map((r) => (
        <RunOverlay key={r.id} doc={doc} node={r} />
      ))}
      {pending && (
        <div
          className="absolute z-10"
          style={{ left: pending.x * PDF_SCALE, top: pending.y * PDF_SCALE }}
        >
          <InlineEditor initial="" onCommit={placeText} onCancel={() => setPending(null)} />
        </div>
      )}
    </div>
  );
}

function RunOverlay({ doc, node }: { doc: CanonicalDocument; node: DocNode }) {
  const select = useWorkspace((s) => s.select);
  const selected = useWorkspace((s) => s.selectedNodeId === node.id);
  const redacted = isRedacted(doc, node.id);
  const b = node.bbox!;
  const style = {
    left: b.x0 * PDF_SCALE,
    top: b.y0 * PDF_SCALE,
    width: (b.x1 - b.x0) * PDF_SCALE,
    height: (b.y1 - b.y0) * PDF_SCALE,
  } as const;
  return (
    <span
      onClick={() => select(node.id)}
      title={redacted ? "Redacted — removed from exports" : "Tap to select · use Trust panel to redact"}
      style={style}
      className={[
        "absolute cursor-pointer",
        redacted ? "bg-slate-900" : selected ? "bg-yellow-300/40" : "hover:bg-blue-200/30",
      ].join(" ")}
    />
  );
}

function ImageNode({
  doc,
  node,
  docId,
}: {
  doc: CanonicalDocument;
  node: DocNode;
  docId: string;
}) {
  // For image-origin documents the uploaded bytes are the image — show them.
  const select = useWorkspace((s) => s.select);
  const selected = useWorkspace((s) => s.selectedNodeId === node.id);
  if (doc.meta.source_format === "image" && node.blob_ref === "original") {
    return (
      <PreviewImage
        src={previewUrl(docId, 0)}
        alt={node.alt_text ?? "Uploaded image"}
        onClick={() => select(node.id)}
        className={[
          "mx-auto my-2 max-w-full rounded border border-slate-200",
          selected ? "outline outline-2 outline-brand-300" : "",
        ].join(" ")}
      />
    );
  }
  return (
    <div
      onClick={(e) => {
        if (e.target === e.currentTarget) select(node.id);
      }}
      className={[
        "my-2 flex cursor-pointer items-center gap-2 rounded border border-dashed border-slate-300 bg-slate-50 px-3 py-4 text-sm text-slate-500",
        selected ? "outline outline-2 outline-brand-300" : "",
      ].join(" ")}
    >
      <span aria-hidden>🖼️</span>
      <span>{node.alt_text ?? "Image"}</span>
      {!node.alt_text && (
        <span className="rounded bg-amber-100 px-2 py-0.5 text-xs text-amber-700">missing alt</span>
      )}
    </div>
  );
}

function FieldNode({ node }: { node: DocNode }) {
  const select = useWorkspace((s) => s.select);
  const selected = useWorkspace((s) => s.selectedNodeId === node.id);
  return (
    <span
      onClick={() => select(node.id)}
      className={[
        "mx-0.5 inline-flex cursor-pointer items-center gap-1 rounded border border-slate-300 bg-slate-50 px-2 py-0.5 text-sm",
        selected ? "outline outline-2 outline-brand-300" : "",
      ].join(" ")}
    >
      <span className="text-xs uppercase text-slate-400">{node.field_name ?? "field"}</span>
      <span>{node.value ?? "—"}</span>
    </span>
  );
}

function SelectableTable({ node, children }: { node: DocNode; children: React.ReactNode }) {
  const select = useWorkspace((s) => s.select);
  const selected = useWorkspace((s) => s.selectedNodeId === node.id);
  return (
    <table
      onClick={() => select(node.id)}
      className={[
        "w-full border-collapse text-sm",
        selected ? "outline outline-2 outline-brand-300" : "",
      ].join(" ")}
    >
      {children}
    </table>
  );
}

function SelectableCell({ node, children }: { node: DocNode; children: React.ReactNode }) {
  const select = useWorkspace((s) => s.select);
  const selected = useWorkspace((s) => s.selectedNodeId === node.id);
  return (
    <td
      onClick={(e) => {
        if (e.target === e.currentTarget) select(node.id);
      }}
      className={[
        "border border-slate-300 px-2 py-1",
        selected ? "bg-brand-50 outline outline-2 outline-brand-300" : "",
      ].join(" ")}
    >
      {children}
    </td>
  );
}

/**
 * Hover affordance around a top-level block: move it up/down or delete it. Every
 * action is a reversible, versioned patch (restorable via undo).
 */
function BlockWrap({
  doc,
  docId,
  parentId,
  nodeId,
  index,
  count,
  children,
}: {
  doc: CanonicalDocument;
  docId: string;
  parentId: string;
  nodeId: string;
  index: number;
  count: number;
  children: React.ReactNode;
}) {
  const queryClient = useQueryClient();
  const refresh = () => {
    queryClient.invalidateQueries({ queryKey: ["model", docId] });
    queryClient.invalidateQueries({ queryKey: ["health", docId] });
  };
  const act = async (fn: () => Promise<unknown>) => {
    await fn();
    refresh();
  };

  return (
    <div className="group relative">
      <div className="absolute -left-1 top-0 z-10 hidden -translate-x-full flex-col gap-1 pr-1 group-hover:flex">
        <BlockBtn
          label="Move block up"
          disabled={index === 0}
          onClick={() => void act(() => moveNode(docId, nodeId, parentId, index - 1))}
        >
          ↑
        </BlockBtn>
        <BlockBtn
          label="Move block down"
          disabled={index === count - 1}
          onClick={() => void act(() => moveNode(docId, nodeId, parentId, index + 1))}
        >
          ↓
        </BlockBtn>
        <BlockBtn
          label="Delete block"
          onClick={() => {
            if (window.confirm("Delete this block? You can undo it."))
              void act(() => deleteNode(docId, nodeId));
          }}
        >
          ✕
        </BlockBtn>
      </div>
      {children}
    </div>
  );
}

function BlockBtn({
  label,
  onClick,
  disabled,
  children,
}: {
  label: string;
  onClick: () => void;
  disabled?: boolean;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      aria-label={label}
      title={label}
      disabled={disabled}
      onClick={onClick}
      className="h-6 w-6 rounded border border-slate-200 bg-white text-xs text-slate-500 shadow-sm hover:bg-slate-50 disabled:opacity-30"
    >
      {children}
    </button>
  );
}
