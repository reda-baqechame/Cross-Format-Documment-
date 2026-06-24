import { defineConfig, devices } from "@playwright/test";

const reuse = !process.env.CI;

export default defineConfig({
  testDir: "./e2e",
  timeout: 45_000,
  expect: { timeout: 8_000 },
  use: {
    baseURL: process.env.PLAYWRIGHT_BASE_URL ?? "http://127.0.0.1:3100",
    trace: "retain-on-failure",
  },
  webServer: process.env.PLAYWRIGHT_BASE_URL
    ? undefined
    : [
        {
          command: "bash ../../scripts/start-e2e-api.sh",
          url: "http://127.0.0.1:8000/health",
          reuseExistingServer: reuse,
          timeout: 180_000,
          cwd: __dirname,
        },
        {
          command:
            'node -e "require(\'fs\').rmSync(\'.next\',{recursive:true,force:true})" && pnpm dev',
          url: "http://127.0.0.1:3100",
          reuseExistingServer: reuse,
          timeout: 180_000,
        },
      ],
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
});
