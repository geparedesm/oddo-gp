import { expect, test } from "@playwright/test";

const database = process.env.E2E_ODOO_DB;
const username = process.env.E2E_ODOO_USERNAME;
const password = process.env.E2E_ODOO_PASSWORD;

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

test("administrator queues a prioritized WhatsApp opportunity without applying", async ({ page }) => {
  test.setTimeout(60000);
  const marker = `E2E Phase 7 ${Date.now()}`;
  const keys = ["job_hunter_management.whatsapp_enabled", "job_hunter_management.whatsapp_authorized_number", "job_hunter_management.whatsapp_minimum_priority"];
  const previous = {};
  const browserErrors = [];
  const serverErrors = [];
  let jobId;
  page.on("pageerror", error => browserErrors.push(error.message));
  page.on("console", message => message.type() === "error" && browserErrors.push(message.text()));
  page.on("response", response => response.status() >= 500 && serverErrors.push(`${response.status()} ${response.url()}`));
  try {
    await page.goto(`/web/login?db=${encodeURIComponent(required(database, "E2E database"))}`);
    await page.locator('input[name="login"]').fill(required(username, "E2E administrator username"));
    await page.locator('input[name="password"]').fill(required(password, "E2E administrator password"));
    await page.locator('button[type="submit"]').click();
    await expect(page.locator(".o_main_navbar")).toBeVisible();
    for (const key of keys) previous[key] = await rpc(page, "ir.config_parameter", "get_param", [key, false]);
    await rpc(page, "ir.config_parameter", "set_param", [keys[0], "True"]);
    await rpc(page, "ir.config_parameter", "set_param", [keys[1], "+61400123456"]);
    await rpc(page, "ir.config_parameter", "set_param", [keys[2], "75"]);
    jobId = await rpc(page, "job.application", "create", [{
      name: "Odoo Engineer", company_name: marker, location: "Sydney", job_url: `https://e2e.phase7.test/${Date.now()}`,
      source: "seek", match_score: 90, sponsorship_status: "yes", state: "good_match", match_explanation: "Strong approved match"
    }]);
    const [action] = await rpc(page, "ir.model.data", "search_read", [[
      ["module", "=", "job_hunter_management"], ["name", "=", "action_job_application"]
    ], ["res_id"]], { limit: 1 });
    await page.goto(`/web#id=${jobId}&action=${action.res_id}&model=job.application&view_type=form`);
    await expect(page.locator('.o_field_widget[name="company_name"] input')).toHaveValue(marker);
    await page.getByRole("button", { name: "Queue WhatsApp Notification" }).click();
    await page.getByRole("tab", { name: "WhatsApp" }).click();
    await expect(page.getByRole("cell", { name: "Pending" })).toBeVisible();
    expect(await rpc(page, "job.application", "read", [[jobId], ["state", "date_applied"]])).toEqual([
      expect.objectContaining({ state: "good_match", date_applied: false })
    ]);
    expect(browserErrors).toEqual([]);
    expect(serverErrors).toEqual([]);
  } finally {
    if (page.url().includes("/web")) {
      const jobIds = await rpc(page, "job.application", "search", [["|", ["id", "=", jobId || 0], ["company_name", "=", marker]]]);
      const notificationIds = await rpc(page, "job.whatsapp.notification", "search", [[["application_id", "in", jobIds]]]);
      const commandIds = await rpc(page, "job.whatsapp.command", "search", [[["application_id", "in", jobIds]]]);
      const approvalIds = await rpc(page, "job.application.approval", "search", [[["application_id", "in", jobIds]]]);
      if (jobIds.length) await rpc(page, "job.application", "unlink", [jobIds]);
      for (const key of keys) await rpc(page, "ir.config_parameter", "set_param", [key, previous[key] || ""]);
      expect(await rpc(page, "job.application", "search_count", [[ ["company_name", "=", marker] ]])).toBe(0);
      expect(await rpc(page, "job.whatsapp.notification", "search_count", [[ ["id", "in", notificationIds] ]])).toBe(0);
      expect(await rpc(page, "job.whatsapp.command", "search_count", [[ ["id", "in", commandIds] ]])).toBe(0);
      expect(await rpc(page, "job.application.approval", "search_count", [[ ["id", "in", approvalIds] ]])).toBe(0);
    }
  }
});
