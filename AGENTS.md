# Odoo 16 Delivery Policy

Use the repository skills in `skills/` for every functional code change. Treat the
following sequence as mandatory quality gates:

1. Define observable acceptance criteria and inspect the affected code with
   `odoo-discovery`.
2. Implement the smallest maintainable change with `odoo-implementation`.
3. Run module, container, and runtime checks with `odoo-quality`.
4. Review access control, record rules, controllers, and configuration with
   `odoo-security-review` whenever models, permissions, APIs, or configuration
   are affected.
5. Use `odoo-ux` when the change affects menus, views, forms, reports, portal
   pages, messages, or any end-user workflow.
6. Use `odoo-e2e` when an end-user workflow, endpoint, or browser asset is
   affected. Verify the browser console and relevant network requests.
7. Inspect `git diff`, relevant Docker logs, and update concise documentation
   before reporting completion.

Do not claim a change is complete when a required check fails or was not run.
State the reason and the remaining risk instead. Do not modify unrelated files,
reset user changes, or expose credentials in output.

For a full feature, use `odoo-delivery-pipeline` to coordinate these gates in
order. For a narrow request, run only the applicable gates, but always complete
discovery, implementation, quality validation, and final diff review.

## Repository Runtime

- Odoo version: 16 Community.
- Runtime: Docker Compose with `db`, `odoo`, and `addon_watcher` services.
- Custom modules: `addons/`.
- Configuration: `config/odoo.conf` and `.env`.
- Database name: read `ODOO_DB_NAME` from `.env`; never hard-code it in new
  scripts.
- Refresh changes: rely on `addon_watcher` for normal module changes and use
  `scripts/dev-update-module.sh <module_name>` for a deliberate update.

## Required Handoff

Report changed files, acceptance criteria verified, commands/tests run, and any
known limitation. For UI work, include the tested URL and the user role used.
