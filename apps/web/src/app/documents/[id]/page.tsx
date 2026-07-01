"use client";

import { useQuery, type UseQueryResult } from "@tanstack/react-query";
import { FileText, Layers3, PanelRightClose, TriangleAlert } from "lucide-react";
import dynamic from "next/dynamic";
import { useParams, useSearchParams } from "next/navigation";
import { useMemo, useState } from "react";

// Univer is heavy + browser-only — load it lazily on the client only.
const UniverSheet = dynamic(() => import("@/components/canvas/UniverSheet"), {
  ssr: false,
  loading: () => <p className="p-6 text-sm text-slate-500">Loading spreadsheet editor…</p>,
});
// PDF.js reader — client-only (uses a web worker).
const PdfReader = dynamic(() => import("@/components/canvas/PdfReader"), {
  ssr: false,
  loading: () => <p className="p-6 text-sm text-slate-500">Loading PDF reader…</p>,
});

import { AiHelperPanel } from "@/components/canvas/AiHelperPanel";
import { ApprovalsPanel } from "@/components/canvas/ApprovalsPanel";
import { BulkSendPanel } from "@/components/workflows/BulkSendPanel";
import { AskPanel } from "@/components/canvas/AskPanel";
import { AutopilotPanel } from "@/components/canvas/AutopilotPanel";
import { ClausesPanel } from "@/components/canvas/ClausesPanel";
import { CommentsPanel } from "@/components/canvas/CommentsPanel";
import { ComparePanel } from "@/components/canvas/ComparePanel";
import { DocumentCanvas } from "@/components/canvas/DocumentCanvas";
import { ExtractPanel } from "@/components/canvas/ExtractPanel";
import {
  DocumentMobileActions,
  DocumentWorkspaceHeader,
  type WorkspaceTab,
} from "@/components/canvas/DocumentWorkspaceHeader";
import { EditorSessionPanel } from "@/components/canvas/EditorSessionPanel";
import { FormsPanel } from "@/components/canvas/FormsPanel";
import { IntelligencePanel } from "@/components/canvas/IntelligencePanel";
import { ModifyStudio } from "@/components/canvas/ModifyStudio";
import { SheetEditor } from "@/components/canvas/SheetEditor";
import { HealthPanel } from "@/components/health-panel/HealthPanel";
import { VerifyPanel } from "@/components/expert/VerifyPanel";
import { TagsPanel } from "@/components/documents/TagsPanel";
import { WorkflowRunnerPanel } from "@/components/workflows/WorkflowRunnerPanel";
import { fetchHealth, fetchModel, type WorkflowPreset } from "@/lib/api";
import { useWorkspace } from "@/lib/store";
import { friendlyLoadError } from "@/lib/upload";
import type { CanonicalDocument, DocumentHealthResponse, DocNode } from "@docos/shared-types";

/** Spreadsheet-shaped formats open in the inline cell editor instead of the text view. */
function isSpreadsheet(doc: CanonicalDocument): boolean {
  return doc.meta.source_format === "xlsx" || doc.meta.source_format === "csv";
}

const TABS: WorkspaceTab[] = [
  "document",
  "editor",
  "modify",
  "ai-helper",
  "autopilot",
  "insights",
  "forms",
  "clauses",
  "verify",
  "trust",
  "comments",
  "approvals",
];

const WORKFLOW_PRESETS: WorkflowPreset[] = [
  "contract_packet",
  "invoice_approval",
  "vendor_onboarding",
  "employee_form_packet",
  "proposal_to_signature",
  "bulk_send_template",
];

