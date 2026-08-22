import { expect, test } from "@playwright/test";
import path from "node:path";
import { fileURLToPath } from "node:url";

const database = process.env.E2E_ODOO_DB;
const administrator = {
  username: process.env.E2E_ODOO_USERNAME,
  password: process.env.E2E_ODOO_PASSWORD
};
const propertyUser = {
  username: process.env.E2E_PROPERTY_USER,
  password: process.env.E2E_PROPERTY_USER_PASSWORD
};
const unitActionId = requireCredential(process.env.E2E_UNIT_ACTION_ID, "E2E unit action ID");
const tenantActionId = requireCredential(process.env.E2E_TENANT_ACTION_ID, "E2E tenant action ID");
const leaseActionId = requireCredential(process.env.E2E_LEASE_ACTION_ID, "E2E lease action ID");
const leaseDashboardActionId = requireCredential(
  process.env.E2E_LEASE_DASHBOARD_ACTION_ID,
  "E2E lease dashboard action ID"
);
const enquiryActionId = requireCredential(process.env.E2E_ENQUIRY_ACTION_ID, "E2E enquiry action ID");
const visitActionId = requireCredential(process.env.E2E_VISIT_ACTION_ID, "E2E visit action ID");
const reservationActionId = requireCredential(process.env.E2E_RESERVATION_ACTION_ID, "E2E reservation action ID");
const whatsappPolicyActionId = requireCredential(process.env.E2E_WHATSAPP_POLICY_ACTION_ID, "E2E WhatsApp policy action ID");
const applicationActionId = requireCredential(process.env.E2E_APPLICATION_ACTION_ID, "E2E application action ID");
const integrationAlertActionId = requireCredential(process.env.E2E_INTEGRATION_ALERT_ACTION_ID, "E2E integration alert action ID");
const maintenanceActionId = requireCredential(process.env.E2E_MAINTENANCE_ACTION_ID, "E2E maintenance action ID");
const maintenanceDashboardActionId = requireCredential(process.env.E2E_MAINTENANCE_DASHBOARD_ACTION_ID, "E2E maintenance dashboard action ID");
const handoverActionId = requireCredential(process.env.E2E_HANDOVER_ACTION_ID, "E2E handover action ID");
const penaltyActionId = requireCredential(process.env.E2E_PENALTY_ACTION_ID, "E2E penalty action ID");
const portfolioActionId = requireCredential(process.env.E2E_PORTFOLIO_ACTION_ID, "E2E portfolio action ID");
const distributionChannelActionId = requireCredential(process.env.E2E_DISTRIBUTION_CHANNEL_ACTION_ID, "E2E distribution channel action ID");
const campaignAttributionActionId = requireCredential(process.env.E2E_CAMPAIGN_ATTRIBUTION_ACTION_ID, "E2E campaign attribution action ID");
const moduleIconPath = path.resolve(
  path.dirname(fileURLToPath(import.meta.url)),
  "../../addons/commercial_property_management/static/description/icon.png"
);

function requireCredential(value, name) {
  if (!value || value.startsWith("replace-with-")) {
    throw new Error(`${name} must be set in .env.e2e before running E2E tests.`);
  }
  return value;
}

function dateOffset(days) {
  const date = new Date();
  date.setDate(date.getDate() + days);
  return date.toISOString().slice(0, 10);
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
  await expect(page.locator(".o_main_navbar")).toBeVisible({ timeout: 30_000 });
}

async function openProperties(page, { canCreate = true } = {}) {
  await expect(page.locator(".o_main_navbar")).toBeVisible();
  await page.locator(".o_main_navbar button").first().click();
  await page.getByRole("menuitem", { name: "Commercial Properties" }).first().click();
  if (canCreate) {
    await expect(page.locator("button.o_list_button_add")).toBeVisible();
  } else {
    await expect(page.getByText("Properties", { exact: true }).last()).toBeVisible();
  }
}

async function openTenants(page) {
  await page.goto("/web", { waitUntil: "domcontentloaded" });
  await page.goto(`/web#action=${tenantActionId}&model=res.partner&view_type=list`, { waitUntil: "domcontentloaded" });
  await expect(page.locator(".o_searchview_input")).toBeVisible();
  await expect(page.locator(".o_list_view")).toBeVisible();
  await page.getByRole("button", { name: "New" }).click();
  await expect(page.getByLabel("Name", { exact: true })).toBeVisible();
}

async function openLeases(page) {
  await page.goto("/web", { waitUntil: "domcontentloaded" });
  await page.goto(`/web#action=${leaseActionId}&model=commercial.lease&view_type=list`, { waitUntil: "domcontentloaded" });
  await expect(page.locator(".o_list_view")).toBeVisible();
  await page.getByRole("button", { name: "New" }).click();
  await expect(page.getByLabel("Property", { exact: true })).toBeVisible();
}

