import { expect, test } from "@playwright/test";

const database = process.env.E2E_ODOO_DB;
const username = process.env.E2E_ODOO_USERNAME;
const password = process.env.E2E_ODOO_PASSWORD;

function required(value, label) {
  if (!value || value.startsWith("replace-with-")) {
    throw new Error(`${label} must be configured for E2E.`);
  }
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

test("administrator analyses sponsorship from the job form with no browser or network errors", async ({ page }) => {
  const marker = `E2E Sponsorship ${Date.now()}`;
  const browserErrors = [];
  const serverErrors = [];
  let jobId;
  page.on("pageerror", error => browserErrors.push(error.message));
  page.on("console", message => message.type() === "error" && browserErrors.push(message.text()));
  page.on("response", response => response.status() >= 500 && serverErrors.push(`${response.status()} ${response.url()}`));

  try {
    await page.goto(`/web/login?db=${encodeURIComponent(required(database, "E2E database"))}`);
    await page.locator('input[name="login"]').fill(required(username, "E2E username"));
    await page.locator('input[name="password"]').fill(required(password, "E2E password"));
    await page.locator('button[type="submit"]').click();
    await expect(page.locator(".o_main_navbar")).toBeVisible();

    jobId = await rpc(page, "job.application", "create", [{
      name: marker,
      company_name: marker,
      job_url: `https://e2e.sponsorship.test/${Date.now()}`,
      job_description: "Employer sponsored business, but no sponsorship available for this role.",
      match_score: 95
    }]);
    const [actionData] = await rpc(page, "ir.model.data", "search_read", [[
      ["module", "=", "job_hunter_management"],
      ["name", "=", "action_job_application"]
    ], ["res_id"]], { limit: 1 });
    const actionId = actionData.res_id;
    await page.goto(`/web#id=${jobId}&action=${actionId}&model=job.application&view_type=form`);
    await expect(page.getByText(marker, { exact: true }).first()).toBeVisible();
    await page.getByRole("button", { name: "Analyse Sponsorship" }).click();
    await page.getByRole("tab", { name: "Sponsorship" }).click();
    await expect(page.locator('.o_field_widget[name="sponsorship_status"]').last()).toContainText("No");
    await expect(page.locator('.o_field_widget[name="priority_score"]').last()).toContainText("45.00");
    await expect(page.locator('.o_field_widget[name="sponsorship_reason"]')).toContainText(/explicit negative sponsorship evidence/i);
    await expect(page.locator(".o_error_dialog")).toHaveCount(0);
    await page.waitForTimeout(500);
    expect(serverErrors).toEqual([]);
    expect(browserErrors).toEqual([]);
  } finally {
    if (page.url().includes("/web")) {
      const ids = await rpc(page, "job.application", "search", [["|", ["id", "=", jobId || 0], ["name", "=", marker]]]);
      if (ids.length) await rpc(page, "job.application", "unlink", [ids]);
      const remaining = await rpc(page, "job.application", "search_count", [[["name", "=", marker]]]);
      expect(remaining).toBe(0);
    }
  }
});
