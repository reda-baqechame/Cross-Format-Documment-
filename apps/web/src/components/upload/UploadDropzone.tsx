"use client";

import { useQueryClient } from "@tanstack/react-query";
import { FileUp, Loader2, Sparkles, TriangleAlert } from "lucide-react";
import { useRouter } from "next/navigation";
import { useRef, useState } from "react";

import { uploadDocument } from "@/lib/api";
import {
  ACCEPT_ATTR,
  friendlyUploadError,
  MAX_UPLOAD_MB,
  supportedSummary,
  validateFile,
} from "@/lib/upload";

type Status =
  | { kind: "idle" }
  | { kind: "uploading"; done: number; total: number; name: string }
  | { kind: "error"; message: string }
  | { kind: "done"; ok: number; failures: string[] };

export function UploadDropzone() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const inputRef = useRef<HTMLInputElement>(null);
  const [status, setStatus] = useState<Status>({ kind: "idle" });
  const [dragActive, setDragActive] = useState(false);

  const busy = status.kind === "uploading";

  function trySample() {
    if (busy) return;
    const sample = `MUTUAL SERVICES AGREEMENT

This Agreement is made on June 1, 2026 between Northwind Traders, Inc. ("Client")
and Acme Consulting LLC ("Provider").

1. Services. Provider will deliver advisory services described in Exhibit A.

2. Fees. Client agrees to pay Provider $12,500 per month, due net 30.
   Contact: billing@northwind.example  ·  +1 (415) 555-0147

3. Term. This Agreement begins on June 1, 2026 and continues for 12 months.

4. Confidentiality. Each party will protect the other's confidential information.

Signature: ______________________    Date: ____________
`;
    const file = new File([sample], "sample-services-agreement.txt", { type: "text/plain" });
    void handleFiles([file]);
  }

  async function handleFiles(files: File[]) {
    if (files.length === 0) return;

    if (files.length === 1) {
      const file = files[0];
      const problem = validateFile(file);
      if (problem) {
        setStatus({ kind: "error", message: problem });
        return;
      }
      setStatus({ kind: "uploading", done: 0, total: 1, name: file.name });
      try {
        const res = await uploadDocument(file);
        void queryClient.invalidateQueries({ queryKey: ["documents"] });
        router.push(`/documents/${res.doc_id}`);
      } catch (e) {
        setStatus({ kind: "error", message: friendlyUploadError(e) });
      }
      return;
    }

    const failures: string[] = [];
    let ok = 0;
    for (let i = 0; i < files.length; i++) {
      const file = files[i];
      setStatus({ kind: "uploading", done: i, total: files.length, name: file.name });
      const problem = validateFile(file);
      if (problem) {
        failures.push(`${file.name}: ${problem}`);
        continue;
      }
      try {
        await uploadDocument(file);
        ok += 1;
      } catch (e) {
        failures.push(`${file.name}: ${friendlyUploadError(e)}`);
      }
    }
    void queryClient.invalidateQueries({ queryKey: ["documents"] });
    setStatus({ kind: "done", ok, failures });
  }

  return (
    <div className="space-y-2">
      <div
        role="button"
        tabIndex={0}
        aria-label="Upload one or more documents"
        aria-busy={busy}
        onClick={() => !busy && inputRef.current?.click()}
        onKeyDown={(e) => {
          if ((e.key === "Enter" || e.key === " ") && !busy) {
            e.preventDefault();
            inputRef.current?.click();
          }
        }}
        onDragOver={(e) => {
          e.preventDefault();
          if (!busy) setDragActive(true);
        }}
        onDragLeave={() => setDragActive(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDragActive(false);
          if (busy) return;
          const files = Array.from(e.dataTransfer.files ?? []);
          if (files.length) void handleFiles(files);
        }}
        className={[
          "flex cursor-pointer flex-col items-center justify-center gap-3 rounded-xl border border-dashed p-8 text-center transition-colors sm:p-10",
          dragActive
            ? "border-brand-500 bg-brand-50"
            : "border-slate-300 bg-white hover:border-brand-400 hover:bg-brand-50/30",
          busy ? "pointer-events-none opacity-80" : "",
        ].join(" ")}
      >
        <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-brand-50 text-brand-700 ring-1 ring-brand-100">
          {busy ? <Loader2 className="h-5 w-5 animate-spin" /> : <FileUp className="h-6 w-6" />}
        </div>

        {status.kind === "uploading" ? (
          <>
            <p className="text-lg font-medium text-slate-800">
              {status.total > 1
                ? `Uploading ${status.done + 1} of ${status.total}...`
                : `Opening "${status.name}"...`}
            </p>
            <p className="text-sm text-slate-500">Reading your document...</p>
          </>
        ) : (
          <>
            <p className="text-lg font-medium text-slate-800">
              <span className="sm:hidden">Tap to choose a file</span>
              <span className="hidden sm:inline">
                Drop files here or{" "}
                <span className="text-brand-600 underline underline-offset-2">
                  browse your files
                </span>
              </span>
            </p>
            <p className="text-sm text-slate-500">
              {supportedSummary()} - up to {MAX_UPLOAD_MB} MB
            </p>
            <p className="hidden text-xs text-slate-400 sm:block">
              Single files open immediately. Multiple files stay in your library.
            </p>
          </>
        )}

        <input
          ref={inputRef}
          type="file"
          multiple
          accept={ACCEPT_ATTR}
          className="hidden"
          onChange={(e) => {
            const files = Array.from(e.target.files ?? []);
            e.target.value = "";
            if (files.length) void handleFiles(files);
          }}
        />
      </div>

      {status.kind !== "uploading" && (
        <button
          type="button"
          onClick={trySample}
          className="inline-flex items-center gap-1.5 text-sm font-medium text-brand-700 transition-colors hover:text-brand-800"
        >
          <Sparkles className="h-4 w-4" aria-hidden />
          No file handy? Try a sample document
        </button>
      )}

      {status.kind === "error" && (
        <p
          role="alert"
          className="flex items-start gap-2 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700"
        >
          <TriangleAlert className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
          <span>{status.message}</span>
        </p>
      )}

      {status.kind === "done" && (
        <div
          role="status"
          className="space-y-1 rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm"
        >
          <p className="font-medium text-slate-700">
            Added {status.ok} document{status.ok === 1 ? "" : "s"}
            {status.failures.length > 0 && ` - ${status.failures.length} failed`}.
          </p>
          {status.failures.map((f) => (
            <p key={f} className="flex items-start gap-2 text-red-700">
              <TriangleAlert className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
              <span>{f}</span>
            </p>
          ))}
        </div>
      )}
    </div>
  );
}
