"use client";

import Link from "next/link";

const JOBS = [
  {
    id: "open",
    icon: "📂",
    title: "Open & convert",
    body: "Upload PDF, Word, Excel, PowerPoint, or scan a photo — export in any format.",
    href: "#upload",
  },
  {
    id: "trust",
    icon: "🛡️",
    title: "Clean & protect",
    body: "Redact sensitive data, strip metadata, fix accessibility, then sign.",
    href: "#upload",
  },
  {
    id: "research",
    icon: "🔍",
    title: "Ask & compare",
    body: "Q&A with citations, multi-doc notebook, and cross-document diff.",
    href: "#research",
  },
  {
    id: "library",
    icon: "📚",
    title: "Find in library",
    body: "Keyword or semantic search across everything you've uploaded.",
    href: "#library",
  },
] as const;

/** Job-to-be-done tiles — competitor pattern (Smallpdf tool grid, Acrobat task hub). */
export function JobTiles() {
  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
      {JOBS.map((job) => (
        <Link
          key={job.id}
          href={job.href}
          className="flex min-h-[120px] flex-col rounded-2xl border border-slate-200 bg-white p-4 shadow-sm transition hover:border-brand-300 hover:shadow-md"
        >
          <span className="text-2xl" aria-hidden>
            {job.icon}
          </span>
          <span className="mt-2 text-sm font-semibold text-ink">{job.title}</span>
          <span className="mt-1 text-xs leading-relaxed text-slate-500">{job.body}</span>
        </Link>
      ))}
    </div>
  );
}
