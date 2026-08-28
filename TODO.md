# TODO — AI Job Hunter con Hermes + Odoo 16

Proyecto: `job_hunter_management`

Objetivo general: construir un sistema de búsqueda, análisis, seguimiento y aplicación asistida a trabajos usando Hermes como motor de automatización/IA y Odoo como sistema central de registro, pipeline, documentos y métricas.

## Reglas globales del proyecto

- Mantener `job_hunter_management` completamente independiente de `commercial_property_management`.
- Flujo de trabajo obligatorio para tareas complejas: `Triage → TechLead → perfil(es) correspondiente(s) → QA → Done`.
- TechLead debe dividir dependencias correctamente antes de ejecutar tareas paralelas.
- No iniciar una fase si las dependencias técnicas de la fase anterior no están terminadas y validadas.
- Si una tarea se bloquea, identificar la causa raíz y crear una tarea correctiva antes de reintentar.
- No aplicar a ningún trabajo automáticamente sin una autorización explícita del usuario.
- No guardar tokens, contraseñas, cookies ni secretos en código, logs o registros Odoo.
- Registrar suficiente trazabilidad para poder auditar por qué una vacante fue aceptada, descartada o aplicada.
- Mantener pruebas automáticas para lógica crítica e integraciones.

---

# FASE 1 — Base del módulo Odoo

## Prompt

```text
Implementa la Fase 1 del proyecto AI Job Hunter.

Crea un nuevo módulo Odoo 16 llamado `job_hunter_management`, completamente independiente de `commercial_property_management`.

Objetivo:
Crear la estructura base para almacenar y gestionar oportunidades laborales que posteriormente serán encontradas y procesadas por Hermes.

Modelo principal:
`job.application`

Campos mínimos:
- `name`: nombre del puesto
- `company_name`: empresa
- `location`: ubicación
- `job_url`: URL de la vacante
- `source`: SEEK / LinkedIn / Indeed / Jora / Company Careers / Other
- `salary_min`
- `salary_max`
- `salary_currency`
- `sponsorship_status`: Yes / No / Unknown
- `match_score`: porcentaje 0-100
- `state`: Found / Analysing / Good Match / Ready to Apply / Applied / Interview / Offer / Rejected / Ignored
- `job_description`: descripción completa
- `cv_file`: CV utilizado
- `cover_letter`: cover letter
- `date_found`
- `date_applied`
- `notes`

Crear vistas:
1. Kanban agrupado por `state`
2. Lista
3. Formulario
4. Búsqueda y filtros

Validaciones:
- `match_score` debe estar entre 0 y 100.
- Evitar duplicados por URL.
- Como respaldo, detectar duplicados por empresa + puesto.
- `date_applied` solo debe establecerse cuando corresponda a una aplicación real.

Preparar el código para futuras integraciones mediante API.

No implementar todavía:
- scraping
- APIs externas
- IA
- WhatsApp
- CV tailoring
- aplicación automática

Flujo de ejecución:
Triage → TechLead → Backend + Frontend → QA.

TechLead debe comprobar dependencias antes de asignar tareas Frontend que necesiten campos Backend.

Definition of Done:
- módulo instala/actualiza sin errores
- modelo y permisos funcionan
- Kanban/list/form/search operativos
- validaciones probadas
- pruebas automáticas críticas pasan
- no hay dependencias con `commercial_property_management`
```

---

# FASE 2 — API segura Odoo ↔ Hermes

## Prompt

