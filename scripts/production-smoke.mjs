#!/usr/bin/env node
/** Revision-aware, read-only production smoke for the public Railway app. */

const base = (process.env.DOCOS_PRODUCTION_URL || "https://docosweb-production.up.railway.app")
  .replace(/\/$/, "");
const expectedRevision = (process.env.DOCOS_EXPECTED_REVISION || process.env.GITHUB_SHA || "")
  .trim();
const deployTimeoutMs = Number(process.env.DOCOS_DEPLOY_TIMEOUT_MS || 10 * 60_000);
const pollIntervalMs = Number(process.env.DOCOS_DEPLOY_POLL_MS || 10_000);

const REQUIRED_OPENAPI_PATHS = [
  "/capabilities",
  "/documents/{doc_id}/agent",
  "/packs/insurance/check",
  "/recipes",
  "/recipes/{recipe_id}",
  "/recipes/{recipe_id}/runs",
  "/recipe-tools",
  "/documents/{doc_id}/proof-report",
  "/documents/{doc_id}/autopilot/run",
  "/jobs/batch-clean",
];

function revisionsMatch(actual, expected) {
  if (!actual || !expected || actual === "unknown") return false;
  return (
    actual === expected ||
    (actual.length >= 7 && expected.startsWith(actual)) ||
    (expected.length >= 7 && actual.startsWith(expected))
  );
}

function openapiFeaturesReady(openapi) {
  const paths = openapi?.paths || {};
  return REQUIRED_OPENAPI_PATHS.every((path) => Boolean(paths[path]));
}

function requireMigration0012OrLater(value) {
  const match = String(value || "").match(/^(\d+)$/);
  if (!match || Number(match[1]) < 12) {
    throw new Error(`expected migration 0012 or later, got ${value || "missing"}`);
  }
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
      const migration = String(health.migration_head || "unknown");
      last = `revision=${revision} migration=${migration}`;

      let openapi = null;
      try {
        openapi = await getJson("/api/openapi.json");
      } catch {
        /* stale or booting */
      }
      const features = openapiFeaturesReady(openapi);
      const migrationOk = migration !== "unknown" && migration !== "untracked";

      if (expectedRevision && revisionsMatch(revision, expectedRevision)) {
        console.log(`[production-smoke] expected deployment is live (${last})`);
        return health;
      }

      if (
        features &&
        health.status === "ok" &&
        health.db === "ok" &&
        migrationOk &&
        Number(migration) >= 12
      ) {
        if (revision === "unknown" || !expectedRevision) {
          console.warn(
            `[production-smoke] feature-ready deployment (${last}); ` +
              "revision not reported — see docs/railway.md",
          );
          return health;
        }
      }
    } catch (error) {
      last = error instanceof Error ? error.message : String(error);
    }
    console.log(`[production-smoke] waiting for Railway: ${last}`);
    await new Promise((resolve) => setTimeout(resolve, pollIntervalMs));
  }
  throw new Error(
    `Railway did not serve expected revision ${expectedRevision || "<reported revision>"} ` +
      `or DocumentOps feature paths within ${deployTimeoutMs}ms; last observed ${last}`,
  );
}

async function requireOk(path, check) {
  const res = await fetch(`${base}${path}`, { redirect: "follow", cache: "no-store" });
  const text = await res.text();
  if (!res.ok) throw new Error(`${path} returned ${res.status}: ${text.slice(0, 200)}`);
  if (check) check(text, res);
  console.log(`[production-smoke] ok ${path}`);
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
  if (
    health.deployed_revision &&
    health.deployed_revision !== "unknown" &&
    !revisionsMatch(ready.deployed_revision, health.deployed_revision)
  ) {
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
  if (byId.document_ops_autopilot?.state !== "verified") {
    throw new Error("document_ops_autopilot is not verified in /capabilities");
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
    for (const path of REQUIRED_OPENAPI_PATHS) {
      if (!paths[path]) throw new Error(`OpenAPI missing ${path}`);
    }
  });

  console.log(
    `[production-smoke] ${base} passed at revision ${health.deployed_revision || "feature-ready"} ` +
      `migration ${health.migration_head}`,
  );
}

main().catch((err) => {
  console.error(`[production-smoke] failed: ${err instanceof Error ? err.message : String(err)}`);
  process.exitCode = 1;
});
