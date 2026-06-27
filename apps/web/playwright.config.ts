import { defineConfig, devices } from "@playwright/test";

const reuse = !process.env.CI;

// The e2e backend is SQLite-backed (scripts/start-e2e-api.sh), which can't safely take concurrent
// upload writes from parallel Playwright workers — run serially in CI. ``PW_EXECUTABLE_PATH`` lets the
// suite use a pre-installed Chromium when the pinned browser build isn't downloaded (e.g. sandboxes).
const executablePath = process.env.PW_EXECUTABLE_PATH || undefined;

export default defineConfig({
  testDir: "./e2e",
  timeout: 45_000,
  expect: { timeout: 8_000 },
  workers: process.env.CI ? 1 : undefined,
  retries: process.env.CI ? 2 : 0,
  use: {
    baseURL: process.env.PLAYWRIGHT_BASE_URL ?? "http://127.0.0.1:3100",
    trace: "retain-on-failure",
    launchOptions: executablePath ? { executablePath } : undefined,
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
