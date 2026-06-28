import { expect, test } from "@playwright/test";

test("recipe manager creates, runs, edits, reviews, and deletes a guarded recipe", async ({
  page,
}) => {
  const health = await page.request.get("/api/health");
  test.skip(!health.ok(), "Backend API is required for the recipe flow.");

  await page.goto("/");
  await page.getByRole("button", { name: "No file handy? Try a sample document" }).click();
  await expect(page).toHaveURL(/\/documents\/doc_/, { timeout: 30_000 });

  await page.getByRole("button", { name: "Automate", exact: true }).click();
  await page.getByRole("button", { name: "Saved recipes" }).click();
  await expect(page.getByRole("heading", { name: "Build a recipe" })).toBeVisible();

  await page.getByLabel("Recipe name").fill("Browser intake checks");
  await page.getByRole("button", { name: /Classify document/ }).click();
  await page.getByRole("button", { name: /Scan for sensitive data/ }).click();
  await page.getByRole("button", { name: "Save manual recipe" }).click();

  const recipe = page.getByRole("article").filter({ hasText: "Browser intake checks" });
  await expect(recipe).toBeVisible();
  await expect(recipe).toContainText("2 steps · Manual only");

  await recipe.getByRole("button", { name: "Run on this file" }).click();
  await expect(page.getByText("Latest run", { exact: true })).toBeVisible();
  await expect(page.getByText("2 step(s) executed; 0 approval-gated; 2 total.").first()).toBeVisible();

  await recipe.getByRole("button", { name: "Run history" }).click();
  await expect(page.getByRole("heading", { name: "Run history" })).toBeVisible();
  await expect(page.getByText("completed", { exact: true }).last()).toBeVisible();

  await recipe.getByRole("button", { name: "Edit" }).click();
  await page.getByLabel("Recipe name").fill("Browser privacy checks");
  await page.getByRole("button", { name: "Save recipe changes" }).click();
  const renamed = page.getByRole("article").filter({ hasText: "Browser privacy checks" });
  await expect(renamed).toBeVisible();

  await renamed.getByRole("button", { name: "Delete" }).click();
  await expect(renamed).toHaveCount(0);
  await expect(page.getByText("No recipes yet. Add validated tools above to create one.")).toBeVisible();
});
