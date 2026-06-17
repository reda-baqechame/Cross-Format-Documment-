"use client";

import { useQueryClient } from "@tanstack/react-query";
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

  async function handleFiles(files: File[]) {
    if (files.length === 0) return;

    // Single file: validate up front and jump straight into the document.
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

    // Bulk: upload sequentially, collect failures, stay on the home shelf.
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
          "flex cursor-pointer flex-col items-center justify-center gap-3 rounded-2xl border-2 border-dashed p-12 text-center transition-colors",
          dragActive
            ? "border-blue-500 bg-blue-50"
            : "border-slate-300 bg-white hover:border-slate-400 hover:bg-slate-50",
          busy ? "pointer-events-none opacity-80" : "",
        ].join(" ")}
      >
        <div className="flex h-12 w-12 items-center justify-center rounded-full bg-blue-100 text-2xl">
          {busy ? "⏳" : "📄"}
        </div>

        {status.kind === "uploading" ? (
          <>
            <p className="text-lg font-medium text-slate-800">
              {status.total > 1
                ? `Uploading ${status.done + 1} of ${status.total}…`
                : `Opening “${status.name}”…`}
            </p>
            <p className="text-sm text-slate-500">Parsing into the canonical model.</p>
          </>
        ) : (
          <>
            <p className="text-lg font-medium text-slate-800">
              Drag documents here, or{" "}
              <span className="text-blue-600 underline underline-offset-2">browse your files</span>
            </p>
            <p className="text-sm text-slate-500">
              {supportedSummary()} · up to {MAX_UPLOAD_MB} MB · multiple files OK
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
            e.target.value = ""; // allow re-picking the same file(s)
            if (files.length) void handleFiles(files);
          }}
        />
      </div>

      {status.kind === "error" && (
        <p
          role="alert"
          className="flex items-start gap-2 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700"
        >
          <span aria-hidden>⚠️</span>
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
            {status.failures.length > 0 && ` · ${status.failures.length} failed`}.
          </p>
          {status.failures.map((f) => (
            <p key={f} className="flex items-start gap-2 text-red-700">
              <span aria-hidden>⚠️</span>
              <span>{f}</span>
            </p>
          ))}
        </div>
      )}
    </div>
  );
}
