"use client";

import { useState } from "react";

import { exportUrl, type ExportFormat } from "@/lib/api";

/** Download the current document — rebuilt from the canonical model — in any format. */
export function DownloadMenu({ docId, sourceFormat }: { docId: string; sourceFormat?: string }) {
  const [open, setOpen] = useState(false);

  const download = (format: ExportFormat) => {
    setOpen(false);
    const a = document.createElement("a");
    a.href = exportUrl(docId, format);
    a.download = "";
    document.body.appendChild(a);
    a.click();
    a.remove();
  };

  return (
    <div className="relative">
      <button
        onClick={() => setOpen((v) => !v)}
        className="rounded-md bg-slate-900 px-3 py-1.5 text-sm font-medium text-white hover:bg-slate-700"
      >
        Download ▾
      </button>
      {open && (
        <div
          className="absolute right-0 z-10 mt-1 w-40 overflow-hidden rounded-md border border-slate-200 bg-white shadow-lg"
          onMouseLeave={() => setOpen(false)}
        >
          <MenuItem label="Word (.docx)" onClick={() => download("docx")} />
          <MenuItem label="Excel (.xlsx)" onClick={() => download("xlsx")} />
          <MenuItem label="PowerPoint (.pptx)" onClick={() => download("pptx")} />
          <MenuItem label="Image (.png)" onClick={() => download("png")} />
          <MenuItem label="Plain text (.txt)" onClick={() => download("txt")} />
          <MenuItem label="Markdown (.md)" onClick={() => download("md")} />
          <MenuItem label="HTML (.html)" onClick={() => download("html")} />
          <MenuItem label="CSV (.csv)" onClick={() => download("csv")} />
          {sourceFormat === "pdf" && (
            <MenuItem label="PDF (with edits)" onClick={() => download("pdf")} />
          )}
        </div>
      )}
    </div>
  );
}

function MenuItem({ label, onClick }: { label: string; onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      className="block w-full px-3 py-2 text-left text-sm hover:bg-slate-50"
    >
      {label}
    </button>
  );
}
