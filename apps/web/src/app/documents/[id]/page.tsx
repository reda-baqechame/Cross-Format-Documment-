"use client";

import { useQuery } from "@tanstack/react-query";
import { useParams } from "next/navigation";
import { useState } from "react";

import { ApprovalsPanel } from "@/components/canvas/ApprovalsPanel";
import { AskPanel } from "@/components/canvas/AskPanel";
import { ComparePanel } from "@/components/canvas/ComparePanel";
import { DocumentCanvas } from "@/components/canvas/DocumentCanvas";
import {
  DocumentMobileActions,
  DocumentWorkspaceHeader,
  type WorkspaceTab,
} from "@/components/canvas/DocumentWorkspaceHeader";
import { CommentsPanel } from "@/components/canvas/CommentsPanel";
import { ExtractPanel } from "@/components/canvas/ExtractPanel";
import { HealthPanel } from "@/components/health-panel/HealthPanel";
import { fetchHealth, fetchModel } from "@/lib/api";
import { friendlyLoadError } from "@/lib/upload";

export default function DocumentPage() {
  const params = useParams<{ id: string }>();
  const docId = params.id;
  const [tab, setTab] = useState<WorkspaceTab>("document");

  const model = useQuery({
    queryKey: ["model", docId],
    queryFn: () => fetchModel(docId),
    enabled: Boolean(docId),
  });
  const health = useQuery({
    queryKey: ["health", docId],
    queryFn: () => fetchHealth(docId),
    enabled: Boolean(docId),
  });

  const doc = model.data?.document;
  const showDocument = tab === "document";
  const showTrust = tab === "trust";
  const showComments = tab === "comments";
  const showApprovals = tab === "approvals";

  return (
    <div className="flex min-h-screen flex-col bg-canvas pb-20 sm:pb-0">
      <DocumentWorkspaceHeader
        docId={docId}
        doc={doc}
        activeTab={tab}
        onTabChange={setTab}
      />

      <p className="hidden border-b border-slate-100 bg-brand-50/50 px-4 py-2 text-center text-xs text-slate-600 sm:block">
        Double-click or long-press text to edit · AI bar for natural-language changes · Tools for
        protect &amp; classify · Download to export
      </p>
      <p className="border-b border-slate-100 bg-brand-50/50 px-4 py-2 text-center text-xs text-slate-600 sm:hidden">
        Long-press text to edit · Use tabs for Trust, Comments, and Approvals
      </p>

      <div className="flex flex-1 flex-col lg:flex-row">
        {/* Main canvas */}
        {(showDocument || !doc) && (
          <main
            className="flex-1 overflow-auto p-4 sm:p-8"
            id="document-canvas"
            aria-label="Document content"
          >
            {model.isLoading && (
              <p className="text-slate-500" aria-live="polite">
                Loading document…
              </p>
            )}
            {model.isError && (
              <div role="alert" className="rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-800">
                <p className="font-medium">Couldn&apos;t open this document</p>
                <p className="mt-1">{friendlyLoadError(model.error)}</p>
              </div>
            )}
            {doc && (
              <>
                <AskPanel docId={docId} />
                <ExtractPanel docId={docId} />
                <ComparePanel docId={docId} />
                <DocumentCanvas doc={doc} docId={docId} />
              </>
            )}
          </main>
        )}

        {/* Side / full-width panels */}
        {showTrust && health.isError && (
          <div role="alert" className="w-full p-8 text-sm text-red-600">
            {friendlyLoadError(health.error)}
          </div>
        )}
        {showTrust && health.isLoading && (
          <p className="p-8 text-sm text-slate-500" aria-live="polite">
            Loading trust panel…
          </p>
        )}
        {showTrust && health.data && (
          <aside className="w-full border-t border-slate-200 bg-white lg:w-96 lg:border-l lg:border-t-0">
            <HealthPanel health={health.data.health} docId={docId} />
          </aside>
        )}
        {showComments && (
          <aside className="w-full border-t border-slate-200 bg-white lg:w-96 lg:border-l lg:border-t-0">
            <CommentsPanel docId={docId} />
          </aside>
        )}
        {showApprovals && (
          <aside className="w-full border-t border-slate-200 bg-white lg:w-96 lg:border-l lg:border-t-0">
            <ApprovalsPanel docId={docId} />
          </aside>
        )}
      </div>

      {doc && (
        <DocumentMobileActions docId={docId} sourceFormat={doc.meta.source_format} />
      )}
    </div>
  );
}
