---
name: odoo-security-review
description: Review Odoo 16 Community changes for authorization, data exposure, API, configuration, and tenancy risks. Use when models, fields, record rules, ir.model.access.csv, controllers, integrations, attachments, settings, or Docker and environment configuration change.
---

# Odoo Security Review

Review the diff from the perspective of a user with the least applicable access.

## Review Checklist

- Confirm model ACLs grant only the intended read, create, write, and unlink
  permissions.
- Confirm record rules isolate records correctly across companies, owners, and
  roles. Test both an allowed and denied user path where possible.
- Verify fields containing sensitive data are not exposed by views, exports,
  APIs, computed fields, or `sudo()` calls without explicit authorization.
- Require suitable authentication and authorization on every controller route;
  validate input and avoid leaking internal errors.
- Keep secrets out of source control and logs. Read credentials from environment
  configuration only.
- Check that Docker ports, volumes, and restart behavior match local-development
  intent and do not silently weaken access control.

## Findings

Fix high-confidence vulnerabilities in scope. Report findings by severity with
file references, explain residual risk, and rerun relevant validation after a
fix.
