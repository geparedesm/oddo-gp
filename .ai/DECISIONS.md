# Decisiones arquitectónicas

## 2026-08-23 — Perfiles Hermes aislados por responsabilidad
DECISION: Usar `tech-lead`, `backend`, `frontend`, `qa`, `reviewer` y `devops`, con toolsets limitados por rol.
REASON: Separación clara, menor contexto y menor privilegio.
ALTERNATIVES: Un solo agente generalista; múltiples servicios externos.
IMPACT: Mejor routing y revisión; cada perfil conserva estado aislado.

## 2026-08-23 — Codex como runtime Hermes y Claude Code como especialista
DECISION: Mantener `openai-codex` como proveedor Hermes de los perfiles; Tech Lead y Reviewer prefieren Claude Code CLI para análisis/review complejos y read-only.
REASON: Codex OAuth ya funciona; Claude Code ya está instalado y autenticado; no se copian secretos a perfiles.
ALTERNATIVES: Duplicar credenciales Anthropic en cada perfil; instalar Codex CLI independiente.
IMPACT: Reutiliza integraciones existentes con menor exposición de credenciales.

## 2026-08-23 — Graphify dirigido, no obligatorio para cambios pequeños
DECISION: Consultar Graphify para arquitectura, dependencias, áreas desconocidas y blast radius; usar acceso directo para contexto conocido y pequeño.
REASON: Minimizar tokens sin perder comprensión.
ALTERNATIVES: Consultarlo siempre; no usarlo.
IMPACT: Menos contexto y menor latencia en cambios triviales.

## 2026-08-23 — No añadir MCP ni skills duplicados
DECISION: Conservar `odoo-properties` y los siete skills Odoo existentes sin instalar GitHub, PostgreSQL o Filesystem MCP.
REASON: Las herramientas actuales ya cubren esas capacidades y añadirlas ampliaría permisos y contexto.
ALTERNATIVES: Instalar MCP y nueve skills nuevos.
IMPACT: Menor superficie de ataque y mantenimiento.

## 2026-08-23 — Conservar `default` por compatibilidad del gateway
DECISION: No cambiar el sticky profile activo; exponer Tech Lead mediante el comando `tech-lead` y el Dashboard.
REASON: `default` aloja el gateway WhatsApp activo y cambiarlo podría alterar reinicios o routing existentes.
ALTERNATIVES: `hermes profile use tech-lead`.
IMPACT: No se rompe WhatsApp; el usuario inicia desarrollo con `tech-lead`.