```text
Implementa la Fase 2 de `job_hunter_management`: integración segura Odoo 16 ↔ Hermes mediante API HTTP.

Objetivo:
Permitir que Hermes cree, consulte y actualice oportunidades laborales almacenadas en `job.application`.

Endpoints mínimos:

1. POST `/api/job-hunter/jobs`
- Crear oportunidad.
- Validar campos obligatorios.
- Evitar duplicados por URL y como respaldo empresa + puesto.
- Devolver ID, estado y resultado.

2. GET `/api/job-hunter/jobs`
Permitir filtros por:
- state
- source
- sponsorship_status
- match_score mínimo
- company_name
- date_found

3. GET `/api/job-hunter/jobs/<id>`
- Obtener detalle completo.

4. PATCH `/api/job-hunter/jobs/<id>`
- Actualizar únicamente campos permitidos.
- Registrar cambios importantes de estado.

Seguridad:
- Bearer Token.
- Token desde configuración segura/variables de entorno.
- Nunca hardcodear secretos.
- Validación estricta de payloads.
- No exponer información sensible.
- JSON consistente.
- Manejar HTTP 200, 201, 400, 401, 404, 409 y 500.

Idempotencia:
- Un reintento de Hermes no debe crear duplicados.
- Admitir `external_id` o clave equivalente para identificar eventos repetidos.

Añadir al modelo si todavía no existen:
- `external_id`
- `source_job_id`
- `raw_job_data`
- `last_sync_at`
- `created_by_integration`

Logging:
- logs útiles para diagnóstico
- nunca registrar tokens, cookies, CV completos u otros datos sensibles

Pruebas automáticas:
- autenticación
- creación
- duplicados
- consulta
- filtros
- actualización
- payload inválido
- recurso inexistente
- idempotencia

No implementar todavía:
- scraping
- matching IA
- sponsorship IA
- WhatsApp
- aplicación automática

Flujo:
Triage → TechLead → Backend → QA.

Definition of Done:
Demostrar mediante pruebas o curl que Hermes puede:
1. enviar una vacante
2. verla aparecer en Odoo
3. consultarla
4. actualizarla
5. reenviar el mismo evento sin duplicarla
```

---

# FASE 3 — Búsqueda automática y captura de vacantes

## Prompt

```text
Implementa la Fase 3 del AI Job Hunter: búsqueda automática de oportunidades mediante Hermes y sincronización con Odoo.

Objetivo:
Hermes debe localizar oportunidades laborales relevantes, normalizarlas y enviarlas a `job_hunter_management` mediante la API creada en la Fase 2.

Fuentes iniciales:
- SEEK
- LinkedIn Jobs
- Indeed
- Jora
- páginas Careers de empresas

Prioridad:
Usar mecanismos permitidos y robustos para cada fuente. Evitar depender de scraping frágil si existe una API, feed, búsqueda web o mecanismo mejor.

Datos mínimos por vacante:
- job title
- company
- location
- URL
- source
- source_job_id cuando exista
- descripción
- salario mínimo/máximo cuando esté disponible
- moneda
- fecha publicada cuando esté disponible
- fecha encontrada
- modalidad: onsite / hybrid / remote
- raw_job_data normalizado o referencia equivalente

Implementar normalización de datos entre fuentes.

Deduplicación:
1. source + source_job_id
2. URL canónica
3. empresa + título + ubicación como fallback

Configuración de búsqueda:
Preparar filtros configurables para:
- keywords
- roles
- ubicación
- remote/hybrid/onsite
- salario mínimo
- antigüedad máxima de publicación
- fuentes habilitadas

No aplicar a empleos.
No generar todavía CVs ni cover letters.
No descartar automáticamente trabajos por sponsorship en esta fase.

Programación:
Preparar el flujo para poder ejecutarse manualmente y mediante scheduler.

Observabilidad:
Registrar por ejecución:
- fuente
- vacantes encontradas
- vacantes nuevas
- duplicados
- errores
- tiempo de ejecución

Errores de una fuente no deben cancelar el resto de fuentes.

Flujo:
Triage → TechLead → Integration/Backend → QA.

Definition of Done:
- ejecutar una búsqueda desde Hermes
- encontrar oportunidades reales o fixtures de prueba equivalentes
- normalizarlas
- enviarlas a Odoo
- evitar duplicados
- soportar fallo parcial de una fuente
- verificar que aparecen en estado `Found`
```

---

# FASE 4 — Matching inteligente con CV y perfil

## Prompt