async function openLeaseOperationsDashboard(page) {
  await page.goto("/web", { waitUntil: "domcontentloaded" });
  await page.goto(
    `/web#action=${leaseDashboardActionId}&model=commercial.lease&view_type=pivot`,
    { waitUntil: "domcontentloaded" }
  );
  await expect(page.locator("div.o_pivot")).toBeVisible();
}

async function openEnquiries(page) {
  await page.goto(`/web#action=${enquiryActionId}&model=commercial.property.lead&view_type=list`, { waitUntil: "domcontentloaded" });
  await expect(page.locator(".o_list_view")).toBeVisible();
}

async function openOperationalAction(page, actionId, model) {
  await page.goto("/web", { waitUntil: "domcontentloaded" });
  await page.goto(`/web#action=${actionId}&model=${model}&view_type=list`, { waitUntil: "domcontentloaded" });
  await expect(page.locator(".o_list_view")).toBeVisible();
}

test("an administrator can review lease operations metrics and expiry filters", async ({ page }) => {
  const monitored = monitorPage(page);

  await login(page, administrator);
  await openLeaseOperationsDashboard(page);
  await expect(page.getByText("Lease Operations Dashboard", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: /Filters/ }).click();
  await expect(page.getByText("Expiring in 30 Days", { exact: true })).toBeVisible();
  await expect(page.getByText("Expiring in 7 Days", { exact: true })).toBeVisible();

  await expectNoClientOrServerErrors(page, monitored);
});

test("an administrator can access enquiries while a Property User cannot", async ({ page }) => {
  const monitored = monitorPage(page);
  await login(page, administrator);
  await openEnquiries(page);
  await expect(page.getByText("Enquiries", { exact: true }).last()).toBeVisible();
  await page.goto("/web/session/logout", { waitUntil: "domcontentloaded" });
  await login(page, propertyUser);
  await page.locator(".o_main_navbar button").first().click();
  await page.getByRole("menuitem", { name: "Commercial Properties" }).first().click();
  await expect(page.getByText("Enquiries", { exact: true })).toHaveCount(0);
  await expectNoClientOrServerErrors(page, monitored);
});

test("an administrator can review the Ecuador WhatsApp policy while a Property User cannot", async ({ page }) => {
  const monitored = monitorPage(page);
  await login(page, administrator);
  await page.goto("/web", { waitUntil: "domcontentloaded" });
  await page.goto(`/web#action=${whatsappPolicyActionId}&model=res.config.settings&view_type=form`, { waitUntil: "domcontentloaded" });
  await expect(page.getByText("WhatsApp enquiry policy — Ecuador", { exact: true })).toBeVisible();
  await expect(page.getByText("Enable only after approving the policy below.", { exact: true })).toBeVisible();
  await page.goto("/web/session/logout", { waitUntil: "domcontentloaded" });
  await login(page, propertyUser);
  await page.locator(".o_main_navbar button").first().click();
  await page.getByRole("menuitem", { name: "Commercial Properties" }).first().click();
  await expect(page.getByText("WhatsApp Policy", { exact: true })).toHaveCount(0);
  await expectNoClientOrServerErrors(page, monitored);
});

async function createProperty(page, name) {
  await page.locator("button.o_list_button_add").click();
  await page.getByLabel("Name", { exact: true }).fill(name);
  await page.getByRole("textbox", { name: "Area?" }).fill("100");
  await page.getByLabel("Monthly Rent", { exact: true }).fill("1500");
  const createResponse = page.waitForResponse(
    (response) =>
      response.url().includes("/web/dataset/call_kw/commercial.property/create") && response.ok()
  );
  await page.getByRole("button", { name: "Save manually" }).click();
  const response = await createResponse;
  const { result } = await response.json();
  await expect(page.getByRole("cell", { name, exact: true })).toBeVisible();
  return result;
}

async function returnToPropertyList(page) {
  await openProperties(page);
  await expect(page.locator(".o_list_view")).toBeVisible();
}

async function showAllProperties(page) {
  const removeFilter = page.getByRole("img", { name: "Remove" });
  if (await removeFilter.count()) {
    await removeFilter.first().click();
  }
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

  await page.getByLabel("State?", { exact: true }).selectOption({ label: "Maintenance" });
  await page.getByLabel("Property Type", { exact: true }).selectOption({ label: "Residential" });
  await page.getByRole("button", { name: "Save manually" }).click();
  await expect(page.getByRole("radio", { name: "Maintenance" })).toBeChecked();
  await expect(page.getByLabel("Property Type", { exact: true }).locator("option:checked")).toHaveText("Residential");

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
  const propertyId = await createProperty(page, propertyName);
  await page.goto("/web/session/logout", { waitUntil: "domcontentloaded" });

  await login(page, propertyUser);
  await openProperties(page, { canCreate: false });
  await expect(page.locator("button.o_list_button_add")).toHaveCount(0);
  await page.goto(`/web#id=${propertyId}&model=commercial.property&view_type=form`, {
    waitUntil: "domcontentloaded",
  });
  await expect(page.getByText(propertyName, { exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "Save manually" })).toHaveCount(0);

  await expectNoClientOrServerErrors(page, monitored);
});

