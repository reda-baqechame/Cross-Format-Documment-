#!/usr/bin/env node
// Production smoke: expert packet audit — create packet, run audit, assert blocking finding.

const base = (process.env.DOCOS_PRODUCTION_URL || "https://docosweb-production.up.railway.app")
  .replace(/\/$/, "");

const invoice =
  "Commercial Invoice\nInvoice No: SMOKE-1\nTotal: CAD 14,920.00\n";
const po = "Purchase Order\nPO No: SMOKE-PO\nTotal: CAD 13,780.00\n";

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
  const health = await readJson(await fetch(`${base}/api/health`), "health");
  if (health.deployed_revision === "unknown") {
    console.warn(
      "[packet-smoke] deployed_revision=unknown — set RAILWAY_GIT_COMMIT_SHA on Railway (see docs/railway.md)",
    );
  }

  let cookies = "";
  async function api(path, init = {}) {
    const res = await fetch(`${base}/api${path}`, {
      ...init,
      headers: {
        ...(init.headers || {}),
        ...(cookies ? { Cookie: cookies } : {}),
      },
    });
    const set = cookieHeader(res.headers);
    if (set) cookies = cookies ? `${cookies}; ${set}` : set;
    return res;
  }

  const docIds = [];
  try {
    for (const [name, text] of [
      ["invoice.txt", invoice],
      ["po.txt", po],
    ]) {
      const form = new FormData();
      form.append("file", new Blob([text], { type: "text/plain" }), name);
      const upload = await readJson(await api("/documents", { method: "POST", body: form }), `upload ${name}`);
      if (!upload.doc_id) throw new Error(`upload ${name} missing doc_id`);
      docIds.push(upload.doc_id);
    }

    const packet = await readJson(
      await api("/packets", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: "production-packet-smoke", pack: "import_export" }),
      }),
      "create packet",
    );
    const packetId = packet.id || packet.packet_id;
    if (!packetId) throw new Error("create packet did not return id");

    await readJson(
      await api(`/packets/${packetId}/documents`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ document_ids: docIds }),
      }),
      "add documents",
    );

    await readJson(await api(`/packets/${packetId}/audit`, { method: "POST" }), "audit");

    const report = await readJson(await api(`/packets/${packetId}/report`), "report");
    const verdict = report.result?.verdict || report.verdict;
    if (verdict !== "blocked") {
      throw new Error(`expected blocked verdict, got ${verdict}`);
    }
    const findings = report.result?.findings || report.findings || [];
    const blocking = findings.filter((f) => f.severity === "blocking");
    if (blocking.length === 0) {
      throw new Error("expected at least one blocking finding");
    }

    console.log(
      `[packet-smoke] ${packetId} blocked with ${blocking.length} finding(s) (revision=${health.deployed_revision})`,
    );
  } finally {
    for (const docId of docIds) {
      const deleteRes = await api(`/documents/${docId}`, { method: "DELETE" });
      if (!deleteRes.ok && deleteRes.status !== 404) {
        const text = await deleteRes.text();
        console.warn(`[packet-smoke] cleanup ${docId}: ${deleteRes.status} ${text.slice(0, 120)}`);
      }
    }
  }
}

main().catch((err) => {
  console.error(`[packet-smoke] failed: ${err instanceof Error ? err.message : String(err)}`);
  process.exitCode = 1;
});
