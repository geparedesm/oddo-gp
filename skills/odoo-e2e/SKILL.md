---
name: odoo-e2e
description: Validate Odoo 16 Community workflows end to end in a running local environment. Use when an end-user flow, view, menu, browser asset, JavaScript, controller route, API endpoint, or permissions behavior is changed.
---

# Odoo End-to-End Validation

Test the workflow as the intended role in the running local environment.

## Test Procedure

- Confirm the Compose services are healthy and identify the exposed Odoo URL.
- Log in with the intended role. Navigate from the user-facing menu instead of
  jumping directly to an internal record whenever possible.
- Execute the acceptance criteria, including one invalid or unauthorized path
  for security-sensitive changes.
- Inspect the browser console for uncaught errors and relevant network requests
  for failed HTTP responses.
- Verify persisted effects by refreshing the page or reopening the relevant
  record.

## Fallback and Evidence

Use browser/computer automation when available. If it is unavailable, perform
the strongest feasible HTTP, module-upgrade, and log checks, then explicitly
state that visual browser validation was not run. Record the tested URL, role,
steps, and result.
