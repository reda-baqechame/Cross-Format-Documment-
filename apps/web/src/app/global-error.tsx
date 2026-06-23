"use client";

import { useEffect } from "react";

/**
 * Last-resort boundary for errors thrown in the root layout itself. It must render its own
 * <html>/<body> because it replaces the whole document tree when the normal layout can't mount.
 */
export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error("Fatal app error:", error);
  }, [error]);

  return (
    <html lang="en">
      <body
        style={{
          margin: 0,
          minHeight: "100vh",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          fontFamily: "system-ui, -apple-system, sans-serif",
          background: "#f8fafc",
          color: "#0f172a",
        }}
      >
        <div style={{ maxWidth: 420, padding: 32, textAlign: "center" }}>
          <h1 style={{ fontSize: 18, fontWeight: 600 }}>The app failed to load</h1>
          <p style={{ marginTop: 8, fontSize: 14, color: "#475569" }}>
            A fatal error occurred while starting this page. Please try again.
          </p>
          <button
            type="button"
            onClick={() => reset()}
            style={{
              marginTop: 24,
              padding: "8px 16px",
              borderRadius: 8,
              border: "none",
              background: "#2451e6",
              color: "white",
              fontSize: 14,
              cursor: "pointer",
            }}
          >
            Try again
          </button>
        </div>
      </body>
    </html>
  );
}
