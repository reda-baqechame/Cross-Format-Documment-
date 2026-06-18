"use client";

import Link from "next/link";
import {
  Bot,
  CheckCircle2,
  ChevronLeft,
  Download,
  FilePenLine,
  FileText,
  FormInput,
  LockKeyhole,
  MessageSquare,
  MoreHorizontal,
  Redo2,
  Search,
  Send,
  Share2,
  Undo2,
  ZoomIn,
  ZoomOut,
} from "lucide-react";

import { AiEditBar } from "@/components/canvas/AiEditBar";
import { DownloadMenu } from "@/components/canvas/DownloadMenu";
import { FormatToolbar } from "@/components/canvas/FormatToolbar";
import { ToolsMenu } from "@/components/canvas/ToolsMenu";
import type { CanonicalDocument } from "@docos/shared-types";

type WorkspaceTab =
  | "document"
  | "editor"
  | "modify"
  | "autopilot"
  | "insights"
  | "forms"
  | "trust"
  | "comments"
  | "approvals";

const PRIMARY_TABS: {
  id: WorkspaceTab;
  label: string;
  icon: typeof FilePenLine;
}[] = [
  { id: "document", label: "Edit", icon: FilePenLine },
  { id: "forms", label: "Forms", icon: FormInput },
  { id: "comments", label: "Review", icon: MessageSquare },
  { id: "trust", label: "Protect", icon: LockKeyhole },
  { id: "autopilot", label: "Automate", icon: Bot },
  { id: "approvals", label: "Send", icon: Send },
];

export function DocumentWorkspaceHeader({
  docId,
  doc,
  activeTab,
  onTabChange,
}: {
  docId: string;
  doc?: CanonicalDocument;
  activeTab: WorkspaceTab;
  onTabChange: (tab: WorkspaceTab) => void;
}) {
  const title = doc?.meta.title ?? `Document ${docId.slice(0, 8)}...`;
  const format = doc?.meta.source_format?.toUpperCase() ?? "DOCUMENT";
  const normalizedTab = activeTab === "modify" || activeTab === "editor" ? "document" : activeTab;

  return (
    <header className="sticky top-0 z-40 border-b border-slate-200 bg-white">
      <div className="flex min-h-[72px] items-center gap-3 px-3 py-3 sm:px-5">
        <Link href="/" className="icon-btn shrink-0" aria-label="Back to home">
          <ChevronLeft className="h-4 w-4" />
        </Link>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <h1 className="truncate text-lg font-semibold tracking-tight text-slate-950">
              {title}
            </h1>
            <span className="rounded-md border border-amber-200 bg-amber-50 px-2 py-0.5 text-xs font-medium text-amber-700">
              In review
            </span>
          </div>
          <div className="mt-1 flex flex-wrap items-center gap-2 text-xs text-slate-500">
            <span>{format}</span>
            <span aria-hidden>-</span>
            <span>Version current</span>
            <span aria-hidden>-</span>
            <span>Audit enabled</span>
          </div>
        </div>

        <div className="hidden items-center gap-2 md:flex">
          <button type="button" className="studio-btn gap-2">
            <Share2 className="h-4 w-4" />
            Share
          </button>
          <DownloadMenu docId={docId} sourceFormat={doc?.meta.source_format} />
          <button type="button" className="icon-btn" aria-label="More actions">
            <MoreHorizontal className="h-4 w-4" />
          </button>
        </div>
      </div>

      <div className="flex items-center overflow-x-auto border-t border-slate-100 px-3 sm:px-5">
        {PRIMARY_TABS.map((tab) => {
          const Icon = tab.icon;
          const active = normalizedTab === tab.id;
          return (
            <button
              key={tab.id}
              type="button"
              onClick={() => onTabChange(tab.id)}
              className={`mode-tab flex shrink-0 items-center gap-2 ${active ? "mode-tab-active" : ""}`}
              aria-current={active ? "page" : undefined}
            >
              <Icon className="h-4 w-4" />
              {tab.label}
            </button>
          );
        })}
      </div>

      <div className="flex items-center gap-2 overflow-x-auto border-t border-slate-100 px-3 py-2 sm:px-5">
        <div className="flex shrink-0 items-center gap-1">
          <button type="button" className="icon-btn" aria-label="Undo">
            <Undo2 className="h-4 w-4" />
          </button>
          <button type="button" className="icon-btn" aria-label="Redo">
            <Redo2 className="h-4 w-4" />
          </button>
          <button type="button" className="icon-btn" aria-label="Zoom out">
            <ZoomOut className="h-4 w-4" />
          </button>
          <span className="px-2 text-xs font-medium text-slate-500">100%</span>
          <button type="button" className="icon-btn" aria-label="Zoom in">
            <ZoomIn className="h-4 w-4" />
          </button>
          <button type="button" className="icon-btn" aria-label="Search document">
            <Search className="h-4 w-4" />
          </button>
        </div>

        <div className="h-6 w-px shrink-0 bg-slate-200" />
        {doc && <FormatToolbar doc={doc} docId={docId} />}
        <ToolsMenu docId={docId} sourceFormat={doc?.meta.source_format} />
        <AiEditBar docId={docId} />

        <div className="ml-auto hidden items-center gap-2 lg:flex">
          <span className="inline-flex items-center gap-1.5 rounded-lg border border-teal-200 bg-teal-50 px-2.5 py-1 text-xs font-medium text-teal-700">
            <CheckCircle2 className="h-3.5 w-3.5" />
            Export validation ready
          </span>
          <button
            type="button"
            onClick={() => onTabChange("insights")}
            className="studio-btn gap-2"
          >
            <FileText className="h-4 w-4" />
            Analyze
          </button>
          <button
            type="button"
            onClick={() => onTabChange("editor")}
            className="studio-btn gap-2"
          >
            <Download className="h-4 w-4" />
            Editor core
          </button>
        </div>
      </div>
    </header>
  );
}

export function DocumentMobileActions({
  docId,
  sourceFormat,
}: {
  docId: string;
  sourceFormat?: string;
}) {
  return (
    <div className="fixed bottom-0 left-0 right-0 z-30 flex items-center gap-1 border-t border-slate-200 bg-white px-2 py-2 safe-bottom sm:hidden">
      <AiEditBar docId={docId} />
      <ToolsMenu docId={docId} sourceFormat={sourceFormat} />
      <DownloadMenu docId={docId} sourceFormat={sourceFormat} />
    </div>
  );
}

export type { WorkspaceTab };
