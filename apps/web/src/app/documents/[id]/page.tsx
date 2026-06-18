"use client";

import { useQuery } from "@tanstack/react-query";
import { useParams, useSearchParams } from "next/navigation";
import { useState } from "react";

import Link from "next/link";

import { ApprovalsPanel } from "@/components/canvas/ApprovalsPanel";
import { AutopilotPanel } from "@/components/canvas/AutopilotPanel";
import { DocumentCanvas } from "@/components/canvas/DocumentCanvas";
import {
  DocumentMobileActions,
  DocumentWorkspaceHeader,
  type WorkspaceTab,
} from "@/components/canvas/DocumentWorkspaceHeader";
import { CommentsPanel } from "@/components/canvas/CommentsPanel";
import { FormsPanel } from "@/components/canvas/FormsPanel";
import { HealthPanel } from "@/components/health-panel/HealthPanel";
import { IntelligencePanel } from "@/components/canvas/IntelligencePanel";
import { EditorSessionPanel } from "@/components/canvas/EditorSessionPanel";
import { ModifyStudio } from "@/components/canvas/ModifyStudio";
import { fetchHealth, fetchModel } from "@/lib/api";
import { friendlyLoadError } from "@/lib/upload";

const TABS: WorkspaceTab[] = [
  "document",
  "editor",
  "modify",
  "autopilot",
  "insights",
  "forms",
  "trust",
  "comments",
  "approvals",
];

export default function DocumentPage() {
  const params = useParams<{ id: string }>();
  const search = useSearchParams();
  const docId = params.id;
  const initialTab = search.get("tab");
  const [tab, setTab] = useState<WorkspaceTab>(
    initialTab && (TABS as string[]).includes(initialTab)
      ? (initialTab as WorkspaceTab)
      : "autopilot",
  );

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
  const showEditor = tab === "editor";
  const showModify = tab === "modify";
  const showAutopilot = tab === "autopilot";
  const showInsights = tab === "insights";
  const showForms = tab === "forms";
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

      <p className="border-b border-slate-100 bg-brand-50/50 px-4 py-2 text-center text-xs text-slate-600">
        Double-click (or long-press) any text to edit it · Download to save your changes
      </p>

      <div className="flex flex-1 flex-col lg:flex-row">
        {/* Main canvas — visible on its own tab and alongside the Autopilot panel */}
        {(showDocument || showEditor || showAutopilot || showModify || !doc) && (
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
                {doc.meta.source_format !== "pdf" && (
                  <div className="mx-auto mb-4 max-w-[816px] rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
                    This is a <strong>text view</strong> of your {doc.meta.source_format.toUpperCase()} file
                    — useful for editing and reading, but it doesn’t preserve the original layout. To keep
                    the exact look, use{" "}
                    <Link href="/tasks/convert" className="font-medium underline">
                      Convert
                    </Link>{" "}
                    or download from the menu above.
                  </div>
                )}
                <DocumentCanvas doc={doc} docId={docId} />
              </>
            )}
          </main>
        )}

        {/* Side / full-width panels */}
        {showAutopilot && doc && (
          <aside className="w-full border-t border-slate-200 bg-white lg:w-96 lg:border-l lg:border-t-0">
            <AutopilotPanel docId={docId} />
          </aside>
        )}
        {showModify && doc && (
          <aside className="w-full border-t border-slate-200 bg-white lg:w-96 lg:border-l lg:border-t-0">
            <ModifyStudio doc={doc} docId={docId} />
          </aside>
        )}
        {showEditor && doc && (
          <aside className="w-full border-t border-slate-200 bg-white lg:w-96 lg:border-l lg:border-t-0">
            <EditorSessionPanel docId={docId} sourceFormat={doc.meta.source_format} />
          </aside>
        )}
        {showInsights && (
          <aside className="w-full border-t border-slate-200 bg-white lg:w-96 lg:border-l lg:border-t-0">
            <IntelligencePanel docId={docId} />
          </aside>
        )}
        {showForms && (
          <aside className="w-full border-t border-slate-200 bg-white lg:w-96 lg:border-l lg:border-t-0">
            <FormsPanel docId={docId} />
          </aside>
        )}
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
