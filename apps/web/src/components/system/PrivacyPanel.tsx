"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { fetchBackendHealth, purgeDocuments } from "@/lib/api";

/**
 * Private Mode — an honest statement of where files live plus a one-click purge. Copy is keyed off
 * the real backend health so it never overclaims: when AI is off, nothing is sent to a third party;
 * we never claim auto-deletion (there is no TTL), only on-demand "delete all now".
 */
export function PrivacyPanel({ className = "" }: { className?: string }) {
  const queryClient = useQueryClient();
  const health = useQuery({ queryKey: ["health"], queryFn: fetchBackendHealth, retry: false });
  const purge = useMutation({
    mutationFn: purgeDocuments,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["documents"] }),
  });

  const aiOff = health.data ? !health.data.ai_enabled : true;

  return (
    <div className={className}>
      <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-500">Private mode</h3>
      <ul className="mt-2 space-y-1.5 text-sm text-slate-600">
        <li className="flex items-start gap-1.5">
          <span className="mt-1.5 h-2 w-2 shrink-0 rounded-full bg-emerald-500" aria-hidden />
          Documents are private to this browser session — no one else can list or open them.
        </li>
        <li className="flex items-start gap-1.5">
          <span className="mt-1.5 h-2 w-2 shrink-0 rounded-full bg-emerald-500" aria-hidden />
          {aiOff
            ? "AI is off: nothing in your files is sent to any third-party service."
            : `AI is on (${health.data?.llm_provider}): only text you ask AI to process is sent.`}
        </li>
        <li className="flex items-start gap-1.5">
          <span className="mt-1.5 h-2 w-2 shrink-0 rounded-full bg-slate-300" aria-hidden />
          Files stay until you delete them — we don&apos;t mine or sell them.
        </li>
      </ul>
      <button
        type="button"
        onClick={() => {
          if (window.confirm("Delete ALL documents in this session? This cannot be undone."))
            purge.mutate();
        }}
        disabled={purge.isPending}
        className="mt-3 min-h-[36px] rounded-lg border border-red-200 px-3 text-sm font-medium text-red-700 hover:bg-red-50 disabled:opacity-40"
      >
        {purge.isPending ? "Deleting…" : "Delete all my documents now"}
      </button>
      {purge.data && (
        <p className="mt-2 text-xs text-emerald-700">Deleted {purge.data.deleted} document(s).</p>
      )}
      {purge.isError && (
        <p role="alert" className="mt-2 text-xs text-red-600">
          Couldn&apos;t delete — please try again.
        </p>
      )}
    </div>
  );
}
