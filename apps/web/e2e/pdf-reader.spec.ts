import { readFileSync } from "node:fs";
import path from "node:path";

import { expect, test } from "@playwright/test";

// Verifies the PDF.js reader renders in a real browser (canvas + text layer), not just builds.
test("PDF opens in the PDF.js reader", async ({ page }) => {
  const health = await page.request.get("/api/health");
  test.skip(!health.ok(), "Backend API is required for the upload→reader flow.");

  await page.goto("/");
  await page.getByRole("button", { name: /Try a sample document/i }).waitFor({ timeout: 60_000 });

  const pdf = readFileSync(path.join(__dirname, "fixtures", "sample.pdf"));
  await page.locator('input[type="file"][multiple]').setInputFiles({
    name: "sample.pdf",
    mimeType: "application/pdf",
    buffer: pdf,
  });
  await expect(page).toHaveURL(/\/documents\/doc_/, { timeout: 30_000 });

  await page.getByRole("button", { name: "Read", exact: true }).click();

  const reader = page.getByTestId("pdf-reader");
  await expect(reader).toBeVisible({ timeout: 30_000 });
  await expect(reader.locator("canvas").first()).toBeVisible({ timeout: 30_000 });
});
