"use client";

import type { CanonicalDocument } from "@docos/shared-types";

import { NodeRenderer } from "@/components/canvas/NodeRenderer";

export function DocumentCanvas({ doc }: { doc: CanonicalDocument }) {
  return (
    <article className="mx-auto w-full max-w-[816px] rounded-lg bg-white p-12 shadow-sm">
      <NodeRenderer doc={doc} nodeId={doc.root_id} />
    </article>
  );
}
