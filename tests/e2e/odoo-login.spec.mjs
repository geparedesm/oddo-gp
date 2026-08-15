import { expect, test } from "@playwright/test";

const username = process.env.E2E_ODOO_USERNAME;
const password = process.env.E2E_ODOO_PASSWORD;

function requireCredential(value, name) {
  if (!value || value.startsWith("replace-with-")) {
    throw new Error(`${name} must be set in .env.e2e before running E2E tests.`);
  }
  return value;
}

test("an authorized user can load the Odoo backend without client or server errors", async ({ page }) => {
  const browserErrors = [];
  const serverErrors = [];

  page.on("pageerror", (error) => browserErrors.push(`pageerror: ${error.message}`));
  page.on("console", (message) => {
    if (message.type() === "error") {
      browserErrors.push(`console: ${message.text()}`);
    }
  });
  page.on("response", (response) => {
    if (response.status() >= 500) {
      serverErrors.push(`${response.status()} ${response.url()}`);
    }
  });

  await page.goto("/web/login", { waitUntil: "domcontentloaded" });
  await page.locator('input[name="login"]').fill(requireCredential(username, "E2E_ODOO_USERNAME"));
  await page.locator('input[name="password"]').fill(requireCredential(password, "E2E_ODOO_PASSWORD"));
  await page.locator('button[type="submit"]').click();

  await page.waitForURL(/\/web(?:#|$)/, { timeout: 30_000 });
  await expect(page.locator(".o_main_navbar")).toBeVisible();
  await expect(page.locator(".o_error_dialog")).toHaveCount(0);

  // Allow deferred Odoo assets to finish so their failures are captured too.
  await page.waitForTimeout(1_000);
  expect(serverErrors, `Unexpected Odoo server errors:\n${serverErrors.join("\n")}`).toEqual([]);
  expect(browserErrors, `Unexpected browser errors:\n${browserErrors.join("\n")}`).toEqual([]);
});
