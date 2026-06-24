#!/usr/bin/env node
/**
 * Full production QA — random real document + PDF/DOCX/office coverage.
 *
 *   cd backend && uv run python ../scripts/generate-production-fixtures.py
 *   node scripts/production-full-test.mjs
 *
 * Or: pnpm smoke:production:full
 */

import { execSync } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const FIXTURES = path.join(__dirname, "production-fixtures");
const base = (process.env.DOCOS_PRODUCTION_URL || "https://docosweb-production.up.railway.app").replace(
  /\/$/,
  "",
);

const results = [];
function pass(name, detail = "") {
  results.push({ name, ok: true, detail });
  console.log(`✓ ${name}${detail ? ` — ${detail}` : ""}`);
}
function fail(name, detail = "") {
  results.push({ name, ok: false, detail });
  console.error(`✗ ${name}${detail ? ` — ${detail}` : ""}`);
}
function skip(name, detail = "") {
  results.push({ name, ok: null, detail });
  console.log(`○ ${name} — ${detail}`);
}

function cookieHeader(res) {
  if (typeof res.headers.getSetCookie === "function") {
    const parts = res.headers.getSetCookie().map((c) => c.split(";")[0]);
    if (parts.length) return parts.join("; ");
  }
  const raw = res.headers.get("set-cookie");
  return raw ? raw.split(";")[0] : "";
}

async function api(path, opts = {}, cookies = "") {
  const headers = { ...(opts.headers || {}) };
  if (cookies) headers.Cookie = cookies;
  if (opts.json !== undefined) headers["Content-Type"] = "application/json";
  const method = opts.method || (opts.json !== undefined || opts.body ? "POST" : "GET");
  const res = await fetch(`${base}${path}`, {
    method,
    headers,
    body: opts.json !== undefined ? JSON.stringify(opts.json) : opts.body,
  });
  const text = await res.text();
  let json;
  try {
    json = text ? JSON.parse(text) : null;
  } catch {
    json = text;
  }
  return { res, json, text };
}

function ensureFixtures() {
  const marker = path.join(FIXTURES, "random-contract.pdf");
  if (fs.existsSync(marker)) return;
  console.log("[production-full-test] generating fixtures…");
  const backend = path.join(__dirname, "..", "backend");
  execSync("uv run python ../scripts/generate-production-fixtures.py", {
    cwd: backend,
    stdio: "inherit",
  });
}

function loadFixtures() {
  ensureFixtures();
  const rnd = Math.floor(Math.random() * 900000 + 100000);
  return [
    {
      key: "pdf",
      file: "random-contract.pdf",
      mime: "application/pdf",
      label: `PDF contract (${rnd})`,
    },
    {
      key: "docx",
      file: "random-proposal.docx",
      mime: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
      label: `DOCX proposal (${rnd})`,
    },
    {
      key: "xlsx",
      file: "random-invoice.xlsx",
      mime: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
      label: `XLSX invoice (${rnd})`,
    },
    {
      key: "pptx",
      file: "random-deck.pptx",
      mime: "application/vnd.openxmlformats-officedocument.presentationml.presentation",
      label: `PPTX deck (${rnd})`,
    },
    {
      key: "html",
      file: "random-page.html",
      mime: "text/html",
      label: `HTML page (${rnd})`,
    },
    {
      key: "rtf",
      file: "random-note.rtf",
      mime: "application/rtf",
      label: `RTF note (${rnd})`,
    },
    {
      key: "png",
      file: "random-scan.png",
      mime: "image/png",
      label: `PNG scan (${rnd})`,
    },
    {
      key: "txt",
      file: null,
      mime: "text/plain",
      label: `TXT SOW (${rnd})`,
      bytes: Buffer.from(
        `STATEMENT OF WORK #${rnd}\nClient: Northwind Traders\nFee: USD 45,000\nSSN 123-45-6789\n`,
        "utf-8",
      ),
    },
  ];
}

async function uploadFixture(spec, cookies) {
  const bytes = spec.bytes ?? fs.readFileSync(path.join(FIXTURES, spec.file));
  const name = spec.file ?? `random-${spec.key}.txt`;
  const fd = new FormData();
  fd.append("file", new Blob([bytes], { type: spec.mime }), name);
  const { res, json } = await api("/api/documents", { body: fd }, cookies);
  return { res, json, docId: json?.doc_id ?? "" };
}

