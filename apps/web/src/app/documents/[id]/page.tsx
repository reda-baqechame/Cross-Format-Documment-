"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useParams } from "next/navigation";

import { DocumentCanvas } from "@/components/canvas/DocumentCanvas";
import { HealthPanel } from "@/components/health-panel/HealthPanel";
import { fetchHealth, fetchModel } from "@/lib/api";
import { useWorkspace } from "@/lib/store";

export default function DocumentPage() {
  const params = useParams<{ id: string }>();
  const docId = params.id;
  const panelOpen = useWorkspace((s) => s.panelOpen);
  const togglePanel = useWorkspace((s) => s.togglePanel);

  const model = useQuery({ queryKey: ["model", docId], queryFn: () => fetchModel(docId) });
  const health = useQuery({ queryKey: ["health", docId], queryFn: () => fetchHealth(docId) });

  return (
    <div className="flex min-h-screen flex-col">
      <header className="flex items-center justify-between border-b border-slate-200 bg-white px-6 py-3">
        <div className="flex items-center gap-4">
          <Link href="/" className="text-sm text-slate-500 hover:underline">
            ← Back
          </Link>
          <span className="text-sm font-medium">
            {model.data?.document.meta.title ?? `Document ${docId.slice(0, 10)}…`}
          </span>
          {model.data && (
            <span className="rounded bg-slate-100 px-2 py-0.5 text-xs uppercase text-slate-500">
              {model.data.document.meta.source_format}
            </span>
          )}
        </div>
        <button onClick={togglePanel} className="text-sm text-slate-500 hover:underline">
          {panelOpen ? "Hide" : "Show"} health
        </button>
      </header>

      <div className="flex flex-1">
        <main className="flex-1 overflow-auto p-8">
          {model.isLoading && <p className="text-slate-500">Loading model…</p>}
          {model.isError && <p className="text-red-600">Failed to load: {String(model.error)}</p>}
          {model.data && <DocumentCanvas doc={model.data.document} />}
        </main>

        {panelOpen && health.data && <HealthPanel health={health.data.health} />}
      </div>
    </div>
  );
}