test("an administrator can use Kanban, filters, photos and notes to review inventory", async ({ page }) => {
  const monitored = monitorPage(page);
  const propertyName = `E2E Workflow ${Date.now()}`;
  const internalNote = "Phase 3 workflow note";

  await login(page, administrator);
  await openProperties(page);
  await createProperty(page, propertyName);
  await page.getByLabel("State?", { exact: true }).selectOption({ label: "Maintenance" });
  await page.getByRole("button", { name: "Save manually" }).click();
  await page.getByText("Internal Notes", { exact: true }).click();
  await page.getByPlaceholder("Add operational notes for the property...").fill(internalNote);
  await page.getByRole("button", { name: "Save manually" }).click();
  await page.getByText("Photo", { exact: true }).click();
  await page.locator('input[type="file"]').last().setInputFiles(moduleIconPath);
  await page.getByRole("button", { name: "Save manually" }).click();

  await returnToPropertyList(page);
  await page.getByRole("img", { name: "Remove" }).click();
  const viewSwitcher = page.locator(".o_control_panel nav:last-child button");
  await viewSwitcher.last().click();
  await expect(page.locator(".o_kanban_view")).toBeVisible();

  await returnToPropertyList(page);
  await page.getByRole("img", { name: "Remove" }).click();
  await page.getByRole("button", { name: /Filters/ }).click();
  await page.getByText("Maintenance", { exact: true }).last().click();
  await page.getByRole("cell", { name: propertyName, exact: true }).click();
  await expect(page.getByLabel("Name", { exact: true })).toHaveValue(propertyName);
  await page.getByRole("tab", { name: "Internal Notes" }).click();
  await expect(page.getByPlaceholder("Add operational notes for the property...")).toHaveValue(internalNote);
  await expectNoClientOrServerErrors(page, monitored);
});

test("an administrator can create person and company tenants while a Property User cannot access tenants", async ({ page }) => {
  const monitored = monitorPage(page);
  const personName = `E2E Tenant Person ${Date.now()}`;
  const companyName = `E2E Tenant Company ${Date.now()}`;

  await login(page, administrator);
  await openTenants(page);
  await page.getByLabel("Name", { exact: true }).fill(personName);
  await page.getByLabel("Identification Number?", { exact: true }).fill("E2E-PERSON-001");
  await page.getByRole("button", { name: "Save manually" }).click();
  await expect(page.getByText(personName, { exact: true })).toBeVisible();
  expect(monitored.browserErrors, "Unexpected browser error after saving a person tenant").toEqual([]);

  await openTenants(page);
  await page.getByRole("radio", { name: "Company" }).check();
  await page.getByLabel("Name", { exact: true }).fill(companyName);
  await page.getByRole("button", { name: "Save manually" }).click();
  expect(monitored.browserErrors, "Unexpected browser error after saving a company tenant").toEqual([]);

  await page.goto("/web/session/logout", { waitUntil: "domcontentloaded" });
  await login(page, propertyUser);
  await page.locator(".o_main_navbar button").first().click();
  await page.getByRole("menuitem", { name: "Commercial Properties" }).first().click();
  await expect(page.getByText("Tenants", { exact: true })).toHaveCount(0);
  await expectNoClientOrServerErrors(page, monitored);
});

test("an administrator can prepare a published public property listing", async ({ page }) => {
  const monitored = monitorPage(page);
  const propertyName = `E2E Public Listing ${Date.now()}`;
  const publicName = "Harbour-view office suite";
  const publicDescription = "Bright office space with flexible meeting areas.";

  await login(page, administrator);
  await openProperties(page);
  await createProperty(page, propertyName);
  await page.getByText("Public Listing", { exact: true }).click();
  await page.getByLabel("Published?", { exact: true }).check();
  await page.getByLabel("Public Name", { exact: true }).fill(publicName);
  await page.getByLabel("Public Monthly Rent", { exact: true }).fill("1800");
  await page.getByPlaceholder("Describe the property for prospective tenants...").fill(publicDescription);
  await page.getByRole("button", { name: "Save manually" }).click();

  await expect(page.getByLabel("Published?", { exact: true })).toBeChecked();
  await expect(page.getByLabel("Public Name", { exact: true })).toHaveValue(publicName);
  await expectNoClientOrServerErrors(page, monitored);
});

