#!/usr/bin/env node
// Browser-level production proof for Client Packet Readiness.
// Run through the web package so @playwright/test resolves:
// pnpm --filter @docos/web exec node ../../scripts/production-client-packet-ui-smoke.mjs

import { mkdtempSync } from "node:fs";
import { createRequire } from "node:module";
import { join } from "node:path";
import { tmpdir } from "node:os";

const require = createRequire(join(process.cwd(), "package.json"));
const { chromium, request } = require("@playwright/test");

const base = (process.env.DOCOS_PRODUCTION_URL || "https://docosweb-production.up.railway.app")
  .replace(/\/$/, "");
const sample = "Proposal for client website service. We can start after approval.";
const screenshotDir =
  process.env.DOCOS_SMOKE_SCREENSHOT_DIR || mkdtempSync(join(tmpdir(), "docos-client-packet-ui-"));

const expected = [
  "client packet readiness",
  "needs fixes before sending",
  "scope and deliverables",
  "payment and deposit terms",
  "signature and acceptance",
  "client onboarding handoff",
  "change control and revisions",
  "review the non-automatic readiness checks",
];

function assertIncludes(haystack, needle, label) {
  if (!haystack.includes(needle)) throw new Error(`${label} missing "${needle}"`);
}

async function main() {
  const api = await request.newContext({ baseURL: base });
  let browser;
  let docId;
  try {
    const upload = await api.post("/api/documents", {
      multipart: {
        file: {
          name: "agency-proposal.txt",
          mimeType: "text/plain",
          buffer: Buffer.from(sample),
        },
      },
    });
    if (!upload.ok()) throw new Error(`upload failed ${upload.status()} ${await upload.text()}`);
    docId = (await upload.json()).doc_id;

    const readiness = await api.get(`/api/documents/${docId}/readiness`);
    if (!readiness.ok()) {
      throw new Error(`readiness failed ${readiness.status()} ${await readiness.text()}`);
    }
    const report = (await readiness.json()).report;
    for (const id of [
      "scope_clarity",
      "payment_terms",
      "signature_acceptance",
      "client_onboarding",
      "scope_change_control",
    ]) {
      const check = report.checks.find((candidate) => candidate.id === id);
      if (!check) throw new Error(`API missing ${id}`);
      if (check.status !== "warn") throw new Error(`${id} expected warn, got ${check.status}`);
      if (check.fixable) throw new Error(`${id} should not claim an automatic fix`);
    }

    browser = await chromium.launch({ headless: true });
    const storageState = await api.storageState();

    const desktop = await browser.newContext({
      storageState,
      viewport: { width: 1280, height: 720 },
    });
    const desktopPage = await desktop.newPage();
    const desktopMessages = [];
    desktopPage.on("console", (msg) => {
      if (["error", "warning"].includes(msg.type())) {
        desktopMessages.push(`${msg.type()}: ${msg.text()}`);
      }
    });
    desktopPage.on("pageerror", (err) => desktopMessages.push(`pageerror: ${err.message}`));
    await desktopPage.goto(`${base}/documents/${docId}?tab=trust`, { waitUntil: "networkidle" });
    const desktopText = (await desktopPage.locator("body").innerText()).toLowerCase();
    for (const needle of expected) assertIncludes(desktopText, needle, "desktop");
    if (desktopText.includes("clean before you send")) {
      throw new Error("desktop should not show Clean before you send for business-only warnings");
    }
    if (desktopMessages.length) throw new Error(`desktop console errors: ${desktopMessages.join(" | ")}`);
    const desktopShot = join(screenshotDir, "client-packet-readiness-desktop.png");
    await desktopPage.screenshot({ path: desktopShot, fullPage: false });

    const mobile = await browser.newContext({
      storageState,
      viewport: { width: 390, height: 844 },
      isMobile: true,
    });
    const mobilePage = await mobile.newPage();
    await mobilePage.goto(`${base}/documents/${docId}?tab=trust`, { waitUntil: "networkidle" });
    const mobileText = (await mobilePage.locator("body").innerText()).toLowerCase();
    for (const needle of ["client packet readiness", "payment and deposit terms"]) {
      assertIncludes(mobileText, needle, "mobile");
    }
    const mobileShot = join(screenshotDir, "client-packet-readiness-mobile.png");
    await mobilePage.screenshot({ path: mobileShot, fullPage: false });

    console.log(
      JSON.stringify(
        {
          docId,
          verdict: report.verdict,
          desktopShot,
          mobileShot,
        },
        null,
        2,
      ),
    );
  } finally {
    if (browser) await browser.close();
    if (docId) {
      const cleanup = await api.delete(`/api/documents/${docId}`);
      if (!cleanup.ok() && cleanup.status() !== 404) {
        console.warn(`[client-packet-ui-smoke] cleanup failed ${cleanup.status()}`);
      }
    }
    await api.dispose();
  }
}

main().catch((err) => {
  console.error(
    `[client-packet-ui-smoke] failed: ${err instanceof Error ? err.message : String(err)}`,
  );
  process.exitCode = 1;
});
