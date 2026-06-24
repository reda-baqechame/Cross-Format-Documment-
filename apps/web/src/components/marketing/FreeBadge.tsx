/**
 * The wedge headline. Keep this honest: every claim here must match the actual deployed limits
 * because it appears on the hero and every task page.
 */
const POINTS = ["Free", "No login", "50 MB files", "Private session"];

export function FreeBadge({ className = "" }: { className?: string }) {
  return (
    <div
      className={`flex flex-wrap items-center gap-x-2 gap-y-1 text-xs font-medium text-slate-600 ${className}`}
      aria-label="Free, no login, 50 MB files, private session"
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