export default function DocumentPage() {
  const params = useParams<{ id: string }>();
  const search = useSearchParams();
  const docId = params.id;
  const initialTab = search.get("tab");
  const workflowParam = search.get("workflow");
  const initialWorkflow = WORKFLOW_PRESETS.includes(workflowParam as WorkflowPreset)
    ? (workflowParam as WorkflowPreset)
    : "contract_packet";
  const [tab, setTab] = useState<WorkspaceTab>(
    initialTab && (TABS as string[]).includes(initialTab)
      ? (initialTab as WorkspaceTab)
      : "document",
  );
  const [zoom, setZoom] = useState(100);
  const [sheetMode, setSheetMode] = useState<"grid" | "simple">("grid");
  const [pdfMode, setPdfMode] = useState<"edit" | "read">("edit");

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
  const showCanvas = tab === "document" || tab === "autopilot" || tab === "modify" || !doc;

  return (
    <div className="flex min-h-screen flex-col bg-chrome pb-20 sm:pb-0">
      <DocumentWorkspaceHeader
        docId={docId}
        doc={doc}
        activeTab={tab}
        onTabChange={setTab}
        zoom={zoom}
        onZoomChange={setZoom}
      />

      <div className="flex min-h-0 flex-1">
        {doc && <PageRail doc={doc} />}

        {showCanvas && (
          <main
            className="min-w-0 flex-1 overflow-auto bg-slate-100 p-4 sm:p-6"
            id="document-canvas"
            aria-label="Document content"
          >
            {model.isLoading && (
              <p className="text-slate-500" aria-live="polite">
                Loading document...
              </p>
            )}
            {model.isError && (
              <div
                role="alert"
                className="rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-800"
              >
                <p className="font-medium">Could not open this document</p>
                <p className="mt-1">{friendlyLoadError(model.error)}</p>
              </div>
            )}
            {doc && (
              <>
                {doc.meta.source_format === "pdf" && (
                  <div className="mx-auto mb-4 flex max-w-[1000px] flex-wrap items-center gap-3 rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
                    <TriangleAlert className="h-4 w-4 shrink-0" />
                    <p className="min-w-0 flex-1">
                      <strong>{pdfMode === "read" ? "PDF reader." : "Basic PDF editing."}</strong>{" "}
                      {pdfMode === "read"
                        ? "Crisp, selectable view (redactions applied)."
                        : "Edit the text overlay; redactions are true removal."}
                    </p>
                    <div className="flex shrink-0 overflow-hidden rounded-md border border-amber-300">
                      <button
                        type="button"
                        onClick={() => setPdfMode("read")}
                        className={`px-3 py-1 text-xs font-medium ${pdfMode === "read" ? "bg-amber-600 text-white" : "bg-white text-amber-700"}`}
                      >
                        Read
                      </button>
                      <button
                        type="button"
                        onClick={() => setPdfMode("edit")}
                        className={`px-3 py-1 text-xs font-medium ${pdfMode === "edit" ? "bg-amber-600 text-white" : "bg-white text-amber-700"}`}
                      >
                        Edit
                      </button>
                    </div>
                  </div>
                )}
                {doc.meta.source_format !== "pdf" && !isSpreadsheet(doc) && (
                  <div className="mx-auto mb-4 flex max-w-[816px] items-start gap-3 rounded-lg border border-slate-200 bg-white px-4 py-3 text-sm text-slate-600">
                    <FileText className="mt-0.5 h-4 w-4 shrink-0 text-slate-500" />
                    <p>
                      This is a structured text view of your {doc.meta.source_format.toUpperCase()} file.
                      To preserve exact appearance, use export validation before download.
                    </p>
                  </div>
                )}
                {isSpreadsheet(doc) && (
                  <div className="mx-auto mb-4 flex max-w-[1100px] flex-wrap items-center gap-3 rounded-lg border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-800">
                    <FileText className="h-4 w-4 shrink-0 text-emerald-600" />
                    <p className="min-w-0 flex-1">
                      <strong>Spreadsheet editor.</strong> Edit cells — every change is a reversible,
                      versioned edit. Use Undo/Redo and export validation as usual.
                    </p>
                    <div className="flex shrink-0 overflow-hidden rounded-md border border-emerald-300">
                      <button
                        type="button"
                        onClick={() => setSheetMode("grid")}
                        className={`px-3 py-1 text-xs font-medium ${sheetMode === "grid" ? "bg-emerald-600 text-white" : "bg-white text-emerald-700"}`}
                      >
                        Grid (Excel)
                      </button>
                      <button
                        type="button"
                        onClick={() => setSheetMode("simple")}
                        className={`px-3 py-1 text-xs font-medium ${sheetMode === "simple" ? "bg-emerald-600 text-white" : "bg-white text-emerald-700"}`}
                      >
                        Simple
                      </button>
                    </div>
                  </div>
                )}
                <div className="mx-auto mb-4 max-w-[816px]">
                  <TagsPanel docId={docId} />
                </div>
                {isSpreadsheet(doc) && sheetMode === "grid" ? (
                  // Univer owns its own zoom + pointer math, so it must not sit inside the scale().
                  <div className="mx-auto w-full max-w-[1100px]">
                    <UniverSheet doc={doc} docId={docId} />
                  </div>
                ) : doc.meta.source_format === "pdf" && pdfMode === "read" ? (
                  // PDF.js renders at its own scale; keep it out of the CSS scale() wrapper.
                  <PdfReader docId={docId} />
                ) : (
                  <div
                    style={{
                      transform: `scale(${zoom / 100})`,
                      transformOrigin: "top center",
                    }}
                  >
                    {isSpreadsheet(doc) ? (
                      <SheetEditor doc={doc} docId={docId} />
                    ) : (
                      <DocumentCanvas doc={doc} docId={docId} />
                    )}
                  </div>
                )}
              </>
            )}
          </main>
        )}

        {doc && (
          <aside className="editor-panel w-full shrink-0 overflow-auto border-l lg:w-[390px]">
            <RightPanel
              tab={tab}
              doc={doc}
              docId={docId}
              health={health}
              initialWorkflow={initialWorkflow}
            />
          </aside>
        )}
      </div>

      {doc && <DocumentMobileActions docId={docId} sourceFormat={doc.meta.source_format} />}
    </div>
  );
}

