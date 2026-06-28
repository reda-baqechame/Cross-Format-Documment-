/**
 * The wedge headline. Keep this honest: every claim here must match the actual deployed limits
 * because it appears on the hero and every task page. The upload-size point is data-driven when
 * the caller passes the live `maxUploadMb` from `/api/capabilities`; otherwise it falls back to
 * the documented default so server rendering stays simple.
 */
const DEFAULT_MAX_UPLOAD_MB = 50;

export function FreeBadge({
  className = "",
  maxUploadMb,
}: {
  className?: string;
  /** Live upload limit from GET /capabilities; when omitted the default is shown. */
  maxUploadMb?: number;
}) {
  const limit = maxUploadMb ?? DEFAULT_MAX_UPLOAD_MB;
  const points = ["Free", "No login", `${limit} MB files`, "Private session"];
  return (
    <div
      className={`flex flex-wrap items-center gap-x-2 gap-y-1 text-xs font-medium text-slate-600 ${className}`}
      aria-label={`Free, no login, ${limit} MB files, private session`}
    >
      {points.map((point, i) => (
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
