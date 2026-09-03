# Job Hunter Management — Fase 9

## Aprobación por WhatsApp

- La integración queda desactivada por defecto. Un administrador configura un
  único número internacional autorizado, el umbral de prioridad y la activación
  en **Job Hunter → WhatsApp Settings**.
- Odoo mantiene un outbox neutral: no llama directamente a WuzAPI/n8n y no
  almacena secretos del proveedor. Un adaptador autenticado usa
  `/api/job-hunter/whatsapp/*` con el Bearer token existente de Hermes.
- Cada mensaje incluye referencia de job y referencia aleatoria de notificación.
  `APPROVE`, `IGNORE`, `DETAILS` y `CV` requieren ambas más un `event_id` único;
  aceptaciones, rechazos y replay quedan auditados.
- `APPROVE` registra una aprobación explícita vigente y pasa a Ready to Apply,
  pero nunca aplica. `CV` solo identifica la última versión aprobada y no expone
  el contenido completo en el mensaje.

## CV adaptado y cover letter controlados

- **Generate Tailored Documents** solo funciona cuando `priority_score` alcanza
  el umbral activo de **Document Generation Rules** (75 por defecto).
- El generador `deterministic-structured-v1` no usa proveedor externo: congela
  un snapshot del perfil profesional aprobado y solo prioriza keywords de la
  vacante que también existen en sus skills/tecnologías. Conserva experiencia,
  empleadores, títulos, certificaciones, fechas y logros literalmente desde esa
  fuente; nunca copia ni sobrescribe el CV maestro.
- Cada ejecución crea una versión independiente ligada a vacante, perfil y
  versión del perfil, con fecha/usuario, checksum del maestro, modelo, versión
  de plantilla, metadata, origen y resumen de cambios ATS-friendly.
- El flujo es explícito **Draft → Reviewed → Approved**. Antes de revisar o
  aprobar se regenera el resultado esperado desde el snapshot congelado; si el
  texto fue alterado con cualquier afirmación adicional queda bloqueado en
  Draft. La procedencia y los estados no son editables directamente.
- Esta fase prepara texto para una futura exportación modular. No genera
  PDF/DOCX porque el módulo no tiene infraestructura existente para ello y no
  envía ni aplica a ninguna vacante.

## Sponsorship australiano y prioridad auditable

- **Analyse Sponsorship** y la acción masiva clasifican cada vacante como Yes,
  No o Unknown usando únicamente frases explícitas de la descripción guardada.
- Se reconocen `visa sponsorship available`, `482 sponsorship` y `employer
  sponsored`; `no sponsorship available` y restricciones citizen/PR-only son
  negativas explícitas y prevalecen si hay señales en conflicto.
- Una exigencia de work rights actuales no prueba sponsorship: queda Unknown.
  Sin evidencia también se conserva Unknown, con confianza 0; nunca se elimina
  una vacante No.
- Cada ejecución registra confianza, evidencia textual resumida, origen, motivo,
  usuario, timestamp, regla, match original y prioridad resultante.
- **Job Hunter → Sponsorship Priority Rules** configura ajustes separados. El
  valor por defecto suma 20 para Yes, 0 para Unknown y resta 50 para No. El
  `priority_score` se limita a 0–100 y nunca modifica `match_score`; las listas
  priorizan Yes, luego Unknown y finalmente No.

## Perfil profesional y matching determinista

- **Job Hunter → Professional Profiles** mantiene skills, tecnologías, años y
  experiencia laboral, educación, certificaciones, idiomas, roles objetivo,
  ubicación, modalidades y salario objetivo. Cada cambio relevante incrementa
  la versión del perfil.
- El CV principal vive una sola vez en el perfil. Cada análisis guarda versión,
  nombre y checksum del CV como referencia auditable; no copia el binario a la
  vacante ni lo reenvía.
- **Analyse Match** en el formulario analiza una vacante. La acción de lista
  **Analyse selected vacancies** procesa una selección controlada.
- El score 0–100 suma pesos explícitos: skills obligatorias 25, deseables 10,
  experiencia 15, seniority 10, educación 10, tecnologías 10, ubicación 5,
  modalidad 5, idioma 5 y rol 5. Los requisitos no informados son neutrales.
- **Job Hunter → Matching Rules** configura umbrales. Por defecto: 75 o más va
  a `Good Match`, 50–74.99 a `Analysing` y un score bajo conserva el estado.
  `Ignored` para scores bajos solo se activa mediante regla explícita.
- Un cambio manual de estado bloquea posteriores transiciones automáticas; el
  score y su traza sí pueden actualizarse. Cada ejecución conserva criterios,
  usuario, fecha, perfil/CV y estados anterior/posterior.

El matching y sponsorship no aplican automáticamente; Fase 6 únicamente genera
y revisa documentos, sin enviarlos a terceros.

La integración HTTP de Hermes usa `HERMES_API_TOKEN` (variable de entorno) o el
parámetro protegido `job_hunter_management.hermes_api_token`. El token se valida
con comparación constante; nunca se escribe en logs.

## Búsqueda y sincronización

### Contrato normalizado de Fase 9

- Todos los adaptadores pasan por un contrato único antes de crear una vacante.
  Exige título, empresa, ubicación, URL HTTP(S), descripción, fuente, ID de la
  fuente, modalidad y fecha de publicación; salario y moneda se validan cuando
  existen. Valores ausentes, tipos incompatibles, rangos invertidos, fechas no
  ISO y modalidades desconocidas se rechazan sin crear `job.application`.
