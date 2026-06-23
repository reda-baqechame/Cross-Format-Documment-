import { expect, test } from "@playwright/test";

test("home page exposes business document command-center workflows", async ({ page }) => {
  await page.goto("/");

  await expect(page.getByRole("heading", { name: /Edit with proof/ })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Start here" })).toBeVisible();

  for (const name of [
    "Contract packet",
    "Vendor onboarding",
    "Invoice approval",
    "Employee form packet",
    "Proposal to signature",
    "Bulk send from template",
  ]) {
    await expect(page.getByRole("link", { name: new RegExp(name) }).first()).toBeVisible();
  }

  await expect(page.getByText("Export validation", { exact: true })).toBeVisible();
  await expect(page.getByText("All document tools")).toBeVisible();
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
