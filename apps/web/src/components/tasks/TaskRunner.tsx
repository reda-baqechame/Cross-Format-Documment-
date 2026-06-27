"use client";

import { useQuery } from "@tanstack/react-query";
import {
  CheckCircle2,
  FileCheck2,
  FileUp,
  Loader2,
  Paperclip,
  TriangleAlert,
  X,
  XCircle,
} from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { FreeBadge } from "@/components/marketing/FreeBadge";
import { fetchBackendHealth, resolveUploadDocId, uploadDocument } from "@/lib/api";
import { getTask, type TaskResult } from "@/lib/tasks";
import { friendlyApiError, friendlyUploadError, validateFile } from "@/lib/upload";

type Phase =
  | { kind: "pick" }
  | { kind: "uploading"; name: string }
  | { kind: "ready" }
  | { kind: "running" }
  | { kind: "error"; message: string }
  | { kind: "result"; result: TaskResult };

interface Uploaded {
  docId: string;
  name: string;
}

export function TaskRunner({ slug }: { slug: string }) {
  const task = getTask(slug);
  const router = useRouter();
  const [files, setFiles] = useState<Uploaded[]>([]);
  const [options, setOptions] = useState<Record<string, string>>(
    Object.fromEntries((task?.options ?? []).map((option) => [option.name, option.default ?? ""])),
  );
  const [phase, setPhase] = useState<Phase>({ kind: "pick" });

  const health = useQuery({ queryKey: ["health"], queryFn: fetchBackendHealth, retry: false });

  if (!task) return null;

  const aiBlocked = !!task.needsAI && health.data?.ai_enabled === false;
  const minFiles = task.minFiles ?? 1;
  const enoughFiles = files.length >= minFiles;
  const busy = phase.kind === "uploading" || phase.kind === "running";

  const addFiles = async (picked: File[]) => {
    if (picked.length === 0) return;
    const toUpload = task.multiple ? picked : picked.slice(0, 1);
    const next = [...files];
    for (const file of toUpload) {
      const problem = validateFile(file);
      if (problem) {
        setPhase({ kind: "error", message: `${file.name}: ${problem}` });
        return;
      }
      setPhase({ kind: "uploading", name: file.name });
      try {
        const res = await uploadDocument(file);
        const docId = await resolveUploadDocId(res); // immediate (sync) or polls the job (async)
        next.push({ docId, name: file.name });
      } catch (error) {
        setPhase({ kind: "error", message: friendlyUploadError(error) });
        return;
      }
    }
    setFiles(task.multiple ? next : next.slice(-1));
    setPhase({ kind: "ready" });
  };

  const run = async () => {
    if (!enoughFiles || aiBlocked) return;
    setPhase({ kind: "running" });
    try {
      const result = await task.run({ docIds: files.map((file) => file.docId), options });
      if (result.kind === "navigate") {
        router.push(result.href);
        return;
      }
      setPhase({ kind: "result", result });
    } catch (error) {
      setPhase({ kind: "error", message: friendlyApiError(error, "That did not work.") });
    }
  };

  const reset = () => {
    setFiles([]);
    setPhase({ kind: "pick" });
  };

  return (
    <div className="mx-auto max-w-2xl space-y-5">
      <header className="text-center">
        <div
          className="mx-auto mb-2 flex h-14 w-14 items-center justify-center rounded-2xl bg-brand-50 text-brand-700 ring-1 ring-brand-100"
          aria-hidden
        >
          <FileCheck2 className="h-7 w-7" />
        </div>
        <h1 className="text-2xl font-semibold tracking-tight text-ink">{task.title}</h1>
        <p className="mt-1 text-sm text-slate-600">{task.blurb}</p>
        <FreeBadge className="mt-3 justify-center" />
      </header>

      {aiBlocked && (
        <div className="rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
          <p className="font-medium">AI is not connected yet</p>
          <p className="mt-1">
            This task needs an AI provider. Set <code>LLM_PROVIDER=anthropic</code> and{" "}
            <code>ANTHROPIC_API_KEY</code> in your deployment, then reload.
          </p>
        </div>
      )}

      <FilePicker
        accept={task.accept}
        acceptLabel={task.acceptLabel}
        multiple={!!task.multiple}
        files={files}
        busy={busy}
        uploadingName={phase.kind === "uploading" ? phase.name : null}
        onPick={addFiles}
        onRemove={(index) => setFiles(files.filter((_, idx) => idx !== index))}
        disabled={aiBlocked}
      />

      {enoughFiles && (task.options?.length ?? 0) > 0 && (
        <div className="space-y-3 rounded-xl border border-slate-200 bg-white p-4">
          {task.options!.map((option) => (
            <label key={option.name} className="block">
              <span className="mb-1 block text-sm font-medium text-slate-700">{option.label}</span>
              {option.type === "select" ? (
                <select
                  value={options[option.name] ?? ""}
                  onChange={(event) =>
                    setOptions({ ...options, [option.name]: event.target.value })
                  }
                  className="studio-input"
                >
                  {option.choices?.map((choice) => (
                    <option key={choice.value} value={choice.value}>
                      {choice.label}
                    </option>
                  ))}
                </select>
              ) : (
                <input
                  type={option.type === "password" ? "password" : "text"}
                  value={options[option.name] ?? ""}
                  placeholder={option.placeholder}
                  onChange={(event) =>
                    setOptions({ ...options, [option.name]: event.target.value })
                  }
                  className="studio-input"
                />
              )}
              {option.help && <span className="mt-1 block text-xs text-slate-400">{option.help}</span>}
            </label>
          ))}
        </div>
      )}

      {phase.kind !== "result" && (
        <button
          type="button"
          onClick={() => void run()}
          disabled={!enoughFiles || busy || aiBlocked}
          className="min-h-[48px] w-full rounded-xl bg-brand-600 px-4 py-3 text-base font-medium text-white transition-colors hover:bg-brand-700 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {phase.kind === "running" ? "Working..." : (task.cta ?? "Run")}
        </button>
      )}

      {phase.kind === "error" && (
        <p
          role="alert"
          className="flex items-start gap-2 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700"
        >
          <TriangleAlert className="mt-0.5 h-4 w-4 shrink-0" />
          <span>{phase.message}</span>
        </p>
      )}

      {phase.kind === "result" && <ResultView result={phase.result} onAgain={reset} />}
    </div>
  );
}

