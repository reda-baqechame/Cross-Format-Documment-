/** Route-level loading fallback shown while a server component segment streams in. */
export default function Loading() {
  return (
    <div className="flex min-h-[60vh] items-center justify-center px-4" aria-live="polite">
      <div className="flex items-center gap-3 text-sm text-slate-500">
        <span
          className="h-5 w-5 animate-spin rounded-full border-2 border-slate-300 border-t-brand-600"
          aria-hidden
        />
        Loading…
      </div>
    </div>
  );
}
