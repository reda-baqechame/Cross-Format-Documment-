"use client";

import { useState } from "react";
import Link from "next/link";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AppShell, Section } from "@/components/layout/AppShell";
import { createPacket, listPackets, PACKET_PACKS, type Packet } from "@/lib/api";
import { useToast } from "@/components/ui/Toast";
import { toneFor } from "@/components/packets/tone";

export default function PacketsPage() {
  const qc = useQueryClient();
  const toast = useToast();
  const [name, setName] = useState("");
  const [pack, setPack] = useState<string>(PACKET_PACKS[0].id);

  const packets = useQuery({ queryKey: ["packets"], queryFn: listPackets });

  const create = useMutation({
    mutationFn: () => createPacket(name.trim() || "Untitled packet", pack),
    onSuccess: (p: Packet) => {
      toast.success("Packet created — add documents and run the audit.");
      qc.invalidateQueries({ queryKey: ["packets"] });
      setName("");
      // Navigate to the new packet's workspace.
      window.location.href = `/packets/${p.id}`;
    },
    onError: (e: unknown) => toast.error(e instanceof Error ? e.message : "Could not create packet"),
  });

  return (
    <AppShell subtitle="Evidence-bound packet auditing — Command Center">
      <main className="mx-auto max-w-6xl px-4 py-8 sm:px-6">
        <Section
          title="Command Center"
          description="Upload a packet of related business documents. The engine audits them together — detecting cross-document contradictions, missing required documents, and redaction/metadata leaks before you send — and cites the exact source of every finding."
        >
          {/* Create a new packet */}
          <div className="card p-5">
            <h3 className="text-sm font-semibold text-ink">Start a new packet audit</h3>
            <div className="mt-4 grid gap-3 sm:grid-cols-2">
              <label className="block">
                <span className="text-xs font-medium text-slate-600">Packet name</span>
                <input
                  className="studio-input mt-1 w-full"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="e.g. Shipment ACME-2026-04"
                />
              </label>
              <label className="block">
                <span className="text-xs font-medium text-slate-600">Vertical</span>
                <select
                  className="studio-input mt-1 w-full"
                  value={pack}
                  onChange={(e) => setPack(e.target.value)}
                >
                  {PACKET_PACKS.map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.label}
                    </option>
                  ))}
                </select>
              </label>
            </div>
            <p className="mt-2 text-xs text-slate-500">
              {PACKET_PACKS.find((p) => p.id === pack)?.hint}
            </p>
            <button
              className="btn-primary mt-4"
              onClick={() => create.mutate()}
              disabled={create.isPending}
            >
              {create.isPending ? "Creating…" : "Create packet"}
            </button>
          </div>

          {/* Existing packets */}
          <div className="mt-8">
            <h3 className="text-sm font-semibold text-ink">Your packets</h3>
            {packets.isLoading && <p className="mt-3 text-sm text-slate-500">Loading…</p>}
            {packets.data && packets.data.length === 0 && (
              <p className="mt-3 text-sm text-slate-500">
                No packets yet. Create one above to begin.
              </p>
            )}
            <ul className="mt-3 space-y-2">
              {packets.data?.map((p) => {
                const tone = toneFor("needs_review"); // verdict unknown until audited
                return (
                  <li key={p.id}>
                    <Link
                      href={`/packets/${p.id}`}
                      className={`card flex items-center gap-3 border border-line p-4 hover:border-brand-300`}
                    >
                      <span className={`inline-block h-2 w-2 rounded-full ${tone.dot}`} />
                      <span className="text-sm font-medium text-ink">{p.name}</span>
                      <span className="rounded-full bg-chrome px-2 py-0.5 text-[10px] text-slate-600">
                        {p.pack}
                      </span>
                      <span className="ml-auto text-xs text-slate-500">
                        {p.document_ids.length} document(s)
                      </span>
                    </Link>
                  </li>
                );
              })}
            </ul>
          </div>
        </Section>
      </main>
    </AppShell>
  );
}
