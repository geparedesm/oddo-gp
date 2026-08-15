---
name: odoo-discovery
description: Inspect an Odoo 16 repository before a functional change. Use for new features, bug fixes, refactors, model changes, views, security, APIs, Docker, and module troubleshooting to identify conventions, dependencies, affected modules, and acceptance criteria.
---

# Odoo Discovery

Inspect before editing. Start with the repository instructions, `git status`,
the module manifest, and the files nearest to the requested behavior.

## Build the Change Map

- Identify affected modules, models, views, controllers, data files, security
  rules, assets, and Compose services.
- Read `__manifest__.py` before changing module code. Confirm dependencies and
  load order.
- Trace model fields to views, access CSV files, record rules, menus, actions,
  tests, and external IDs.
- Preserve established names, module boundaries, and the current Odoo version.
- Inspect uncommitted changes and avoid overwriting them.

## Define Acceptance Criteria

State concise, observable outcomes before implementation. Include the intended
user role, expected UI/API behavior, invalid cases, and data effects. For
security-sensitive work, specify both allowed and denied behavior.

## Report Before Editing

Summarize the affected surface, the files likely to change, and the checks that
will be required. Do not implement speculative scope.
