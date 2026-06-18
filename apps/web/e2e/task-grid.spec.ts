import { expect, test } from "@playwright/test";

test("home page exposes business document command-center workflows", async ({ page }) => {
  await page.goto("/");

  await expect(page.getByRole("heading", { name: "Every document tool, in one place" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Workflow" })).toBeVisible();

  for (const name of [
    "Build a form",
    "Create contract packet",
    "Vendor onboarding",
    "Invoice approval",
    "Proposal to signature",
    "Bulk send from template",
  ]) {
    await expect(page.getByRole("link", { name: new RegExp(name) })).toBeVisible();
  }
});

test("create from template is runnable without requiring a starter upload", async ({ page }) => {
  await page.goto("/tasks/create-from-template");

  await expect(page.getByRole("heading", { name: "Create from template" })).toBeVisible();
  await expect(page.getByText("Accepts optional starter document")).toBeVisible();

  const openTemplates = page.getByRole("button", { name: "Open templates" });
  await expect(openTemplates).toBeEnabled();
  await openTemplates.click();
  await expect(page).toHaveURL(/\/#templates$/);
});