```text
Implementa la Fase 4 del AI Job Hunter: cálculo de compatibilidad entre cada vacante y el perfil profesional/CV del candidato.

Objetivo:
Hermes debe analizar automáticamente cada nueva vacante y asignar un `match_score` de 0 a 100 junto con una explicación estructurada.

Crear un perfil profesional reutilizable que pueda incluir:
- skills
- tecnologías
- años de experiencia
- experiencia laboral
- educación
- certificaciones
- idiomas
- roles objetivo
- ubicación
- preferencias remote/hybrid/onsite
- salario objetivo

El perfil debe poder alimentarse desde un CV principal y actualizarse sin modificar manualmente todos los jobs existentes.

Criterios mínimos de scoring:
- skills obligatorias
- skills deseables
- experiencia requerida
- seniority
- educación
- tecnologías
- ubicación/modalidad
- idioma
- compatibilidad general del rol

No basar el resultado solo en similitud semántica.

Guardar en Odoo:
- `match_score`
- fortalezas del candidato para la vacante
- gaps principales
- requisitos obligatorios no cumplidos
- skills coincidentes
- skills faltantes
- breve explicación del score
- versión del perfil/CV utilizado para el análisis

Reglas de estado iniciales configurables:
- score alto → `Good Match`
- score intermedio → mantener `Analysing` o `Found`
- score bajo → no eliminar; marcar como baja prioridad o `Ignored` solo si una regla explícita lo permite

El cálculo debe ser determinista en sus criterios aunque utilice IA para interpretación de texto.

No generar todavía documentos personalizados.
No aplicar automáticamente.

Optimización de tokens:
- utilizar modelos económicos para clasificación rutinaria
- reservar modelos más potentes para vacantes ambiguas o de alto potencial
- reutilizar perfil estructurado en lugar de reenviar el CV completo cuando sea posible

Pruebas:
Crear fixtures con vacantes de match alto, medio y bajo y validar coherencia del scoring.

Flujo:
Triage → TechLead → AI/Backend → QA.

Definition of Done:
- toda vacante nueva puede analizarse
- Odoo recibe score + explicación
- los scores cumplen 0-100
- casos de prueba alto/medio/bajo tienen resultados razonables
- existe trazabilidad sobre cómo se obtuvo el score
```

---

# FASE 5 — Detección y evaluación de visa sponsorship

## Prompt

```text
Implementa la Fase 5 del AI Job Hunter: análisis de visa sponsorship para oportunidades en Australia.

Objetivo:
Clasificar cada vacante según la evidencia disponible sobre sponsorship, sin inventar información.

Valores principales:
- Yes
- No
- Unknown

Añadir opcionalmente nivel de confianza 0-100.

Analizar señales como:
- `visa sponsorship available`
- `482 sponsorship`
- `employer sponsored`
- `must have full working rights`
- `Australian citizen or permanent resident only`
- `no sponsorship available`
- requisitos explícitos de work rights
- información disponible de la empresa cuando sea pertinente

Guardar:
- sponsorship_status
- sponsorship_confidence
- evidencia textual resumida
- origen de la evidencia
- motivo de clasificación

Reglas:
- nunca convertir ausencia de información en `No`
- si no existe evidencia suficiente, usar `Unknown`
- evidencia explícita negativa debe prevalecer sobre inferencias débiles positivas
- separar `visa sponsorship` de una simple exigencia de permiso de trabajo actual

Prioridad:
Permitir configurar el sistema para ordenar primero:
1. Sponsorship Yes
2. Sponsorship Unknown
3. Sponsorship No

No eliminar automáticamente registros `No`; mantener historial.

Integración con matching:
Crear un `priority_score` o criterio equivalente que combine match profesional y sponsorship sin alterar el significado de `match_score`.

Ejemplo:
Un job con 95% match pero sponsorship explícitamente No puede tener alta compatibilidad técnica pero baja prioridad de aplicación.

No aplicar todavía.

Flujo:
Triage → TechLead → AI/Backend → QA.

Definition of Done:
- las vacantes pueden clasificarse Yes/No/Unknown
- cada decisión tiene evidencia y confianza
- ausencia de evidencia produce Unknown
- Odoo permite filtrar y ordenar por sponsorship
```

---

# FASE 6 — CV y cover letter personalizados

## Prompt

