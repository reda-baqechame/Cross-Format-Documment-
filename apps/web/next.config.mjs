import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const monorepoRoot = path.join(__dirname, "../..");

/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // The canonical-model types are shared from a workspace package (transpiled here).
  transpilePackages: ["@docos/shared-types"],
  // Emit a self-contained server bundle for a small production runtime image.
  output: "standalone",
  // Next.js 14: tracing root lives under `experimental` (top-level key is Next 15+ only).
  experimental: {
    outputFileTracingRoot: monorepoRoot,
  },
};

export default nextConfig;
