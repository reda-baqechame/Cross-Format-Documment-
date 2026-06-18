"use client";

import { useState } from "react";

import { downloadExport, downloadSearchablePdf, type ExportFormat } from "@/lib/api";
import { useDismissOnOutside } from "@/lib/useDismiss";
import { friendlyApiError } from "@/lib/upload";

const FORMATS: { format: ExportFormat; label: string; show?: (sf?: string) => boolean }[] = [
  { format: "docx", label: "Word (.docx)" },
  { format: "xlsx", label: "Excel (.xlsx)" },
  { format: "pptx", label: "PowerPoint (.pptx)" },
  { format: "png", label: "Image (.png)" },
  { format: "txt", label: "Plain text (.txt)" },
  { format: "md", label: "Markdown (.md)" },
  { format: "html", label: "HTML (.html)" },
  { format: "csv", label: "CSV (.csv)" },
  { format: "pdf", label: "PDF (with edits)", show: (sf) => sf === "pdf" },
];

/** Download the current document — rebuilt from the canonical model — in any format. */
export function DownloadMenu({ docId, sourceFormat }: { docId: string; sourceFormat?: string }) {
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState<ExportFormat | "searchable" | null>(null);
  const [error, setError] = useState<string | null>(null);
  const ref = useDismissOnOutside(open, () => setOpen(false));

  async function run(label: ExportFormat | "searchable", fn: () => Promise<unknown>) {
    setOpen(false);
    setBusy(label);
    setError(null);
    try {
      await fn();
    } catch (e) {
      setError(friendlyApiError(e, "Export failed."));
    } finally {
      setBusy(null);
    }
  }

  const download = (format: ExportFormat) => run(format, () => downloadExport(docId, format));

  return (
    <div className="relative" ref={ref}>
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        aria-haspopup="menu"
        disabled={!!busy}
        className="min-h-[44px] rounded-lg bg-ink px-3 py-2 text-sm font-medium text-white hover:bg-slate-800 disabled:opacity-50"
      >
        {busy ? "Exporting…" : "Export ▾"}
      </button>
      {error && (
        <p role="alert" className="absolute right-0 top-full z-20 mt-1 w-56 rounded-lg bg-red-50 px-2 py-1 text-xs text-red-700">
          {error}
        </p>
      )}
      {open && (
        <div
          role="menu"
          className="absolute right-0 z-10 mt-1 max-h-[70vh] w-48 overflow-auto rounded-lg border border-slate-200 bg-white py-1 shadow-lg"
        >
          {FORMATS.filter((f) => !f.show || f.show(sourceFormat)).map((f) => (
            <button
              key={f.format}
              type="button"
              role="menuitem"
              onClick={() => void download(f.format)}
              className="block min-h-[44px] w-full px-3 py-2 text-left text-sm hover:bg-slate-50"
            >
              {f.label}
            </button>
          ))}
          <div className="my-1 border-t border-slate-100" />
          <button
            type="button"
            role="menuitem"
            onClick={() => void run("searchable", () => downloadSearchablePdf(docId))}
            className="block min-h-[44px] w-full px-3 py-2 text-left text-sm hover:bg-slate-50"
          >
            Searchable PDF (OCR layer)
          </button>
        </div>
      )}
    </div>
  );
}
