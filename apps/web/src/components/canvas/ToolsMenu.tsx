"use client";

import { useState } from "react";

import { classifyDocument, compressPdf, protectPdf, saveAsTemplate, watermarkPdf } from "@/lib/api";
import { useDismissOnOutside } from "@/lib/useDismiss";
import { friendlyApiError } from "@/lib/upload";

/**
 * Document tools — compress, protect, watermark, classify (PDF-focused where noted).
 */
export function ToolsMenu({ docId, sourceFormat }: { docId: string; sourceFormat?: string }) {
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const ref = useDismissOnOutside(open, () => setOpen(false));
  const isPdf = sourceFormat === "pdf";

  const run = async (fn: () => Promise<unknown>) => {
    setOpen(false);
    setBusy(true);
    setError(null);
    try {
      await fn();
    } catch (e) {
      setError(friendlyApiError(e, "That tool failed."));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="relative" ref={ref}>
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        aria-haspopup="menu"
        disabled={busy}
        className="min-h-[44px] rounded-lg border border-slate-300 px-3 py-2 text-sm hover:bg-slate-50 disabled:opacity-40"
      >
        {busy ? "Working…" : "Tools ▾"}
      </button>
      {error && (
        <p role="alert" className="absolute right-0 top-full z-20 mt-1 w-56 rounded-lg bg-red-50 px-2 py-1 text-xs text-red-700">
          {error}
        </p>
      )}
      {open && (
        <div
          role="menu"
          className="absolute right-0 z-10 mt-1 w-52 overflow-hidden rounded-lg border border-slate-200 bg-white py-1 shadow-lg"
        >
          <MenuItem
            label="Classify document type"
            onClick={() =>
              void run(async () => {
                const c = await classifyDocument(docId);
                window.alert(
                  `Type: ${c.label}` +
                    (c.signals.length
                      ? ` (${Math.round(c.confidence * 100)}% — ${c.signals.join(", ")})`
                      : ""),
                );
              })
            }
          />
          <MenuItem
            label="Compress PDF"
            disabled={!isPdf}
            hint={!isPdf ? "PDF only" : undefined}
            onClick={() => run(() => compressPdf(docId))}
          />
          <MenuItem
            label="Password-protect PDF"
            disabled={!isPdf}
            onClick={() => {
              const pw = window.prompt("Set a password for the PDF:")?.trim();
              if (pw) void run(() => protectPdf(docId, pw));
            }}
          />
          <MenuItem
            label="Add watermark"
            disabled={!isPdf}
            onClick={() => {
              const text = window.prompt("Watermark text:")?.trim();
              if (text) void run(() => watermarkPdf(docId, text));
            }}
          />
          <MenuItem
            label="Save as template"
            onClick={() => {
              const name = window.prompt("Template name:")?.trim();
              if (name)
                void run(async () => {
                  await saveAsTemplate(docId, name);
                  window.alert(`Saved "${name}" — find it under “Start from a template” on the home page.`);
                });
            }}
          />
        </div>
      )}
    </div>
  );
}

function MenuItem({
  label,
  onClick,
  disabled,
  hint,
}: {
  label: string;
  onClick: () => void;
  disabled?: boolean;
  hint?: string;
}) {
  return (
    <button
      type="button"
      role="menuitem"
      disabled={disabled}
      onClick={onClick}
      className="block min-h-[44px] w-full px-3 py-2 text-left text-sm hover:bg-slate-50 disabled:opacity-40"
    >
      {label}
      {hint && <span className="ml-1 text-xs text-slate-400">({hint})</span>}
    </button>
  );
}
