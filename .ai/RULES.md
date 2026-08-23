# Reglas obligatorias

1. Nunca push directo a `main`; el repositorio usa actualmente `develop` y `feature/*`.
2. Nunca deploy a producción sin aprobación explícita.
3. Nunca modificar datos de producción sin aprobación explícita.
4. Nunca exponer secretos ni leerlos salvo necesidad explícita y segura; nunca persistirlos en memoria, sesiones, prompts, logs o documentación.
5. Nunca confirmar `.env`, credenciales o tokens.
6. Ejecutar pruebas relevantes antes de declarar finalización.
7. Revisar `git diff`, archivos accidentales y logs relevantes antes del cierre.
8. Preferir cambios mínimos, mantenibles y upgrade-safe.
9. Respetar convenciones Odoo 16 Community y no duplicar funcionalidad.
10. Preservar cambios locales ajenos; no resetear ni reescribir historia.
11. Usar Graphify para arquitectura, dependencias, áreas desconocidas, cambios transversales, blast radius y refactors; ir directo a archivos conocidos para cambios pequeños.
12. Presupuesto de contexto: buscar → identificar → leer mínimo → modificar → probar.
13. No leer repositorios, módulos ni archivos completos innecesariamente; no reanalizar archivos sin cambios.
14. Features significativas: discovery → implementación especializada → QA independiente → review → tests → diff final.
15. CRITICAL de QA o Reviewer bloquea el cierre.
16. Backend y Frontend solo trabajan en paralelo con archivos e interfaces claramente separados.
17. No hacer commit ni push salvo solicitud explícita del usuario.
18. Seguir `AGENTS.md` y los skills Odoo del repositorio como quality gates.

## Matriz de perfiles
- `tech-lead`: terminal, archivos, skills, planificación, memoria y delegación; sin web, navegador, multimedia ni cron.
- `backend`: terminal, archivos, ejecución y skills; sin navegador, delegación ni memoria.
- `frontend`: terminal, archivos, ejecución, navegador, visión y computer use; sin delegación ni memoria.
- `qa`: igual que Frontend para validar UI y runtime, con independencia del implementador.
- `reviewer`: toolsets `terminal`, `skills` y `todo` únicamente; terminal solo para inspección o para invocar Claude Code con `--allowedTools Read`; sin toolset de archivos, navegador, ejecución, memoria ni delegación. Hermes no separa comandos read/write dentro de terminal, por lo que SOUL y approvals son una segunda barrera obligatoria.
- `devops`: terminal, archivos y ejecución; sin navegador, delegación ni acceso autónomo a producción.

El punto de entrada es `tech-lead` (alias local) o el perfil `tech-lead` del Dashboard. `default` permanece activo para no alterar el gateway WhatsApp existente.
