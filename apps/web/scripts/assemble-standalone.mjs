// Assemble the Next.js standalone output so `node .next/standalone/apps/web/server.js`
// can serve a complete app. `output: "standalone"` does NOT copy `.next/static` or
// `public/` into the standalone tree (Next leaves that to the deployer — our Dockerfile
// does it via COPY). This makes `pnpm start` work the same way on platforms that build
// with nixpacks/buildpacks (e.g. Railway) instead of the Dockerfile.
//
// Safe to run repeatedly; a no-op if the standalone output is missing.

import { cpSync, existsSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const webRoot = dirname(fileURLToPath(import.meta.url)) + "/..";
const standaloneWeb = join(webRoot, ".next/standalone/apps/web");

if (!existsSync(standaloneWeb)) {
  console.warn("[assemble-standalone] no standalone output — skipping (is output:'standalone' set?)");
  process.exit(0);
}

// Static assets (JS/CSS chunks) → served from <standalone>/apps/web/.next/static
const staticSrc = join(webRoot, ".next/static");
if (existsSync(staticSrc)) {
  cpSync(staticSrc, join(standaloneWeb, ".next/static"), { recursive: true });
  console.log("[assemble-standalone] copied .next/static");
}

// Optional public/ assets → served from <standalone>/apps/web/public
const publicSrc = join(webRoot, "public");
if (existsSync(publicSrc)) {
  cpSync(publicSrc, join(standaloneWeb, "public"), { recursive: true });
  console.log("[assemble-standalone] copied public/");
}
