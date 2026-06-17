const STEPS = [
  {
    step: "1",
    title: "Open any file",
    body: "Upload from your phone or desktop. We parse PDF, Office, RTF, text, and images into one model.",
  },
  {
    step: "2",
    title: "Edit & check trust",
    body: "Change text, run AI edits, scan for sensitive data, fix accessibility — all as reversible changes.",
  },
  {
    step: "3",
    title: "Export safely",
    body: "Download in the format you need with redactions and edits burned in. Share with confidence.",
  },
] as const;

export function WorkflowStrip() {
  return (
    <ol className="grid gap-3 sm:grid-cols-3">
      {STEPS.map((s) => (
        <li
          key={s.step}
          className="relative rounded-xl border border-slate-200 bg-white p-4 shadow-sm"
        >
          <span className="inline-flex h-7 w-7 items-center justify-center rounded-full bg-brand-600 text-xs font-bold text-white">
            {s.step}
          </span>
          <h3 className="mt-2 text-sm font-semibold text-ink">{s.title}</h3>
          <p className="mt-1 text-sm leading-relaxed text-slate-600">{s.body}</p>
        </li>
      ))}
    </ol>
  );
}
