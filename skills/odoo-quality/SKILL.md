---
name: odoo-quality
description: Validate Odoo 16 modules and the local Docker Compose runtime. Use after Odoo code or configuration changes to check syntax, manifests, XML/data loading, module installation or upgrade, container health, logs, and relevant automated tests.
---

# Odoo Quality

Validate the changed behavior proportionally before reporting success.

## Required Checks

- Run `docker compose config` after Compose or environment changes.
- Confirm required services are running with `docker compose ps`.
- Check logs for Python tracebacks, XML parse errors, module loading failures,
  and PostgreSQL connection failures.
- Upgrade each changed custom module. Use
  `scripts/dev-update-module.sh <module_name>` when available.
- Run existing targeted tests. Add tests if a behavior lacks coverage and the
  repository supports them.

## Installation Paths

For a new module, validate installation on a clean database when practical. For
an existing module, validate an upgrade on the development database. These paths
catch different manifest, data, and migration failures.

## Result Discipline

Record the actual commands and outcomes. If the environment, browser, database,
or a dependency prevents a check, do not infer success; report the skipped check
and its risk.
