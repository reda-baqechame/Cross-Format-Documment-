#!/usr/bin/env node
// Browser-level production proof for the structured document editor.
// Run through the web package so @playwright/test resolves:
// pnpm --filter @docos/web exec node ../../scripts/production-editor-smoke.mjs

import { createRequire } from "node:module";
import { join } from "node:path";

const require = createRequire(join(process.cwd(), "package.json"));
const { chromium, expect, request } = require("@playwright/test");

const base = (process.env.DOCOS_PRODUCTION_URL || "https://docosweb-production.up.railway.app")
  .replace(/\/$/, "");

const sample = "Editor smoke title\nThis paragraph should be editable and format-safe.";
const editedText = "Production editor smoke\nSecond persisted line";

async function main() {
  const api = await request.newContext({ baseURL: base });
  let browser;
  let docId;

  try {
    const upload = await api.post("/api/documents", {
      multipart: {
        file: {
          name: "editor-smoke.txt",
          mimeType: "text/plain",
          buffer: Buffer.from(sample),
        },
      },
    });
    if (!upload.ok()) throw new Error(`upload failed ${upload.status()} ${await upload.text()}`);
    docId = (await upload.json()).doc_id;
    if (!docId) throw new Error("upload did not return doc_id");

    browser = await chromium.launch({ headless: true });
    const context = await browser.newContext({
      storageState: await api.storageState(),
      viewport: { width: 1280, height: 760 },
    });
    const page = await context.newPage();
    const messages = [];
    page.on("console", (msg) => {
      if (["error", "warning"].includes(msg.type())) {
        messages.push(`${msg.type()}: ${msg.text()}`);
      }
    });
    page.on("pageerror", (err) => messages.push(`pageerror: ${err.message}`));

    await page.goto(`${base}/documents/${docId}`, { waitUntil: "networkidle" });
    const originalRun = page.locator('span[title="Double-click or long-press to edit"]').first();
    await expect(originalRun).toBeVisible();
    await originalRun.dblclick();

    const editor = page.getByLabel("Inline document text editor");
    await expect(editor).toBeVisible();
    await editor.fill(editedText);
    await editor.press("Control+Enter");

    const editedRun = page.locator('span[title="Double-click or long-press to edit"]').filter({
      hasText: "Production editor smoke",
    });
    await expect(editedRun).toBeVisible();
    await expect(editedRun).toContainText("Second persisted line");

    await editedRun.click();
    await page.getByLabel("Font family").selectOption("Georgia");
    await page.getByLabel("Font size preset").selectOption("18");
    await page.getByLabel("Text color").fill("#2563eb");
    await page.getByLabel("Bold").click();
    await expect(page.getByLabel("Bold")).toHaveAttribute("aria-pressed", "true");

    await expect
      .poll(async () => {
        const model = await api.get(`/api/documents/${docId}/model`);
        if (!model.ok()) return null;
        const body = await model.json();
        const run = Object.values(body.document.nodes).find(
          (node) => node.type === "run" && node.text?.includes("Production editor smoke"),
        );
        if (!run) return null;
        return {
          text: run.text,
          bold: run.bold,
          font: run.font,
          size: run.size,
          color: run.color,
        };
      })
      .toEqual({
        text: editedText,
        bold: true,
        font: "Georgia",
        size: 18,
        color: "#2563eb",
      });

    const actionableMessages = messages.filter(
      (message) =>
        !message.includes("Cross origin request detected") &&
        !message.includes("Failed to load resource: the server responded with a status of 404"),
    );
    if (actionableMessages.length) {
      throw new Error(`browser console issues: ${actionableMessages.join(" | ")}`);
    }

    console.log(
      JSON.stringify(
        {
          docId,
          base,
          edited: true,
          formatting: { bold: true, font: "Georgia", size: 18, color: "#2563eb" },
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
        console.warn(`[production-editor-smoke] cleanup failed ${cleanup.status()}`);
      }
    }
    await api.dispose();
  }
}

main().catch((err) => {
  console.error(`[production-editor-smoke] failed: ${err instanceof Error ? err.message : String(err)}`);
  process.exitCode = 1;
});
