import { defineConfig } from "@playwright/test";
import path from "node:path";

// End-to-end tests against the real FastAPI app on a throwaway SQLite database (frontend/.e2e/).
// Run: npm run e2e  (needs backend/.venv; uses the system Chrome, no browser download)
const PORT = Number(process.env.E2E_PORT ?? 8766);
const DB = path.resolve(import.meta.dirname, ".e2e/promptopt-e2e.db");

export default defineConfig({
  testDir: "e2e",
  timeout: 90_000,
  expect: { timeout: 30_000 },  // the first optimize loads the Stage A model
  fullyParallel: false,
  workers: 1,
  reporter: [["list"]],
  use: {
    baseURL: `http://127.0.0.1:${PORT}`,
    channel: process.env.PW_CHANNEL ?? "chrome",
    viewport: { width: 1440, height: 900 },
    trace: "retain-on-failure",
  },
  webServer: {
    command: `mkdir -p .e2e && rm -f ${DB} && cd ../backend && DATABASE_URL=sqlite:///${DB} .venv/bin/python -m app.init_db >/dev/null && DATABASE_URL=sqlite:///${DB} .venv/bin/uvicorn app.api:app --port ${PORT}`,
    url: `http://127.0.0.1:${PORT}/api/options`,
    reuseExistingServer: false,
    timeout: 120_000,
  },
});