function RightPanel({
  tab,
  doc,
  docId,
  health,
  initialWorkflow,
}: {
  tab: WorkspaceTab;
  doc: CanonicalDocument;
  docId: string;
  health: UseQueryResult<DocumentHealthResponse, Error>;
  initialWorkflow: WorkflowPreset;
}) {
  if (tab === "forms") return <FormsPanel docId={docId} />;
  if (tab === "clauses") return <ClausesPanel doc={doc} docId={docId} />;
  if (tab === "comments") return <CommentsPanel docId={docId} />;
  if (tab === "approvals") {
    return (
      <div className="flex h-full flex-col overflow-auto">
        <ApprovalsPanel docId={docId} />
        <BulkSendPanel docId={docId} />
      </div>
    );
  }
  if (tab === "verify") {
    return (
      <div className="flex h-full w-full flex-col overflow-auto lg:w-96">
        <VerifyPanel docId={docId} />
      </div>
    );
  }
  if (tab === "trust") {
    if (health.isError) {
      return (
        <div role="alert" className="p-6 text-sm text-red-600">
          {friendlyLoadError(health.error)}
        </div>
      );
    }
    if (health.isLoading || !health.data) {
      return <p className="p-6 text-sm text-slate-500">Loading trust checks...</p>;
    }
    return (
      <div className="flex h-full w-full flex-col overflow-auto lg:w-96">
        <HealthPanel health={health.data.health} docId={docId} />
      </div>
    );
  }
  if (tab === "editor") return <EditorSessionPanel docId={docId} sourceFormat={doc.meta.source_format} />;
  if (tab === "modify" || tab === "document") return <ModifyStudio doc={doc} docId={docId} />;
  if (tab === "ai-helper") return <AiHelperPanel docId={docId} />;
  if (tab === "insights") {
    return (
      <div className="flex flex-col gap-4 overflow-auto p-4">
        <IntelligencePanel docId={docId} />
        <AskPanel docId={docId} />
        <ExtractPanel docId={docId} />
        <ComparePanel docId={docId} />
      </div>
    );
  }
  return (
    <div className="grid h-full grid-rows-[minmax(320px,1fr)_auto]">
      <WorkflowRunnerPanel docId={docId} initialPreset={initialWorkflow} />
      <div className="border-t border-slate-200">
        <AutopilotPanel docId={docId} />
      </div>
    </div>
  );
}

function PageRail({ doc }: { doc: CanonicalDocument }) {
  const selectNode = useWorkspace((state) => state.select);
  const selectedNodeId = useWorkspace((state) => state.selectedNodeId);
  const pages = useMemo(() => orderedPages(doc), [doc]);

  return (
    <aside className="editor-rail hidden w-[196px] shrink-0 overflow-auto border-r lg:block">
      <div className="flex items-center justify-between border-b border-slate-200 px-4 py-3">
        <div className="flex items-center gap-2">
          <Layers3 className="h-4 w-4 text-slate-500" />
          <p className="text-sm font-semibold text-slate-900">Pages</p>
        </div>
        <button type="button" className="icon-btn" aria-label="Collapse page rail">
          <PanelRightClose className="h-4 w-4" />
        </button>
      </div>
      <div className="space-y-3 p-4">
        {pages.length === 0 && <p className="text-sm text-slate-500">No pages detected.</p>}
        {pages.map((page, index) => {
          const selected = selectedNodeId === page.id;
          return (
            <button
              key={page.id}
              type="button"
              onClick={() => selectNode(page.id)}
              className={[
                "block w-full rounded-lg border bg-white p-2 text-left transition-colors",
                selected ? "border-blue-500 ring-2 ring-blue-100" : "border-slate-200 hover:border-blue-300",
              ].join(" ")}
            >
              <span className="flex aspect-[3/4] items-center justify-center rounded-md border border-slate-200 bg-slate-50 text-xs font-semibold text-slate-500">
                {index + 1}
              </span>
              <span className="mt-2 block text-center text-xs font-medium text-slate-600">
                {page.type === "page" ? "Page" : "Slide"} {page.page_number ?? index + 1}
              </span>
            </button>
          );
        })}
      </div>
    </aside>
  );
}

function orderedPages(doc: CanonicalDocument): DocNode[] {
  const root = doc.nodes[doc.root_id];
  const rootPages =
    root?.children
      .map((id) => doc.nodes[id])
      .filter((node): node is DocNode => Boolean(node) && node.type === "page") ?? [];
  if (rootPages.length) return rootPages;
  return Object.values(doc.nodes)
    .filter((node): node is DocNode => node.type === "page")
    .sort((a, b) => (a.page_number ?? 0) - (b.page_number ?? 0));
}
