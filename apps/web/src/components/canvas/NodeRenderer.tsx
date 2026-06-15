"use client";

import type { CanonicalDocument, DocNode } from "@docos/shared-types";

import { useWorkspace } from "@/lib/store";

/**
 * Renders a single node by walking its children in the canonical model. The model
 * — not the raw file — is the source of truth, which is the core architectural bet.
 */
export function NodeRenderer({ doc, nodeId }: { doc: CanonicalDocument; nodeId: string }) {
  const node = doc.nodes[nodeId];
  if (!node) return null;
  const children = node.children.map((cid) => (
    <NodeRenderer key={cid} doc={doc} nodeId={cid} />
  ));

  switch (node.type) {
    case "root":
      return <div className="space-y-3">{children}</div>;
    case "heading":
      return <Heading node={node}>{children}</Heading>;
    case "paragraph":
      return <p className="leading-relaxed">{children}</p>;
    case "run":
      return <RunSpan node={node} />;
    case "table":
      return <table className="w-full border-collapse text-sm">{children}</table>;
    case "table_row":
      return <tr>{children}</tr>;
    case "table_cell":
      return <td className="border border-slate-300 px-2 py-1">{children}</td>;
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

function RunSpan({ node }: { node: DocNode }) {
  const select = useWorkspace((s) => s.select);
  const selected = useWorkspace((s) => s.selectedNodeId === node.id);
  return (
    <span
      onClick={() => select(node.id)}
      className={[
        node.bold ? "font-bold" : "",
        node.italic ? "italic" : "",
        node.underline ? "underline" : "",
        selected ? "bg-yellow-100" : "",
        "cursor-text",
      ].join(" ")}
    >
      {node.text}
    </span>
  );
}
