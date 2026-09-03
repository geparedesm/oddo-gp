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

test("job hunter user generates, reviews and approves truthful tailored documents", async ({ page }) => {
  test.setTimeout(60000);
  const marker = `E2E Phase 6 ${Date.now()}`;
  const browserErrors = [];
  const serverErrors = [];
  let jobId;
  let profileId;
  let ruleId;
  page.on("pageerror", error => browserErrors.push(error.message));
  page.on("console", message => message.type() === "error" && browserErrors.push(message.text()));
  page.on("response", response => response.status() >= 500 && serverErrors.push(`${response.status()} ${response.url()}`));

  try {
    await page.goto(`/web/login?db=${encodeURIComponent(required(database, "E2E database"))}`);
    await page.locator('input[name="login"]').fill(required(username, "E2E username"));
    await page.locator('input[name="password"]').fill(required(password, "E2E password"));
    await page.locator('button[type="submit"]').click();
    await expect(page.locator(".o_main_navbar")).toBeVisible();
    profileId = await rpc(page, "job.hunter.profile", "create", [{
      name: marker, skills: "Python, Odoo", technologies: "Docker", years_experience: 5,
      work_experience: "Built approved Odoo services from 2020 to 2025.", target_roles: "Odoo Developer"
    }]);
    ruleId = await rpc(page, "job.document.generation.rule", "create", [{ name: marker, minimum_priority_score: 75 }]);
    jobId = await rpc(page, "job.application", "create", [{
      name: "Odoo Developer", company_name: marker, job_url: `https://e2e.phase6.test/${Date.now()}`,
      mandatory_skills: "Python, Kubernetes", required_technologies: "Docker", match_score: 90
    }]);
    const [actionData] = await rpc(page, "ir.model.data", "search_read", [[
      ["module", "=", "job_hunter_management"], ["name", "=", "action_job_application"]
    ], ["res_id"]], { limit: 1 });
    await page.goto(`/web#id=${jobId}&action=${actionData.res_id}&model=job.application&view_type=form`);
    await expect(page.locator('.o_field_widget[name="company_name"] input')).toHaveValue(marker);
    await page.getByRole("button", { name: "Generate Tailored Documents" }).click();
    await page.getByRole("tab", { name: "Application Documents" }).click();
    await page.getByRole("row").filter({ hasText: "Draft" }).click();
    await expect(page.locator('.o_field_widget[name="tailored_cv"]')).toContainText("Python");
    await expect(page.locator('.o_field_widget[name="tailored_cv"]')).not.toContainText("Kubernetes");
    await page.getByRole("button", { name: "Mark Reviewed" }).click();
    await page.getByRole("button", { name: "Approve" }).click();
    await expect(page.locator('.o_field_widget[name="state"]').last()).toContainText("Approved");
    await expect(page.locator(".o_error_dialog")).toHaveCount(0);
    expect(serverErrors).toEqual([]);
    expect(browserErrors).toEqual([]);
  } finally {
    if (page.url().includes("/web")) {
      const jobIds = await rpc(page, "job.application", "search", [["|", ["id", "=", jobId || 0], ["company_name", "=", marker]]]);
      if (jobIds.length) await rpc(page, "job.application", "unlink", [jobIds]);
      const profileIds = await rpc(page, "job.hunter.profile", "search", [["|", ["id", "=", profileId || 0], ["name", "=", marker]]]);
      if (profileIds.length) await rpc(page, "job.hunter.profile", "unlink", [profileIds]);
      const ruleIds = await rpc(page, "job.document.generation.rule", "search", [["|", ["id", "=", ruleId || 0], ["name", "=", marker]]]);
      if (ruleIds.length) await rpc(page, "job.document.generation.rule", "unlink", [ruleIds]);
      expect(await rpc(page, "job.application.document", "search_count", [[[
        "application_id", "in", jobIds
      ]]])).toBe(0);
      expect(await rpc(page, "job.application", "search_count", [[[
        "company_name", "=", marker
      ]]])).toBe(0);
      expect(await rpc(page, "job.hunter.profile", "search_count", [[[
        "name", "=", marker
      ]]])).toBe(0);
      expect(await rpc(page, "job.document.generation.rule", "search_count", [[[
        "name", "=", marker
      ]]])).toBe(0);
    }
  }
});
