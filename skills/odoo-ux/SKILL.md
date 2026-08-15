---
name: odoo-ux
description: Improve the usability and clarity of Odoo 16 Community interfaces. Use when changes affect menus, window actions, tree, form, kanban, search, settings, reports, portal pages, notifications, translations, or end-user workflows.
---

# Odoo UX

Make the Odoo experience clear for the role completing the task while preserving
the repository's existing visual language.

## Evaluate the Workflow

- Start from the menu or action a real user would use.
- Ensure menu labels, action names, page titles, field labels, help text, and
  validation messages explain the task in plain language.
- Place required fields and primary actions where users expect them. Use groups,
  notebook pages, status bars, and search filters to reduce cognitive load.
- Keep list, form, kanban, and search views aligned with the workflow.
- Respect permissions in the interface: unavailable actions should not appear
  actionable to users who cannot complete them.

## Deliverable

Implement the smallest usability improvements supported by the task. Verify the
affected view on desktop-sized and narrow browser layouts when browser access is
available. Do not redesign unrelated Odoo screens.
