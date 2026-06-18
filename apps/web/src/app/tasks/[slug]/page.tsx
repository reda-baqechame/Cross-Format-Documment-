import Link from "next/link";
import { notFound } from "next/navigation";

import { AppShell } from "@/components/layout/AppShell";
import { BackendStatus } from "@/components/system/BackendStatus";
import { TaskRunner } from "@/components/tasks/TaskRunner";
import { getTask, TASKS } from "@/lib/tasks";

export function generateStaticParams() {
  return TASKS.map((t) => ({ slug: t.slug }));
}

export default function TaskPage({ params }: { params: { slug: string } }) {
  if (!getTask(params.slug)) notFound();

  return (
    <AppShell>
      <BackendStatus />
      <main className="mx-auto max-w-3xl px-4 py-6 sm:px-6 sm:py-10">
        <Link href="/" className="mb-6 inline-block text-sm text-slate-500 hover:text-brand-600">
          ← All tools
        </Link>
        <TaskRunner slug={params.slug} />
      </main>
    </AppShell>
  );
}
