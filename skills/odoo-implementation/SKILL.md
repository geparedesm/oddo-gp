---
name: odoo-implementation
description: Implement clean, maintainable Odoo 16 Community changes. Use for models, business logic, views, menus, security, controllers, data files, module manifests, Docker development tooling, and bug fixes after repository discovery.
---

# Odoo Implementation

Implement the smallest change that satisfies the agreed acceptance criteria.

## Odoo Conventions

- Keep Python models thin and place business invariants in model methods.
- Use Odoo ORM APIs, translated user-facing strings, stable XML IDs, and clear
  names. Do not bypass access checks without a documented reason.
- Add fields, views, security CSV, record rules, data, and manifest entries in
  a consistent order. Declare every new XML/CSV file in `__manifest__.py`.
- Make view inheritance narrow and resilient. Avoid XPath expressions that are
  unnecessarily broad.
- Do not introduce Enterprise-only dependencies into Community modules.

## Development Safety

- Use `apply_patch` for edits and retain unrelated user changes.
- Keep configuration in `.env` or `config/`; do not commit secrets.
- Prefer a focused migration or upgrade-safe default to hidden data mutation.
- Add or update automated tests whenever business behavior changes.

## Before the Next Gate

Review the diff for dead code, unused imports, manifest order, missing security
entries, and missing translations. Hand the exact module names and expected
runtime behavior to `odoo-quality`.
