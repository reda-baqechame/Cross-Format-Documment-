"use client";

import Link from "next/link";

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
  const title = doc?.meta.title ?? `Document ${docId.slice(0, 8)}…`;
  const format = doc?.meta.source_format;

  const tabs: { id: WorkspaceTab; label: string; short: string }[] = [
    { id: "document", label: "Edit", short: "Edit" },
    { id: "editor", label: "Editor core", short: "Core" },
    { id: "modify", label: "Tools", short: "Tools" },
    { id: "autopilot", label: "Automate", short: "Auto" },
    { id: "insights", label: "Analyze", short: "Analyze" },
    { id: "forms", label: "Forms", short: "Forms" },
    { id: "trust", label: "Protect", short: "Protect" },
    { id: "comments", label: "Review", short: "Review" },
    { id: "approvals", label: "Send", short: "Send" },
  ];

  return (
    <header className="sticky top-0 z-40 border-b border-slate-200 bg-white/95 backdrop-blur">
      <div className="flex items-center gap-2 px-3 py-2 sm:px-4">
        <Link
          href="/"
          className="shrink-0 rounded-lg px-2 py-1.5 text-sm text-slate-500 hover:bg-slate-100"
        >
          ←
        </Link>
        <div className="min-w-0 flex-1">
          <p className="truncate text-sm font-semibold text-ink">{title}</p>
          {format && (
            <p className="text-[10px] font-medium uppercase tracking-wide text-slate-400">
              {format}
            </p>
          )}
        </div>
      </div>

      {/* Mobile: tab bar */}
      <nav
        className="flex border-t border-slate-100 sm:hidden"
        aria-label="Workspace sections"
      >
        {tabs.map((t) => (
          <button
            key={t.id}
            type="button"
            onClick={() => onTabChange(t.id)}
            className={[
              "min-h-[48px] flex-1 text-xs font-medium transition-colors",
              activeTab === t.id
                ? "border-b-2 border-brand-600 text-brand-700"
                : "text-slate-500",
            ].join(" ")}
            aria-current={activeTab === t.id ? "page" : undefined}
          >
            {t.short}
          </button>
        ))}
      </nav>

      {doc && activeTab === "document" && (
        <div className="flex flex-wrap items-center gap-2 border-t border-slate-100 px-3 py-2 sm:hidden">
          <FormatToolbar doc={doc} docId={docId} />
        </div>
      )}

      {/* Desktop: tool strip */}
      <div className="hidden flex-wrap items-center gap-2 border-t border-slate-100 px-4 py-2 sm:flex">
        {doc && <FormatToolbar doc={doc} docId={docId} />}
        <AiEditBar docId={docId} />
        <ToolsMenu docId={docId} sourceFormat={doc?.meta.source_format} />
        <DownloadMenu docId={docId} sourceFormat={doc?.meta.source_format} />
        <div className="ml-auto flex gap-1">
          {tabs.slice(1).map((t) => (
            <button
              key={t.id}
              type="button"
              onClick={() => onTabChange(t.id)}
              className={[
                "rounded-md px-3 py-1.5 text-sm",
                activeTab === t.id
                  ? "bg-brand-50 font-medium text-brand-700"
                  : "text-slate-500 hover:bg-slate-50",
              ].join(" ")}
            >
              {t.label}
            </button>
          ))}
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
