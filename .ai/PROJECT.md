# Proyecto

## Propósito
Desarrollar y mantener `commercial_property_management`, módulo Odoo 16 Community para inmuebles comerciales, unidades, prospectos, visitas, reservas, solicitudes, contratos, mantenimiento, publicación e integraciones.

## Stack y alcance
- Odoo 16 Community, Python, ORM Odoo, XML/QWeb, JavaScript y PostgreSQL 15.
- Docker Compose: `db`, `odoo`, `addon_watcher`.
- Módulo principal: `addons/commercial_property_management`; `login_csrf_guard` es auxiliar y solo entra en alcance cuando cambia autenticación/login.
- Dependencias Odoo: `base`, `contacts`, `mail`.
- Testing: tests Odoo, Playwright E2E y tests Node del MCP.
- Integraciones: Hermes, WhatsApp, MCP `odoo-properties` y Graphify.

## Convenciones
- Nombres técnicos estables en inglés; texto visible traducible.
- Cambios mínimos, upgrade-safe y compatibles con Community.
- ORM antes que SQL directo; permisos explícitos y menor privilegio.
- Criterios observables, pruebas proporcionales y diff final revisado.
- Git actual: `develop` como rama de integración y `feature/*` para features; no imponer `main` mientras no exista.
