# Job Hunter Management — Fase 3

La integración HTTP de Hermes usa `HERMES_API_TOKEN` (variable de entorno) o el
parámetro protegido `job_hunter_management.hermes_api_token`. El token se valida
con comparación constante; nunca se escribe en logs.

## Búsqueda y sincronización

- Crear una configuración desde **Job Hunter → Search Configurations** con keywords,
  roles, ubicación, modalidad, salario mínimo, antigüedad máxima y fuentes habilitadas.
- **Run Search** ejecuta manualmente la búsqueda; `cron_run_active_configs` queda
  disponible para un scheduler.
- Las fuentes iniciales (SEEK, LinkedIn, Indeed, Jora y Company Careers) tienen
  adaptadores deterministas fixture, sin scraping frágil ni secretos. Pueden
  sustituirse por adaptadores de feeds/API permitidos sin cambiar la sincronización.
- Cada ejecución registra por fuente vacantes encontradas, nuevas, duplicadas,
  errores y duración; una fuente fallida no interrumpe las demás.
- La normalización conserva título, empresa, ubicación, URL, fuente, ID de fuente,
  descripción, salario/moneda, fecha, modalidad y payload JSON normalizado.
- La sincronización es idempotente por `source + source_job_id`, URL canónica
  (sin parámetros de tracking) y empresa+título+ubicación. Las vacantes nuevas
  quedan en estado `found`; esta fase no aplica, analiza ni genera documentos.

## API de Hermes (Fase 2)

- `POST /api/job-hunter/jobs` crea una vacante (`external_id` hace el reintento idempotente).
- `GET /api/job-hunter/jobs` lista vacantes.
- `GET /api/job-hunter/jobs/<id>` devuelve una vacante.
- `PATCH /api/job-hunter/jobs/<id>` actualiza únicamente campos autorizados.

Todas las solicitudes requieren `Authorization: Bearer ...` y JSON estricto.
El serializer no expone `cv_file`, `cover_letter`, `notes` ni `raw_job_data`.
