"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";

import { deleteTemplate, instantiateTemplate, listTemplates } from "@/lib/api";
import { friendlyApiError } from "@/lib/upload";

/**
 * Template gallery — reuse saved documents as starting points. "Use template"
 * stamps out a fresh, fully independent document and opens it.
 */
export function TemplateGallery() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const templates = useQuery({ queryKey: ["templates"], queryFn: listTemplates });

  const use = useMutation({
    mutationFn: (templateId: string) => instantiateTemplate(templateId),
    onSuccess: (res) => router.push(`/documents/${res.doc_id}`),
  });
  const remove = useMutation({
    mutationFn: (templateId: string) => deleteTemplate(templateId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["templates"] }),
  });

  if (templates.isLoading) return <p className="text-sm text-slate-500">Loading templates…</p>;
  if (templates.isError) {
    return (
      <p role="alert" className="text-sm text-red-600">
        {friendlyApiError(templates.error, "Couldn't load templates.")}
      </p>
    );
  }

  const list = templates.data ?? [];
  if (list.length === 0) {
    return (
      <div className="rounded-lg border border-dashed border-slate-300 bg-white px-4 py-8 text-center text-sm text-slate-500">
        No templates yet. Open a document and choose <strong>Tools → Save as template</strong> to
        reuse it later.
      </div>
    );
  }

  return (
    <ul className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
      {list.map((t) => (
        <li
          key={t.id}
          className="flex flex-col justify-between rounded-xl border border-slate-200 bg-white p-4 shadow-sm"
        >
          <div>
            <div className="flex items-center justify-between gap-2">
              <span className="text-sm font-semibold text-ink">{t.name}</span>
              <span className="rounded bg-slate-100 px-2 py-0.5 text-[10px] uppercase text-slate-500">
                {t.source_format}
              </span>
            </div>
            {t.description && <p className="mt-1 text-xs text-slate-500">{t.description}</p>}
          </div>
          <div className="mt-3 flex items-center gap-2">
            <button
              type="button"
              onClick={() => use.mutate(t.id)}
              disabled={use.isPending}
              className="min-h-[40px] flex-1 rounded-lg bg-brand-600 px-3 text-sm font-medium text-white hover:bg-brand-700 disabled:opacity-40"
            >
              {use.isPending ? "Creating…" : "Use template"}
            </button>
            <button
              type="button"
              onClick={() => {
                if (window.confirm(`Delete template "${t.name}"?`)) remove.mutate(t.id);
              }}
              disabled={remove.isPending}
              aria-label={`Delete template ${t.name}`}
              className="min-h-[40px] min-w-[40px] rounded-lg px-2 text-xs text-slate-400 hover:text-red-600"
            >
              Delete
            </button>
          </div>
        </li>
      ))}
    </ul>
  );
}
