---
name: odoo-delivery-pipeline
description: Coordinate a complete Odoo 16 Community delivery workflow from requirements through verified handoff. Use for functional features, non-trivial bug fixes, refactors, module work, and release-ready changes that require implementation, review, validation, UX evaluation, and end-to-end testing.
---

# Odoo Delivery Pipeline

Coordinate the repository skills in order. Treat every stage as a quality gate.

## 1. Discover

Use `odoo-discovery`. Define acceptance criteria, affected modules, user roles,
data impact, and required validation. Stop and ask for direction only when a
material product or data decision is genuinely missing.

## 2. Implement

Use `odoo-implementation`. Make focused, upgrade-safe changes and add targeted
tests for changed business behavior.

## 3. Validate Runtime

Use `odoo-quality`. Check the Compose configuration, services, module upgrade,
targeted tests, and logs. Resolve failures before continuing.

## 4. Review Security

Use `odoo-security-review` whenever authorization, records, fields, routes,
settings, integrations, uploads, or configuration are affected. Resolve
high-confidence findings in scope.

## 5. Validate UX

Use `odoo-ux` only for user-facing changes: menus, views, actions, forms,
reports, portal, notifications, or translations. Keep the improvement focused.

## 6. Validate End to End

Use `odoo-e2e` when a browser flow, JavaScript asset, endpoint, or permission
behavior changes. Check console and network errors. Do not represent fallback
checks as a browser test.

## 7. Hand Off

Inspect the final diff and relevant logs. Report changed files, acceptance
criteria verified, commands and tests run, browser evidence when applicable,
and any limitation or residual risk. Never report completion with an unresolved
required-gate failure.
