# Arquitectura

## Módulos
- `commercial_property_management`: dominio principal.
- `login_csrf_guard`: módulo auxiliar independiente.

## Dominio principal
- Inmuebles y unidades comerciales.
- Leads, visitas, reservas y solicitudes.
- Inquilinos, contratos, depósitos, penalidades y renovaciones.
- Mantenimiento, handover, portfolios, publicación y canales de distribución.
- Alertas de integración y configuración.

Los modelos se relacionan mediante ORM Odoo; las vistas, acciones, menús, ACL y record rules completan cada workflow.

## Servicios e integraciones
- Odoo web y cron sobre PostgreSQL.
- `addon_watcher` actualiza cambios de módulos en desarrollo.
- API Hermes en `controllers/hermes_api.py`.
- MCP `odoo-properties` mediante `scripts/run-hermes-property-mcp.sh`.
- WhatsApp consume el flujo público de búsqueda y consultas.
- Playwright valida workflows de navegador.

## Workflows importantes
1. Publicación y búsqueda de propiedades/unidades disponibles.
2. Lead → visita → reserva/solicitud → contrato.
3. Contrato → depósito/renovación/vencimiento → disponibilidad de unidad.
4. Mantenimiento y handover.
5. Consulta WhatsApp/Hermes → API Odoo → enquiry revisada por manager.

Graphify es la fuente detallada de símbolos y relaciones; este archivo solo resume límites estables.
