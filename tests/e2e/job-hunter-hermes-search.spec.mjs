import { expect, test } from "@playwright/test";

const database = process.env.E2E_ODOO_DB;
const username = process.env.E2E_PROPERTY_USER;
const password = process.env.E2E_PROPERTY_USER_PASSWORD;

function required(value, label) {
  if (!value || value.startsWith("replace-with-")) throw new Error(`${label} must be configured for E2E.`);
  return value;
}

async function rpc(page, model, method, args = [], kwargs = {}) {
  const response = await page.request.post(`/web/dataset/call_kw/${model}/${method}`, {
    data: { jsonrpc: "2.0", method: "call", params: { model, method, args, kwargs }, id: Date.now() }
  });
  expect(response.ok()).toBeTruthy();
  const body = await response.json();
  if (body.error) throw new Error(body.error.data?.message || body.error.message);
  return body.result;
}

test("profile and authenticated global Hermes searches persist and clean up", async ({ page }) => {
  test.setTimeout(60000);
  const marker = `E2E Hermes ${Date.now()}`;
  const token = `hermes-search-e2e-${Date.now()}`;
  const parameter = "job_hunter_management.hermes_api_token";
  const browserErrors = [];
  const serverErrors = [];
  let profileId;
  let previousToken;
  let baseline = {};
  page.on("pageerror", error => browserErrors.push(error.message));
  page.on("console", message => message.type() === "error" && browserErrors.push(message.text()));
  page.on("response", response => response.status() >= 500 && serverErrors.push(`${response.status()} ${response.url()}`));
  try {
    await page.goto(`/web/login?db=${encodeURIComponent(required(database, "E2E database"))}`);
    await page.locator('input[name="login"]').fill(required(username, "E2E username"));
    await page.locator('input[name="password"]').fill(required(password, "E2E password"));
    await page.locator('button[type="submit"]').click();
    await expect(page.locator(".o_main_navbar")).toBeVisible();
    previousToken = await rpc(page, "ir.config_parameter", "get_param", [parameter, false]);
    await rpc(page, "ir.config_parameter", "set_param", [parameter, token]);
    for (const model of ["job.application", "job.hunter.search.run", "job.hunter.search.config"]) {
      baseline[model] = await rpc(page, model, "search", [[]]);
    }
    profileId = await rpc(page, "job.hunter.profile", "create", [{
      name: marker, skills: "Python, Odoo", target_roles: marker,
      location: "Sydney", target_salary: 125000, remote_ok: true, hybrid_ok: true, onsite_ok: false
    }]);
    const [action] = await rpc(page, "ir.model.data", "search_read", [[
      ["module", "=", "job_hunter_management"], ["name", "=", "action_job_hunter_profile"]
    ], ["res_id"]], { limit: 1 });
    await page.goto(`/web#id=${profileId}&action=${action.res_id}&model=job.hunter.profile&view_type=form`);
    await Promise.all([
      page.waitForResponse(response => response.url().includes("/web/dataset/call_button")),
      page.getByRole("button", { name: "Run Hermes Search" }).click()
    ]);
    const [searchedProfile] = await rpc(page, "job.hunter.profile", "read", [[profileId], ["last_hermes_search_at"]]);
    expect(searchedProfile.last_hermes_search_at).toBeTruthy();
    await expect(page.locator('.o_field_widget[name="last_hermes_search_at"]')).not.toBeEmpty();
    const denied = await page.request.post("/api/job-hunter/search/run", {
      headers: { Authorization: "Bearer wrong", "Content-Type": "application/json" }, data: {}
    });
    expect(denied.status()).toBe(401);
    const response = await page.request.post("/api/job-hunter/search/run", {
      headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" }, data: {}
    });
    expect(response.ok()).toBeTruthy();
    expect(await response.json()).toEqual(expect.objectContaining({ runs: expect.any(Number), errors: expect.any(Number) }));
    expect(await rpc(page, "job.hunter.search.config", "search_count", [[["profile_id", "=", profileId]]])).toBe(1);
    expect(browserErrors).toEqual([]);
    expect(serverErrors).toEqual([]);
  } finally {
    if (page.url().includes("/web")) {
      for (const model of ["job.hunter.search.run", "job.hunter.search.config", "job.application"]) {
        const created = await rpc(page, model, "search", [["!", ["id", "in", baseline[model] || []]]]);
        if (created.length) await rpc(page, model, "unlink", [created]);
        expect(await rpc(page, model, "search_count", [["!", ["id", "in", baseline[model] || []]]])).toBe(0);
      }
      const profiles = await rpc(page, "job.hunter.profile", "search", [["|", ["id", "=", profileId || 0], ["name", "=", marker]]]);
      if (profiles.length) await rpc(page, "job.hunter.profile", "unlink", [profiles]);
      await rpc(page, "ir.config_parameter", "set_param", [parameter, previousToken || ""]);
      expect(await rpc(page, "job.hunter.profile", "search_count", [[["name", "=", marker]]])).toBe(0);
    }
  }
});
