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
