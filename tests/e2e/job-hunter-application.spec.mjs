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

test("approved job preparation stops at manual action required without submission", async ({ page }) => {
  test.setTimeout(60000);
  const marker = `E2E Phase 8 ${Date.now()}`;
  const browserErrors = [];
  const serverErrors = [];
  let jobId;
  let profileId;
  let ruleId;
  let notificationId;
  const token = `phase8-e2e-token-${Date.now()}`;
  const parameterKeys = [
    "job_hunter_management.hermes_api_token", "job_hunter_management.whatsapp_enabled",
    "job_hunter_management.whatsapp_authorized_number", "job_hunter_management.whatsapp_minimum_priority"
  ];
  const previous = {};
  page.on("pageerror", error => browserErrors.push(error.message));
  page.on("console", message => message.type() === "error" && browserErrors.push(message.text()));
  page.on("response", response => response.status() >= 500 && serverErrors.push(`${response.status()} ${response.url()}`));
  try {
    await page.goto(`/web/login?db=${encodeURIComponent(required(database, "E2E database"))}`);
    await page.locator('input[name="login"]').fill(required(username, "E2E username"));
    await page.locator('input[name="password"]').fill(required(password, "E2E password"));
    await page.locator('button[type="submit"]').click();
    await expect(page.locator(".o_main_navbar")).toBeVisible();
    for (const key of parameterKeys) previous[key] = await rpc(page, "ir.config_parameter", "get_param", [key, false]);
    await rpc(page, "ir.config_parameter", "set_param", [parameterKeys[0], token]);
    await rpc(page, "ir.config_parameter", "set_param", [parameterKeys[1], "True"]);
    await rpc(page, "ir.config_parameter", "set_param", [parameterKeys[2], "+61400123456"]);
    await rpc(page, "ir.config_parameter", "set_param", [parameterKeys[3], "0"]);
    profileId = await rpc(page, "job.hunter.profile", "create", [{
      name: marker, skills: "Odoo, Python", work_experience: "Approved E2E experience."
    }]);
    ruleId = await rpc(page, "job.document.generation.rule", "create", [{ name: marker, minimum_priority_score: 0 }]);
    jobId = await rpc(page, "job.application", "create", [{
      name: "Phase 8 Engineer", company_name: marker, job_url: `https://e2e.phase8.test/${Date.now()}`,
      source: "other", match_score: 90, state: "good_match"
    }]);
    await rpc(page, "job.application", "action_generate_documents", [[jobId]]);
    const documentIds = await rpc(page, "job.application.document", "search", [[["application_id", "=", jobId]]]);
    await rpc(page, "job.application.document", "action_review", [documentIds]);
    await rpc(page, "job.application.document", "action_approve", [documentIds]);
    await rpc(page, "job.application", "action_queue_whatsapp_notification", [[jobId]]);
    [notificationId] = await rpc(page, "job.whatsapp.notification", "search", [[
      ["application_id", "=", jobId], ["kind", "=", "opportunity"]
    ]], { limit: 1 });
    const [notification] = await rpc(page, "job.whatsapp.notification", "read", [[notificationId], ["short_ref", "job_ref"]]);
    const approvalResponse = await page.request.post("/api/job-hunter/whatsapp/commands", {
      headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
      data: {
        event_id: `phase8-e2e-${Date.now()}`, sender: "+61400123456", command: "APPROVE",
        job_ref: notification.job_ref, notification_ref: notification.short_ref
      }
    });
    expect(approvalResponse.ok()).toBeTruthy();
    const [action] = await rpc(page, "ir.model.data", "search_read", [[
      ["module", "=", "job_hunter_management"], ["name", "=", "action_job_application"]
    ], ["res_id"]], { limit: 1 });
    await page.goto(`/web#id=${jobId}&action=${action.res_id}&model=job.application&view_type=form`);
    await expect(page.locator('.o_field_widget[name="company_name"] input')).toHaveValue(marker);
    await page.getByRole("button", { name: "Prepare Application" }).click();
    await page.getByRole("button", { name: "Ok" }).click();
    await expect(page.locator('.o_field_widget[name="state"]')).toContainText("Manual Action Required");
    await page.getByRole("tab", { name: "Application Attempts" }).click();
    await expect(page.getByRole("cell", { name: "Manual Action Required" }).first()).toBeVisible();
    const [job] = await rpc(page, "job.application", "read", [[jobId], ["state", "date_applied"]]);
    expect(job).toEqual(expect.objectContaining({ state: "manual_action_required", date_applied: false }));
    expect(await rpc(page, "job.application.attempt", "search_count", [[["application_id", "=", jobId]]])).toBe(1);
    expect(browserErrors).toEqual([]);
    expect(serverErrors).toEqual([]);
  } finally {
    if (page.url().includes("/web")) {
      const jobIds = await rpc(page, "job.application", "search", [["|", ["id", "=", jobId || 0], ["company_name", "=", marker]]]);
      const attemptIds = await rpc(page, "job.application.attempt", "search", [[["application_id", "in", jobIds]]]);
      const approvalIds = await rpc(page, "job.application.approval", "search", [[["application_id", "in", jobIds]]]);
      const notificationIds = await rpc(page, "job.whatsapp.notification", "search", [[["application_id", "in", jobIds]]]);
      if (jobIds.length) await rpc(page, "job.application", "unlink", [jobIds]);
      const profileIds = await rpc(page, "job.hunter.profile", "search", [["|", ["id", "=", profileId || 0], ["name", "=", marker]]]);
      const ruleIds = await rpc(page, "job.document.generation.rule", "search", [["|", ["id", "=", ruleId || 0], ["name", "=", marker]]]);
      if (profileIds.length) await rpc(page, "job.hunter.profile", "unlink", [profileIds]);
      if (ruleIds.length) await rpc(page, "job.document.generation.rule", "unlink", [ruleIds]);
      for (const key of parameterKeys) await rpc(page, "ir.config_parameter", "set_param", [key, previous[key] || ""]);
      expect(await rpc(page, "job.application", "search_count", [[["id", "in", jobIds]]])).toBe(0);
      expect(await rpc(page, "job.application.attempt", "search_count", [[["id", "in", attemptIds]]])).toBe(0);
      expect(await rpc(page, "job.application.approval", "search_count", [[["id", "in", approvalIds]]])).toBe(0);
      expect(await rpc(page, "job.whatsapp.notification", "search_count", [[["id", "in", notificationIds]]])).toBe(0);
    }
  }
});
