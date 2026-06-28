"use client";

import { useQuery } from "@tanstack/react-query";

import { fetchBackendHealth, fetchCapabilities, type BackendHealth } from "@/lib/api";

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
    {
      label: "E-signature",
      value: h.esign_configured ? "Provider connected" : "Integrity seal only (not legally binding)",
      tone: h.esign_configured ? "ok" : "muted",
    },
    {
      label: "Cloud IDP",
      value: h.idp_configured ? "Connected" : "Local OCR + extraction",
      tone: h.idp_configured ? "ok" : "muted",
    },
    {
      label: "Handwriting OCR",
      value: h.handwriting_configured ? "Connected" : "Not connected",
      tone: h.handwriting_configured ? "ok" : "muted",
    },
    {
      label: "Text-to-speech",
      value: h.tts_configured ? "Connected" : "Not connected",
      tone: h.tts_configured ? "ok" : "muted",
    },
    {
      label: "DRM",
      value: h.drm_configured ? "Provider connected" : "Password protection only",
      tone: h.drm_configured ? "ok" : "muted",
    },
    {
      label: "Cloud storage",
      value:
        h.cloud_integrations && h.cloud_integrations.length > 0
          ? `Connected · ${h.cloud_integrations.join(", ")}`
          : "Not connected",
      tone: h.cloud_integrations && h.cloud_integrations.length > 0 ? "ok" : "muted",
    },
    {
      label: "Billing (Stripe)",
      value: h.billing_configured ? "Configured" : "Not configured — upgrade links offline",
      tone: h.billing_configured ? "ok" : "muted",
    },
    {
      label: "Real-time presence",
      value: h.presence_enabled === false ? "Off" : "On (single-node)",
      tone: "ok",
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
  const caps = useQuery({
    queryKey: ["capabilities"],
    queryFn: fetchCapabilities,
    retry: false,
    staleTime: 5 * 60 * 1000,
  });
  if (!health.data) return null;

  // Honest engine/licence notes surfaced only by /capabilities (not /health). Shown compactly
  // so the panel never implies a capability the deployment doesn't truly have.
  const searchCap = caps.data?.capabilities.find((c) => c.id === "search");
  const licenceRisks = caps.data?.licence_risks ?? [];

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
      {(searchCap || licenceRisks.length > 0) && (
        <div className="mt-3 space-y-1 border-t border-slate-100 pt-2 text-xs text-slate-500">
          {searchCap && searchCap.state !== "verified" && (
            <p>
              <span className="font-medium text-slate-600">Search:</span>{" "}
              {searchCap.limitations[0] ?? "Keyword ranking only."}
            </p>
          )}
          {licenceRisks.map((risk) => (
            <p key={risk.slice(0, 40)} className="text-amber-700">
              ⚠ {risk}
            </p>
          ))}
        </div>
      )}
    </div>
  );
}