```text
Implementa la Fase 6 del AI Job Hunter: generación controlada de CV y cover letter adaptados a cada vacante.

Objetivo:
Para oportunidades priorizadas, Hermes debe crear una versión del CV y una cover letter adaptadas al puesto sin inventar experiencia, skills, empleadores, títulos, certificaciones o logros.

Fuente de verdad:
- CV maestro
- perfil profesional estructurado
- información aprobada previamente por el usuario

CV personalizado:
- priorizar experiencia relevante
- ajustar resumen profesional
- reordenar skills según relevancia
- destacar proyectos relacionados
- usar keywords legítimas del anuncio
- conservar hechos y fechas reales
- mantener formato ATS-friendly

Cover letter:
- específica para puesto y empresa
- breve y profesional
- explicar fit real
- mencionar sponsorship/work rights únicamente mediante datos configurados y autorizados
- no incluir afirmaciones no verificadas

Guardar en Odoo por aplicación:
- versión del CV
- cover letter
- fecha de generación
- modelo/prompts/versiones utilizados
- job relacionado
- estado de revisión

Estados sugeridos para documentos:
- Draft
- Reviewed
- Approved

Añadir mecanismo de diff o resumen de cambios entre CV maestro y CV adaptado.

Nunca sobrescribir el CV maestro.

Validaciones automáticas:
Detectar posibles alucinaciones comparando el documento generado contra el perfil fuente.
Si aparece un dato profesional no presente en la fuente de verdad, bloquear el documento para revisión.

Formato:
Preparar documentos para exportación a PDF/DOCX si esa infraestructura ya existe o implementarla modularmente sin romper el flujo principal.

No enviar aplicaciones todavía.

Optimización:
Solo generar documentos para vacantes que superen criterios configurables de prioridad.

Flujo:
Triage → TechLead → AI/Backend → QA.

Definition of Done:
- una vacante priorizada genera CV adaptado + cover letter
- no se altera el CV maestro
- existe revisión/approval
- no se permiten hechos inventados
- documentos quedan asociados a la vacante correcta en Odoo
```

---

# FASE 7 — Aprobación y control por WhatsApp

## Prompt

```text
Implementa la Fase 7 del AI Job Hunter: notificaciones y aprobación de oportunidades mediante WhatsApp.

Objetivo:
Hermes debe enviar al número autorizado únicamente oportunidades que cumplan los criterios configurados y permitir controlarlas mediante respuestas simples.

Mensaje resumido sugerido:
- puesto
- empresa
- ubicación
- salary si existe
- match_score
- sponsorship_status
- fuente
- enlace
- breve motivo de recomendación

Comandos mínimos:
- APPROVE
- IGNORE
- DETAILS
- CV

Comportamiento:
APPROVE:
- registrar aprobación explícita
- cambiar a `Ready to Apply`
- dejar disponible para Fase 8
- NO aplicar todavía si la Fase 8 no está habilitada

IGNORE:
- cambiar a `Ignored`
- registrar fecha y motivo si el usuario lo proporciona

DETAILS:
- enviar resumen extendido de la vacante, requisitos, match y sponsorship

CV:
- proporcionar o identificar la versión de CV preparada para esa vacante

Seguridad:
- aceptar comandos únicamente desde números autorizados
- validar que la respuesta corresponda a una vacante concreta
- no confiar únicamente en texto libre sin contexto
- prevenir replay/doble aprobación
- nunca exponer secretos técnicos

Identificación:
Cada notificación debe incluir un identificador corto o mecanismo inequívoco para relacionar la respuesta con `job.application`.

Idempotencia:
Responder APPROVE dos veces no debe crear dos solicitudes ni dos eventos de aplicación.

Notificaciones adicionales:
- avisar cuando una tarea crítica se bloquee
- avisar cuando se complete una aplicación
- evitar spam agrupando eventos rutinarios cuando sea razonable

Modelo:
El chat de WhatsApp debe utilizar el perfil/modelo gratuito configurado para WhatsApp según la política global de Hermes.

Flujo:
Triage → TechLead → WhatsApp/Integration + Backend → QA.

Definition of Done:
- una vacante priorizada genera notificación
- APPROVE/IGNORE/DETAILS/CV funcionan
- solo números autorizados pueden operar
- cada acción queda auditada en Odoo
- no se realizan aplicaciones sin APPROVE
```

---

# FASE 8 — Aplicación asistida/automática con aprobación obligatoria

## Prompt

