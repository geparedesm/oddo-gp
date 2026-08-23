PHASE: 20 — AI Development Team para Hermes
OBJECTIVE: Configurar Hermes como coordinador multiagente seguro y eficiente para Odoo.
STATUS: COMPLETE
TASKS: Auditoría; backups; perfiles; permisos; memoria del proyecto; validación.
COMPLETED: Auditoría; backups; seis perfiles y toolsets; memoria `.ai`; prueba Tech Lead; smoke tests; QA; review Claude; diff final.
IN PROGRESS: Ninguno.
BLOCKED: Ninguno.
ACCEPTANCE CRITERIA: Perfiles operativos; routing claro; Graphify dirigido; acceso mínimo soportado por toolsets, con Reviewer sin file/code_execution; contexto persistente; validación sin deploy ni cambios de datos.
FILES AFFECTED: `AGENTS.md`, `.gitignore`, `.ai/*`, perfiles Hermes fuera del repositorio.
TESTS: Seis config checks; matriz de toolsets; smoke de modelos; Compose config/ps; QA read-only; Claude Code read-only; `npm run test:all` PASS (27 E2E); diff check.
REVIEW STATUS: PASS — sin findings CRITICAL/HIGH abiertos.
