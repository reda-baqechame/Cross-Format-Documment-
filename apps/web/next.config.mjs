import path from "node:path";

/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // The canonical-model types are shared from a workspace package (transpiled here).
  transpilePackages: ["@docos/shared-types"],
  // Emit a self-contained server bundle for a small production runtime image.
  output: "standalone",
  // Trace workspace files from the monorepo root so standalone includes them.
  outputFileTracingRoot: path.join(import.meta.dirname, "../../"),
};

export default nextConfig;
