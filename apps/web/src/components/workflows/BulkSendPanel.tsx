"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useState } from "react";

import { listBulkSends } from "@/lib/api";

export function BulkSendPanel({ docId }: { docId: string }) {
  const batches = useQuery({ queryKey: ["bulk-send", docId], queryFn: () => listBulkSends(docId) });
  const [copied, setCopied] = useState<string | null>(null);

  if (batches.isLoading) return null;
  const list = batches.data ?? [];
  if (list.length === 0) return null;

  const origin = typeof window !== "undefined" ? window.location.origin : "";

  async function copyLink(key: string, url: string) {
    const full = `${origin}${url}`;
    await navigator.clipboard.writeText(full);
    setCopied(key);
    setTimeout(() => setCopied(null), 2000);
  }

  return (
    <section className="border-t border-slate-200 bg-slate-50 p-4">
      <h3 className="text-sm font-semibold text-slate-900">Bulk-send portal links</h3>
      <p className="mt-1 text-xs text-slate-500">
        Each recipient gets their own packet and sign-off link — no account required.
      </p>
      <ul className="mt-3 space-y-3">
        {list.map((batch) => (
          <li key={batch.batch_id} className="rounded-lg border border-slate-200 bg-white p-3">
            <p className="text-xs font-medium text-slate-500">Batch {batch.batch_id.slice(-8)}</p>
            <ul className="mt-2 space-y-2">
              {batch.packets.map((p) => {
                const key = `${batch.batch_id}-${p.recipient}`;
                return (
                  <li key={key} className="text-sm">
                    <span className="font-medium text-slate-800">{p.recipient}</span>
                    <span className="ml-2 text-xs text-slate-500">({p.state.replace("_", " ")})</span>
                    {p.portal_url ? (
                      <div className="mt-1 flex flex-wrap items-center gap-2">
                        <Link
                          href={p.portal_url}
                          className="text-xs text-brand-600 hover:underline"
                          target="_blank"
                          rel="noopener noreferrer"
                        >
                          Open portal
                        </Link>
                        <button
                          type="button"
                          onClick={() => void copyLink(key, p.portal_url!)}
                          className="text-xs text-slate-500 hover:text-slate-800"
                        >
                          {copied === key ? "Copied!" : "Copy link"}
                        </button>
                      </div>
                    ) : (
                      <p className="mt-1 text-xs text-slate-400">Portal link unavailable</p>
                    )}
                  </li>
                );
              })}
            </ul>
          </li>
        ))}
      </ul>
    </section>
  );
}
