import { expect, test } from "@playwright/test";

async function uploadText(
  page: import("@playwright/test").Page,
  name: string,
  text: string,
): Promise<string> {
  const res = await page.request.post("/api/documents", {
    multipart: {
      file: {
        name,
        mimeType: "text/plain",
        buffer: Buffer.from(text),
      },
    },
  });
  expect(res.ok()).toBeTruthy();
  const body = await res.json();
  return body.doc_id as string;
}

test("packet audit surfaces cited blocking finding", async ({ page }) => {
  const health = await page.request.get("/api/health");
  test.skip(!health.ok(), "Backend API is required.");

  const invoice =
    "Commercial Invoice\nInvoice No: E2E-1\nTotal: CAD 14,920.00\n";
  const po = "Purchase Order\nPO No: E2E-PO\nTotal: CAD 13,780.00\n";

  await page.goto("/");
  await uploadText(page, "invoice.txt", invoice);
  await uploadText(page, "po.txt", po);

  await page.goto("/packets");
  await page.getByLabel(/Vertical/i).selectOption("import_export");
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
  await expect(page.getByText(/BLOCKED/i).first()).toBeVisible({ timeout: 60_000 });
  await page.getByRole("button", { name: "Issues" }).click();
  await expect(page.getByText(/total|mismatch|disagree/i).first()).toBeVisible();
});
