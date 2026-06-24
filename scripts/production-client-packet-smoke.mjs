#!/usr/bin/env node
// Mutating production proof for the SMB/agency client-packet wedge.
// Uploads a tiny throwaway proposal, verifies the business-readiness checks, then deletes it.

const base = (process.env.DOCOS_PRODUCTION_URL || "https://docosweb-production.up.railway.app")
  .replace(/\/$/, "");

const sample = [
  "Proposal for client website service.",
  "We can start after approval.",
].join(" ");

const expectedWarns = [
  "scope_clarity",
  "payment_terms",
  "signature_acceptance",
  "client_onboarding",
  "scope_change_control",
];

function cookieHeader(headers) {
  const getSetCookie =
    typeof headers.getSetCookie === "function" ? headers.getSetCookie.bind(headers) : null;
  const raw = getSetCookie ? getSetCookie() : [headers.get("set-cookie")].filter(Boolean);
  return raw.map((line) => line.split(";")[0]).join("; ");
}

async function readJson(res, label) {
  const text = await res.text();
  if (!res.ok) {
    throw new Error(`${label} returned ${res.status}: ${text.slice(0, 300)}`);
  }
  return JSON.parse(text);
}

async function main() {
  const form = new FormData();
  form.append(
    "file",
    new Blob([sample], { type: "text/plain" }),
    "agency-client-packet-smoke.txt",
  );

  const uploadRes = await fetch(`${base}/api/documents`, {
    method: "POST",
    body: form,
  });
  const cookies = cookieHeader(uploadRes.headers);
  const upload = await readJson(uploadRes, "upload");
  if (!upload.doc_id) throw new Error(`upload did not return doc_id: ${JSON.stringify(upload)}`);

  try {
    const readinessRes = await fetch(`${base}/api/documents/${upload.doc_id}/readiness`, {
      headers: cookies ? { Cookie: cookies } : {},
    });
    const readiness = await readJson(readinessRes, "readiness");
    const checks = new Map(readiness.report.checks.map((check) => [check.id, check]));

    if (readiness.report.verdict !== "needs_fixes") {
      throw new Error(`expected needs_fixes, got ${readiness.report.verdict}`);
    }

    for (const id of expectedWarns) {
      const check = checks.get(id);
      if (!check) throw new Error(`missing readiness check ${id}`);
      if (check.status !== "warn") throw new Error(`${id} expected warn, got ${check.status}`);
      if (check.fixable) throw new Error(`${id} should not claim an automatic fix`);
    }

    console.log(
      `[client-packet-smoke] ${upload.doc_id} returned ${expectedWarns.length} business warnings`,
    );
  } finally {
    const deleteRes = await fetch(`${base}/api/documents/${upload.doc_id}`, {
      method: "DELETE",
      headers: cookies ? { Cookie: cookies } : {},
    });
    if (!deleteRes.ok && deleteRes.status !== 404) {
      const text = await deleteRes.text();
      throw new Error(`cleanup returned ${deleteRes.status}: ${text.slice(0, 300)}`);
    }
    console.log(`[client-packet-smoke] cleaned up ${upload.doc_id}`);
  }
}

main().catch((err) => {
  console.error(`[client-packet-smoke] failed: ${err instanceof Error ? err.message : String(err)}`);
  process.exitCode = 1;
});
