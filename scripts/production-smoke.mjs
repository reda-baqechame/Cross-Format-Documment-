#!/usr/bin/env node
// Read-only production smoke for the public Railway app. It never uploads files or
// creates documents; mutating release tests belong in staging.

const base = (process.env.DOCOS_PRODUCTION_URL || "https://docosweb-production.up.railway.app")
  .replace(/\/$/, "");
const requireHardeningOpenApi = process.env.DOCOS_REQUIRE_HARDENING_OPENAPI === "1";

async function requireOk(path, check) {
  const res = await fetch(`${base}${path}`, { redirect: "follow" });
  const text = await res.text();
  if (!res.ok) {
    throw new Error(`${path} returned ${res.status}: ${text.slice(0, 200)}`);
  }
  if (check) check(text, res);
  console.log(`[production-smoke] ok ${path}`);
}

async function main() {
  await requireOk("/", (text) => {
    for (const needle of [
      "All document tools",
      "Client Packet Readiness",
      "Client contract packet",
    ]) {
      if (!text.includes(needle)) throw new Error(`home page missing "${needle}"`);
    }
    if (requireHardeningOpenApi && !text.includes("Invoice and deposit review")) {
      throw new Error('home page missing "Invoice and deposit review"');
    }
  });

  await requireOk("/api/health", (text) => {
    const health = JSON.parse(text);
    if (health.status !== "ok" || health.db !== "ok") {
      throw new Error(`health not ok: ${text}`);
    }
  });

  await requireOk("/api/openapi.json", (text) => {
    const schema = JSON.parse(text);
    const paths = schema.paths || {};
    for (const path of [
      "/documents/{doc_id}/editor/session",
      "/documents/{doc_id}/ops-agent/plan",
      "/documents/{doc_id}/fields/detect",
      "/documents/{doc_id}/workflows/preview",
      "/documents/{doc_id}/workflows/execute",
    ]) {
      if (!paths[path]) {
        const message = `OpenAPI missing ${path}`;
        if (requireHardeningOpenApi) throw new Error(message);
        console.warn(`[production-smoke] warn ${message}`);
      }
    }
  });

  console.log(`[production-smoke] ${base} passed read-only smoke checks`);
}

main().catch((err) => {
  console.error(`[production-smoke] failed: ${err instanceof Error ? err.message : String(err)}`);
  process.exitCode = 1;
});