function FilePicker({
  accept,
  acceptLabel,
  multiple,
  files,
  busy,
  uploadingName,
  onPick,
  onRemove,
  disabled,
}: {
  accept: string;
  acceptLabel: string;
  multiple: boolean;
  files: Uploaded[];
  busy: boolean;
  uploadingName: string | null;
  onPick: (files: File[]) => void;
  onRemove: (index: number) => void;
  disabled: boolean;
}) {
  const [dragActive, setDragActive] = useState(false);
  return (
    <div className="space-y-2">
      <label
        onDragOver={(event) => {
          event.preventDefault();
          if (!busy && !disabled) setDragActive(true);
        }}
        onDragLeave={() => setDragActive(false)}
        onDrop={(event) => {
          event.preventDefault();
          setDragActive(false);
          if (busy || disabled) return;
          const picked = Array.from(event.dataTransfer.files ?? []);
          if (picked.length) onPick(picked);
        }}
        className={[
          "flex cursor-pointer flex-col items-center justify-center gap-2 rounded-2xl border border-dashed p-8 text-center transition-colors",
          dragActive ? "border-brand-500 bg-brand-50" : "border-slate-300 bg-white hover:border-brand-400",
          busy || disabled ? "pointer-events-none opacity-60" : "",
        ].join(" ")}
      >
        <span className="text-brand-700" aria-hidden>
          {uploadingName ? <Loader2 className="h-6 w-6 animate-spin" /> : <FileUp className="h-6 w-6" />}
        </span>
        <span className="text-sm font-medium text-slate-800">
          {uploadingName
            ? `Adding "${uploadingName}"...`
            : multiple
              ? "Drop files here or click to choose"
              : "Drop a file here or click to choose"}
        </span>
        <span className="text-xs text-slate-500">Accepts {acceptLabel}</span>
        <input
          type="file"
          accept={accept}
          multiple={multiple}
          className="hidden"
          disabled={busy || disabled}
          onChange={(event) => {
            const picked = Array.from(event.target.files ?? []);
            event.target.value = "";
            if (picked.length) onPick(picked);
          }}
        />
      </label>

      {files.length > 0 && (
        <ul className="space-y-1">
          {files.map((file, index) => (
            <li
              key={`${file.docId}-${index}`}
              className="flex items-center justify-between rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm"
            >
              <span className="flex min-w-0 items-center gap-2 truncate text-slate-700">
                <Paperclip className="h-4 w-4 shrink-0 text-slate-400" />
                {file.name}
              </span>
              <button
                type="button"
                onClick={() => onRemove(index)}
                className="ml-2 inline-flex h-7 w-7 shrink-0 items-center justify-center rounded-md text-slate-400 hover:bg-red-50 hover:text-red-600"
                aria-label={`Remove ${file.name}`}
              >
                <X className="h-4 w-4" />
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function ResultView({ result, onAgain }: { result: TaskResult; onAgain: () => void }) {
  return (
    <div className="space-y-4 rounded-xl border border-emerald-200 bg-emerald-50/50 p-5 text-center">
      {result.kind === "downloaded" && (
        <div className="space-y-2">
          <p className="flex items-center justify-center gap-2 text-lg font-medium text-emerald-800">
            <CheckCircle2 className="h-5 w-5" />
            Done. Your download has started.
          </p>
          {result.validation && (
            <p
              className={
                result.validation.status === "fail"
                  ? "flex items-center justify-center gap-2 text-sm font-medium text-red-700"
                  : result.validation.status === "warn"
                    ? "flex items-center justify-center gap-2 text-sm font-medium text-amber-700"
                    : "flex items-center justify-center gap-2 text-sm font-medium text-emerald-700"
              }
            >
              {result.validation.status === "fail" ? (
                <XCircle className="h-4 w-4" />
              ) : result.validation.status === "warn" ? (
                <TriangleAlert className="h-4 w-4" />
              ) : (
                <CheckCircle2 className="h-4 w-4" />
              )}
              Output verified: {result.validation.summary}
            </p>
          )}
        </div>
      )}
      {result.kind === "text" && (
        <div className="space-y-2 text-left">
          <p className="font-semibold text-ink">{result.title}</p>
          <p className="whitespace-pre-wrap text-sm leading-relaxed text-slate-700">{result.body}</p>
          {result.citations && result.citations.length > 0 && (
            <div className="mt-2 space-y-1 border-t border-emerald-200 pt-2">
              <p className="text-xs font-medium uppercase tracking-wide text-slate-500">Sources</p>
              {result.citations.map((citation, index) => (
                <p key={index} className="text-xs italic text-slate-500">
                  &quot;{citation}&quot;
                </p>
              ))}
            </div>
          )}
        </div>
      )}
      {result.kind === "list" && (
        <div className="space-y-1 text-left">
          <p className="font-semibold text-ink">{result.title}</p>
          <ul className="list-inside list-disc text-sm text-slate-700">
            {result.items.map((item, index) => (
              <li key={index}>{item}</li>
            ))}
          </ul>
        </div>
      )}
      <button type="button" onClick={onAgain} className="studio-btn">
        Do another
      </button>
    </div>
  );
}
