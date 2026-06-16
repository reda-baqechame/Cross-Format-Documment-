"use client";

import type { CanonicalDocument } from "@docos/shared-types";

import { NodeRenderer } from "@/components/canvas/NodeRenderer";

export function DocumentCanvas({ doc, docId }: { doc: CanonicalDocument; docId: string }) {
  const isPdf = doc.meta.source_format === "pdf";
  // PDF pages render full-bleed (their own page chrome); other formats get a page sheet.
  return isPdf ? (
    <div className="mx-auto w-full max-w-[920px]">
      <NodeRenderer doc={doc} nodeId={doc.root_id} docId={docId} />
    </div>
  ) : (
    <article className="mx-auto w-full max-w-[816px] rounded-lg bg-white p-12 shadow-sm">
      <NodeRenderer doc={doc} nodeId={doc.root_id} docId={docId} />
    </article>
  );
}
