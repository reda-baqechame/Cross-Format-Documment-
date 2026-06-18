import Link from "next/link";

import { tasksByCategory } from "@/lib/tasks";

/** The home task picker: every job as a card, grouped by category (iLovePDF-style). */
export function TaskGrid() {
  const groups = tasksByCategory();
  return (
    <div className="space-y-10">
      {groups.map(({ category, tasks }) => (
        <div key={category}>
          <h3 className="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-500">
            {category}
          </h3>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {tasks.map((task) => (
              <Link
                key={task.slug}
                href={`/tasks/${task.slug}`}
                className="group flex items-start gap-3 rounded-xl border border-slate-200 bg-white p-4 transition-colors hover:border-brand-400 hover:bg-brand-50/40"
              >
                <span
                  className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-slate-100 text-xl group-hover:bg-white"
                  aria-hidden
                >
                  {task.emoji}
                </span>
                <span className="min-w-0">
                  <span className="block font-medium text-ink">{task.title}</span>
                  <span className="mt-0.5 block text-sm leading-snug text-slate-500">
                    {task.blurb}
                  </span>
                </span>
              </Link>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}
