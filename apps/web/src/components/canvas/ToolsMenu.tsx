"use client";

import { useState } from "react";

import { classifyDocument, compressPdf, protectPdf, watermarkPdf } from "@/lib/api";

/**
 * Document tools — the cross-format actions (compress/protect/watermark a PDF, classify
 * the document) that competitors split across separate single-purpose apps, here in one
 * place over the canonical model.
 */
export function ToolsMenu({ docId, sourceFormat }: { docId: string; sourceFormat?: string }) {
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const isPdf = sourceFormat === "pdf";

  const run = async (fn: () => Promise<unknown>) => {
    setOpen(false);
    setBusy(true);
    try {
      await fn();
    } catch (e) {
      window.alert(String(e));
    } finally {
      setBusy(false);
    }
  };

  const classify = () =>
    run(async () => {
      const c = await classifyDocument(docId);
      window.alert(
        `Type: ${c.label}` +
          (c.signals.length ? ` (${Math.round(c.confidence * 100)}% — ${c.signals.join(", ")})` : ""),
      );
    });

  const protect = () => {
    const pw = window.prompt("Set a password for the PDF:")?.trim();
    if (pw) run(() => protectPdf(docId, pw));
  };

  const watermark = () => {
    const text = window.prompt("Watermark text:")?.trim();
    if (text) run(() => watermarkPdf(docId, text));
  };

  return (
    <div className="relative">
      <button
        onClick={() => setOpen((v) => !v)}
        disabled={busy}
        className="rounded-md border border-slate-300 px-3 py-1.5 text-sm hover:bg-slate-50 disabled:opacity-40"
      >
        {busy ? "Working…" : "Tools ▾"}
      </button>
      {open && (
        <div
          className="absolute right-0 z-10 mt-1 w-52 overflow-hidden rounded-md border border-slate-200 bg-white shadow-lg"
          onMouseLeave={() => setOpen(false)}
        >
          <Item label="Classify document" onClick={classify} />
          <Item
            label="Compress PDF"
            onClick={() => run(() => compressPdf(docId))}
            disabled={!isPdf}
          />
          <Item label="Password-protect PDF" onClick={protect} disabled={!isPdf} />
          <Item label="Watermark PDF" onClick={watermark} disabled={!isPdf} />
        </div>
      )}
    </div>
  );
}

function Item({
  label,
  onClick,
  disabled,
}: {
  label: string;
  onClick: () => void;
  disabled?: boolean;
}) {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      title={disabled ? "PDF documents only" : undefined}
      className="block w-full px-3 py-2 text-left text-sm hover:bg-slate-50 disabled:opacity-40"
    >
      {label}
    </button>
  );
}
