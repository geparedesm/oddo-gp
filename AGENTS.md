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
7. After every E2E run, remove every record created by the E2E workflow. This
   cleanup is mandatory whether the run passes, fails, or is interrupted; use a
   `finally`/`trap` cleanup path when the runner supports it, and verify that
   no E2E-created records remain.
8. Inspect `git diff`, relevant Docker logs, and update concise documentation
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

## graphify

This project has a knowledge graph at graphify-out/ with god nodes, community structure, and cross-file relationships.

When the user types `/graphify`, use the installed graphify skill or instructions before doing anything else.

Rules:
- For architecture discovery, dependency analysis, unfamiliar code, cross-module changes, impact analysis, blast radius, call relationships, or large refactors, first run `graphify query "<question>"` when graphify-out/graph.json exists. Use `graphify path "<A>" "<B>"` for relationships and `graphify explain "<concept>"` for focused concepts. These return a scoped subgraph, usually much smaller than GRAPH_REPORT.md or raw grep output.
- For a small change in one or two known files (for example a typo, known XML record, single known method, small CSS change, or known test), skip Graphify when targeted search/direct reads consume less context. State that choice in discovery.
- Dirty graphify-out/ files are expected after hooks or incremental updates; dirty graph files are not a reason to skip graphify. Only skip graphify if the task is about stale or incorrect graph output, or the user explicitly says not to use it.
- If graphify-out/wiki/index.md exists, use it for broad navigation instead of raw source browsing.
- Read graphify-out/GRAPH_REPORT.md only for broad architecture review or when query/path/explain do not surface enough context.
- After modifying code, run `graphify update .` to keep the graph current (AST-only, no API cost).
