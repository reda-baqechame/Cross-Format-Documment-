#!/usr/bin/env node
/** Production smoke: auth registration, billing seam, share/portal OpenAPI routes. */

const base = (process.env.DOCOS_PRODUCTION_URL || "https://docosweb-production.up.railway.app")
  .replace(/\/$/, "");

function cookieHeader(res) {
  if (typeof res.headers.getSetCookie === "function") {
    const parts = res.headers.getSetCookie().map((c) => c.split(";")[0]);
    if (parts.length) return parts.join("; ");
  }
  const raw = res.headers.get("set-cookie");
  return raw ? raw.split(";")[0] : "";
}

async function main() {
  const email = `smoke_${Date.now()}@example.com`;
  const password = "smoke-test-password-123";

  const register = await fetch(`${base}/api/auth/register`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password, name: "Smoke Test" }),
  });
  const regText = await register.text();
  if (!register.ok) {
    throw new Error(`/auth/register returned ${register.status}: ${regText.slice(0, 200)}`);
  }
  const regBody = JSON.parse(regText);
  if (!regBody.user?.email || regBody.user.email !== email) {
    throw new Error("register response missing user email");
  }
  console.log("[production-auth-smoke] ok register");

  const cookies = cookieHeader(register);
  const me = await fetch(`${base}/api/auth/me`, {
    headers: cookies ? { Cookie: cookies } : {},
  });
  if (!me.ok) throw new Error(`/auth/me returned ${me.status}`);
  const meBody = await me.json();
  if (meBody?.email !== email) throw new Error("/auth/me did not return registered user");
  console.log("[production-auth-smoke] ok /auth/me");

  const billing = await fetch(`${base}/api/billing/status`, {
    headers: cookies ? { Cookie: cookies } : {},
  });
  if (!billing.ok) throw new Error(`/billing/status returned ${billing.status}`);
  const billingBody = await billing.json();
  if (billingBody.plan !== "free") throw new Error("expected free plan for new user");
  console.log("[production-auth-smoke] ok billing/status (plan=free)");

  const openapi = await fetch(`${base}/api/openapi.json`);
  if (!openapi.ok) throw new Error("openapi.json unavailable");
  const schema = await openapi.json();
  const paths = schema.paths || {};
  for (const path of [
    "/auth/register",
    "/auth/login",
    "/portal/{token}",
    "/portal/{token}/approve",
    "/documents/{doc_id}/shares",
  ]) {
    if (!paths[path]) throw new Error(`OpenAPI missing ${path}`);
  }
  console.log("[production-auth-smoke] ok OpenAPI auth/share/portal routes");

  const ready = await fetch(`${base}/api/ready`);
  const readyText = await ready.text();
  if (!ready.ok) throw new Error(`/api/ready returned ${ready.status}: ${readyText.slice(0, 200)}`);
  const readyBody = JSON.parse(readyText);
  const migrations = readyBody.checks?.migrations ?? "";
  if (!String(migrations).includes("0011")) {
    throw new Error(`expected migration 0011 in ready checks, got: ${migrations}`);
  }
  console.log("[production-auth-smoke] ok /api/ready (migration 0011)");

  console.log(`[production-auth-smoke] ${base} passed auth + billing + portal seam checks`);
}

main().catch((err) => {
  console.error(`[production-auth-smoke] failed: ${err instanceof Error ? err.message : String(err)}`);
  process.exitCode = 1;
});