```text
Implementa la Fase 8 del AI Job Hunter: aplicación asistida a oportunidades aprobadas explícitamente por el usuario.

Objetivo:
Hermes debe poder iniciar y completar, cuando sea técnicamente viable y permitido, el proceso de aplicación para registros en estado `Ready to Apply` que tengan una aprobación válida.

REGLA ABSOLUTA:
Nunca iniciar ni enviar una aplicación si no existe una aprobación explícita y vigente asociada a esa vacante.

Precondiciones:
- estado `Ready to Apply`
- aprobación registrada
- CV aprobado
- cover letter aprobada si es necesaria
- URL válida
- no existir aplicación previa confirmada

Automatización:
Usar navegación/browser automation cuando corresponda.

Flujo recomendado:
1. abrir página de aplicación
2. identificar plataforma/formulario
3. completar datos conocidos
4. adjuntar CV correcto
5. adjuntar cover letter si aplica
6. detectar preguntas nuevas
7. responder automáticamente solo cuando exista una respuesta previamente autorizada y segura
8. si aparece una pregunta desconocida o sensible, pausar y solicitar respuesta al usuario
9. revisar resumen antes del envío cuando sea posible
10. enviar únicamente si las reglas configuradas permiten submission automático después del APPROVE
11. registrar confirmación

Preguntas que deben escalarse al usuario si no existe respuesta aprobada:
- expectativa salarial no configurada
- razones personales de salida
- antecedentes o declaraciones legales
- discapacidad/salud
- diversidad/EEO opcional
- información migratoria no configurada
- security clearance
- preguntas subjetivas importantes

Nunca inventar respuestas.

Compatibilidad:
Diseñar adaptadores por plataforma, por ejemplo:
- SEEK
- LinkedIn
- Indeed
- Workday
- Greenhouse
- Lever
- formularios propios

No asumir que todas las plataformas permiten automatización completa.
Si una aplicación no puede enviarse de manera confiable:
- dejarla preparada hasta el último paso posible
- marcar `Manual Action Required`
- notificar al usuario

Registrar en Odoo:
- plataforma
- fecha/hora de intento
- fecha/hora de envío
- resultado
- confirmation/reference id cuando exista
- CV usado
- cover letter usada
- respuestas relevantes
- screenshots/logs técnicos no sensibles cuando sean útiles
- error si falla

Estados sugeridos adicionales:
- Applying
- Manual Action Required
- Applied
- Application Failed

Idempotencia:
Nunca enviar dos veces la misma aplicación por reintentos.

Reintentos:
- fallos técnicos transitorios pueden reintentarse
- nunca repetir automáticamente un submission si existe posibilidad razonable de que el primer envío haya sido exitoso
- verificar estado antes de reintentar

Post-aplicación:
- actualizar Odoo a `Applied`
- establecer `date_applied`
- enviar notificación WhatsApp
- crear seguimiento futuro si la arquitectura de tareas lo permite

Flujo:
Triage → TechLead → Browser/Integration + Backend → QA.

Definition of Done:
- solo aplicaciones aprobadas pueden avanzar
- una aplicación de prueba puede completarse o llegar correctamente a Manual Action Required
- no hay duplicados
- resultados quedan registrados en Odoo
- errores son recuperables y auditables
```

---

# Checklist final del proyecto

- [x] Fase 1 — Base Odoo
- [ ] Fase 2 — API Odoo ↔ Hermes
- [ ] Fase 3 — Búsqueda automática
- [ ] Fase 4 — Matching con CV
- [ ] Fase 5 — Sponsorship
- [ ] Fase 6 — CV + Cover Letter
- [ ] Fase 7 — WhatsApp Approval
- [ ] Fase 8 — Aplicación asistida/automática

## Flujo final esperado

```text
Fuentes de empleo
      ↓
    Hermes
      ↓
Normalización + deduplicación
      ↓
     Odoo
      ↓
Matching profesional
      ↓
Sponsorship analysis
      ↓
Priority score
      ↓
CV + Cover Letter
      ↓
WhatsApp
      ↓
APPROVE / IGNORE / DETAILS / CV
      ↓
Aplicación asistida
      ↓
Odoo: Applied / Interview / Offer / Rejected
```

## Regla de oro

```text
Encontrar y analizar puede ser automático.
Preparar documentos puede ser automático.
La decisión de aplicar pertenece al usuario.
Nunca enviar una candidatura sin aprobación explícita.
```
