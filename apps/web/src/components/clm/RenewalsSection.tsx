"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CalendarClock } from "lucide-react";
import { useState } from "react";

import { createRenewal, deleteRenewal, listRenewals, type Renewal } from "@/lib/api";
import { friendlyApiError } from "@/lib/upload";

const URGENCY_STYLE: Record<Renewal["urgency"], string> = {
  overdue: "bg-red-100 text-red-700",
  soon: "bg-amber-100 text-amber-700",
  later: "bg-slate-100 text-slate-600",
};

export function RenewalsSection() {
  const queryClient = useQueryClient();
  const renewals = useQuery({ queryKey: ["renewals"], queryFn: listRenewals });
  const [title, setTitle] = useState("");
  const [dueDate, setDueDate] = useState("");
  const [error, setError] = useState<string | null>(null);

  const refresh = () => queryClient.invalidateQueries({ queryKey: ["renewals"] });

  const add = useMutation({
    mutationFn: () => createRenewal({ title: title.trim(), due_date: dueDate }),
    onSuccess: () => {
      setTitle("");
      setDueDate("");
      setError(null);
      refresh();
    },
    onError: (e) => setError(friendlyApiError(e, "Could not add the reminder.")),
  });

  const remove = useMutation({ mutationFn: deleteRenewal, onSuccess: refresh });

  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-5">
      <div className="flex items-center gap-2">
        <CalendarClock className="h-5 w-5 text-trust-700" />
        <h2 className="text-sm font-semibold text-slate-900">Renewal reminders</h2>
      </div>
      <p className="mt-1 text-xs text-slate-500">
        Track contract renewal and expiry dates. In-app reminders, sorted by due date.
      </p>

      <div className="mt-3 flex flex-col gap-2 sm:flex-row">
        <input
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          placeholder="What renews? (e.g. Acme MSA)"
          className="min-w-0 flex-1 rounded border border-slate-300 px-2 py-1 text-sm"
        />
        <input
          type="date"
          value={dueDate}
          onChange={(e) => setDueDate(e.target.value)}
          className="rounded border border-slate-300 px-2 py-1 text-sm"
        />
        <button
          type="button"
          disabled={!title.trim() || !dueDate || add.isPending}
          onClick={() => add.mutate()}
          className="btn-primary px-3 py-1 text-sm disabled:opacity-40"
        >
          Add
        </button>
      </div>
      {error && <p className="mt-2 text-xs text-red-600">{error}</p>}

      <ul className="mt-4 space-y-2">
        {renewals.data?.length === 0 && (
          <li className="text-xs text-slate-500">No renewals tracked yet.</li>
        )}
        {renewals.data?.map((r) => (
          <li
            key={r.id}
            className="flex items-center justify-between gap-3 rounded-lg border border-slate-200 px-3 py-2"
          >
            <div className="min-w-0">
              <p className="truncate text-sm font-medium text-slate-900">{r.title}</p>
              <p className="text-xs text-slate-500">Due {r.due_date}</p>
            </div>
            <div className="flex shrink-0 items-center gap-2">
              <span
                className={`rounded-full px-2 py-0.5 text-xs font-medium capitalize ${URGENCY_STYLE[r.urgency]}`}
              >
                {r.urgency}
              </span>
              <button
                type="button"
                onClick={() => remove.mutate(r.id)}
                className="text-xs text-slate-400 hover:text-red-600"
                aria-label={`Delete reminder ${r.title}`}
              >
                ✕
              </button>
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}
