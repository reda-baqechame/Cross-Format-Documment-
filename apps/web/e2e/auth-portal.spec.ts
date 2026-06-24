import { expect, test } from "@playwright/test";

test("signup and pricing pages render", async ({ page }) => {
  await page.goto("/signup");
  await expect(page.getByRole("heading", { name: /Create your DocOS account/i })).toBeVisible();
  await expect(page.getByLabel(/Email/i)).toBeVisible();

  await page.goto("/login");
  await expect(page.getByRole("heading", { name: /Sign in to DocOS/i })).toBeVisible();

  await page.goto("/pricing");
  await expect(page.getByRole("heading", { name: /Pricing/i })).toBeVisible();
  await expect(page.getByText(/Free/i).first()).toBeVisible();
});

test("home page shows wired marketing sections", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: /How it works/i })).toBeVisible();
  await expect(page.getByRole("heading", { name: /Ask across your library/i })).toBeVisible();
  await expect(page.getByRole("heading", { name: /Platform capabilities/i })).toBeVisible();
});

test("signup shows account email in header", async ({ page }) => {
  const email = `e2e_${Date.now()}@example.com`;
  await page.goto("/signup");
  await page.getByPlaceholder("Email").fill(email);
  await page.getByPlaceholder("Password (8+ characters)").fill("password123");
  await page.getByRole("button", { name: "Create account" }).click();
  await expect(page.getByText(email)).toBeVisible({ timeout: 15_000 });
});

test("invalid portal token shows error", async ({ page }) => {
  await page.goto("/portal/not-a-valid-token");
  await expect(page.getByText(/not found|expired|404/i)).toBeVisible();
});
