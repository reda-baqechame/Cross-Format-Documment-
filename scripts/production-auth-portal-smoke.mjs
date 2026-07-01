#!/usr/bin/env node
/** Production canary: auth, owner transfer, and cross-session recipe/run isolation. */

const base = (process.env.DOCOS_PRODUCTION_URL || "https://docosweb-production.up.railway.app")
  .replace(/\/$/, "");
const expectedRevision = (process.env.DOCOS_EXPECTED_REVISION || process.env.GITHUB_SHA || "")
  .trim();

function cookieHeader(res) {
  if (typeof res.headers.getSetCookie === "function") {
    const parts = res.headers.getSetCookie().map((cookie) => cookie.split(";")[0]);
    if (parts.length) return parts.join("; ");
  }
  const raw = res.headers.get("set-cookie");
  return raw ? raw.split(";")[0] : "";
}

function mergeCookies(...headers) {
  const values = new Map();
  for (const header of headers) {
    for (const cookie of String(header || "").split(";")) {
      const trimmed = cookie.trim();
      const index = trimmed.indexOf("=");
      if (index > 0) values.set(trimmed.slice(0, index), trimmed.slice(index + 1));
    }
  }
  return [...values].map(([name, value]) => `${name}=${value}`).join("; ");
}

async function request(path, init = {}, cookies = "") {
  const headers = new Headers(init.headers || {});
  if (cookies) headers.set("Cookie", cookies);
  return fetch(`${base}${path}`, { ...init, headers, redirect: "follow" });
}

async function jsonResponse(response, label) {
  const text = await response.text();
  if (!response.ok) {
    throw new Error(`${label} returned ${response.status}: ${text.slice(0, 300)}`);
  }
  return JSON.parse(text);
}

function revisionsMatch(actual, expected) {
  if (!actual || !expected || actual === "unknown") return false;
  return actual === expected || (actual.length >= 7 && expected.startsWith(actual)) ||
    (expected.length >= 7 && actual.startsWith(expected));
}

