import dotenv from "dotenv";
import { defineConfig, devices } from "@playwright/test";

dotenv.config({ path: ".env.e2e" });
dotenv.config({ path: ".env.e2e.runtime", override: true });

// Verificación de seguridad: asegurar que los E2E tests solo corren en base de pruebas
const e2eTestsEnabled = process.env.E2E_TESTS_ENABLED === "true";
const e2eDb = process.env.E2E_ODOO_DB || "";
const isDeveloperDb = e2eDb.includes("dev") && !e2eDb.includes("e2e");

if (!e2eTestsEnabled || isDeveloperDb) {
  throw new Error(
    `E2E tests are disabled or pointing to a developer database for safety.\n\n` +
    `Current configuration:\n` +
    `  E2E_TESTS_ENABLED: ${e2eTestsEnabled}\n` +
    `  E2E_ODOO_DB: ${e2eDb}\n\n` +
    `To enable E2E tests:\n` +
    `1. Use a SEPARATE test database (e.g., odoo16_commercial_property_e2e_test)\n` +
    `2. Set E2E_TESTS_ENABLED=true in .env.e2e\n` +
    `3. NEVER use your developer database for E2E tests\n\n` +
    `Preventing accidental data destruction on ${e2eDb}.`
  );
}

export default defineConfig({
  testDir: "./tests/e2e",
  fullyParallel: false,
  forbidOnly: Boolean(process.env.CI),
  retries: process.env.CI ? 1 : 0,
  reporter: [["list"], ["html", { open: "never" }]],
  use: {
    baseURL: process.env.E2E_ODOO_URL || "http://127.0.0.1:8069",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    video: "retain-on-failure"
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] }
    }
  ]
});
