import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const monorepoRoot = path.join(__dirname, "../..");
const standaloneEnabled =
  process.env.DOCOS_NEXT_STANDALONE === "1" ||
  (process.platform !== "win32" && process.env.DOCOS_NEXT_STANDALONE !== "0");

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
};

export default nextConfig;
