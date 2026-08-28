# Job Hunter Management — Fase 2 API

La integración HTTP de Hermes usa `HERMES_API_TOKEN` (variable de entorno) o el
parámetro protegido `job_hunter_management.hermes_api_token`. El token se valida
con comparación constante; nunca se escribe en logs.

## Endpoints

- `POST /api/job-hunter/jobs` crea una vacante (`external_id` hace el reintento idempotente).
- `GET /api/job-hunter/jobs` lista vacantes y admite `state`, `source`, `sponsorship_status`,
  `match_score_min`, `company_name`, `date_found` y `limit`.
- `GET /api/job-hunter/jobs/<id>` devuelve una vacante.
- `PATCH /api/job-hunter/jobs/<id>` actualiza únicamente campos de integración autorizados.

Todas las solicitudes requieren `Authorization: Bearer ...` y JSON estricto.
Las respuestas son JSON con el objeto `job` o `jobs`, y errores con
`{"error": {"code": ..., "message": ...}}`. El serializer no expone `cv_file`,
`cover_letter`, `notes` ni `raw_job_data`.

Esta fase no implementa scraping, matching IA, WhatsApp ni aplicación automática.
