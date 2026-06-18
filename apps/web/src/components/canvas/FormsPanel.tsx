"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { fillField, listFields, type FormField } from "@/lib/api";
import { friendlyApiError } from "@/lib/upload";

function FieldRow({ docId, field }: { docId: string; field: FormField }) {
  const queryClient = useQueryClient();
  const [value, setValue] = useState(field.value ?? "");
  const filled = Boolean((field.value ?? "").trim());

  const save = useMutation({
    mutationFn: () => fillField(docId, field.node_id, value),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["fields", docId] });
      queryClient.invalidateQueries({ queryKey: ["model", docId] });
      queryClient.invalidateQueries({ queryKey: ["intelligence", docId] });
    },
  });

  return (
    <li className="rounded-lg border border-slate-200 p-3">
      <div className="flex items-center justify-between gap-2">
        <label className="text-sm font-medium text-slate-700" htmlFor={`field-${field.node_id}`}>
          {field.field_name || "Field"}
          <span className="ml-2 text-[10px] uppercase tracking-wide text-slate-400">
            {field.field_kind}
          </span>
        </label>
        <span
          className={`rounded-full px-2 py-0.5 text-[10px] font-medium ${
            filled ? "bg-emerald-50 text-emerald-700" : "bg-amber-50 text-amber-700"
          }`}
        >
          {filled ? "filled" : "blank"}
        </span>
      </div>
      <div className="mt-2 flex gap-2">
        <input
          id={`field-${field.node_id}`}
          value={value}
          onChange={(e) => setValue(e.target.value)}
          placeholder="Enter a value…"
          className="min-h-[40px] flex-1 rounded-lg border border-slate-300 px-2 py-1 text-sm"
        />
        <button
          type="button"
          onClick={() => save.mutate()}
          disabled={save.isPending || value === (field.value ?? "")}
          className="min-h-[40px] rounded-lg bg-brand-600 px-3 text-sm font-medium text-white hover:bg-brand-700 disabled:opacity-40"
        >
          {save.isPending ? "Saving…" : "Save"}
        </button>
      </div>
      {save.isError && (
        <p role="alert" className="mt-1 text-xs text-red-600">
          {friendlyApiError(save.error, "Couldn't save this field.")}
        </p>
      )}
    </li>
  );
}

/**
 * Forms — list and fill a document's fillable fields. Each save is a reversible,
 * versioned patch (same path as any edit), so fills can be undone.
 */
export function FormsPanel({ docId }: { docId: string }) {
  const fields = useQuery({ queryKey: ["fields", docId], queryFn: () => listFields(docId) });

  if (fields.isLoading) return <p className="p-6 text-sm text-slate-500">Loading form fields…</p>;
  if (fields.isError) {
    return (
      <p role="alert" className="p-6 text-sm text-red-600">
        {friendlyApiError(fields.error, "Couldn't load form fields.")}
      </p>
    );
  }

  const list = fields.data ?? [];
  const filled = list.filter((f) => (f.value ?? "").trim()).length;

  return (
    <div className="p-6">
      <h2 className="text-base font-semibold text-ink">Form fields</h2>
      {list.length === 0 ? (
        <p className="mt-2 text-sm text-slate-500">
          This document has no fillable fields. Fields appear here for forms and templates with
          placeholders.
        </p>
      ) : (
        <>
          <p className="mt-1 text-sm text-slate-600">
            {filled}/{list.length} fields completed.
          </p>
          <ul className="mt-4 space-y-3">
            {list.map((f) => (
              <FieldRow key={f.node_id} docId={docId} field={f} />
            ))}
          </ul>
        </>
      )}
    </div>
  );
}
