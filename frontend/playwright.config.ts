import { defineConfig, devices } from "@playwright/test";

const webPort = process.env.SASYAAI_WEB_PORT ?? "5173";
const apiPort = process.env.SASYAAI_API_PORT ?? "8000";

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  forbidOnly: Boolean(process.env.CI),
  retries: process.env.CI ? 2 : 0,
  reporter: process.env.CI ? "github" : "list",
  use: {
    baseURL: `http://127.0.0.1:${webPort}`,
    trace: "retain-on-failure",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: [
    {
      command: `python -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port ${apiPort}`,
      cwd: "..",
      url: `http://127.0.0.1:${apiPort}/health`,
      env: {
        ...process.env,
        APP_ENVIRONMENT: "development",
        RUNTIME_MODE: "demo",
        AUTH_REQUIRED: "false",
        PRODUCTION_DATA_MODE: "live",
      },
      reuseExistingServer: !process.env.CI,
    },
    {
      command: `npm run dev -- --host 127.0.0.1 --port ${webPort}`,
      url: `http://127.0.0.1:${webPort}`,
      reuseExistingServer: !process.env.CI,
    },
  ],
});
