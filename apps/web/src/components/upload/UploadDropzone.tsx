"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { uploadDocument } from "@/lib/api";

export function UploadDropzone() {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleFile(file: File) {
    setBusy(true);
    setError(null);
    try {
      const res = await uploadDocument(file);
      router.push(`/documents/${res.doc_id}`);
    } catch (e) {
      setError(e instanceof Error ? e.message : "upload failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div
      onDragOver={(e) => e.preventDefault()}
      onDrop={(e) => {
        e.preventDefault();
        const file = e.dataTransfer.files?.[0];
        if (file) void handleFile(file);
      }}
      className="flex flex-col items-center justify-center gap-3 rounded-xl border-2 border-dashed border-slate-300 bg-white p-12 text-center"
    >
      <p className="text-lg font-medium">Drop a document to open it</p>
      <p className="text-sm text-slate-500">
        TXT, DOCX, PDF, XLSX, PPTX, RTF, and images are parsed into the canonical model.
      </p>
      <label className="mt-2 cursor-pointer rounded-md bg-ink px-4 py-2 text-sm font-medium text-white">
        {busy ? "Uploading…" : "Choose file"}
        <input
          type="file"
          className="hidden"
          onChange={(e) => {
            const file = e.target.files?.[0];
            if (file) void handleFile(file);
          }}
        />
      </label>
      {error && <p className="text-sm text-red-600">{error}</p>}
    </div>
  );
}