- Se aceptan aliases habituales (`title/name`, `company/company_name`,
  `url/job_url`, `description/job_description`, `currency/salary_currency`,
  `work_mode/modalidad`, `date_found/published_at`) y estructuras fixture de
  Adzuna, Greenhouse, Lever y Ashby. El JSON de procedencia conserva solamente
  campos permitidos, identifica esquema/proveedor y descarta claves de secretos.
- La URL canónica elimina fragmentos y tracking conocido, ordena la query
  funcional, normaliza host/esquema/puertos por defecto y rechaza todo esquema
  distinto de HTTP(S).
- Cada vacante sincronizada guarda claves auditables para `source+source_job_id`,
  URL canónica y `company+title+location`. Las tres participan en deduplicación
  cruzada e idempotencia; los registros anteriores sin claves siguen siendo
  comparados por URL canónica.
- Cada línea de ejecución registra proveedor, timestamp de consulta,
  disponibilidad, paginación/límite cuando existe y un error sanitizado. Un
  payload inválido o una fuente caída marca la ejecución como parcial y no
  detiene el resto. Los adaptadores continúan siendo fixtures deterministas:
  esta fase no conecta APIs reales.

- Cada perfil profesional dispone de **Run Hermes Search** y la lista ofrece
  **Run All Hermes Searches**. La búsqueda deriva roles, ubicación, salario y
  modalidades directamente del perfil, persiste `Last Hermes Search` y reutiliza
  una sola configuración interna por perfil en ejecuciones sucesivas.
- Crear una configuración desde **Job Hunter → Search Configurations** con keywords,
  roles, ubicación, modalidad, salario mínimo, antigüedad máxima y fuentes habilitadas.
  Las configuraciones sin perfil conservan este comportamiento legacy; al vincular
  un perfil, sus criterios derivados se muestran readonly.
- **Run Search** ejecuta manualmente la búsqueda; `cron_run_active_configs` queda
  disponible para un scheduler.
- Las búsquedas iniciadas desde un perfil mediante **Run Hermes Search**, desde
  **Run All Hermes Searches** o mediante `POST /api/job-hunter/search/run`
  excluyen siempre los `FixtureAdapter`. Solo se consultan fuentes reales
  activas y configuradas; las fixtures quedan reservadas para configuraciones
  manuales, pruebas y compatibilidad legacy.
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

### Adzuna Australia (Fase 10)

- La fuente `Adzuna Australia` usa exclusivamente la API oficial HTTPS
  `/v1/api/jobs/au/search/{page}`; no hace scraping. Se instala inactiva y debe
  activarse explícitamente después de revisar límites y credenciales. Un
  administrador puede activarla desde **Job Hunter → WhatsApp Settings → Real
  job sources → Enable Adzuna Australia**.
- Configure `ADZUNA_APP_ID` y `ADZUNA_APP_KEY` desde los campos protegidos de
  **Job Hunter → WhatsApp Settings → Real job sources**. Como alternativa para
  despliegues automatizados, se aceptan las variables de entorno del proceso
  Odoo o los parámetros protegidos `job_hunter_management.adzuna_app_id` y
  `job_hunter_management.adzuna_app_key`. No escriba estos valores en este
  repositorio, URLs guardadas ni campos funcionales.
- Sin ambas credenciales la fuente no abre conexiones: registra disponibilidad
  parcial y deja continuar las fuentes fixture. Los resultados de tests usan un
  transporte HTTP simulado; no realizan tráfico real.
- El adaptador envía roles/keywords, ubicación, salario mínimo, antigüedad y
  tamaño de página. La modalidad se infiere únicamente de evidencia explícita
  del anuncio y se post-filtra; no se inventan valores ni se convierten
  `full_time`/`permanent` en una modalidad de trabajo.
- Paginación, límite de resultados, intervalo monotónico, reintentos, timeout y
  tope de `Retry-After` viven en la fuente (`default_page_size`, `result_limit`,
  `rate_limit_seconds`, `retry_count`, `request_timeout_seconds` y
  `retry_after_max_seconds`). Los secretos nunca forman parte de la procedencia
  allowlisted ni de mensajes de error persistidos.

## API de Hermes (Fase 2)

- `POST /api/job-hunter/jobs` crea una vacante (`external_id` hace el reintento idempotente).
- `GET /api/job-hunter/jobs` lista vacantes.
- `GET /api/job-hunter/jobs/<id>` devuelve una vacante.
- `PATCH /api/job-hunter/jobs/<id>` actualiza únicamente campos autorizados.
- `POST /api/job-hunter/search/run` ejecuta todos los perfiles activos. Solo acepta
  un objeto JSON vacío (o cuerpo vacío) y devuelve contadores, timestamp y errores.

Todas las solicitudes requieren `Authorization: Bearer ...` y JSON estricto.
El serializer no expone `cv_file`, `cover_letter`, `notes` ni `raw_job_data`.
# Phase 8 — controlled application preparation

Application preparation is approval-gated and audit-only by default. The UI
uses the deterministic `manual` adapter, which prepares known data and always
stops before submission as **Manual Action Required**. It requires a current
WhatsApp approval, `Ready to Apply`, an approved tailored CV (and approved
cover letter when required), a valid HTTP(S) URL, and no prior confirmed
submission.

Platform integrations implement the side-effect boundary in
`ApplicationAdapter`. Unknown or sensitive questions are stored only as a safe
escalation summary; answers are never inferred. The `test_confirmed` adapter is
simulation-only and remains disabled unless the administrator explicitly sets
`job_hunter_management.allow_test_submission=True`; no production browser or
auto-submit adapter is included.

Attempts are immutable audit records. Only explicitly retryable technical
failures can be retried, and interrupted/ambiguous outcomes block automatic
retry. Confirmed attempts set `date_applied` and replays return the existing
attempt instead of creating another submission.
