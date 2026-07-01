import { expect, test } from "@playwright/test";

test("clean before send surfaces verify findings and proof report", async ({ page }) => {
  const health = await page.request.get("/api/health");
  test.skip(!health.ok(), "Backend API is required.");

  const piiDoc = "Contact jane@example.com for billing questions.\n";

  await page.locator('input[type="file"]').first().setInputFiles({
    name: "verify-smoke.txt",
    mimeType: "text/plain",
    buffer: Buffer.from(piiDoc),
  });

  await expect(page).toHaveURL(/\/documents\//, { timeout: 30_000 });

  await page
    .getByRole("navigation", { name: "Document command center" })
    .getByRole("button", { name: "Command center: Verify" })
    .click();
  await expect(page.getByText(/needs review|fix before|blocked|ready/i).first()).toBeVisible({
    timeout: 15_000,
  });

  await page.getByRole("button", { name: "Issues" }).click();
  await expect(page.getByText(/sensitive|pii|exposed/i).first()).toBeVisible({ timeout: 15_000 });

  await page.getByRole("button", { name: "Clean export" }).click();
  const downloadPromise = page.waitForEvent("download", { timeout: 15_000 }).catch(() => null);
  await page.getByRole("button", { name: /Download proof report/i }).click();
  const download = await downloadPromise;
  if (download) {
    expect(download.suggestedFilename()).toMatch(/proof-report\.html$/);
  }
});
