import { expect, test } from "@playwright/test";

// Verifies the Univer (Apache-2.0) spreadsheet surface actually renders in the browser — not just
// that it type-checks/builds. Uploads a CSV (opens in the sheet workspace), then asserts the Grid
// (Excel) toggle is present and Univer mounts its canvas.
test("spreadsheet opens in the Univer grid editor", async ({ page }) => {
  const health = await page.request.get("/api/health");
  test.skip(!health.ok(), "Backend API is required for the upload→workspace flow.");

  await page.goto("/");

  const csv = "Item,Qty,Price\nWidget,10,2.50\nGadget,4,9.99\nSprocket,7,1.25\n";
  await page.locator('input[type="file"][multiple]').setInputFiles({
    name: "inventory.csv",
    mimeType: "text/csv",
    buffer: Buffer.from(csv),
  });

  await expect(page).toHaveURL(/\/documents\/doc_/, { timeout: 30_000 });

  // The spreadsheet workspace exposes the Grid (Excel) / Simple toggle.
  await expect(page.getByRole("button", { name: "Grid (Excel)" })).toBeVisible({ timeout: 30_000 });

  // Univer mounts into the tagged container and renders to a canvas.
  const sheet = page.getByTestId("univer-sheet");
  await expect(sheet).toBeVisible({ timeout: 30_000 });
  await expect(sheet.locator("canvas").first()).toBeVisible({ timeout: 30_000 });
});
