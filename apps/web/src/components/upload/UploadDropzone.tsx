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
  | { kind: "uploading"; name: string }
  | { kind: "error"; message: string };

export function UploadDropzone() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const inputRef = useRef<HTMLInputElement>(null);
  const [status, setStatus] = useState<Status>({ kind: "idle" });
  const [dragActive, setDragActive] = useState(false);

  const busy = status.kind === "uploading";

  async function handleFile(file: File) {
    const problem = validateFile(file);
    if (problem) {
      setStatus({ kind: "error", message: problem });
      return;
    }
    setStatus({ kind: "uploading", name: file.name });
    try {
      const res = await uploadDocument(file);
      // Refresh the recent-documents shelf before navigating into the new doc.
      void queryClient.invalidateQueries({ queryKey: ["documents"] });
      router.push(`/documents/${res.doc_id}`);
    } catch (e) {
      setStatus({ kind: "error", message: friendlyUploadError(e) });
    }
  }

  return (
    <div className="space-y-2">
      <div
        role="button"
        tabIndex={0}
        aria-label="Upload a document"
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
          const file = e.dataTransfer.files?.[0];
          if (file) void handleFile(file);
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

        {busy ? (
          <>
            <p className="text-lg font-medium text-slate-800">Opening “{status.name}”…</p>
            <p className="text-sm text-slate-500">Parsing into the canonical model.</p>
          </>
        ) : (
          <>
            <p className="text-lg font-medium text-slate-800">
              Drag a document here, or{" "}
              <span className="text-blue-600 underline underline-offset-2">browse your files</span>
            </p>
            <p className="text-sm text-slate-500">
              {supportedSummary()} · up to {MAX_UPLOAD_MB} MB
            </p>
          </>
        )}

        <input
          ref={inputRef}
          type="file"
          accept={ACCEPT_ATTR}
          className="hidden"
          onChange={(e) => {
            const file = e.target.files?.[0];
            // Reset so picking the same file again still fires onChange.
            e.target.value = "";
            if (file) void handleFile(file);
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
    </div>
  );
}
