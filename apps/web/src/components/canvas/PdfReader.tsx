"use client";

import { useEffect, useRef, useState } from "react";

import { exportUrl } from "@/lib/api";

/**
 * Crisp client-side PDF reader (PDF.js, Apache-2.0). Renders each page to a vector canvas with a
 * selectable text layer for in-browser reading/search — sharper than the server raster preview and
 * with real text selection. Read-only by design: editing/redaction stays in the editable overlay
 * (`NodeRenderer`). Loaded client-only (`next/dynamic` `ssr:false`); the worker is bundled via a
 * module URL so there's no CDN dependency. Fed the redaction-applied PDF bytes from `?format=pdf`,
 * so redactions are honored in the reader too.
 */

const MAX_PAGES = 30; // guardrail for very large PDFs
const SCALE = 1.3;

export default function PdfReader({ docId }: { docId: string }) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [status, setStatus] = useState<"loading" | "ready" | "error">("loading");
  const [pageCount, setPageCount] = useState(0);

  useEffect(() => {
    let cancelled = false;
    const container = containerRef.current;

    (async () => {
      try {
        const pdfjs = await import("pdfjs-dist");
        // Worker is served from /public (copied at pre(build|dev) time) rather than bundled —
        // Terser can't minify the prebuilt .mjs worker, which breaks `next build`.
        pdfjs.GlobalWorkerOptions.workerSrc = "/pdf.worker.min.mjs";

        const res = await fetch(exportUrl(docId, "pdf"));
        if (!res.ok) throw new Error(`failed to load PDF (${res.status})`);
        const data = await res.arrayBuffer();
        if (cancelled || !container) return;

        const pdf = await pdfjs.getDocument({ data }).promise;
        if (cancelled || !container) return;
        container.innerHTML = "";
        const total = Math.min(pdf.numPages, MAX_PAGES);
        setPageCount(pdf.numPages);

        for (let p = 1; p <= total; p++) {
          const page = await pdf.getPage(p);
          if (cancelled) return;
          const viewport = page.getViewport({ scale: SCALE });

          const pageEl = document.createElement("div");
          pageEl.className = "relative mx-auto mb-4 bg-white shadow-sm";
          pageEl.style.width = `${viewport.width}px`;
          pageEl.style.height = `${viewport.height}px`;

          const canvas = document.createElement("canvas");
          canvas.width = viewport.width;
          canvas.height = viewport.height;
          const ctx = canvas.getContext("2d");
          if (!ctx) continue;
          pageEl.appendChild(canvas);
          container.appendChild(pageEl);

          await page.render({ canvasContext: ctx, viewport }).promise;

          // Best-effort selectable text layer (API differs across PDF.js majors — never fatal).
          try {
            const textContent = await page.getTextContent();
            const textLayerDiv = document.createElement("div");
            textLayerDiv.className = "textLayer";
            Object.assign(textLayerDiv.style, {
              position: "absolute",
              inset: "0",
              overflow: "hidden",
              opacity: "0.25",
              lineHeight: "1",
            });
            pageEl.appendChild(textLayerDiv);
            const TextLayer = (pdfjs as unknown as { TextLayer?: new (o: object) => { render: () => Promise<void> } })
              .TextLayer;
            if (TextLayer) {
              await new TextLayer({ textContentSource: textContent, container: textLayerDiv, viewport }).render();
            }
          } catch {
            /* text layer is optional */
          }
        }
        if (!cancelled) setStatus("ready");
      } catch (e) {
        console.error("[PdfReader]", e);
        if (!cancelled) setStatus("error");
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [docId]);

  return (
    <div className="mx-auto w-full max-w-[1000px]">
      {status === "loading" && <p className="p-6 text-sm text-slate-500">Rendering PDF…</p>}
      {status === "error" && (
        <p className="p-6 text-sm text-red-600">Could not render this PDF in the reader.</p>
      )}
      {status === "ready" && pageCount > MAX_PAGES && (
        <p className="mb-3 text-xs text-slate-500">
          Showing the first {MAX_PAGES} of {pageCount} pages.
        </p>
      )}
      <div ref={containerRef} data-testid="pdf-reader" />
    </div>
  );
}
