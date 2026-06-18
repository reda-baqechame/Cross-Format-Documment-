const CAPABILITIES = [
  {
    category: "Open & convert",
    tag: "Ingest",
    color: "border-sky-200 bg-sky-50/80",
    icon: "📂",
    summary: "One upload, every major business format parsed into a single editable model.",
    items: [
      "PDF, Word, Excel, PowerPoint, RTF, text, images",
      "Cross-format export: DOCX, PDF, Markdown, HTML, CSV, PNG",
      "Layout preserved in the canonical model — not a one-way conversion",
    ],
  },
  {
    category: "Edit & understand",
    tag: "Work",
    color: "border-violet-200 bg-violet-50/80",
    icon: "✏️",
    summary: "Edit inline, ask AI, or query the whole library — with cited answers.",
    items: [
      "Double-tap text to edit; bold, italic, underline",
      "Natural-language AI edits → reversible patches",
      "Ask this document · summarize · multi-doc notebook",
    ],
  },
  {
    category: "Trust & compliance",
    tag: "Protect",
    color: "border-emerald-200 bg-emerald-50/80",
    icon: "🛡️",
    summary: "Redaction, metadata scrubbing, accessibility fixes, and signing in one health panel.",
    items: [
      "True redaction on export (content removed, not hidden)",
      "PII scan + one-click redact · metadata sanitize",
      "Accessibility score + auto-fix · integrity seal",
    ],
  },
  {
    category: "Review & collaborate",
    tag: "Team",
    color: "border-amber-200 bg-amber-50/80",
    icon: "👥",
    summary: "Comments, approvals, compare, and semantic search across your corpus.",
    items: [
      "Comment threads anchored to any paragraph",
      "Ordered approval workflows before sign-off",
      "Cross-document diff · keyword + semantic search",
    ],
  },
] as const;

export function CapabilityGrid() {
  return (
    <div className="grid gap-4 sm:grid-cols-2">
      {CAPABILITIES.map((cap) => (
        <article
          key={cap.category}
          className={`rounded-2xl border p-5 shadow-sm ${cap.color}`}
        >
          <div className="mb-3 flex items-start justify-between gap-2">
            <span className="text-2xl" aria-hidden>
              {cap.icon}
            </span>
            <span className="rounded-full bg-white/80 px-2.5 py-0.5 text-[10px] font-semibold uppercase tracking-wider text-slate-600">
              {cap.tag}
            </span>
          </div>
          <h3 className="text-base font-semibold text-ink">{cap.category}</h3>
          <p className="mt-1 text-sm text-slate-600">{cap.summary}</p>
          <ul className="mt-3 space-y-1.5 border-t border-black/5 pt-3">
            {cap.items.map((item) => (
              <li key={item} className="flex gap-2 text-sm text-slate-700">
                <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-brand-500" aria-hidden />
                {item}
              </li>
            ))}
          </ul>
        </article>
      ))}
    </div>
  );
}
