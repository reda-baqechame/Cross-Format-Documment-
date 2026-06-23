"use client";

import { useQuery } from "@tanstack/react-query";
import { useState } from "react";

import { presenceHeartbeat } from "@/lib/api";

/**
 * Live presence: heartbeats this view every few seconds and shows everyone currently viewing the
 * document. Single-node and dependency-free. Documents are private to their session today, so
 * "viewers" are this session's open tabs/devices; cross-person sharing + co-editing need infra.
 */
export function PresenceIndicator({ docId }: { docId: string }) {
  // A per-tab id so two tabs of the same session show as two viewers.
  const [viewerId] = useState(() =>
    typeof crypto !== "undefined" && "randomUUID" in crypto
      ? crypto.randomUUID()
      : Math.random().toString(36).slice(2),
  );

  const presence = useQuery({
    queryKey: ["presence", docId, viewerId],
    queryFn: () => presenceHeartbeat(docId, viewerId),
    refetchInterval: 5000,
    retry: false,
  });

  const viewers = presence.data?.viewers ?? [];
  if (viewers.length <= 1) return null; // nothing meaningful to show for a single view

  const shown = viewers.slice(0, 4);
  return (
    <div
      className="flex items-center gap-1.5 rounded-full border border-slate-200 bg-white px-2 py-1"
      title={`${viewers.length} active view(s)`}
    >
      <div className="flex -space-x-1.5">
        {shown.map((v) => (
          <span
            key={v.viewer_id}
            className="inline-flex h-5 w-5 items-center justify-center rounded-full text-[10px] font-semibold text-white ring-2 ring-white"
            style={{ backgroundColor: v.color }}
          >
            {(v.name || "G").charAt(0).toUpperCase()}
          </span>
        ))}
      </div>
      <span className="text-xs font-medium text-slate-600">{viewers.length} viewing</span>
    </div>
  );
}