test("an administrator can activate a lease and review its property history", async ({ page }) => {
  const monitored = monitorPage(page);
  const propertyName = `E2E Lease Property ${Date.now()}`;
  const tenantName = `E2E Lease Tenant ${Date.now()}`;

  await login(page, administrator);
  await openProperties(page);
  await createProperty(page, propertyName);

  await openTenants(page);
  await page.getByLabel("Name", { exact: true }).fill(tenantName);
  await page.getByRole("button", { name: "Save manually" }).click();

  await openLeases(page);
  await page.getByRole("combobox", { name: "Property" }).fill(propertyName);
  await page.getByRole("option", { name: propertyName, exact: true }).click();
  await page.getByRole("combobox", { name: "Tenant" }).fill(tenantName);
  await page.getByRole("option", { name: tenantName, exact: true }).click();
  await page.getByLabel("Start Date", { exact: true }).fill(dateOffset(-1));
  await page.getByLabel("End Date", { exact: true }).fill(dateOffset(30));
  await page.getByLabel("Monthly Rent", { exact: true }).fill("1500");
  await page.getByRole("button", { name: "Save manually" }).click();
  await page.getByRole("button", { name: "Activate", exact: true }).click();
  await expect(page.getByText("Active", { exact: true })).toBeVisible();

  await openLeases(page);
  await page.getByRole("combobox", { name: "Property" }).fill(propertyName);
  await page.getByRole("option", { name: propertyName, exact: true }).click();
  await page.getByRole("combobox", { name: "Tenant" }).fill(tenantName);
  await page.getByRole("option", { name: tenantName, exact: true }).click();
  await page.getByLabel("Start Date", { exact: true }).fill(dateOffset(31));
  await page.getByLabel("End Date", { exact: true }).fill(dateOffset(365));
  await page.getByLabel("Monthly Rent", { exact: true }).fill("1500");
  await page.getByRole("button", { name: "Save manually" }).click();
  await page.getByRole("button", { name: "Activate", exact: true }).click();
  await expect(page.getByRole("dialog")).toContainText("A commercial unit can have only one active lease.");
  await page.getByRole("button", { name: "Ok" }).click();
  await expect(page.getByRole("dialog")).toHaveCount(0);

  await page.getByRole("link", { name: "Lease Contracts" }).click();
  await expect(page.locator(".o_list_view")).toBeVisible();

  await page.goto("/web/session/logout", { waitUntil: "domcontentloaded" });
  await login(page, propertyUser);
  await page.locator(".o_main_navbar button").first().click();
  await page.getByRole("menuitem", { name: "Commercial Properties" }).first().click();
  await expect(page.getByText("Lease Contracts", { exact: true })).toHaveCount(0);

  await expectNoClientOrServerErrors(page, monitored);
});

test("an administrator sees a future confirmed lease reserve its property", async ({ page }) => {
  const monitored = monitorPage(page);
  const propertyName = `E2E Reserved Property ${Date.now()}`;
  const tenantName = `E2E Reserved Tenant ${Date.now()}`;

  await login(page, administrator);
  await openProperties(page);
  await createProperty(page, propertyName);

  await openTenants(page);
  await page.getByLabel("Name", { exact: true }).fill(tenantName);
  await page.getByRole("button", { name: "Save manually" }).click();

  await openLeases(page);
  await page.getByRole("combobox", { name: "Property" }).fill(propertyName);
  await page.getByRole("option", { name: propertyName, exact: true }).click();
  await page.getByRole("combobox", { name: "Tenant" }).fill(tenantName);
  await page.getByRole("option", { name: tenantName, exact: true }).click();
  await page.getByLabel("Start Date", { exact: true }).fill(dateOffset(14));
  await page.getByLabel("End Date", { exact: true }).fill(dateOffset(365));
  await page.getByLabel("Monthly Rent", { exact: true }).fill("1500");
  await page.getByRole("button", { name: "Save manually" }).click();
  await page.getByRole("button", { name: "Activate", exact: true }).click();

  await expectNoClientOrServerErrors(page, monitored);
});

test("an administrator can access phase 12 visits and reservations while a Property User cannot", async ({ page }) => {
  const monitored = monitorPage(page);
  await login(page, administrator);
  await openOperationalAction(page, visitActionId, "commercial.property.visit");
  await expect(page.getByRole("button", { name: "New" })).toBeVisible();
  await openOperationalAction(page, reservationActionId, "commercial.property.reservation");
  await expect(page.getByRole("button", { name: "New" })).toBeVisible();
  await page.goto("/web/session/logout", { waitUntil: "domcontentloaded" });
  await login(page, propertyUser);
  await page.locator(".o_main_navbar button").first().click();
  await page.getByRole("menuitem", { name: "Commercial Properties" }).first().click();
  await expect(page.getByText("Visits", { exact: true })).toHaveCount(0);
  await expect(page.getByText("Reservations", { exact: true })).toHaveCount(0);
  await expectNoClientOrServerErrors(page, monitored);
});

test("an administrator can access phase 13 applications while a Property User cannot", async ({ page }) => {
  const monitored = monitorPage(page);
  await login(page, administrator);
  await openOperationalAction(page, applicationActionId, "commercial.property.application");
  await expect(page.getByRole("button", { name: "New" })).toBeVisible();
  await page.goto("/web/session/logout", { waitUntil: "domcontentloaded" });
  await login(page, propertyUser);
  await page.locator(".o_main_navbar button").first().click();
  await page.getByRole("menuitem", { name: "Commercial Properties" }).first().click();
  await expect(page.getByText("Applications", { exact: true })).toHaveCount(0);
  await expectNoClientOrServerErrors(page, monitored);
});

