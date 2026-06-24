import { expect, test } from "@playwright/test";

test("home page exposes business document command-center workflows", async ({ page }) => {
  await page.goto("/");

  await expect(page.getByRole("heading", { name: /Get client packets ready/ })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Start with the packet" })).toBeVisible();
  await expect(page.getByRole("link", { name: "Check a client packet" })).toBeVisible();
  await expect(page.getByRole("link", { name: /Client Packet Readiness/ }).first()).toBeVisible();

  for (const name of [
    "Client contract packet",
    "Vendor onboarding",
    "Invoice and deposit review",
    "Employee form packet",
    "Proposal to signature",
    "Bulk send from template",
  ]) {
    await expect(page.getByRole("link", { name: new RegExp(name) }).first()).toBeVisible();
  }

  await expect(page.getByText("Scope checks", { exact: true })).toBeVisible();
  await expect(page.getByText("Payment terms", { exact: true })).toBeVisible();
  await expect(page.getByText("All document tools")).toBeVisible();
});

test("client packet readiness task is routable and upload-ready", async ({ page }) => {
  await page.goto("/tasks/client-packet-readiness");

  await expect(page.getByRole("heading", { name: "Client Packet Readiness" })).toBeVisible();
  await expect(
    page.getByText("missing scope, payment, signature, safety, and export risks"),
  ).toBeVisible();
  await expect(page.getByText("Accepts proposal, SOW, contract, invoice, or onboarding packet")).toBeVisible();
  await expect(page.getByRole("button", { name: "Check packet" })).toBeDisabled();
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
