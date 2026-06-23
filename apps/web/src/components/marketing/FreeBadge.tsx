/**
 * The wedge headline. The single biggest documented frustration with iLovePDF/Smallpdf is task
 * caps + file-size limits + forced login. We have none of those, so we say it loudly — on the
 * hero and atop every tool page. Keep this honest: it must stay true (no caps, no login).
 */
const POINTS = ["Free", "Unlimited", "No login", "No file-size caps"];

export function FreeBadge({ className = "" }: { className?: string }) {
  return (
    <div
      className={`flex flex-wrap items-center gap-x-2 gap-y-1 text-xs font-medium text-slate-600 ${className}`}
      aria-label="Free, unlimited, no login, no file-size caps"
    >
      {POINTS.map((point, i) => (
        <span key={point} className="inline-flex items-center gap-2">
          {i > 0 && <span className="text-slate-300">·</span>}
          <span className="inline-flex items-center gap-1 text-emerald-700">
            <span aria-hidden>✓</span>
            {point}
          </span>
        </span>
      ))}
    </div>
  );
}
