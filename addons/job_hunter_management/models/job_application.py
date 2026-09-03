import logging
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

from .vacancy_contract import SOURCES, canonical_url


_logger = logging.getLogger(__name__)


class JobApplication(models.Model):
    _name = "job.application"
    _description = "Job Application"
    _order = "date_found desc, id desc"

    name = fields.Char(string="Position", required=True)
    company_name = fields.Char(string="Company", required=True)
    location = fields.Char()
    job_url = fields.Char(string="Job URL", required=True)
    source = fields.Selection(
        [
            ("seek", "SEEK"),
            ("linkedin", "LinkedIn"),
            ("indeed", "Indeed"),
            ("jora", "Jora"),
            ("company_careers", "Company Careers"),
            ("adzuna", "Adzuna"),
            ("greenhouse", "Greenhouse"),
            ("lever", "Lever"),
            ("ashby", "Ashby"),
            ("other", "Other"),
        ],
        required=True,
        default="other",
    )
    salary_min = fields.Float(string="Minimum Salary")
    salary_max = fields.Float(string="Maximum Salary")
    salary_currency = fields.Char(string="Salary Currency")
    sponsorship_status = fields.Selection(
        [("yes", "Yes"), ("no", "No"), ("unknown", "Unknown")],
        string="Sponsorship Status",
        required=True,
        default="unknown",
    )
    match_score = fields.Float(string="Match Score (%)")
    state = fields.Selection(
        [
            ("found", "Found"),
            ("analysing", "Analysing"),
            ("good_match", "Good Match"),
            ("ready_to_apply", "Ready to Apply"),
            ("applying", "Applying"),
            ("manual_action_required", "Manual Action Required"),
            ("applied", "Applied"),
            ("application_failed", "Application Failed"),
            ("interview", "Interview"),
            ("offer", "Offer"),
            ("rejected", "Rejected"),
            ("ignored", "Ignored"),
        ],
        required=True,
        default="found",
    )
    job_description = fields.Text(string="Job Description")
    cv_file = fields.Binary(string="CV", attachment=True)
    cv_filename = fields.Char(string="CV Filename")
    cover_letter = fields.Text(string="Cover Letter")
    date_found = fields.Date(string="Date Found", required=True, default=fields.Date.context_today)
    date_applied = fields.Date(string="Date Applied")
    notes = fields.Text()
    external_id = fields.Char(string="External ID", index=True)
    source_job_id = fields.Char(string="Source Job ID", index=True)
    raw_job_data = fields.Json(string="Raw Job Data")
    modalidad = fields.Selection(
        [("onsite", "Onsite"), ("hybrid", "Hybrid"), ("remote", "Remote")],
        string="Work Mode",
    )
    last_sync_at = fields.Datetime(string="Last Sync At")
    created_by_integration = fields.Boolean(string="Created by Integration", default=False, index=True)
    dedup_source_key = fields.Char(readonly=True, copy=False, index=True)
    dedup_url_key = fields.Char(readonly=True, copy=False, index=True)
    dedup_content_key = fields.Char(readonly=True, copy=False, index=True)

    _sql_constraints = [
        (
            "job_application_external_id_unique",
            "unique(external_id)",
            "An application with this external ID already exists.",
        ),
        (
            "job_application_url_unique",
            "unique(job_url)",
            "An application with this job URL already exists.",
        ),
        (
            "job_app_company_pos_loc_unique",
            "unique(company_name, name, location)",
            "An application for this company and position already exists.",
        ),
    ]

    @api.model
    def _check_duplicate_values(self, values, excluded_ids=None):
        excluded_ids = excluded_ids or []
        position_domain = [("company_name", "=", values.get("company_name")), ("name", "=", values.get("name"))]
        if values.get("location"):
            position_domain.append(("location", "=", values["location"]))
        duplicate_checks = (
            ([("job_url", "=", values.get("job_url"))], _("An application with this job URL already exists.")),
            (position_domain, _("An application for this company and position already exists.")),
        )
        for domain, message in duplicate_checks:
            if all(value for _field, _operator, value in domain):
                if excluded_ids:
                    domain.append(("id", "not in", excluded_ids))
                if self.with_context(active_test=False).search_count(domain):
                    raise ValidationError(message)

    @api.model_create_multi
    def create(self, values_list):
        pending_urls = set()
        pending_company_positions = set()
        for values in values_list:
            self._check_duplicate_values(values)
            job_url = values.get("job_url")
            company_position = (values.get("company_name"), values.get("name"), values.get("location"))
            if job_url and job_url in pending_urls:
                raise ValidationError(_("An application with this job URL already exists."))
            if all(company_position) and company_position in pending_company_positions:
                raise ValidationError(
                    _("An application for this company and position already exists.")
                )
            if job_url:
                pending_urls.add(job_url)
            if all(company_position):
                pending_company_positions.add(company_position)
        return super().create(values_list)

    def write(self, values):
        changed_states = {
            application.id: (application.state, values["state"])
            for application in self
            if "state" in values and values["state"] != application.state
        }
        effective_values = {
            application.id: {
                "job_url": values.get("job_url", application.job_url),
                "company_name": values.get("company_name", application.company_name),
                "name": values.get("name", application.name),
                "location": values.get("location", application.location),
            }
            for application in self
        }
        seen_urls = set()
        seen_company_positions = set()
        for application in self:
            application_values = effective_values[application.id]
            self._check_duplicate_values(application_values, excluded_ids=self.ids)
            job_url = application_values["job_url"]
            company_position = (
                application_values["company_name"],
                application_values["name"],
                application_values.get("location"),
            )
            if job_url in seen_urls:
                raise ValidationError(_("An application with this job URL already exists."))
            if company_position in seen_company_positions:
                raise ValidationError(
                    _("An application for this company and position already exists.")
                )
            seen_urls.add(job_url)
            seen_company_positions.add(company_position)
        result = super().write(values)
        for application_id, (old_state, new_state) in changed_states.items():
            _logger.info(
                "Job application %s state changed from %s to %s",
                application_id,
                old_state,
                new_state,
            )
        return result

    def get_api_data(self):
        """Return the intentionally public integration projection."""
        self.ensure_one()
        return {
            "id": self.id,
            "external_id": self.external_id or None,
            "source_job_id": self.source_job_id or None,
            "name": self.name,
            "company_name": self.company_name,
            "location": self.location or None,
            "job_url": self.job_url,
            "source": self.source,
            "salary_min": self.salary_min,
            "salary_max": self.salary_max,
            "salary_currency": self.salary_currency or None,
            "sponsorship_status": self.sponsorship_status,
            "sponsorship_confidence": self.sponsorship_confidence,
            "sponsorship_evidence": self.sponsorship_evidence or None,
            "sponsorship_evidence_source": self.sponsorship_evidence_source or None,
            "sponsorship_reason": self.sponsorship_reason or None,
            "sponsorship_analyzed_at": fields.Datetime.to_string(self.sponsorship_analyzed_at) if self.sponsorship_analyzed_at else None,
            "priority_score": self.priority_score,
            "match_score": self.match_score,
            "state": self.state,
            "job_description": self.job_description or None,
            "date_found": fields.Date.to_string(self.date_found) if self.date_found else None,
            "date_applied": fields.Date.to_string(self.date_applied) if self.date_applied else None,
            "last_sync_at": fields.Datetime.to_string(self.last_sync_at) if self.last_sync_at else None,
            "created_by_integration": bool(self.created_by_integration),
            "modalidad": self.modalidad or None,
        }

    @api.model
    def sync_normalized_job(self, values):
        """Idempotently store an already-normalized discovery result.

        This is shared by scheduled/manual discovery and keeps the API's model
        contract in one place.  It deliberately never changes application state.
        """
        values = dict(values)
        source = values.get("source")
        source_job_id = values.get("source_job_id")
        if source not in SOURCES or not source_job_id:
            raise ValidationError(_("A supported source and source job ID are required for synchronization."))
        values["job_url"] = canonical_url(values.get("job_url"))
        values["dedup_source_key"] = "%s:%s" % (source, source_job_id.strip())
        values["dedup_url_key"] = values["job_url"]
        values["dedup_content_key"] = " | ".join(
            (values.get(field_name) or "").strip().casefold()
            for field_name in ("company_name", "name", "location")
        )
        domains = (
            [("dedup_source_key", "=", values["dedup_source_key"])],
            [("source", "=", source), ("source_job_id", "=", source_job_id)],
            [("dedup_url_key", "=", values["dedup_url_key"])],
            [("job_url", "=", values["job_url"])],
            [("dedup_content_key", "=", values["dedup_content_key"])],
            [("company_name", "=ilike", values.get("company_name")),
             ("name", "=ilike", values.get("name")),
             ("location", "=ilike", values.get("location"))],
        )
        if any(self.with_context(active_test=False).search_count(domain) for domain in domains):
            return False
        # Records created before Phase 9 have no explicit keys; compare their URL canonically once.
        for legacy in self.with_context(active_test=False).search([("dedup_url_key", "=", False)]):
            try:
                if canonical_url(legacy.job_url) == values["dedup_url_key"]:
                    return False
            except ValidationError:
                continue
        values.setdefault("state", "found")
        values.setdefault("sponsorship_status", "unknown")
        values["created_by_integration"] = True
        values["last_sync_at"] = fields.Datetime.now()
        self.create(values)
        return True

    @staticmethod
    def _canonical_url(url):
        return canonical_url(url)

    @api.constrains("external_id")
    def _check_external_id(self):
        for application in self:
            if application.external_id and not application.external_id.strip():
                raise ValidationError(_("External ID cannot be empty or contain only spaces."))

    @api.constrains("source_job_id")
    def _check_source_job_id(self):
        for application in self:
            if application.source_job_id and not application.source_job_id.strip():
                raise ValidationError(_("Source Job ID cannot be empty or contain only spaces."))

    @api.constrains("external_id", "source_job_id")
    def _check_integration_lengths(self):
        for application in self:
            if application.external_id and len(application.external_id) > 128:
                raise ValidationError(_("External ID cannot exceed 128 characters."))
            if application.source_job_id and len(application.source_job_id) > 128:
                raise ValidationError(_("Source Job ID cannot exceed 128 characters."))

    @api.constrains("name", "company_name", "job_url")
    def _check_required_text(self):
        for application in self:
            if not all(
                value and value.strip()
                for value in (application.name, application.company_name, application.job_url)
            ):
                raise ValidationError(
                    _("Position, company, and job URL cannot be empty or contain only spaces.")
                )

    @api.constrains("match_score")
    def _check_match_score(self):
        for application in self:
            if not 0 <= application.match_score <= 100:
                raise ValidationError(_("Match score must be between 0 and 100."))

    @api.constrains("date_applied", "state")
    def _check_date_applied(self):
        allowed_states = {"applied", "interview", "offer", "rejected"}
        for application in self:
            if application.date_applied and application.state not in allowed_states:
                raise ValidationError(
                    _("Date applied can only be set for an applied, interview, offer, or rejected application.")
                )

    @api.constrains("salary_min", "salary_max")
    def _check_salary_range(self):
        for application in self:
            if (
                application.salary_min
                and application.salary_max
                and application.salary_min > application.salary_max
            ):
                raise ValidationError(_("Minimum salary cannot exceed maximum salary."))