test("an administrator can access phase 14 integration alerts while a Property User cannot", async ({ page }) => {
  const monitored = monitorPage(page);
  await login(page, administrator);
  await openOperationalAction(page, integrationAlertActionId, "commercial.property.integration.alert");
  await expect(page.getByRole("button", { name: "New" })).toBeVisible();
  await page.goto("/web/session/logout", { waitUntil: "domcontentloaded" });
  await login(page, propertyUser);
  await page.locator(".o_main_navbar button").first().click();
  await page.getByRole("menuitem", { name: "Commercial Properties" }).first().click();
  await expect(page.getByText("Integration Alerts", { exact: true })).toHaveCount(0);
  await expectNoClientOrServerErrors(page, monitored);
});

test("an administrator can access phase 15 maintenance and handover checklists while a Property User cannot", async ({ page }) => {
  const monitored = monitorPage(page);
  await login(page, administrator);
  await openOperationalAction(page, maintenanceActionId, "commercial.property.maintenance");
  await expect(page.getByRole("button", { name: "New" })).toBeVisible();
  await page.goto("/web", { waitUntil: "domcontentloaded" });
  await page.goto(`/web#action=${maintenanceDashboardActionId}&model=commercial.property.maintenance&view_type=pivot`, { waitUntil: "domcontentloaded" });
  await expect(page.getByRole("listitem").getByText("Maintenance Dashboard", { exact: true })).toBeVisible();
  await openOperationalAction(page, handoverActionId, "commercial.property.handover");
  await expect(page.getByRole("button", { name: "New" })).toBeVisible();
  await page.goto("/web/session/logout", { waitUntil: "domcontentloaded" });
  await login(page, propertyUser);
  await page.locator(".o_main_navbar button").first().click();
  await page.getByRole("menuitem", { name: "Commercial Properties" }).first().click();
  await expect(page.getByText("Maintenance", { exact: true })).toHaveCount(0);
  await expect(page.getByText("Delivery / Return Checklists", { exact: true })).toHaveCount(0);
  await expectNoClientOrServerErrors(page, monitored);
});

