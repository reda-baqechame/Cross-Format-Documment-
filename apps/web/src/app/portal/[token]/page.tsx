"use client";

import { useQuery } from "@tanstack/react-query";
import { useParams } from "next/navigation";
import { useState } from "react";

import { DocumentCanvas } from "@/components/canvas/DocumentCanvas";
import { fetchPortalModel, fetchPortalReadiness } from "@/lib/api";

export default function PortalPage() {
  const params = useParams<{ token: string }>();
  const token = params.token;
  const [pin, setPin] = useState("");
  const [submittedPin, setSubmittedPin] = useState<string | undefined>(undefined);

  const model = useQuery({
    queryKey: ["portal-model", token, submittedPin],
    queryFn: () => fetchPortalModel(token, submittedPin),
    enabled: Boolean(token),
    retry: false,
  });
  const readiness = useQuery({
    queryKey: ["portal-readiness", token, submittedPin],
    queryFn: () => fetchPortalReadiness(token, submittedPin),
    enabled: Boolean(token) && model.isSuccess,
    retry: false,
  });

  const needsPin = model.isError && String(model.error).includes("401");

  return (
    <div className="min-h-screen bg-canvas">
      <header className="border-b border-slate-200 bg-white px-4 py-4">
        <h1 className="text-lg font-semibold text-slate-900">Client packet portal</h1>
        <p className="text-sm text-slate-500">Shared by your agency — view only, no account required</p>
      </header>
      <main className="mx-auto max-w-4xl p-4 sm:p-8">
        {needsPin && (
          <form
            className="mb-6 flex max-w-sm gap-2"
            onSubmit={(e) => {
              e.preventDefault();
              setSubmittedPin(pin || undefined);
            }}
          >
            <input
              type="password"
              value={pin}
              onChange={(e) => setPin(e.target.value)}
              placeholder="PIN"
              className="flex-1 rounded-lg border border-slate-300 px-3 py-2 text-sm"
            />
            <button type="submit" className="rounded-lg bg-brand-600 px-4 py-2 text-sm text-white">
              Unlock
            </button>
          </form>
        )}
        {model.isLoading && <p className="text-slate-500">Loading shared document…</p>}
        {model.isError && !needsPin && (
          <p role="alert" className="text-red-600">
            {model.error instanceof Error ? model.error.message : "Link not found or expired"}
          </p>
        )}
        {model.data && (
          <>
            {readiness.data && (
              <div className="mb-6 rounded-lg border border-slate-200 bg-white p-4">
                <p className="text-sm font-medium text-slate-800">Packet readiness</p>
                <p className="mt-1 text-sm text-slate-600">{readiness.data.report.summary}</p>
              </div>
            )}
            <DocumentCanvas doc={model.data.document} docId={model.data.document.doc_id} />
          </>
        )}
      </main>
    </div>
  );
}
