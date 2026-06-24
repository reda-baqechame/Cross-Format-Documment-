#!/usr/bin/env node
/**
 * Exhaustive production tool matrix — every API surface + real user document.
 * Usage: node scripts/production-tool-matrix.mjs [path-to.pdf]
 */

import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const base = (process.env.DOCOS_PRODUCTION_URL || "https://docosweb-production.up.railway.app").replace(/\/$/, "");
const FIX = path.join(__dirname, "production-fixtures");
const USER_PDF =
  process.argv[2] ||
  process.env.PROD_QA_USER_PDF ||
  "C:\\Users\\redab\\Downloads\\myte codi text\\myte cody text project.pdf";

const R = [];
const ok = (n, d = "") => { R.push({ n, s: "ok", d }); console.log(`✓ ${n}${d ? ` — ${d}` : ""}`); };
const bad = (n, d = "") => { R.push({ n, s: "fail", d }); console.error(`✗ ${n}${d ? ` — ${d}` : ""}`); };
const skip = (n, d = "") => { R.push({ n, s: "skip", d }); console.log(`○ ${n} — ${d}`); };
const expect = (n, d = "") => { R.push({ n, s: "expect", d }); console.log(`◦ ${n} — ${d}`); };

function jar(res) {
  if (typeof res.headers.getSetCookie === "function") {
    const p = res.headers.getSetCookie().map((c) => c.split(";")[0]);
    if (p.length) return p.join("; ");
  }
  const raw = res.headers.get("set-cookie");
  return raw ? raw.split(";")[0] : "";
}

async function api(path, opts = {}, cookies = "") {
  const headers = { ...(opts.headers || {}) };
  if (cookies) headers.Cookie = cookies;
  if (opts.json !== undefined) headers["Content-Type"] = "application/json";
  const method = opts.method || (opts.json !== undefined || opts.body ? "POST" : "GET");
  const res = await fetch(`${base}${path}`, { method, headers, body: opts.json !== undefined ? JSON.stringify(opts.json) : opts.body });
  const buf = await res.arrayBuffer();
  const text = Buffer.from(buf).toString("utf8");
  let json;
  try { json = JSON.parse(text); } catch { json = text; }
  return { res, json, text };
}

async function waitForBackend(maxMs = 30_000) {
  const start = Date.now();
  while (Date.now() - start < maxMs) {
    try {
      const { res } = await api("/api/health");
      if (res.ok) return true;
    } catch { /* retry */ }
    await new Promise((r) => setTimeout(r, 2000));
  }
  return false;
}

async function uploadFile(cookies, filePath, mime, name) {
  const bytes = fs.readFileSync(filePath);
  const fd = new FormData();
  fd.append("file", new Blob([bytes], { type: mime }), name || path.basename(filePath));
  return api("/api/documents", { body: fd }, cookies);
}

async function uploadBytes(cookies, bytes, name, mime) {
  const fd = new FormData();
  fd.append("file", new Blob([bytes], { type: mime }), name);
  return api("/api/documents", { body: fd }, cookies);
}

function runId(model) {
  const nodes = model?.document?.nodes ?? {};
  return Object.values(nodes).find((n) => n.type === "run")?.id ?? "";
}

async function testExport(cookies, docId, fmt, label) {
  const { res } = await api(`/api/documents/${docId}/export?format=${fmt}`, {}, cookies);
  if (res.ok) ok(label, `${res.headers.get("content-type")?.split(";")[0]}`);
  else if (res.status === 400) skip(label, "format not supported for source");
  else if (res.status === 501) skip(label, "501 seam");
  else bad(label, String(res.status));
}

