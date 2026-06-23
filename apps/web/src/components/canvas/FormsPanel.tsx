"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import {
  autofillDocument,
  createField,
  deleteField,
  detectFields,
  fillField,
  getFillProfile,
  listFields,
  saveFillProfile,
  updateField,
  type FormField,
} from "@/lib/api";
import { friendlyApiError } from "@/lib/upload";

/** Parse "Key: value" lines into a profile map. */
function parseProfile(text: string): Record<string, string> {
  const out: Record<string, string> = {};
  for (const line of text.split("\n")) {
    const idx = line.indexOf(":");
    if (idx <= 0) continue;
    const key = line.slice(0, idx).trim();
    const value = line.slice(idx + 1).trim();
    if (key) out[key] = value;
  }
  return out;
}

function serializeProfile(data: Record<string, string>): string {
  return Object.entries(data)
    .map(([k, v]) => `${k}: ${v}`)
    .join("\n");
}

function FieldRow({ docId, field }: { docId: string; field: FormField }) {
  const queryClient = useQueryClient();
  const [value, setValue] = useState(field.value ?? "");
  const [name, setName] = useState(field.field_name);
  const [kind, setKind] = useState(field.field_kind);
  const [required, setRequired] = useState(field.required);
  const [options, setOptions] = useState((field.options ?? []).join(", "));
  const filled = Boolean((field.value ?? "").trim());
  const refresh = () => {
    queryClient.invalidateQueries({ queryKey: ["fields", docId] });
    queryClient.invalidateQueries({ queryKey: ["model", docId] });
    queryClient.invalidateQueries({ queryKey: ["intelligence", docId] });
    queryClient.invalidateQueries({ queryKey: ["autopilot", docId] });
  };

  const save = useMutation({
    mutationFn: () => fillField(docId, field.node_id, value),
    onSuccess: refresh,
  });

  const configure = useMutation({
    mutationFn: () =>
      updateField(docId, field.node_id, {
        field_name: name,
        field_kind: kind,
        required,
        options: options.split(",").map((o) => o.trim()).filter(Boolean),
      }),
    onSuccess: refresh,
  });

  const remove = useMutation({
    mutationFn: () => deleteField(docId, field.node_id),
    onSuccess: refresh,
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
      <details className="mt-3">
        <summary className="cursor-pointer text-xs font-medium text-slate-500">
          Field settings
        </summary>
        <div className="mt-2 grid gap-2">
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            className="min-h-[36px] rounded-lg border border-slate-300 px-2 text-sm"
            aria-label="Field name"
          />
          <select
            value={kind}
            onChange={(e) => setKind(e.target.value)}
            className="min-h-[36px] rounded-lg border border-slate-300 px-2 text-sm"
            aria-label="Field type"
          >
            {["text", "date", "signature", "checkbox", "dropdown", "email", "phone"].map((k) => (
              <option key={k} value={k}>
                {k}
              </option>
            ))}
          </select>
          <input
            value={options}
            onChange={(e) => setOptions(e.target.value)}
            placeholder="Options, comma separated"
            className="min-h-[36px] rounded-lg border border-slate-300 px-2 text-sm"
          />
          <label className="flex items-center gap-2 text-sm text-slate-600">
            <input
              type="checkbox"
              checked={required}
              onChange={(e) => setRequired(e.target.checked)}
            />
            Required
          </label>
          <div className="flex gap-2">
            <button
              type="button"
              onClick={() => configure.mutate()}
              disabled={configure.isPending}
              className="min-h-[36px] rounded-lg border border-slate-300 px-3 text-sm font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-40"
            >
              Save settings
            </button>
            <button
              type="button"
              onClick={() => remove.mutate()}
              disabled={remove.isPending}
              className="min-h-[36px] rounded-lg border border-red-200 px-3 text-sm font-medium text-red-700 hover:bg-red-50 disabled:opacity-40"
            >
              Delete field
            </button>
          </div>
        </div>
      </details>
      {save.isError && (
        <p role="alert" className="mt-1 text-xs text-red-600">
          {friendlyApiError(save.error, "Couldn't save this field.")}
        </p>
      )}
      {(configure.isError || remove.isError) && (
        <p role="alert" className="mt-1 text-xs text-red-600">
          {friendlyApiError(configure.error ?? remove.error, "Couldn't update this field.")}
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
  const queryClient = useQueryClient();
  const [newName, setNewName] = useState("New field");
  const [newKind, setNewKind] = useState("text");
  const refresh = () => {
    queryClient.invalidateQueries({ queryKey: ["fields", docId] });
    queryClient.invalidateQueries({ queryKey: ["model", docId] });
    queryClient.invalidateQueries({ queryKey: ["intelligence", docId] });
    queryClient.invalidateQueries({ queryKey: ["autopilot", docId] });
  };
  const detect = useMutation({ mutationFn: () => detectFields(docId), onSuccess: refresh });
  const create = useMutation({
    mutationFn: () =>
      createField(docId, {
        field_name: newName,
        field_kind: newKind,
        required: true,
        placeholder: newName,
      }),
    onSuccess: refresh,
  });

  // Fill Once: a reusable profile that auto-populates matching fields across documents.
  const profile = useQuery({ queryKey: ["fill-profile"], queryFn: getFillProfile });
  const [profileText, setProfileText] = useState<string | null>(null);
  const autofill = useMutation({
    mutationFn: () => autofillDocument(docId),
    onSuccess: refresh,
  });
  const saveProfile = useMutation({
    mutationFn: () => saveFillProfile(parseProfile(profileText ?? "")),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["fill-profile"] }),
  });
  const profileLines = profileText ?? serializeProfile(profile.data?.data ?? {});

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
      <div className="mt-4 space-y-2 rounded-lg border border-slate-200 p-3">
        <button
          type="button"
          onClick={() => detect.mutate()}
          disabled={detect.isPending}
          className="min-h-[40px] w-full rounded-lg border border-slate-300 px-3 text-sm font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-40"
        >
          {detect.isPending ? "Detecting..." : "Detect blanks as fields"}
        </button>
        <div className="grid grid-cols-[1fr_auto] gap-2">
          <input
            value={newName}
            onChange={(e) => setNewName(e.target.value)}
            className="min-h-[40px] rounded-lg border border-slate-300 px-2 text-sm"
          />
          <select
            value={newKind}
            onChange={(e) => setNewKind(e.target.value)}
            className="min-h-[40px] rounded-lg border border-slate-300 px-2 text-sm"
          >
            {["text", "date", "signature", "checkbox", "dropdown", "email", "phone"].map((k) => (
              <option key={k} value={k}>
                {k}
              </option>
            ))}
          </select>
        </div>
        <button
          type="button"
          onClick={() => create.mutate()}
          disabled={!newName.trim() || create.isPending}
          className="min-h-[40px] w-full rounded-lg bg-brand-600 px-3 text-sm font-medium text-white hover:bg-brand-700 disabled:opacity-40"
        >
          Add field
        </button>
      </div>
      {(detect.isError || create.isError) && (
        <p role="alert" className="mt-2 text-xs text-red-600">
          {friendlyApiError(detect.error ?? create.error, "Couldn't update form fields.")}
        </p>
      )}

      <div className="mt-3 space-y-2 rounded-lg border border-trust-200 bg-trust-50 p-3">
        <div className="flex items-center justify-between">
          <span className="text-sm font-semibold text-ink">Fill Once</span>
          <button
            type="button"
            onClick={() => autofill.mutate()}
            disabled={autofill.isPending}
            className="min-h-[36px] rounded-lg bg-trust-700 px-3 text-sm font-medium text-white hover:bg-trust-800 disabled:opacity-40"
          >
            {autofill.isPending ? "Filling…" : "Autofill from my profile"}
          </button>
        </div>
        <p className="text-xs text-slate-600">
          Save your details once; matching blank fields fill automatically on every form.
        </p>
        <details>
          <summary className="cursor-pointer text-xs font-medium text-slate-500">
            Edit my profile
          </summary>
          <textarea
            value={profileLines}
            onChange={(e) => setProfileText(e.target.value)}
            rows={5}
            placeholder={"Name: Ada Lovelace\nEmail: ada@example.com\nAddress: 1 Analytical Way"}
            className="mt-2 w-full rounded-lg border border-slate-300 px-2 py-1 font-mono text-xs"
          />
          <button
            type="button"
            onClick={() => saveProfile.mutate()}
            disabled={saveProfile.isPending}
            className="mt-2 min-h-[36px] rounded-lg border border-slate-300 px-3 text-sm font-medium text-slate-700 hover:bg-white disabled:opacity-40"
          >
            {saveProfile.isPending ? "Saving…" : "Save profile"}
          </button>
        </details>
        {autofill.data && (
          <p className="text-xs text-trust-700">Filled {autofill.data.filled} field(s).</p>
        )}
        {(autofill.isError || saveProfile.isError) && (
          <p role="alert" className="text-xs text-red-600">
            {friendlyApiError(autofill.error ?? saveProfile.error, "Couldn't autofill.")}
          </p>
        )}
      </div>
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
