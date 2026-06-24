"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useState } from "react";

import { createShare, fetchBillingStatus, listShares } from "@/lib/api";

export function ShareLinkModal({ docId, onClose }: { docId: string; onClose: () => void }) {
  const queryClient = useQueryClient();
  const billing = useQuery({ queryKey: ["billing"], queryFn: fetchBillingStatus });
  const shares = useQuery({ queryKey: ["shares", docId], queryFn: () => listShares(docId) });
  const [permission, setPermission] = useState("view");
  const [createdUrl, setCreatedUrl] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const create = useMutation({
    mutationFn: () => createShare(docId, { permission }),
    onSuccess: (share) => {
      setCreatedUrl(share.portal_url);
      void queryClient.invalidateQueries({ queryKey: ["shares", docId] });
      setError(null);
    },
    onError: (e) => {
      const msg = e instanceof Error ? e.message : String(e);
      setError(msg);
      if (msg.includes("402") || msg.toLowerCase().includes("upgrade")) {
        setError("Client portal links require Pro. Upgrade on the pricing page.");
      }
    },
  });

  const origin = typeof window !== "undefined" ? window.location.origin : "";

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div className="max-h-[90vh] w-full max-w-lg overflow-auto rounded-xl bg-white p-6 shadow-xl">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold text-slate-900">Share client portal link</h2>
          <button type="button" onClick={onClose} className="text-slate-400 hover:text-slate-700">
            Close
          </button>
        </div>
        <p className="mt-2 text-sm text-slate-600">
          Send a read-only link your client can open without an account. Your plan:{" "}
          <strong>{billing.data?.plan ?? "free"}</strong>.
        </p>
        {billing.data?.plan === "free" && (
          <p className="mt-2 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-800">
            Portal links are a Pro feature.{" "}
            <Link href="/pricing" className="font-medium underline">
              View pricing
            </Link>
          </p>
        )}
        <label className="mt-4 block text-xs font-medium uppercase text-slate-500">Permission</label>
        <select
          value={permission}
          onChange={(e) => setPermission(e.target.value)}
          className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
        >
          <option value="view">View only</option>
          <option value="comment">View + comment</option>
          <option value="sign">View + sign off</option>
        </select>
        <button
          type="button"
          onClick={() => create.mutate()}
          disabled={create.isPending || billing.data?.plan === "free"}
          className="mt-4 w-full rounded-lg bg-brand-600 py-2.5 text-sm font-medium text-white hover:bg-brand-500 disabled:opacity-50"
        >
          {create.isPending ? "Creating…" : billing.data?.plan === "free" ? "Upgrade to create links" : "Create link"}
        </button>
        {createdUrl && (
          <div className="mt-4 rounded-lg border border-green-200 bg-green-50 p-3 text-sm">
            <p className="font-medium text-green-800">Link ready</p>
            <code className="mt-1 block break-all text-xs text-green-900">
              {origin}
              {createdUrl}
            </code>
          </div>
        )}
        {error && (
          <p role="alert" className="mt-3 text-sm text-red-600">
            {error}
          </p>
        )}
        {shares.data && shares.data.shares.length > 0 && (
          <ul className="mt-4 space-y-2 border-t border-slate-100 pt-4 text-xs text-slate-600">
            {shares.data.shares.map((s) => (
              <li key={s.id}>
                {s.permission} · {origin}
                {s.portal_url}
                {s.revoked ? " (revoked)" : ""}
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
