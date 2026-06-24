"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useParams } from "next/navigation";
import { useState } from "react";

import { DocumentCanvas } from "@/components/canvas/DocumentCanvas";
import {
  fetchPortalApprovals,
  fetchPortalInfo,
  fetchPortalModel,
  fetchPortalReadiness,
  portalApprove,
} from "@/lib/api";

export default function PortalPage() {
  const params = useParams<{ token: string }>();
  const token = params.token;
  const queryClient = useQueryClient();
  const [pin, setPin] = useState("");
  const [submittedPin, setSubmittedPin] = useState<string | undefined>(undefined);

  const info = useQuery({
    queryKey: ["portal-info", token, submittedPin],
    queryFn: () => fetchPortalInfo(token, submittedPin),
    enabled: Boolean(token),
    retry: false,
  });

  const model = useQuery({
    queryKey: ["portal-model", token, submittedPin],
    queryFn: () => fetchPortalModel(token, submittedPin),
    enabled: Boolean(token) && info.isSuccess,
    retry: false,
  });
  const readiness = useQuery({
    queryKey: ["portal-readiness", token, submittedPin],
    queryFn: () => fetchPortalReadiness(token, submittedPin),
    enabled: Boolean(token) && model.isSuccess,
    retry: false,
  });
  const approvals = useQuery({
    queryKey: ["portal-approvals", token, submittedPin],
    queryFn: () => fetchPortalApprovals(token, submittedPin),
    enabled: Boolean(token) && info.data?.permission === "sign" && model.isSuccess,
    retry: false,
  });

  const approve = useMutation({
    mutationFn: () => portalApprove(token, { pin: submittedPin }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["portal-approvals", token] });
    },
  });

  const loadError = info.error ?? model.error;
  const needsPin =
    (info.isError && String(info.error).includes("401")) ||
    (model.isError && String(model.error).includes("401"));

  return (
    <div className="min-h-screen bg-canvas">
      <header className="border-b border-slate-200 bg-white px-4 py-4">
        <h1 className="text-lg font-semibold text-slate-900">Client packet portal</h1>
        <p className="text-sm text-slate-500">
          Shared by your agency — {info.data?.permission === "sign" ? "review and sign off" : "view only"}
          , no account required
        </p>
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
        {info.isLoading && <p className="text-slate-500">Loading shared link…</p>}
        {loadError && !needsPin && (
          <p role="alert" className="text-red-600">
            {loadError instanceof Error ? loadError.message : "Link not found or expired"}
          </p>
        )}
        {info.data && model.data && (
          <>
            {readiness.data && (
              <div className="mb-6 rounded-lg border border-slate-200 bg-white p-4">
                <p className="text-sm font-medium text-slate-800">Packet readiness</p>
                <p className="mt-1 text-sm text-slate-600">{readiness.data.report.summary}</p>
              </div>
            )}
            {info.data.permission === "sign" && approvals.data && (
              <div className="mb-6 rounded-lg border border-slate-200 bg-white p-4">
                <p className="text-sm font-medium text-slate-800">Sign-off</p>
                <p className="mt-1 text-sm text-slate-600">
                  Status: <strong>{approvals.data.state.replace("_", " ")}</strong>
                  {info.data.recipient_label ? ` · as ${info.data.recipient_label}` : ""}
                </p>
                {approvals.data.state === "in_progress" &&
                  info.data.recipient_label &&
                  approvals.data.current_approvers.includes(info.data.recipient_label) && (
                    <button
                      type="button"
                      onClick={() => approve.mutate()}
                      disabled={approve.isPending}
                      className="mt-3 rounded-lg bg-brand-600 px-4 py-2 text-sm font-medium text-white hover:bg-brand-500 disabled:opacity-50"
                    >
                      {approve.isPending ? "Submitting…" : "Approve packet"}
                    </button>
                  )}
                {approvals.data.state === "approved" && (
                  <p className="mt-2 text-sm text-green-700">✓ This packet has been approved.</p>
                )}
                {approve.isError && (
                  <p role="alert" className="mt-2 text-sm text-red-600">
                    {approve.error instanceof Error ? approve.error.message : "Could not approve"}
                  </p>
                )}
              </div>
            )}
            <DocumentCanvas doc={model.data.document} docId={model.data.document.doc_id} readOnly />
          </>
        )}
      </main>
    </div>
  );
}
