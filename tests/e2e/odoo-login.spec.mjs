import { expect, test } from "@playwright/test";

const database = process.env.E2E_ODOO_DB;
const administrator = {
  username: process.env.E2E_ODOO_USERNAME,
  password: process.env.E2E_ODOO_PASSWORD
};
const propertyUser = {
  username: process.env.E2E_PROPERTY_USER,
  password: process.env.E2E_PROPERTY_USER_PASSWORD
};

function requireCredential(value, name) {
  if (!value || value.startsWith("replace-with-")) {
    throw new Error(`${name} must be set in .env.e2e before running E2E tests.`);
  }
  return value;
}

function monitorPage(page) {
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

  return { browserErrors, serverErrors };
}

async function login(page, credentials) {
  const selectedDatabase = requireCredential(database, "E2E_ODOO_DB");
  await page.goto(`/web/login?db=${encodeURIComponent(selectedDatabase)}`, { waitUntil: "domcontentloaded" });
  await page.locator('input[name="login"]').fill(requireCredential(credentials.username, "E2E username"));
  await page.locator('input[name="password"]').fill(requireCredential(credentials.password, "E2E password"));
  await page.locator('button[type="submit"]').click();
  await page.waitForURL(/\/web(?:#|$)/, { timeout: 30_000 });
}

async function openProperties(page, { canCreate = true } = {}) {
  await expect(page.locator(".o_main_navbar")).toBeVisible();
  await page.locator(".o_main_navbar button").first().click();
  await page.getByText("Commercial Properties", { exact: true }).click();
  if (canCreate) {
    await expect(page.locator("button.o_list_button_add")).toBeVisible();
  } else {
    await expect(page.getByText("Properties", { exact: true }).last()).toBeVisible();
  }
}

async function createProperty(page, name) {
  await page.locator("button.o_list_button_add").click();
  await page.getByLabel("Name", { exact: true }).fill(name);
  await page.getByRole("textbox", { name: "Area?" }).fill("100");
  await page.getByLabel("Monthly Rent", { exact: true }).fill("1500");
  await page.getByRole("button", { name: "Save manually" }).click();
  await expect(page.getByText(name, { exact: true })).toBeVisible();
}

async function expectNoClientOrServerErrors(page, monitored) {
  await expect(page.locator(".o_error_dialog")).toHaveCount(0);
  await page.waitForTimeout(1_000);
  expect(monitored.serverErrors, `Unexpected Odoo server errors:\n${monitored.serverErrors.join("\n")}`).toEqual([]);
  expect(monitored.browserErrors, `Unexpected browser errors:\n${monitored.browserErrors.join("\n")}`).toEqual([]);
}

test("an administrator can set a status and archive a commercial property", async ({ page }) => {
  const monitored = monitorPage(page);
  const propertyName = `E2E Lifecycle ${Date.now()}`;

  await login(page, administrator);
  await openProperties(page);
  await createProperty(page, propertyName);

  await page.getByLabel("State", { exact: true }).selectOption({ label: "Maintenance" });
  await page.getByRole("button", { name: "Save manually" }).click();
  await expect(page.getByRole("radio", { name: "Maintenance" })).toBeChecked();

  await page.getByRole("button", { name: /Action/ }).click();
  await page.getByText("Archive", { exact: true }).click();
  await page.getByRole("dialog").getByRole("button", { name: "Archive" }).click();
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await page.getByRole("button", { name: /Action/ }).click();
  await expect(page.getByText("Unarchive", { exact: true })).toBeVisible();

  await expectNoClientOrServerErrors(page, monitored);
});

test("an administrator sees validation messages for invalid property values", async ({ page }) => {
  const monitored = monitorPage(page);

  await login(page, administrator);
  await openProperties(page);
  await page.locator("button.o_list_button_add").click();
  await page.getByLabel("Name", { exact: true }).fill(`E2E Invalid Area ${Date.now()}`);
  await page.getByLabel("Monthly Rent", { exact: true }).fill("100");
  await page.getByRole("button", { name: "Save manually" }).click();
  await expect(page.getByRole("dialog")).toContainText("The area must be greater than zero.");
  await page.getByRole("button", { name: "Ok" }).click();
  await page.getByRole("button", { name: "Discard changes" }).click();

  await page.locator("button.o_list_button_add").click();
  await page.getByLabel("Name", { exact: true }).fill(`E2E Invalid Rent ${Date.now()}`);
  await page.getByRole("textbox", { name: "Area?" }).fill("100");
  await page.getByLabel("Monthly Rent", { exact: true }).fill("-1");
  await page.getByRole("button", { name: "Save manually" }).click();
  await expect(page.getByRole("dialog")).toContainText("The monthly rent cannot be negative.");

  expect(monitored.serverErrors, `Unexpected Odoo server errors:\n${monitored.serverErrors.join("\n")}`).toEqual([]);
  expect(monitored.browserErrors, `Unexpected browser errors:\n${monitored.browserErrors.join("\n")}`).toEqual([]);
});

test("a Property User can read inventory but cannot create or edit it", async ({ page }) => {
  const monitored = monitorPage(page);
  const propertyName = `E2E Read Only ${Date.now()}`;

  await login(page, administrator);
  await openProperties(page);
  await createProperty(page, propertyName);
  await page.goto("/web/session/logout", { waitUntil: "domcontentloaded" });

  await login(page, propertyUser);
  await openProperties(page, { canCreate: false });
  await expect(page.locator("button.o_list_button_add")).toHaveCount(0);
  await page.getByText(propertyName, { exact: true }).click();
  await expect(page.getByRole("button", { name: "Save manually" })).toHaveCount(0);

  await expectNoClientOrServerErrors(page, monitored);
});
