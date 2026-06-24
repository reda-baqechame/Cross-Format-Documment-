import { expect, test } from "@playwright/test";

test("word-like editor edits multiline text and persists formatting", async ({ page }) => {
  const health = await page.request.get("/api/health");
  test.skip(!health.ok(), "Backend API is required for the full editor flow.");

  await page.goto("/");

  await page.getByRole("button", { name: "No file handy? Try a sample document" }).click();

  await expect(page).toHaveURL(/\/documents\/doc_/);
  await expect(page.getByText("MUTUAL SERVICES AGREEMENT")).toBeVisible();

  await page.getByText("MUTUAL SERVICES AGREEMENT").dblclick();
  const editor = page.getByLabel("Inline document text editor");
  await expect(editor).toBeVisible();
  await editor.fill("Updated scope line\nSecond editor line");
  await editor.press("Control+Enter");

  const editedRun = page.locator('span[title="Double-click or long-press to edit"]').filter({
    hasText: "Updated scope line",
  });
  await expect(editedRun).toBeVisible();
  await expect(editedRun).toContainText("Second editor line");

  await editedRun.click();
  await page.getByLabel("Font family").selectOption("Georgia");
  await page.getByLabel("Font size preset").selectOption("18");
  await page.getByLabel("Text color").fill("#2563eb");
  await page.getByLabel("Bold").click();
  await expect(page.getByLabel("Bold")).toHaveAttribute("aria-pressed", "true");

  const docId = new URL(page.url()).pathname.split("/").pop();
  expect(docId).toBeTruthy();
  await expect
    .poll(async () => {
      const model = await page.request.get(`/api/documents/${docId}/model`);
      if (!model.ok()) return null;
      const body = await model.json();
      const run = Object.values(body.document.nodes).find(
        (node: any) => node.type === "run" && node.text?.includes("Updated scope line"),
      ) as any;
      if (!run) return null;
      return {
        bold: run.bold,
        font: run.font,
        size: run.size,
        color: run.color,
      };
    })
    .toEqual({ bold: true, font: "Georgia", size: 18, color: "#2563eb" });
});