test("an administrator can create, assign and complete a building-wide maintenance ticket", async ({ page }) => {
  const monitored = monitorPage(page);
  const propertyName = `E2E Maintenance Building ${Date.now()}`;

  await login(page, administrator);
  await openProperties(page);
  await createProperty(page, propertyName);
  await expect(page.locator('.o_field_widget[name="operational_status"]')).toHaveText("Operational");
  await page.waitForURL(/id=\d+/);
  const propertyUrl = page.url();

  await openOperationalAction(page, maintenanceActionId, "commercial.property.maintenance");
  await page.locator("button.o_list_button_add").click();
  await page.getByRole("combobox", { name: "Building" }).fill(propertyName);
  await page.getByRole("option", { name: propertyName, exact: true }).click();
  await page.getByLabel("Description", { exact: true }).fill("Replace the lobby air conditioning filter.");
  await page.getByRole("combobox", { name: "Internal Owner" }).fill("Administrator");
  await page.getByRole("option", { name: "Administrator", exact: true }).click();
  await page.getByRole("button", { name: "Save manually" }).click();

  await page.getByRole("button", { name: "Assign", exact: true }).click();
  await expect(page.getByText("Assigned", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Start Work", exact: true }).click();
  await expect(page.getByText("In Progress", { exact: true })).toBeVisible();

  await page.getByRole("button", { name: "Complete", exact: true }).click();
  await expect(page.getByRole("dialog")).toContainText("Add completion notes before closing a maintenance ticket.");
  await page.getByRole("button", { name: "Ok" }).click();

  await page.getByLabel("Completion Notes", { exact: true }).fill("Filter replaced and airflow verified.");
  await page.getByRole("button", { name: "Save manually" }).click();
  await page.getByRole("button", { name: "Complete", exact: true }).click();
  await expect(page.getByText("Completed", { exact: true })).toBeVisible();

  await page.goto("/web", { waitUntil: "domcontentloaded" });
  await page.goto(propertyUrl, { waitUntil: "domcontentloaded" });
  await expect(page.locator('.o_field_widget[name="operational_status"]')).toHaveText("Operational");

  await expectNoClientOrServerErrors(page, monitored);
});

test("an administrator can complete a delivery checklist and a Property User cannot see it", async ({ page }) => {
  const monitored = monitorPage(page);
  const propertyName = `E2E Handover Building ${Date.now()}`;

  await login(page, administrator);
  await openProperties(page);
  await createProperty(page, propertyName);

  await openOperationalAction(page, handoverActionId, "commercial.property.handover");
  await page.locator("button.o_list_button_add").click();
  await page.getByRole("combobox", { name: "Commercial Unit" }).fill(propertyName);
  await page.getByRole("option", { name: propertyName, exact: true }).click();

  await page.getByRole("button", { name: "Complete", exact: true }).click();
  await expect(page.getByRole("dialog")).toContainText("Add at least one checklist item before completing a handover.");
  await page.getByRole("button", { name: "Ok" }).click();

  await page.getByRole("button", { name: "Add a line" }).click();
  await page.keyboard.type("Entrance door and lock");
  await page.getByRole("button", { name: "Save manually" }).click();

  await page.getByRole("button", { name: "Complete", exact: true }).click();
  await expect(page.getByText("Completed", { exact: true })).toBeVisible();

  await page.goto("/web/session/logout", { waitUntil: "domcontentloaded" });
  await login(page, propertyUser);
  await page.locator(".o_main_navbar button").first().click();
  await page.getByRole("menuitem", { name: "Commercial Properties" }).first().click();
  await expect(page.getByText("Delivery / Return Checklists", { exact: true })).toHaveCount(0);
  await expectNoClientOrServerErrors(page, monitored);
});

test("an administrator can access phase 16 penalties and portfolio performance while a Property User cannot", async ({ page }) => {
  const monitored = monitorPage(page);
  await login(page, administrator);
  await openOperationalAction(page, penaltyActionId, "commercial.lease.penalty");
  await expect(page.getByRole("button", { name: "New" })).toBeVisible();
  await page.goto("/web", { waitUntil: "domcontentloaded" });
  await page.goto(`/web#action=${portfolioActionId}&model=commercial.property&view_type=pivot`, { waitUntil: "domcontentloaded" });
  await expect(page.getByRole("listitem").getByText("Portfolio Performance", { exact: true })).toBeVisible();
  await page.goto("/web/session/logout", { waitUntil: "domcontentloaded" });
  await login(page, propertyUser);
  await page.locator(".o_main_navbar button").first().click();
  await page.getByRole("menuitem", { name: "Commercial Properties" }).first().click();
  await expect(page.getByText("Penalties", { exact: true })).toHaveCount(0);
  await expect(page.getByText("Portfolio Performance", { exact: true })).toHaveCount(0);
  await expectNoClientOrServerErrors(page, monitored);
});

test("an administrator can manage a lease deposit and apply a rent adjustment", async ({ page }) => {
  const monitored = monitorPage(page);
  const propertyName = `E2E Financial Building ${Date.now()}`;
  const tenantName = `E2E Financial Tenant ${Date.now()}`;

  await login(page, administrator);
  await openProperties(page);
  await createProperty(page, propertyName);

  await openTenants(page);
  await page.getByLabel("Name", { exact: true }).fill(tenantName);
  await page.getByRole("button", { name: "Save manually" }).click();

  await openLeases(page);
  await page.getByRole("combobox", { name: "Property" }).fill(propertyName);
  await page.getByRole("option", { name: propertyName, exact: true }).click();
  await page.getByRole("combobox", { name: "Tenant" }).fill(tenantName);
  await page.getByRole("option", { name: tenantName, exact: true }).click();
  await page.getByLabel("Start Date", { exact: true }).fill(dateOffset(-1));
  await page.getByLabel("End Date", { exact: true }).fill(dateOffset(60));
  await page.getByLabel("Monthly Rent", { exact: true }).fill("1500");
  await page.getByRole("button", { name: "Save manually" }).click();
  await page.getByRole("button", { name: "Activate", exact: true }).click();
  await expect(page.getByText("Active", { exact: true })).toBeVisible();

  await page.getByLabel("Deposit Amount", { exact: true }).fill("500");
  await page.getByRole("button", { name: "Save manually" }).click();
  const depositStatusBadge = page.locator('.o_field_widget[name="deposit_status"]');
  await page.getByRole("button", { name: "Mark Held", exact: true }).click();
  await expect(depositStatusBadge).toHaveText("Held");
  await page.getByRole("button", { name: "Refund", exact: true }).click();
  await expect(depositStatusBadge).toHaveText("Refunded");

  await page.getByText("Rent Adjustments", { exact: true }).click();
  await page.getByRole("button", { name: "Add a line" }).click();
  await page.locator("tr.o_selected_row").locator('[name="new_rent"] input').fill("1800");
  await page.getByRole("button", { name: "Save manually" }).click();
  await page.locator("tr").filter({ hasText: "1,800.00" }).getByRole("button", { name: "Apply" }).click();
  await expect(page.getByLabel("Monthly Rent", { exact: true })).toHaveValue(/1.?800/);

  await expectNoClientOrServerErrors(page, monitored);
});

test("an administrator can record a lease penalty, collect it, and renew the lease", async ({ page }) => {
  const monitored = monitorPage(page);
  const propertyName = `E2E Renewal Building ${Date.now()}`;
  const tenantName = `E2E Renewal Tenant ${Date.now()}`;

  await login(page, administrator);
  await openProperties(page);
  await createProperty(page, propertyName);

  await openTenants(page);
  await page.getByLabel("Name", { exact: true }).fill(tenantName);
  await page.getByRole("button", { name: "Save manually" }).click();

  await openLeases(page);
  await page.getByRole("combobox", { name: "Property" }).fill(propertyName);
  await page.getByRole("option", { name: propertyName, exact: true }).click();
  await page.getByRole("combobox", { name: "Tenant" }).fill(tenantName);
  await page.getByRole("option", { name: tenantName, exact: true }).click();
  await page.getByLabel("Start Date", { exact: true }).fill(dateOffset(-5));
  await page.getByLabel("End Date", { exact: true }).fill(dateOffset(10));
  await page.getByLabel("Monthly Rent", { exact: true }).fill("1200");
  await page.getByRole("button", { name: "Save manually" }).click();
  await page.getByRole("button", { name: "Activate", exact: true }).click();
  await expect(page.getByText("Active", { exact: true })).toBeVisible();

  await page.getByRole("tab", { name: "Penalties" }).click();
  await expect(page.getByRole("columnheader", { name: "Date" })).toBeVisible();
  const penaltySelectedRow = page.locator("tr.o_selected_row");
  await expect(async () => {
    const errorDialog = page.getByRole("dialog");
    if (await errorDialog.isVisible().catch(() => false)) {
      await page.getByRole("button", { name: "Ok" }).click();
    }
    await page.getByRole("button", { name: "Add a line" }).click();
    await expect(penaltySelectedRow).toBeVisible({ timeout: 3000 });
  }).toPass({ timeout: 20000 });
  await penaltySelectedRow.locator('[name="amount"] input').fill("150");
  await page.getByRole("button", { name: "Save manually" }).click();
  await page.locator("tr").filter({ hasText: "150.00" }).getByRole("button", { name: "Collect" }).click();
  await expect(page.getByText("Collected", { exact: true })).toBeVisible();

  await page.getByRole("button", { name: "Renew", exact: true }).click();
  await expect(page.getByRole("button", { name: "Activate", exact: true })).toBeVisible();
  await expect(page.locator('.o_field_widget[name="renewed_from_id"]')).toBeVisible();

  await expectNoClientOrServerErrors(page, monitored);
});

test("an administrator can access phase 17 distribution channels and campaign attribution while a Property User cannot", async ({ page }) => {
  const monitored = monitorPage(page);
  await login(page, administrator);
  await openOperationalAction(page, distributionChannelActionId, "commercial.property.distribution.channel");
  await expect(page.getByRole("button", { name: "New" })).toBeVisible();
  await page.goto("/web", { waitUntil: "domcontentloaded" });
  await page.goto(`/web#action=${campaignAttributionActionId}&model=commercial.property.lead&view_type=pivot`, { waitUntil: "domcontentloaded" });
  await expect(page.getByRole("listitem").getByText("Campaign Attribution", { exact: true })).toBeVisible();
  await page.goto("/web/session/logout", { waitUntil: "domcontentloaded" });
  await login(page, propertyUser);
  await page.locator(".o_main_navbar button").first().click();
  await page.getByRole("menuitem", { name: "Commercial Properties" }).first().click();
  await expect(page.getByText("Distribution Channels", { exact: true })).toHaveCount(0);
  await expect(page.getByText("Campaign Attribution", { exact: true })).toHaveCount(0);
  await expectNoClientOrServerErrors(page, monitored);
});

test("an administrator can pass the listing quality checklist, publish a unit and unpublish it with a reason", async ({ page }) => {
  const monitored = monitorPage(page);
  const propertyName = `E2E Quality Building ${Date.now()}`;
  const featureName = `E2E Feature ${Date.now()}`;

  await login(page, administrator);
  await openProperties(page);
  await createProperty(page, propertyName);

  await openOperationalAction(page, unitActionId, "commercial.property.unit");
  await page.locator(".o_searchview_input").fill(propertyName);
  await page.keyboard.press("Enter");
  await page.getByRole("cell", { name: propertyName, exact: true }).first().click();

  await page.getByText("Public Listing", { exact: true }).click();
  await page.getByLabel("Public Name", { exact: true }).fill("Bright downtown suite");
  await page.getByLabel("Public Monthly Rent", { exact: true }).fill("1800");
  await page.locator('[name="public_description"] textarea').fill("A bright, well-connected office suite.");
  await page.locator("#public_feature_ids").fill(featureName);
  await page.keyboard.press("Enter");
  await page.getByLabel("Public Location Description?", { exact: true }).fill("Near the central plaza, 5 minutes from the main avenue");
  await page.getByLabel("Virtual Tour URL?", { exact: true }).fill("https://tours.example.com/e2e-quality-suite");
  await page.locator('input[type="file"]').last().setInputFiles(moduleIconPath);
  await page.getByRole("button", { name: "Save manually" }).click();

  await expect(page.getByLabel("Quality Checklist Passed?", { exact: true })).toBeChecked();

  await page.getByLabel("Published?", { exact: true }).check();
  await page.getByRole("button", { name: "Save manually" }).click();
  await expect(page.locator('.o_field_widget[name="publication_date"]')).not.toHaveText("");
  await expect(page.locator('.o_field_widget[name="publication_approved_by_id"]')).toContainText("Administrator");

  await page.getByLabel("Published?", { exact: true }).uncheck();
  await page.getByRole("button", { name: "Save manually" }).click();
  await expect(page.getByRole("dialog")).toContainText("Select an unpublish reason before unpublishing a listing.");
  await page.getByRole("button", { name: "Ok" }).click();

  await page.getByRole("combobox", { name: "Unpublish Reason" }).selectOption({ label: "Manager Decision" });
  await page.getByRole("button", { name: "Save manually" }).click();
  await expect(page.getByLabel("Published?", { exact: true })).not.toBeChecked();

  await expectNoClientOrServerErrors(page, monitored);
});

test("an administrator can attribute an enquiry to a distribution channel", async ({ page }) => {
  const monitored = monitorPage(page);
  const propertyName = `E2E Campaign Building ${Date.now()}`;
  const channelName = `E2E Campaign Channel ${Date.now()}`;
  const prospectName = `E2E Campaign Prospect ${Date.now()}`;

  await login(page, administrator);
  await openProperties(page);
  await createProperty(page, propertyName);
  await page.getByText("Public Listing", { exact: true }).click();
  await page.getByLabel("Published?", { exact: true }).check();
  await page.getByLabel("Public Name", { exact: true }).fill("Campaign attribution suite");
  await page.getByLabel("Public Monthly Rent", { exact: true }).fill("1500");
  await page.getByPlaceholder("Describe the property for prospective tenants...").fill("Published for campaign attribution testing.");
  await page.getByRole("button", { name: "Save manually" }).click();

  await openOperationalAction(page, distributionChannelActionId, "commercial.property.distribution.channel");
  await page.locator("button.o_list_button_add").click();
  await page.getByLabel("Name", { exact: true }).fill(channelName);
  await page.getByRole("button", { name: "Save manually" }).click();

  await openOperationalAction(page, enquiryActionId, "commercial.property.lead");
  await page.locator("button.o_list_button_add").click();
  await page.locator('[name="name"] input').fill(prospectName);
  await page.getByLabel("Phone", { exact: true }).fill("+15555550123");
  await page.getByRole("combobox", { name: "Commercial Unit" }).fill(propertyName);
  await page.getByRole("option", { name: propertyName, exact: true }).click();
  await page.getByRole("combobox", { name: "Campaign / Channel" }).fill(channelName);
  await page.getByRole("option", { name: channelName, exact: true }).click();
  await page.getByRole("button", { name: "Save manually" }).click();
  await expect(page.getByRole("combobox", { name: "Campaign / Channel" })).toHaveValue(channelName);

  await expectNoClientOrServerErrors(page, monitored);
});

test("an administrator can set a unit's virtual tour link and record a prospect's stated budget", async ({ page }) => {
  const monitored = monitorPage(page);
  const propertyName = `E2E Phase18 Building ${Date.now()}`;
  const prospectName = `E2E Phase18 Prospect ${Date.now()}`;
  const tourUrl = "https://tours.example.com/phase18-suite";

  await login(page, administrator);
  await openProperties(page);
  await createProperty(page, propertyName);

  await openOperationalAction(page, unitActionId, "commercial.property.unit");
  await page.locator(".o_searchview_input").fill(propertyName);
  await page.keyboard.press("Enter");
  await page.getByRole("cell", { name: propertyName, exact: true }).first().click();

  await page.getByText("Public Listing", { exact: true }).click();
  await page.getByLabel("Virtual Tour URL?", { exact: true }).fill(tourUrl);
  await page.getByRole("button", { name: "Save manually" }).click();
  await expect(page.getByLabel("Virtual Tour URL?", { exact: true })).toHaveValue(tourUrl);

  await openOperationalAction(page, enquiryActionId, "commercial.property.lead");
  await page.locator("button.o_list_button_add").click();
  await page.locator('[name="name"] input').fill(prospectName);
  await page.getByLabel("Phone", { exact: true }).fill("+15555550124");
  await page.getByRole("combobox", { name: "Commercial Unit" }).fill(propertyName);
  await page.getByRole("option", { name: propertyName, exact: true }).click();
  await page.getByLabel("Stated Budget?", { exact: true }).fill("1200");
  await page.getByRole("button", { name: "Save manually" }).click();
  await expect(page.getByLabel("Stated Budget?", { exact: true })).toHaveValue(/1.?200/);

  await expectNoClientOrServerErrors(page, monitored);
});
