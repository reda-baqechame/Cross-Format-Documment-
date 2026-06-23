import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const monorepoRoot = path.join(__dirname, "../..");
const standaloneEnabled =
  process.env.DOCOS_NEXT_STANDALONE === "1" ||
  (process.platform !== "win32" && process.env.DOCOS_NEXT_STANDALONE !== "0");
const isProd = process.env.NODE_ENV === "production";

// Pragmatic CSP: Next 14's runtime needs inline/eval for hydration + styled-jsx, and the app
// renders PNG previews/thumbnails and triggers blob downloads, so images/media allow data:+blob:.
// The browser only talks to its own origin (the same-origin /api proxy), so connect-src is 'self'.
const csp = [
  "default-src 'self'",
  "script-src 'self' 'unsafe-inline' 'unsafe-eval'",
  "style-src 'self' 'unsafe-inline'",
  "img-src 'self' data: blob:",
  "font-src 'self' data:",
  "connect-src 'self'",
  "media-src 'self' blob:",
  "object-src 'none'",
  "base-uri 'self'",
  "form-action 'self'",
  "frame-ancestors 'self'",
].join("; ");

const securityHeaders = [
  { key: "Content-Security-Policy", value: csp },
  { key: "X-Content-Type-Options", value: "nosniff" },
  { key: "X-Frame-Options", value: "SAMEORIGIN" },
  { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
  { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=(), browsing-topics=()" },
  // HSTS only in production (don't pin localhost http during dev).
  ...(isProd
    ? [{ key: "Strict-Transport-Security", value: "max-age=63072000; includeSubDomains" }]
    : []),
];

/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // The canonical-model types are shared from a workspace package (transpiled here).
  transpilePackages: ["@docos/shared-types"],
  // Emit a self-contained server bundle for production Linux runtimes. On Windows local
  // builds, Next's standalone trace copy tries to create symlinks and often fails with
  // EPERM unless Developer Mode/admin privileges are enabled, so local Windows builds
  // intentionally skip standalone unless DOCOS_NEXT_STANDALONE=1 is set.
  ...(standaloneEnabled ? { output: "standalone" } : {}),
  // Next.js 14: tracing root lives under `experimental` (top-level key is Next 15+ only).
  experimental: {
    outputFileTracingRoot: monorepoRoot,
  },
  async headers() {
    return [{ source: "/:path*", headers: securityHeaders }];
  },
};

export default nextConfig;
