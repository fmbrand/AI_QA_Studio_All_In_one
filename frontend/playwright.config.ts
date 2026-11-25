import { defineConfig, devices } from "@playwright/test";

/**
 * End-to-end tests drive the real stack: Next.js (3000), the FastAPI API (8000), the worker and PostgreSQL.
 * Locally, start the stack yourself (see docs/setup-guide.md); the config reuses running servers.
 * In CI (CI=true) the config starts the API and the web app; the database must already be migrated.
 * The worker has no port Playwright can wait on, so it is always started outside this config
 * (the CI workflow runs it as a background step). Without it, uploads stay "Queued".
 */
const uv = process.env.UV_CMD ?? "uv";

export default defineConfig({
  testDir: "./tests/e2e",
  timeout: 60_000,
  expect: { timeout: 15_000 },
  fullyParallel: false,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? [["list"], ["html", { open: "never" }]] : "list",
  use: {
    baseURL: process.env.E2E_BASE_URL ?? "http://localhost:3000",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: [
    {
      command: `${uv} run uvicorn app.main:app --port 8000`,
      cwd: "../backend",
      url: "http://localhost:8000/api/v1/health",
      reuseExistingServer: !process.env.CI,
      timeout: 60_000,
    },
    {
      command: process.env.CI ? "npm run start" : "npm run dev",
      url: "http://localhost:3000/login",
      reuseExistingServer: !process.env.CI,
      timeout: 120_000,
    },
  ],
});
