"use client";

import type { CanonicalDocument } from "@docos/shared-types";

import { NodeRenderer } from "@/components/canvas/NodeRenderer";

export function DocumentCanvas({
  doc,
  docId,
  readOnly = false,
}: {
  doc: CanonicalDocument;
  docId: string;
  readOnly?: boolean;
}) {
  const viewDoc: CanonicalDocument = readOnly
    ? {
        ...doc,
        permissions: {
          can_edit: false,
          can_export: doc.permissions?.can_export ?? true,
          can_copy: doc.permissions?.can_copy ?? true,
          encrypted: doc.permissions?.encrypted ?? false,
          password_protected: doc.permissions?.password_protected ?? false,
        },
      }
    : doc;
  const isPdf = viewDoc.meta.source_format === "pdf";
  // PDF pages render full-bleed (their own page chrome); other formats get a page sheet.
  return isPdf ? (
    <div className="mx-auto w-full max-w-[920px]">
      <NodeRenderer doc={viewDoc} nodeId={viewDoc.root_id} docId={docId} />
    </div>
  ) : (
    <article className="mx-auto w-full max-w-[816px] rounded-lg bg-white p-12 shadow-sm">
      <NodeRenderer doc={viewDoc} nodeId={viewDoc.root_id} docId={docId} />
    </article>
  );
}
