# Job Pilot — Career Profile

Odoo 16 module that lets each internal user maintain a structured career
profile and import data from an uploaded CV (PDF or DOCX) through a
controlled extract → parse → review → import workflow.

## Models

- `job_pilot.profile` — core profile (personal info, professional
  title/summary, address), one per user (`user_id` unique).
- `job_pilot.profile.attribute` — free-form professional attributes.
- `job_pilot.additional.info` — unclassified/free-form profile notes.
- `job_pilot.skill.category`, `job_pilot.skill`
- `job_pilot.work.experience`, `job_pilot.work.experience.project`,
  `job_pilot.work.experience.item` (responsibilities/achievements)
- `job_pilot.education`
- `job_pilot.certification`
- `job_pilot.language`
- `job_pilot.leadership.volunteering`
- `job_pilot.reference`
- `job_pilot.cv.upload` — uploaded CV file and workflow state machine
  (`draft` → `extracted` → `parsed` → `reviewed` → `imported`, plus
  `error`).
- `job_pilot.cv.import.line` — one proposed change per field/record found
  in the CV, with a `decision` (`pending` / `keep` / `apply`) and a
  duplicate flag (`is_duplicate`) plus a reference to the matching
  existing record when applicable.
- `job_pilot.cv.unclassified` — text blocks extracted from the CV that
  the parser could not confidently map to a field, kept for manual
  handling (`open` / `resolved` / `ignored`).

## CV workflow and non-overwrite guarantee

1. **Extract** (`action_extract_text`): reads the uploaded PDF (via
   `pypdf`/`PyPDF2`) or DOCX (via the standard library `zipfile` +
   `xml.etree`, no external dependency) into `extracted_text`. Unsupported
   extensions or unreadable files move the record to `error` with
   `error_message` set instead of raising into the UI.
2. **Parse** (`action_parse`): heuristically detects an email, a phone
   number, a "Summary" block and "Skills"/"Languages" sections, and
   creates one `job_pilot.cv.import.line` per candidate change. Every
   other paragraph becomes a `job_pilot.cv.unclassified` record.
   - Conflicting fields (a value already present on the profile) and
     duplicate skills/languages (matched by case-insensitive name)
     default to **`keep`** — the safe, non-destructive choice.
   - Brand-new information (no current value / no duplicate) defaults to
     `apply` since accepting it cannot overwrite anything.
3. **Review** (`action_mark_reviewed`): blocked with a `UserError` while
   any line is still `pending`, forcing an explicit decision on every
   conflict/duplicate before proceeding.
4. **Import** (`action_import`): only lines explicitly marked `apply` are
   written to the profile or created as new skill/language records.
   `action_reset_draft` clears review/unclassified data to re-run the
   workflow from scratch.

## Security

- `group_job_pilot_user` (implies `base.group_user`): full CRUD on their
  own profile and its related records only (enforced by `ir.rule`
  domains on `user_id`/`profile_id.user_id`), read-only on skill
  categories.
- `group_job_pilot_manager` (implies the user group): unrestricted access
  to all profiles and full CRUD on skill categories; only managers see
  the Configuration menu.

## Known limitations

- Parsing is rule-based (regex/section-heading heuristics), not ML/NLP.
- For structured extraction, configure the API key from **Job Pilot →
  Configuration → Codex API**. The key is stored in an Odoo system parameter
  and the field is masked. Environment variables `JOB_PILOT_CODEX_API_KEY` (or
  `OPENAI_API_KEY`) remain supported as a deployment fallback. The optional
  `JOB_PILOT_CODEX_ENDPOINT` defaults to `https://api.openai.com/v1/responses`
  and `JOB_PILOT_CODEX_MODEL` defaults to `gpt-5.3-codex`. The **Extract with
  Codex** action always creates proposals for manual review before import.
  It reliably extracts contact fields, a professional summary block,
  skills and languages; multi-field record sections are surfaced as
  Unclassified Information for manual entry instead.
- Scanned/image-only PDFs with no embedded text layer cannot be
  extracted (no OCR).
- PDF extraction depends on `pypdf` or `PyPDF2` being installed on the
  server; DOCX extraction has no external dependency.

## Tests

`tests/test_job_pilot_profile.py` and `tests/test_job_pilot_cv_upload.py`
cover the unique-profile constraint, work-experience date validation, and
the full extract → parse → review → import cycle including the duplicate
"keep" default and the pending-review guard.