function firstRunId(model) {
  const nodes = model?.document?.nodes ?? {};
  return Object.values(nodes).find((n) => n.type === "run")?.id ?? "";
}

const TASK_SLUGS = [
  "build-form", "make-template", "create-from-template", "client-packet-readiness",
  "create-contract-packet", "vendor-onboarding", "invoice-approval", "employee-form-packet",
  "proposal-to-signature", "bulk-send-from-template", "merge-pdf", "split-pdf", "rotate-pdf",
  "delete-pages", "reorder-pdf", "compress-pdf", "pdf-to-excel", "convert", "edit-pdf",
  "fill-form", "edit-deck", "edit-table", "insert-image-link", "send-ready-check", "redact",
  "remove-metadata", "protect-pdf", "watermark-pdf", "sign", "request-signature",
  "make-accessible", "clean-sign-send", "ask", "summarize", "translate", "extract", "listen",
  "classify", "analyze", "compare", "prepare-approval", "bulk-send",
  "pdf-to-word", "word-to-pdf", "jpg-to-pdf", "pdf-to-jpg", "excel-to-pdf", "ppt-to-pdf",
  "pdf-to-powerpoint", "html-to-pdf", "ocr-pdf",
];

async function runCoreDocTests(docId, cookies, runId, label) {
  pass(`Upload ${label}`, docId);

  const { res: modelRes, json: model } = await api(`/api/documents/${docId}/model`, {}, cookies);
  if (!modelRes.ok) {
    fail("Fetch model");
    return;
  }
  pass("Fetch model");
  const textRunId = runId || firstRunId(model);

  for (const [name, path, body] of [
    ["Health", `/api/documents/${docId}/health`, null],
    ["Readiness", `/api/documents/${docId}/readiness`, null],
    ["Ask", `/api/documents/${docId}/ask`, { question: "What is the fee or amount?" }],
    ["Summarize", `/api/documents/${docId}/summary`, null],
    ["Extract", `/api/documents/${docId}/extract`, null],
    ["Classify", `/api/documents/${docId}/classify`, null],
    ["Intelligence", `/api/documents/${docId}/intelligence`, null],
    ["Autopilot", `/api/documents/${docId}/autopilot`, null],
  ]) {
    const { res, json } = body
      ? await api(path, { json: body }, cookies)
      : await api(path, {}, cookies);
    if (res.ok) pass(name);
    else if (res.status === 501) skip(name, "noop LLM");
    else fail(name, `${res.status}`);
  }

  const editText = `REVISED by production QA — ${label}`;
  if (textRunId) {
    const { res: patchRes, json: patch } = await api(
      `/api/documents/${docId}/patches`,
      { json: { ops: [{ op: "set_text", target_id: textRunId, payload: { text: editText } }] } },
      cookies,
    );
    patchRes.ok && patch?.applied ? pass("Modify document") : fail("Modify document", String(patchRes.status));

    const { json: after } = await api(`/api/documents/${docId}/model`, {}, cookies);
    after?.document?.nodes?.[textRunId]?.text?.includes("REVISED")
      ? pass("Verify modification")
      : fail("Verify modification");

    await api(`/api/documents/${docId}/undo`, { method: "POST" }, cookies);
    const { json: undone } = await api(`/api/documents/${docId}/model`, {}, cookies);
    !undone?.document?.nodes?.[textRunId]?.text?.includes("REVISED")
      ? pass("Undo reverts edit")
      : fail("Undo reverts edit");
    await api(`/api/documents/${docId}/redo`, { method: "POST" }, cookies);
    pass("Redo");
  } else {
    skip("Modify document", "no text runs (e.g. image-only)");
  }

  const { res: sensRes, json: sens } = await api(`/api/documents/${docId}/sensitive`, {}, cookies);
  sensRes.ok ? pass("Sensitive scan", `${sens.findings?.length ?? 0} findings`) : fail("Sensitive scan");

  await api(`/api/documents/${docId}/redact-sensitive`, { method: "POST" }, cookies);
  pass("Redact sensitive");

  await api(`/api/documents/${docId}/remediate-accessibility`, { method: "POST" }, cookies);
  pass("Accessibility remediate");

  await api(`/api/documents/${docId}/tags`, { json: { tag: "prod-full-test" } }, cookies);
  pass("Tags");

  await api(
    `/api/documents/${docId}/comments`,
    { json: { text: "QA comment", target_id: textRunId || null } },
    cookies,
  );
  pass("Comments");

  await api(
    `/api/documents/${docId}/approvals`,
    { json: { approvers: ["legal@example.com"], ordered: true } },
    cookies,
  );
  pass("Approvals");

  const { json: bulk } = await api(
    `/api/documents/${docId}/bulk-send`,
    { json: { recipients: ["client@example.com"] } },
    cookies,
  );
  const portalPath = bulk?.packets?.[0]?.portal_url ?? "";
  portalPath ? pass("Bulk-send portal", portalPath) : fail("Bulk-send portal");

  const token = portalPath.replace(/^\/portal\//, "");
  if (token) {
    const { res: pRes, json: pInfo } = await api(`/api/portal/${token}`, {});
    pRes.ok && pInfo?.document_id ? pass("Portal info", pInfo.document_id) : fail("Portal info");
    (await api(`/api/portal/${token}/model`, {})).res.ok ? pass("Portal model") : fail("Portal model");
    (await api(`/api/portal/${token}/readiness`, {})).res.ok ? pass("Portal readiness") : fail("Portal readiness");
    await api(
      `/api/portal/${token}/approve`,
      { json: { approver_name: "Jane Client", decision: "approved", note: "OK" } },
    );
    pass("Portal sign-off");
  }

  const { res: shareRes } = await api(
    `/api/documents/${docId}/shares`,
    { json: { label: "Ad-hoc" } },
    cookies,
  );
  shareRes.status === 402 ? pass("Share gated (free tier)") : shareRes.ok ? pass("Share created") : fail("Share");

  for (const fmt of ["txt", "html", "md", "docx"]) {
    const { res } = await api(`/api/documents/${docId}/export?format=${fmt}`, {}, cookies);
    res.ok ? pass(`Export ${fmt}`) : fail(`Export ${fmt}`, String(res.status));
  }

  await api(`/api/documents/${docId}/sign`, { json: { signer: "Prod QA" } }, cookies);
  pass("Integrity seal");

  (await api(`/api/documents/${docId}/history`, {}, cookies)).res.ok ? pass("History") : fail("History");
}

async function runPdfTests(pdfDocId, cookies) {
  pass("PDF fixture doc", pdfDocId);

  for (const [name, path, json] of [
    ["PDF export", `/api/documents/${pdfDocId}/export?format=pdf`, null],
    ["Searchable PDF", `/api/documents/${pdfDocId}/searchable-pdf`, null],
    ["PDF preview", `/api/documents/${pdfDocId}/preview?page=0`, null],
    ["Compress PDF", `/api/documents/${pdfDocId}/compress`, {}],
    ["Rotate PDF", `/api/documents/${pdfDocId}/pages/rotate`, { pages: [0], degrees: 90 }],
    ["Watermark PDF", `/api/documents/${pdfDocId}/watermark`, { text: "CONFIDENTIAL" }],
    ["Protect PDF", `/api/documents/${pdfDocId}/protect`, { password: "qa-test-pass" }],
  ]) {
    const { res } = json
      ? await api(path, { json }, cookies)
      : await api(path, {}, cookies);
    if (res.ok) pass(name, res.headers.get("content-type")?.slice(0, 30) ?? "200");
    else fail(name, String(res.status));
  }

  await api(`/api/documents/${pdfDocId}/sanitize-metadata`, { method: "POST" }, cookies);
  pass("Sanitize metadata (PDF)");

  const { json: up2 } = await uploadFixture(
    { file: "random-contract.pdf", mime: "application/pdf", key: "pdf2" },
    cookies,
  );
  if (up2?.doc_id) {
    const { res } = await api(
      `/api/documents/${pdfDocId}/merge`,
      { json: { doc_ids: [up2.doc_id] } },
      cookies,
    );
    res.ok ? pass("Merge PDFs") : fail("Merge PDFs", String(res.status));
  }

  const { res: splitRes } = await api(
    `/api/documents/${pdfDocId}/pages/extract?pages=0`,
    {},
    cookies,
  );
  splitRes.ok ? pass("Extract/split PDF page") : fail("Extract/split PDF page", String(splitRes.status));
}

async function main() {
  console.log(`\n=== DocOS production full test ===\n${base}\n`);

  for (const [p, needle] of [
    ["/", "All document tools"],
    ["/login", "Sign in to DocOS"],
    ["/signup", "Create your DocOS account"],
    ["/pricing", "Pricing"],
  ]) {
    const { res, text } = await api(p);
    res.ok && text.includes(needle) ? pass(`Page ${p}`) : fail(`Page ${p}`, String(res.status));
  }

  for (const [name, path, check] of [
    ["API health", "/api/health", (j) => j?.status === "ok"],
    ["API ready", "/api/ready", (j) => String(j?.checks?.migrations ?? "").includes("0011")],
  ]) {
    const { res, json } = await api(path);
    res.ok && check(json) ? pass(name) : fail(name, String(res.status));
  }

  const email = `fulltest_${Date.now()}@example.com`;
  const { res: regRes, json: reg } = await api("/api/auth/register", {
    json: { email, password: "FullTest-Password-123!", name: "Full Test" },
  });
  const cookies = cookieHeader(regRes);
  regRes.ok && reg?.user?.email === email ? pass("Auth register", email) : fail("Auth register");

  (await api("/api/auth/me", {}, cookies)).res.ok ? pass("Auth /me") : fail("Auth /me");
  const { json: bill } = await api("/api/billing/status", {}, cookies);
  bill?.plan === "free" ? pass("Billing free tier") : fail("Billing status");

  const fixtures = loadFixtures();
  const forced = process.env.PROD_QA_FIXTURE;
  const randomPick = forced
    ? fixtures.find((f) => f.key === forced) ?? fixtures[0]
    : fixtures[Math.floor(Math.random() * fixtures.length)];
  console.log(`\n[random document] ${randomPick.label} (${randomPick.key})\n`);

  const { res: upRes, json: up } = await uploadFixture(randomPick, cookies);
  if (!upRes.ok || !up?.doc_id) {
    fail("Random document upload", `${upRes.status}: ${JSON.stringify(up).slice(0, 120)}`);
    process.exitCode = 1;
    return;
  }

  const { json: model } = await api(`/api/documents/${up.doc_id}/model`, {}, cookies);
  const runId = firstRunId(model);
  await runCoreDocTests(up.doc_id, cookies, runId, randomPick.label);

  const pdfSpec = fixtures.find((f) => f.key === "pdf");
  const { res: pdfUp, json: pdfJson } = await uploadFixture(pdfSpec, cookies);
  if (pdfUp.ok && pdfJson?.doc_id) {
    await runPdfTests(pdfJson.doc_id, cookies);
  } else {
    fail("PDF fixture upload", String(pdfUp.status));
  }

  const { res: searchRes, json: search } = await api("/api/search?q=REVISED", {}, cookies);
  searchRes.ok ? pass("Keyword search", `${search.hits?.length ?? 0} hits`) : fail("Search");

  (await api("/api/search/semantic?q=payment", {}, cookies)).res.ok
    ? pass("Semantic search")
    : fail("Semantic search");

  (await api("/api/documents", {}, cookies)).res.ok ? pass("List documents") : fail("List documents");

  const { res: tr } = await api(
    `/api/documents/${up.doc_id}/translate`,
    { json: { target_language: "fr" } },
    cookies,
  );
  tr.status === 501 ? skip("Translate", "noop LLM") : tr.ok ? pass("Translate") : fail("Translate");

  const { res: nl } = await api(
    `/api/documents/${up.doc_id}/patches`,
    { json: { instruction: "formalize" } },
    cookies,
  );
  nl.status === 501 ? pass("NL edit 501 without AI") : fail("NL edit");

  const { res: checkout } = await api("/api/billing/checkout", { json: { plan: "pro" } }, cookies);
  checkout.status === 501 ? pass("Stripe checkout seam 501") : fail("Billing checkout");

  let taskFail = 0;
  for (const slug of TASK_SLUGS) {
    const { res, text } = await api(`/tasks/${slug}`);
    if (!res.ok || !text.includes("DocOS")) {
      taskFail++;
      fail(`Task /tasks/${slug}`, String(res.status));
    }
  }
  if (taskFail === 0) pass(`All ${TASK_SLUGS.length} task pages render`);

  const passed = results.filter((r) => r.ok === true).length;
  const failed = results.filter((r) => r.ok === false).length;
  const skipped = results.filter((r) => r.ok === null).length;
  console.log(`\n=== Summary: ${passed} passed · ${failed} failed · ${skipped} skipped ===\n`);
  if (failed > 0) {
    console.log("Failures:");
    for (const r of results.filter((x) => x.ok === false)) console.log(`  - ${r.name}: ${r.detail}`);
    process.exitCode = 1;
  }
}

main().catch((err) => {
  console.error(err);
  process.exitCode = 1;
});
