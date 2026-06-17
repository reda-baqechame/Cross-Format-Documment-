"use client";

import { useQuery } from "@tanstack/react-query";

import { fetchBackendHealth } from "@/lib/api";

const isProduction = process.env.NODE_ENV === "production";

/** Warns when the API proxy cannot reach the backend. */
export function BackendStatus() {
  const health = useQuery({
    queryKey: ["backend-health"],
    queryFn: fetchBackendHealth,
    retry: 1,
    refetchInterval: 20_000,
  });

  if (health.isLoading || health.isSuccess) return null;

  return (
    <div
      role="alert"
      className="border-b border-red-300 bg-red-50 px-4 py-3 text-sm text-red-900 sm:px-6"
    >
      <p className="font-medium">Service temporarily unavailable</p>
      <p className="mt-1 text-red-800">
        {isProduction ? (
          <>
            The app cannot reach the document API. If you deployed on Railway, set{" "}
            <code className="rounded bg-red-100 px-1 text-xs">API_PROXY_TARGET</code> on the web
            service to your API private URL (see{" "}
            <code className="rounded bg-red-100 px-1 text-xs">docs/railway.md</code>).
          </>
        ) : (
          <>
            Start Postgres and the API, then refresh. Run{" "}
            <code className="rounded bg-red-100 px-1 text-xs">.\scripts\dev.ps1</code> from the
            repo root.
          </>
        )}
      </p>
    </div>
  );
}
