import Link from "next/link";
import {
  Bot,
  FileOutput,
  FilePenLine,
  FilePlus2,
  GitCompare,
  LayoutGrid,
  LockKeyhole,
  type LucideIcon,
} from "lucide-react";

import { tasksByCategory, type TaskCategory } from "@/lib/tasks";

const CATEGORY_ICONS: Record<TaskCategory, LucideIcon> = {
  Create: FilePlus2,
  Workflow: LayoutGrid,
  "Organize PDF": FileOutput,
  Convert: FileOutput,
  Edit: FilePenLine,
  Secure: LockKeyhole,
  "Ask AI": Bot,
  Review: GitCompare,
};

export function TaskGrid({ compact = false }: { compact?: boolean }) {
  const groups = tasksByCategory();
  return (
    <div className={compact ? "grid gap-5 lg:grid-cols-2" : "space-y-10"}>
      {groups.map(({ category, tasks }) => {
        const Icon = CATEGORY_ICONS[category];
        return (
          <div key={category}>
            <div className="mb-3 flex items-center gap-2">
              <Icon className="h-4 w-4 text-slate-500" />
              <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                {category}
              </h3>
            </div>
            <div className={compact ? "grid gap-2" : "grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3"}>
              {tasks.map((task) => (
                <Link
                  key={task.slug}
                  href={`/tasks/${task.slug}`}
                  className={[
                    "group flex items-start gap-3 rounded-lg border border-slate-200 bg-white transition-colors hover:border-brand-400 hover:bg-brand-50/40 focus:outline-none focus:ring-2 focus:ring-blue-100",
                    compact ? "p-3" : "p-4",
                  ].join(" ")}
                >
                  <span
                    className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-slate-100 text-slate-600 group-hover:bg-white"
                    aria-hidden
                  >
                    <Icon className="h-4 w-4" />
                  </span>
                  <span className="min-w-0">
                    <span className="block text-sm font-medium text-ink">{task.title}</span>
                    <span className="mt-0.5 block text-sm leading-snug text-slate-500">
                      {task.blurb}
                    </span>
                  </span>
                </Link>
              ))}
            </div>
          </div>
        );
      })}
    </div>
  );
}