async function main() {
  console.log(`\n=== DocOS tool matrix ===\n${base}\n`);

  const { res: regRes, json: reg } = await api("/api/auth/register", {
    json: { email: `matrix_${Date.now()}@example.com`, password: "Matrix-Test-123!", name: "Matrix QA" },
  });
  const cookies = jar(regRes);
  if (!regRes.ok) { bad("Auth register", String(regRes.status)); process.exit(1); }
  ok("Auth register", reg?.user?.email);

  // ── Uploads ──────────────────────────────────────────────────────────────
  const uploads = {};
  const uploadSpecs = [
    ["userPdf", USER_PDF, "application/pdf", null],
    ["fixturePdf", path.join(FIX, "random-contract.pdf"), "application/pdf", "contract.pdf"],
    ["docx", path.join(FIX, "random-proposal.docx"), "application/vnd.openxmlformats-officedocument.wordprocessingml.document", "proposal.docx"],
    ["xlsx", path.join(FIX, "random-invoice.xlsx"), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "invoice.xlsx"],
    ["pptx", path.join(FIX, "random-deck.pptx"), "application/vnd.openxmlformats-officedocument.presentationml.presentation", "deck.pptx"],
    ["png", path.join(FIX, "random-scan.png"), "image/png", "scan.png"],
    ["rtf", path.join(FIX, "random-note.rtf"), "application/rtf", "note.rtf"],
    ["html", path.join(FIX, "random-page.html"), "text/html", "page.html"],
  ];

  for (const [key, filePath, mime, name] of uploadSpecs) {
    if (!fs.existsSync(filePath)) { skip(`Upload ${key}`, "file missing"); continue; }
    const { res, json } = await uploadFile(cookies, filePath, mime, name);
    if (res.ok && json?.doc_id) { uploads[key] = json.doc_id; ok(`Upload ${key}`, `${json.doc_id} (${(fs.statSync(filePath).size / 1024).toFixed(0)} KB)`); }
    else if (key === "html" && res.status === 415) skip(`Upload ${key}`, "HTML blocked until deploy");
    else bad(`Upload ${key}`, `${res.status}: ${JSON.stringify(json).slice(0, 100)}`);
  }

  const txtBody = `INVOICE QA\nClient: Northwind\nAmount: USD 12500\nSSN 111-22-3333\nEmail: test@example.com\n`;
  const txtUp = await uploadBytes(cookies, Buffer.from(txtBody), "invoice.txt", "text/plain");
  if (txtUp.res.ok) { uploads.txt = txtUp.json.doc_id; ok("Upload txt", uploads.txt); }
  else bad("Upload txt", String(txtUp.res.status));

  const pdfId = uploads.userPdf || uploads.fixturePdf;
  const smallPdfId = uploads.fixturePdf || pdfId;
  const docxId = uploads.docx;
  const txtId = uploads.txt;
  const pngId = uploads.png;

  if (!pdfId) { bad("Abort", "no PDF uploaded"); process.exit(1); }

  // ── Model + modify ───────────────────────────────────────────────────────
  const { json: pdfModel } = await api(`/api/documents/${pdfId}/model`, {}, cookies);
  const pdfRun = runId(pdfModel);
  if (pdfRun) {
    const patch = await api(`/api/documents/${pdfId}/patches`, {
      json: { ops: [{ op: "set_text", target_id: pdfRun, payload: { text: "EDITED BY TOOL MATRIX QA" } }] },
    }, cookies);
    patch.res.ok && patch.json?.applied ? ok("Modify PDF text") : bad("Modify PDF text", String(patch.res.status));
  } else skip("Modify PDF text", "no text runs in PDF");

  // ── Trust / scan / send-ready (reads first; mutations on small doc) ───────
  for (const [label, p] of [
    ["Sensitive scan (GET)", `/api/documents/${pdfId}/sensitive`],
    ["Document health panel", `/api/documents/${pdfId}/health`],
    ["Readiness / send-ready", `/api/documents/${pdfId}/readiness`],
    ["Redaction audit (un-redact test)", `/api/documents/${pdfId}/redaction-audit`],
  ]) {
    const { res, json } = await api(p, {}, cookies);
    res.ok ? ok(label, json?.findings ? `${json.findings.length} findings` : "") : bad(label, String(res.status));
  }

  const redact = await api(`/api/documents/${txtId}/redact-sensitive`, { method: "POST" }, cookies);
  redact.res.ok ? ok("Redact sensitive (POST on txt)") : bad("Redact sensitive", String(redact.res.status));

  const meta = await api(`/api/documents/${smallPdfId}/sanitize-metadata`, { method: "POST" }, cookies);
  meta.res.ok ? ok("Sanitize metadata") : bad("Sanitize metadata", String(meta.res.status));

  const a11y = await api(`/api/documents/${smallPdfId}/remediate-accessibility`, { method: "POST" }, cookies);
  a11y.res.ok ? ok("Remediate accessibility") : bad("Remediate accessibility", String(a11y.res.status));

  // ── Exports from PDF (before heavy clean/OCR) ───────────────────────────
  for (const fmt of ["pdf", "docx", "txt", "html", "md", "csv", "xlsx", "pptx"]) {
    await testExport(cookies, pdfId, fmt, `Export PDF→${fmt}`);
  }
  // Raster/heavy writers — use small fixture PDF to avoid 60s proxy timeout on large uploads.
  for (const fmt of ["png", "rtf"]) {
    await testExport(cookies, smallPdfId, fmt, `Export PDF→${fmt}`);
  }
  const { res: expReport } = await api(`/api/documents/${smallPdfId}/export/report?format=pdf`, {}, cookies);
  expReport.ok ? ok("Export validation report") : bad("Export validation report", String(expReport.status));

  if (docxId) {
    for (const fmt of ["docx", "pdf", "txt", "html"]) {
      await testExport(cookies, docxId, fmt, `Export DOCX→${fmt}`);
    }
  }

  // ── PDF page tools (small fixture to avoid mutating the large user PDF) ───
  for (const [label, p, body] of [
    ["Compress PDF", `/api/documents/${smallPdfId}/compress`, null],
    ["Rotate PDF", `/api/documents/${smallPdfId}/pages/rotate`, { pages: [0], degrees: 90 }],
    ["Watermark PDF", `/api/documents/${smallPdfId}/watermark`, { text: "QA TEST" }],
    ["Protect PDF", `/api/documents/${smallPdfId}/protect`, { password: "matrix-qa" }],
  ]) {
    const opts = body ? { json: body } : { method: "POST" };
    const { res } = await api(p, opts, cookies);
    res.ok ? ok(label) : bad(label, String(res.status));
  }

  if (uploads.fixturePdf && uploads.userPdf && uploads.fixturePdf !== uploads.userPdf) {
    const m = await api(`/api/documents/${smallPdfId}/merge`, { json: { doc_ids: [uploads.userPdf] } }, cookies);
    m.res.ok ? ok("Merge PDFs") : bad("Merge PDFs", String(m.res.status));
  }

  const split = await api(`/api/documents/${smallPdfId}/pages/extract?pages=0`, {}, cookies);
  split.res.ok ? ok("Split/extract PDF page") : bad("Split/extract PDF page", String(split.res.status));

  const del = await api(`/api/documents/${smallPdfId}/pages/delete`, { method: "POST", json: { pages: [999] } }, cookies);
  del.res.status === 422 ? ok("Delete pages (422 invalid page expected)") : del.res.ok ? ok("Delete pages") : bad("Delete pages", String(del.res.status));

  // ── Intelligence / AI reads ──────────────────────────────────────────────
  for (const [label, p, body] of [
    ["Ask document", `/api/documents/${pdfId}/ask`, { question: "What is this document about?" }],
    ["Summarize", `/api/documents/${pdfId}/summary`, null],
    ["Extract data", `/api/documents/${pdfId}/extract`, null],
    ["Classify", `/api/documents/${pdfId}/classify`, null],
    ["Intelligence analyze", `/api/documents/${pdfId}/intelligence`, null],
    ["Autopilot", `/api/documents/${pdfId}/autopilot`, null],
    ["Translate", `/api/documents/${pdfId}/translate`, { target_language: "fr" }],
  ]) {
    const { res } = body ? await api(p, { json: body }, cookies) : await api(p, {}, cookies);
    if (res.ok) ok(label);
    else if (res.status === 501) expect(label, "noop LLM/TTS seam");
    else bad(label, String(res.status));
  }

  // ── Forms / fields ───────────────────────────────────────────────────────
  const fields = await api(`/api/documents/${txtId}/fields`, {}, cookies);
  fields.res.ok ? ok("List form fields", `${fields.json?.fields?.length ?? 0} fields`) : bad("List form fields", String(fields.res.status));

  const detect = await api(`/api/documents/${txtId}/fields/detect`, { method: "POST" }, cookies);
  detect.res.ok ? ok("Detect form fields/blanks") : bad("Detect form fields", String(detect.res.status));

  // ── Compare / diff ───────────────────────────────────────────────────────
  if (txtId && docxId) {
    const diff = await api(`/api/documents/${txtId}/diff?against=${docxId}`, {}, cookies);
    diff.res.ok ? ok("Compare documents (diff)") : bad("Compare documents", String(diff.res.status));
  }

  // ── Workflows ────────────────────────────────────────────────────────────
  for (const preset of ["contract_packet", "invoice_approval", "vendor_onboarding", "employee_form_packet", "proposal_to_signature", "bulk_send_template"]) {
    const prev = await api(`/api/documents/${pdfId}/workflows/preview`, { json: { preset } }, cookies);
    prev.res.ok ? ok(`Workflow preview ${preset}`) : bad(`Workflow preview ${preset}`, String(prev.res.status));
  }

  // ── CLM ──────────────────────────────────────────────────────────────────
  const clause = await api("/api/clauses", { json: { title: "QA Clause", body: "Payment net-30." } }, cookies);
  clause.res.ok ? ok("Create clause") : bad("Create clause", String(clause.res.status));

  if (clause.json?.id && txtId) {
    const ins = await api(`/api/documents/${txtId}/insert-clause`, { json: { clause_id: clause.json.id } }, cookies);
    ins.res.ok ? ok("Insert clause") : bad("Insert clause", String(ins.res.status));
  }

  const renewal = await api("/api/renewals", { json: { title: "QA MSA", due_date: "2027-01-01", doc_id: txtId } }, cookies);
  renewal.res.ok ? ok("Create renewal reminder") : bad("Create renewal reminder", String(renewal.res.status));

  const renewSug = await api(`/api/documents/${txtId}/renewal-suggestions`, {}, cookies);
  renewSug.res.ok ? ok("Renewal suggestions") : bad("Renewal suggestions", String(renewSug.res.status));

  // ── Templates ────────────────────────────────────────────────────────────
  const tmpl = await api(`/api/documents/${txtId}/save-as-template`, { json: { name: "QA Template" } }, cookies);
  if (tmpl.res.ok && tmpl.json?.id) {
    ok("Save as template");
    const inst = await api(`/api/templates/${tmpl.json.id}/instantiate`, { method: "POST", json: { title: "From QA Template" } }, cookies);
    inst.res.ok ? ok("Instantiate template", inst.json?.doc_id) : bad("Instantiate template", String(inst.res.status));
  } else bad("Save as template", String(tmpl.res.status));

  // ── Editor session ───────────────────────────────────────────────────────
  const es = await api(`/api/documents/${docxId || pdfId}/editor/session`, { json: { provider: "local" } }, cookies);
  es.res.ok ? ok("Editor session create", es.json?.session_id?.slice(0, 8)) : es.res.status === 501 ? expect("Editor session", "501 seam") : bad("Editor session", String(es.res.status));

  // ── Ops agent ────────────────────────────────────────────────────────────
  const ops = await api(`/api/documents/${pdfId}/ops-agent/plan`, { json: { goal: "prepare for client send" } }, cookies);
  ops.res.ok ? ok("Ops agent plan") : ops.res.status === 501 ? expect("Ops agent plan", "501 without AI") : bad("Ops agent plan", String(ops.res.status));

  // ── Listen / TTS ─────────────────────────────────────────────────────────
  const audio = await api(`/api/documents/${txtId}/audio`, {}, cookies);
  audio.res.ok ? ok("Listen (TTS audio)") : audio.res.status === 501 ? expect("Listen (TTS)", "501 not configured") : bad("Listen (TTS)", String(audio.res.status));

  // ── E-sign / DRM / integrations ──────────────────────────────────────────
  const sig = await api(`/api/documents/${pdfId}/sign`, { json: { signer: "Matrix QA" } }, cookies);
  sig.res.ok ? ok("Integrity seal / sign") : bad("Sign", String(sig.res.status));

  const sigGet = await api(`/api/documents/${pdfId}/signature`, {}, cookies);
  sigGet.res.ok ? ok("Get signature status") : bad("Get signature", String(sigGet.res.status));

  const esign = await api(`/api/documents/${pdfId}/signature-request`, { json: { signers: [{ name: "Matrix QA", email: "qa@example.com" }] } }, cookies);
  esign.res.status === 501 ? expect("Request e-signature", "501 seam") : esign.res.ok ? ok("Request e-signature") : esign.res.status === 422 ? expect("Request e-signature", "422 validation/provider") : bad("Request e-signature", String(esign.res.status));

  const drm = await api(`/api/documents/${pdfId}/drm`, { json: { policy: "view-only" } }, cookies);
  drm.res.status === 501 ? expect("DRM protect", "501 seam") : drm.res.ok ? ok("DRM protect") : bad("DRM protect", String(drm.res.status));

  const ints = await api("/api/integrations", {}, cookies);
  ints.res.ok ? ok("List integrations", `${ints.json?.integrations?.length ?? 0} providers`) : bad("List integrations", String(ints.res.status));

  // ── Notebook / search / library ──────────────────────────────────────────
  const nb = await api("/api/notebook/ask", { json: { question: "Any payment terms?" } }, cookies);
  nb.res.ok ? ok("Notebook multi-doc ask") : nb.res.status === 501 ? expect("Notebook ask", "501") : bad("Notebook ask", String(nb.res.status));

  const search = await api("/api/search?q=INVOICE", {}, cookies);
  search.res.ok ? ok("Keyword search", `${search.json?.hits?.length ?? 0} hits`) : bad("Keyword search", String(search.res.status));

  const sem = await api("/api/search/semantic?q=payment", {}, cookies);
  sem.res.ok ? ok("Semantic search") : bad("Semantic search", String(sem.res.status));

  // ── Comments / tags / approvals / bulk / portal ──────────────────────────
  const tag = await api(`/api/documents/${txtId}/tags`, { json: { tag: "matrix-qa" } }, cookies);
  tag.res.ok ? ok("Add tag") : bad("Add tag", String(tag.res.status));

  const untag = await api(`/api/documents/${txtId}/tags/matrix-qa`, { method: "DELETE" }, cookies);
  untag.res.ok ? ok("Remove tag") : bad("Remove tag", String(untag.res.status));

  const comment = await api(`/api/documents/${txtId}/comments`, { json: { text: "Review scan results" } }, cookies);
  comment.res.ok ? ok("Add comment") : bad("Add comment", String(comment.res.status));

  const appr = await api(`/api/documents/${txtId}/approvals`, { json: { approvers: ["legal@example.com"], ordered: true } }, cookies);
  appr.res.ok ? ok("Start approvals") : bad("Start approvals", String(appr.res.status));

  const bulk = await api(`/api/documents/${txtId}/bulk-send`, { json: { recipients: ["client@example.com"] } }, cookies);
  const portalPath = bulk.json?.packets?.[0]?.portal_url ?? "";
  bulk.res.ok ? ok("Bulk send", portalPath) : bad("Bulk send", String(bulk.res.status));

  const bulkList = await api(`/api/documents/${txtId}/bulk-send`, {}, cookies);
  bulkList.res.ok ? ok("List bulk sends") : bad("List bulk sends", String(bulkList.res.status));

  if (portalPath) {
    const token = portalPath.replace(/^\/portal\//, "");
    (await api(`/api/portal/${token}`, {})).res.ok ? ok("Portal view") : bad("Portal view");
    (await api(`/api/portal/${token}/readiness`, {})).res.ok ? ok("Portal readiness") : bad("Portal readiness");
  }

  // ── Heavy scan/clean pipeline (after most tools; small doc for clean) ────
  const clean = await api(`/api/documents/${txtId}/clean`, { method: "POST" }, cookies);
  clean.res.ok ? ok("Clean before send (POST on txt)") : clean.res.status === 504 ? bad("Clean before send", "504 timeout") : bad("Clean before send", `${clean.res.status}: ${JSON.stringify(clean.json).slice(0, 80)}`);

  for (const [label, id] of [["Searchable PDF (PNG scan)", pngId], ["Searchable PDF (user doc)", pdfId]]) {
    if (!id) continue;
    const { res } = await api(`/api/documents/${id}/searchable-pdf`, {}, cookies);
    if (res.ok) ok(label, res.headers.get("content-type"));
    else if (res.status === 504) bad(label, "504 timeout — deploy searchable-pdf fix or raise API_PROXY_TIMEOUT_MS");
    else bad(label, String(res.status));
  }
  if (!(await waitForBackend())) bad("Backend recovery", "health check failed after heavy ops");

  // ── Fill profile ─────────────────────────────────────────────────────────
  const fp = await api("/api/fill-profile", { method: "PUT", json: { data: { name: "QA User", email: "qa@example.com" } } }, cookies);
  fp.res.ok ? ok("Save fill profile") : bad("Fill profile save", String(fp.res.status));

  const autofill = await api(`/api/documents/${txtId}/autofill`, { method: "POST" }, cookies);
  autofill.res.ok ? ok("Autofill document") : autofill.res.status === 422 ? skip("Autofill", "no matching fields") : bad("Autofill", String(autofill.res.status));

  // ── Preview / thumbnail ──────────────────────────────────────────────────
  const prev = await api(`/api/documents/${pdfId}/preview?page=0`, {}, cookies);
  prev.res.ok ? ok("PDF preview PNG", prev.res.headers.get("content-type")) : bad("PDF preview", String(prev.res.status));

  if (uploads.pptx) {
    const { json: pptModel } = await api(`/api/documents/${uploads.pptx}/model`, {}, cookies);
    const slide = Object.values(pptModel?.document?.nodes ?? {}).find((n) => n.type === "page")?.id;
    if (slide) {
      const thumb = await api(`/api/documents/${uploads.pptx}/slide-thumbnail?node_id=${slide}`, {}, cookies);
      thumb.res.ok ? ok("Slide thumbnail") : bad("Slide thumbnail", String(thumb.res.status));
    }
  }

  // ── Summary ──────────────────────────────────────────────────────────────
  const passed = R.filter((x) => x.s === "ok").length;
  const failed = R.filter((x) => x.s === "fail").length;
  const skipped = R.filter((x) => x.s === "skip").length;
  const expected = R.filter((x) => x.s === "expect").length;
  console.log(`\n=== ${passed} passed · ${failed} FAILED · ${skipped} skipped · ${expected} expected seams ===\n`);
  if (failed) {
    console.log("FAILURES:");
    for (const f of R.filter((x) => x.s === "fail")) console.log(`  • ${f.n}: ${f.d}`);
    process.exitCode = 1;
  }
  const outPath = path.join(__dirname, "production-tool-matrix-results.json");
  fs.writeFileSync(outPath, JSON.stringify({ base, uploads, results: R, summary: { passed, failed, skipped, expected } }, null, 2));
  console.log(`Results: ${outPath}`);
}

main().catch((e) => { console.error(e); process.exit(1); });
