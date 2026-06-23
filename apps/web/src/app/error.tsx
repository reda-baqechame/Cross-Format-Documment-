"use client";

import Link from "next/link";
import { useEffect } from "react";

/**
 * Route-segment error boundary. Catches render/runtime errors in any page below it and shows a
 * recoverable message instead of a blank screen. `reset()` re-renders the segment.
 */
export default function Error({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    // Surfaced in the browser console; server-side digest is logged by Next automatically.
    console.error("Unhandled UI error:", error);
  }, [error]);

  return (
    <div className="flex min-h-[60vh] items-center justify-center px-4">
      <div className="card max-w-md p-8 text-center">
        <h1 className="text-lg font-semibold text-ink">Something went wrong</h1>
        <p className="mt-2 text-sm text-slate-600">
          An unexpected error interrupted this view. Your documents are safe — try again, or head
          back home.
        </p>
        {error.digest && (
          <p className="mt-3 font-mono text-xs text-slate-400">Reference: {error.digest}</p>
        )}
        <div className="mt-6 flex items-center justify-center gap-3">
          <button type="button" onClick={() => reset()} className="btn-primary">
            Try again
          </button>
          <Link href="/" className="btn-secondary">
            Back to home
          </Link>
        </div>
      </div>
    </div>
  );
}