async function main() {
  const health = await jsonResponse(await request("/api/health"), "/api/health");
  const revision = String(health.deployed_revision || "unknown");
  const migration = String(health.migration_head || "unknown");
  const openapi = await jsonResponse(await request("/api/openapi.json"), "/api/openapi.json");
  const hasAutopilot = Boolean(openapi.paths?.["/documents/{doc_id}/autopilot/run"]);
  if (
    expectedRevision &&
    !revisionsMatch(revision, expectedRevision) &&
    !(hasAutopilot && health.db === "ok")
  ) {
    throw new Error(
      `refusing canary against stale revision ${revision}; expected ${expectedRevision}`,
    );
  }
  if (migration !== "unknown" && Number(migration) < 12) {
    throw new Error(`expected migration 0012+, got ${migration}`);
  }

  // Create one isolated anonymous document and recipe. The response cookie is the ownership key.
  const form = new FormData();
  form.append(
    "file",
    new Blob(["Canary invoice 42. Total due $100. canary@example.com"], { type: "text/plain" }),
    `recipe-canary-${Date.now()}.txt`,
  );
  const upload = await request("/api/documents", { method: "POST", body: form });
  const anonCookies = cookieHeader(upload);
  const uploadBody = await jsonResponse(upload, "/documents upload");
  const docId = uploadBody.doc_id;
  if (!docId || !anonCookies) throw new Error("anonymous upload did not return doc_id + owner cookie");

  const create = await request(
    "/api/recipes",
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        name: `Production recipe canary ${Date.now()}`,
        trigger: "manual",
        steps: [{ tool: "classify" }, { tool: "sensitive_scan" }],
      }),
    },
    anonCookies,
  );
  const recipe = await jsonResponse(create, "/recipes create");

  const run = await request(
    `/api/recipes/${recipe.id}/run`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ doc_id: docId }),
    },
    anonCookies,
  );
  const runBody = await jsonResponse(run, "/recipes run");
  if (runBody.status !== "completed" || !runBody.run_id) {
    throw new Error("anonymous recipe run did not complete with a persisted run id");
  }
  const history = await jsonResponse(
    await request(`/api/recipes/${recipe.id}/runs`, {}, anonCookies),
    "/recipes history",
  );
  if (!history.some((item) => item.id === runBody.run_id)) {
    throw new Error("anonymous recipe run was not present in history");
  }
  console.log("[production-auth-smoke] ok anonymous recipe create/run/history");

  // A fresh anonymous session must not read either the recipe or the run.
  for (const path of [
    `/api/recipes/${recipe.id}`,
    `/api/recipes/${recipe.id}/runs`,
    `/api/recipes/${recipe.id}/runs/${runBody.run_id}`,
  ]) {
    const foreign = await request(path);
    if (foreign.status !== 404) {
      throw new Error(`${path} leaked across anonymous sessions (status ${foreign.status})`);
    }
  }
  console.log("[production-auth-smoke] ok anonymous cross-session isolation");

  // Register from the owning anonymous session; both recipe and run must transfer to the user.
  const email = `recipe_canary_${Date.now()}@example.com`;
  const password = "smoke-test-password-123";
  const register = await request(
    "/api/auth/register",
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password, name: "Recipe Canary" }),
    },
    anonCookies,
  );
  const registerBody = await jsonResponse(register, "/auth/register");
  if (registerBody.claimed?.workflow_recipes !== 1 || registerBody.claimed?.workflow_runs !== 1) {
    throw new Error(`recipe ownership was not claimed: ${JSON.stringify(registerBody.claimed)}`);
  }
  const ownerCookies = mergeCookies(anonCookies, cookieHeader(register));

  const me = await jsonResponse(await request("/api/auth/me", {}, ownerCookies), "/auth/me");
  if (me.email !== email) throw new Error("/auth/me did not return registered recipe owner");

  // Log in from a new browser session: user ownership (not the original session id) must work.
  const login = await request("/api/auth/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  await jsonResponse(login, "/auth/login");
  const loginCookies = cookieHeader(login);
  await jsonResponse(
    await request(`/api/recipes/${recipe.id}`, {}, loginCookies),
    "claimed recipe from fresh login",
  );
  await jsonResponse(
    await request(`/api/recipes/${recipe.id}/runs/${runBody.run_id}`, {}, loginCookies),
    "claimed run from fresh login",
  );
  console.log("[production-auth-smoke] ok registered ownership transfer + fresh login");

  const billing = await jsonResponse(
    await request("/api/billing/status", {}, loginCookies),
    "/billing/status",
  );
  if (billing.plan !== "free") throw new Error("expected free plan for canary user");

  const openapi = await jsonResponse(await request("/api/openapi.json"), "/openapi.json");
  const paths = openapi.paths || {};
  for (const path of [
    "/auth/register",
    "/auth/login",
    "/portal/{token}",
    "/portal/{token}/approve",
    "/documents/{doc_id}/shares",
    "/recipes/{recipe_id}/runs/{run_id}",
  ]) {
    if (!paths[path]) throw new Error(`OpenAPI missing ${path}`);
  }

  // Clean up canary content. The throwaway user remains because account deletion is not exposed.
  const deleteRecipe = await request(
    `/api/recipes/${recipe.id}`,
    { method: "DELETE" },
    loginCookies,
  );
  if (!deleteRecipe.ok) throw new Error(`recipe cleanup returned ${deleteRecipe.status}`);
  const deleteDocument = await request(
    `/api/documents/${docId}`,
    { method: "DELETE" },
    loginCookies,
  );
  if (deleteDocument.status !== 204) {
    throw new Error(`document cleanup returned ${deleteDocument.status}`);
  }

  console.log(
    `[production-auth-smoke] ${base} passed isolated recipe/auth canary at ` +
      `${health.deployed_revision}`,
  );
}

main().catch((err) => {
  console.error(`[production-auth-smoke] failed: ${err instanceof Error ? err.message : String(err)}`);
  process.exitCode = 1;
});
