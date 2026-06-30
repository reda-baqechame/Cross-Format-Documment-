"use client";

import { useState } from "react";
import Link from "next/link";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  addPacketDocuments,
  getPacketReport,
  listDocuments,
  type Packet,
} from "@/lib/api";
import type { DocumentListResponse } from "@docos/shared-types";
import { AppShell } from "@/components/layout/AppShell";
import { PacketWorkspace } from "@/components/packets/PacketWorkspace";
import { useToast } from "@/components/ui/Toast";

export default function PacketDetailPage({ params }: { params: { id: string } }) {
  const packetId = params.id;
  const qc = useQueryClient();
  const toast = useToast();
  const [selected, setSelected] = useState<Set<string>>(new Set());

  // The packet itself (cached from the list page).
  const packet = useQuery<Packet | undefined>({
    queryKey: ["packets"],
    queryFn: async () => {
      const { listPackets } = await import("@/lib/api");
      const all = await listPackets();
      return all.find((p) => p.id === packetId);
    },
  });

  // Library documents available to add.
  const library = useQuery<DocumentListResponse>({
    queryKey: ["documents"],
    queryFn: listDocuments,
  });

  // Whether an audit run exists (to know whether to show the "add documents" panel).
  const report = useQuery({
    queryKey: ["packet-report", packetId],
    queryFn: () => getPacketReport(packetId),
    retry: false,
  });

  const addDocs = useMutation({
    mutationFn: () => addPacketDocuments(packetId, Array.from(selected)),
    onSuccess: () => {
      toast.success("Documents added.");
      setSelected(new Set());
      qc.invalidateQueries({ queryKey: ["packets"] });
    },
    onError: (e: unknown) =>
      toast.error(e instanceof Error ? e.message : "Could not add documents"),
  });

  const current = packet.data;
  const alreadyInPacket = new Set(current?.document_ids ?? []);
  const addable = library.data?.documents.filter((d) => !alreadyInPacket.has(d.doc_id)) ?? [];

  function toggle(docId: string) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(docId)) next.delete(docId);
      else next.add(docId);
      return next;
    });
  }

  return (
    <AppShell subtitle="Command Center — packet audit">
      <main className="mx-auto max-w-6xl px-4 py-8 sm:px-6">
        <div className="mb-4 flex items-center gap-3">
          <Link href="/packets" className="text-sm text-slate-500 hover:text-slate-800">
            ← All packets
          </Link>
          <h1 className="text-lg font-semibold text-ink">
            {current?.name ?? "Packet"}
          </h1>
          {current && (
            <span className="rounded-full bg-chrome px-2 py-0.5 text-[10px] text-slate-600">
              {current.pack}
            </span>
          )}
        </div>

        <div className="grid gap-6 lg:grid-cols-[1fr_320px]">
          {/* Audit workspace */}
          <div>
            <PacketWorkspace packetId={packetId} />
          </div>

          {/* Document management rail */}
          <aside className="space-y-4">
            <section className="card p-4">
              <h3 className="text-sm font-semibold text-ink">In this packet</h3>
              <ul className="mt-2 space-y-1">
                {current?.document_ids.map((id) => (
                  <li key={id} className="text-xs text-slate-600">
                    • {id}
                  </li>
                ))}
                {current && current.document_ids.length === 0 && (
                  <li className="text-xs text-slate-500">No documents yet.</li>
                )}
              </ul>
            </section>

            {addable.length > 0 && (
              <section className="card p-4">
                <h3 className="text-sm font-semibold text-ink">Add documents</h3>
                <p className="mt-1 text-[11px] text-slate-500">
                  Select from your library. The audit runs across all packet documents at once.
                </p>
                <ul className="mt-2 max-h-72 space-y-1 overflow-auto">
                  {addable.map((d) => (
                    <li key={d.doc_id}>
                      <label className="flex items-center gap-2 rounded px-2 py-1 text-xs hover:bg-chrome">
                        <input
                          type="checkbox"
                          checked={selected.has(d.doc_id)}
                          onChange={() => toggle(d.doc_id)}
                        />
                        <span className="truncate text-slate-700">
                          {d.title ?? d.doc_id}
                        </span>
                        <span className="ml-auto text-[10px] text-slate-400">
                          {d.source_format}
                        </span>
                      </label>
                    </li>
                  ))}
                </ul>
                <button
                  className="btn-secondary mt-3 w-full"
                  onClick={() => addDocs.mutate()}
                  disabled={selected.size === 0 || addDocs.isPending}
                >
                  {addDocs.isPending
                    ? "Adding…"
                    : `Add ${selected.size || ""} document${selected.size === 1 ? "" : "s"}`}
                </button>
              </section>
            )}
          </aside>
        </div>
      </main>
    </AppShell>
  );
}
