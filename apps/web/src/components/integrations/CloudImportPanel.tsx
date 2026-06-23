"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Cloud } from "lucide-react";

import {
  connectIntegration,
  disconnectIntegration,
  listIntegrations,
  type Integration,
} from "@/lib/api";

/**
 * Cloud-storage connections. Honest by design: a provider shows "Connect" only when this deployment
 * has its OAuth client credentials configured; otherwise it's "Not configured". Connecting runs the
 * real OAuth handshake; imported files go through the same validation/scan/ingest pipeline as uploads.
 */
export function CloudImportPanel({ className = "" }: { className?: string }) {
  const queryClient = useQueryClient();
  const integrations = useQuery({ queryKey: ["integrations"], queryFn: listIntegrations });

  const connect = useMutation({ mutationFn: connectIntegration });
  const disconnect = useMutation({
    mutationFn: disconnectIntegration,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["integrations"] }),
  });

  if (!integrations.data) return null;

  const row = (i: Integration) => {
    if (i.connected) {
      return (
        <button
          type="button"
          onClick={() => disconnect.mutate(i.name)}
          className="text-xs font-medium text-emerald-700 hover:text-red-600"
        >
          Connected · Disconnect
        </button>
      );
    }
    if (i.configured) {
      return (
        <button
          type="button"
          onClick={() => connect.mutate(i.name)}
          className="btn-secondary px-2.5 py-1 text-xs"
        >
          Connect
        </button>
      );
    }
    return <span className="text-xs text-slate-400">Not configured</span>;
  };

  return (
    <div className={`rounded-2xl border border-slate-200 bg-white p-5 ${className}`}>
      <div className="flex items-center gap-2">
        <Cloud className="h-5 w-5 text-trust-700" />
        <h2 className="text-sm font-semibold text-slate-900">Cloud storage</h2>
      </div>
      <p className="mt-1 text-xs text-slate-500">
        Connect a cloud account to import documents. Files run through the same validation and
        privacy pipeline as direct uploads.
      </p>
      <ul className="mt-3 space-y-2">
        {integrations.data.map((i) => (
          <li key={i.name} className="flex items-center justify-between gap-3 text-sm">
            <span className="text-slate-700">{i.label}</span>
            {row(i)}
          </li>
        ))}
      </ul>
    </div>
  );
}
