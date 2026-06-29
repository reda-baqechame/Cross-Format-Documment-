#!/usr/bin/env node
/** Revision-aware, read-only production smoke for the public Railway app. */

const base = (process.env.DOCOS_PRODUCTION_URL || "https://docosweb-production.up.railway.app")
  .replace(/\/$/, "");
const expectedRevision = (process.env.DOCOS_EXPECTED_REVISION || process.env.GITHUB_SHA || "")
  .trim();
const deployTimeoutMs = Number(process.env.DOCOS_DEPLOY_TIMEOUT_MS || 10 * 60_000);
const pollIntervalMs = Number(process.env.DOCOS_DEPLOY_POLL_MS || 10_000);

function revisionsMatch(actual, expected) {
  if (!actual || !expected || actual === "unknown") return false;
  return actual === expected || (actual.length >= 7 && expected.startsWith(actual)) ||
    (expected.length >= 7 && actual.startsWith(expected));
}

async function getJson(path) {
  const separator = path.includes("?") ? "&" : "?";
  const res = await fetch(`${base}${path}${separator}_smoke=${Date.now()}`, {
    redirect: "follow",
    cache: "no-store",
    headers: { "Cache-Control": "no-cache" },
  });
  const text = await res.text();
  if (!res.ok) throw new Error(`${path} returned ${res.status}: ${text.slice(0, 200)}`);
  return JSON.parse(text);
}

async function waitForExpectedDeployment() {
  const deadline = Date.now() + deployTimeoutMs;
  let last = "no health response";
  while (Date.now() < deadline) {
    try {
      const health = await getJson("/api/health");
      const revision = String(health.deployed_revision || "unknown");
      last = `revision=${revision} migration=${health.migration_head || "unknown"}`;
      if (expectedRevision ? revisionsMatch(revision, expectedRevision) : revision !== "unknown") {
        console.log(`[production-smoke] expected deployment is live (${last})`);
        return health;
      }
    } catch (error) {
      last = error instanceof Error ? error.message : String(error);
    }
    console.log(`[production-smoke] waiting for Railway: ${last}`);
    await new Promise((resolve) => setTimeout(resolve, pollIntervalMs));
  }
  throw new Error(
    `Railway did not serve expected revision ${expectedRevision || "<reported revision>"} ` +
      `within ${deployTimeoutMs}ms; last observed ${last}`,
  );
}

async function requireOk(path, check) {
  const res = await fetch(`${base}${path}`, { redirect: "follow", cache: "no-store" });
  const text = await res.text();
  if (!res.ok) throw new Error(`${path} returned ${res.status}: ${text.slice(0, 200)}`);
  if (check) check(text, res);
  console.log(`[production-smoke] ok ${path}`);
}

function requireMigration0012OrLater(value) {
  const match = String(value || "").match(/^(\d+)$/);
  if (!match || Number(match[1]) < 12) {
    throw new Error(`expected migration 0012 or later, got ${value || "missing"}`);
  }
}

async function main() {
  const health = await waitForExpectedDeployment();
  if (health.status !== "ok" || health.db !== "ok") {
    throw new Error(`health not ok: ${JSON.stringify(health)}`);
  }
  if (health.ai_enabled !== false || health.llm_provider !== "noop") {
    throw new Error("provider-free production must report AI disabled with llm_provider=noop");
  }
  requireMigration0012OrLater(health.migration_head);

  await requireOk("/", (text) => {
    for (const needle of [
      "All document tools",
      "Client Packet Readiness",
      "Client contract packet",
      "Invoice and deposit review",
    ]) {
      if (!text.includes(needle)) throw new Error(`home page missing "${needle}"`);
    }
  });

  await requireOk("/login", (text) => {
    if (!text.includes("Sign in to DocOS")) throw new Error("login page missing branding");
  });
  await requireOk("/pricing", (text) => {
    if (!text.includes("Pricing")) throw new Error("pricing page missing heading");
  });

  const ready = await getJson("/api/ready");
  if (!ready.ok) throw new Error(`readiness not ok: ${JSON.stringify(ready)}`);
  if (!revisionsMatch(ready.deployed_revision, health.deployed_revision)) {
    throw new Error("/health and /ready disagree on the deployed revision");
  }
  requireMigration0012OrLater(ready.migration_head);

  const capabilities = await getJson("/api/capabilities");
  const byId = Object.fromEntries(
    (capabilities.capabilities || []).map((capability) => [capability.id, capability]),
  );
  if (byId.workflow_recipes?.state !== "verified") {
    throw new Error("workflow recipes are not enabled in the live capability ledger");
  }
  for (const id of ["ai_ask_summarize", "ai_edit"]) {
    if (byId[id]?.state !== "provider_gated") {
      throw new Error(`${id} must remain provider_gated without credentials`);
    }
  }
  if (capabilities.database === "sqlite" && byId.upload_store?.state !== "degraded") {
    throw new Error("SQLite/local storage must be explicitly degraded in /capabilities");
  }

  await requireOk("/api/openapi.json", (text) => {
    const paths = JSON.parse(text).paths || {};
    for (const path of [
      "/capabilities",
      "/documents/{doc_id}/agent",
      "/packs/insurance/check",
      "/recipes",
      "/recipes/{recipe_id}",
      "/recipes/{recipe_id}/runs",
      "/recipe-tools",
    ]) {
      if (!paths[path]) throw new Error(`OpenAPI missing ${path}`);
    }
  });

  console.log(
    `[production-smoke] ${base} passed at revision ${health.deployed_revision} ` +
      `migration ${health.migration_head}`,
  );
}

main().catch((err) => {
  console.error(`[production-smoke] failed: ${err instanceof Error ? err.message : String(err)}`);
  process.exitCode = 1;
});
