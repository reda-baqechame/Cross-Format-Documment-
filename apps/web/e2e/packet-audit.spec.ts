import { expect, test } from "@playwright/test";

test("packet audit surfaces cited blocking finding", async ({ page }) => {
  const health = await page.request.get("/api/health");
  test.skip(!health.ok(), "Backend API is required.");

  await page.goto("/");

  const invoice =
    "Commercial Invoice\nInvoice No: E2E-1\nTotal: CAD 14,920.00\n";
  const po = "Purchase Order\nPO No: E2E-PO\nTotal: CAD 13,780.00\n";

  await page.locator('input[type="file"][multiple]').setInputFiles([
    { name: "invoice.txt", mimeType: "text/plain", buffer: Buffer.from(invoice) },
    { name: "po.txt", mimeType: "text/plain", buffer: Buffer.from(po) },
  ]);

  await page.goto("/packets");
  await page.getByPlaceholder("e.g. Shipment ACME-2026-04").fill("E2E mismatch packet");
  await page.getByRole("button", { name: "Create packet" }).click();
  await expect(page).toHaveURL(/\/packets\//, { timeout: 30_000 });

  const checkboxes = page.locator('aside input[type="checkbox"]');
  await expect(checkboxes.first()).toBeVisible({ timeout: 30_000 });
  const count = await checkboxes.count();
  for (let i = 0; i < count; i++) {
    await checkboxes.nth(i).check();
  }
  await page.getByRole("button", { name: /Add .* document/i }).click();

  await page.getByRole("button", { name: /Run audit/i }).first().click();
  await expect(page.getByText(/BLOCKED/i)).toBeVisible({ timeout: 30_000 });
  await page.getByRole("button", { name: "Issues" }).click();
  await expect(page.getByText(/total|mismatch|disagree/i).first()).toBeVisible();
});
