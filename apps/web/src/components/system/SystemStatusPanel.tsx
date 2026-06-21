"use client";

import { useQuery } from "@tanstack/react-query";

import { fetchBackendHealth, type BackendHealth } from "@/lib/api";

type Tone = "ok" | "muted" | "warn";

interface Row {
  label: string;
  value: string;
  tone: Tone;
}

function rows(h: BackendHealth): Row[] {
  return [
    {
      label: "AI provider",
      value: h.ai_enabled ? `Connected · ${h.llm_provider}` : "Not connected",
      tone: h.ai_enabled ? "ok" : "muted",
    },
    {
      label: "Office native editor",
      value: h.office_editor ? "Connected" : "Structured editing only",
      tone: h.office_editor ? "ok" : "muted",
    },
    {
      label: "PDF native editor",
      value: h.pdf_editor ? "Connected" : "Structured editing only",
      tone: h.pdf_editor ? "ok" : "muted",
    },
    {
      label: "Storage",
      value: h.blob_backend === "s3" ? "Object storage (S3)" : "Local disk",
      tone: h.blob_backend === "s3" ? "ok" : "warn",
    },
    {
      label: "Database",
      value: h.database === "postgres" ? "Postgres" : "SQLite (ephemeral without a volume)",
      tone: h.database === "postgres" ? "ok" : "warn",
    },
  ];
}

const DOT: Record<Tone, string> = {
  ok: "bg-emerald-500",
  warn: "bg-amber-500",
  muted: "bg-slate-300",
};

/**
 * Honest, at-a-glance view of what is actually wired up — AI, native editors, storage, and
 * database — so the UI never implies capabilities the deployment doesn't have. Reads the same
 * `/health` summary the rest of the app uses.
 */
export function SystemStatusPanel({ className = "" }: { className?: string }) {
  const health = useQuery({ queryKey: ["health"], queryFn: fetchBackendHealth, retry: false });
  if (!health.data) return null;

  return (
    <div className={className}>
      <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-500">System status</h3>
      <dl className="mt-2 space-y-1.5">
        {rows(health.data).map((row) => (
          <div key={row.label} className="flex items-center justify-between gap-3 text-sm">
            <dt className="text-slate-600">{row.label}</dt>
            <dd className="flex items-center gap-1.5 text-slate-700">
              <span className={`h-2 w-2 shrink-0 rounded-full ${DOT[row.tone]}`} aria-hidden />
              {row.value}
            </dd>
          </div>
        ))}
      </dl>
    </div>
  );
}
