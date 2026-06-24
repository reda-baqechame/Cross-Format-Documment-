"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { addTag, listTags, removeTag } from "@/lib/api";

export function TagsPanel({ docId }: { docId: string }) {
  const queryClient = useQueryClient();
  const [draft, setDraft] = useState("");
  const tags = useQuery({ queryKey: ["tags", docId], queryFn: () => listTags(docId) });

  const add = useMutation({
    mutationFn: (tag: string) => addTag(docId, tag),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["tags", docId] });
      void queryClient.invalidateQueries({ queryKey: ["documents"] });
      setDraft("");
    },
  });

  const remove = useMutation({
    mutationFn: (tag: string) => removeTag(docId, tag),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["tags", docId] });
      void queryClient.invalidateQueries({ queryKey: ["documents"] });
    },
  });

  const list = tags.data?.tags ?? [];

  return (
    <section className="rounded-lg border border-slate-200 bg-white p-4">
      <h3 className="text-sm font-semibold text-slate-800">Tags</h3>
      <div className="mt-2 flex flex-wrap gap-2">
        {list.map((tag) => (
          <span
            key={tag}
            className="inline-flex items-center gap-1 rounded-full bg-slate-100 px-2 py-1 text-xs text-slate-700"
          >
            {tag}
            <button
              type="button"
              aria-label={`Remove tag ${tag}`}
              onClick={() => remove.mutate(tag)}
              className="text-slate-400 hover:text-red-600"
            >
              ×
            </button>
          </span>
        ))}
        {list.length === 0 && <span className="text-xs text-slate-400">No tags yet</span>}
      </div>
      <form
        className="mt-3 flex gap-2"
        onSubmit={(e) => {
          e.preventDefault();
          const t = draft.trim();
          if (t) add.mutate(t);
        }}
      >
        <input
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          placeholder="Add tag…"
          className="min-h-[40px] flex-1 rounded-lg border border-slate-300 px-3 py-2 text-sm"
        />
        <button
          type="submit"
          disabled={!draft.trim() || add.isPending}
          className="rounded-lg border border-slate-300 px-3 py-2 text-sm hover:bg-slate-50 disabled:opacity-40"
        >
          Add
        </button>
      </form>
    </section>
  );
}
