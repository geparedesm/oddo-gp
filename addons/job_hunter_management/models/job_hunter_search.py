import hashlib
import json
import logging
import math
import os
import re
import time
from datetime import datetime, timedelta
from email.utils import parsedate_to_datetime
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

from .vacancy_contract import MODES, SOURCES, canonical_url, normalize_job

_logger = logging.getLogger(__name__)

ADZUNA_API_ROOT = "https://api.adzuna.com/v1/api/jobs/au/search"


class AdzunaCredentialsError(RuntimeError):
    pass


class AdzunaRequestError(RuntimeError):
    pass


class FixtureAdapter:
    """Deterministic, non-scraping adapter used when external feeds are unavailable."""
    def __init__(self, source):
        self.source = source

    def search(self, config):
        criteria = config.get_search_criteria()
        keyword = (criteria["keywords"] or criteria["roles"] or "Software Engineer").split(",")[0].strip()
        slug = hashlib.sha1((self.source + keyword).encode()).hexdigest()[:10]
        return [{"source_job_id": "%s-%s" % (self.source, slug), "title": "%s (%s)" % (keyword, SOURCES[self.source]),
                 "company": "Fixture %s Pty Ltd" % SOURCES[self.source],
                 "location": criteria["location"] or "Australia", "url": "https://fixtures.example/%s/jobs/%s" % (self.source, slug),
                 "description": "Deterministic fixture opportunity for %s." % keyword,
                 "salary_min": criteria["salary_min"] or 90000,
                 "salary_max": (criteria["salary_min"] or 90000) + 20000,
                 "currency": criteria["salary_currency"] or "AUD",
                 "modalidad": criteria["modalities"][0] if criteria["modalities"] else "remote",
                 "date_found": fields.Date.today()}]


class AdzunaAdapter:
    """Official Adzuna Australia API adapter with bounded, secret-safe HTTP."""

    _default_opener = staticmethod(urlopen)

    def __init__(self, source, opener=None, sleeper=None, monotonic=None):
        self.source = source
        self._opener = opener or self._default_opener
        self._sleep = sleeper or time.sleep
        self._monotonic = monotonic or time.monotonic
        self._last_request_at = None
        self.last_page = 0

    def _credentials(self):
        parameters = self.source.env["ir.config_parameter"].sudo()
        app_id = os.environ.get("ADZUNA_APP_ID") or parameters.get_param(
            "job_hunter_management.adzuna_app_id",
        )
        app_key = os.environ.get("ADZUNA_APP_KEY") or parameters.get_param(
            "job_hunter_management.adzuna_app_key",
        )
        if not app_id or not app_key:
            raise AdzunaCredentialsError(
                "Adzuna credentials are not configured; the source remains unavailable."
            )
        return app_id, app_key

    def _request_params(self, config, app_id, app_key):
        criteria = config.get_search_criteria()
        params = {
            "app_id": app_id,
            "app_key": app_key,
            "results_per_page": self.source.default_page_size,
        }
        what = criteria.get("keywords") or criteria.get("roles")
        if what:
            params["what"] = str(what).split(",", 1)[0].strip()
        if criteria.get("location"):
            params["where"] = criteria["location"]
        if criteria.get("salary_min"):
            salary_min = criteria["salary_min"]
            params["salary_min"] = int(salary_min) if float(salary_min).is_integer() else salary_min
        if criteria.get("max_age_days"):
            params["max_days_old"] = criteria["max_age_days"]
        return params

    def _rate_limit(self):
        now = self._monotonic()
        if self._last_request_at is not None:
            remaining = self.source.rate_limit_seconds - (now - self._last_request_at)
            if remaining > 0:
                self._sleep(remaining)
                now = self._monotonic()
        self._last_request_at = now

    def _retry_delay(self, error, attempt):
        if isinstance(error, HTTPError) and error.code == 429:
            value = error.headers.get("Retry-After") if error.headers else None
            if value:
                try:
                    delay = float(value)
                except (TypeError, ValueError):
                    try:
                        retry_at = parsedate_to_datetime(value)
                        delay = max(0.0, (retry_at - datetime.now(retry_at.tzinfo)).total_seconds())
                    except (TypeError, ValueError, OverflowError):
                        delay = 0.0
                return min(max(0.0, delay), self.source.retry_after_max_seconds)
        return min(float(2 ** attempt), self.source.retry_after_max_seconds)

    @staticmethod
    def _retryable(error):
        if isinstance(error, HTTPError):
            return error.code == 429 or 500 <= error.code < 600
        return isinstance(error, (URLError, TimeoutError))

    def _fetch_page(self, page, params):
        url = "%s/%s?%s" % (ADZUNA_API_ROOT, page, urlencode(params))
        request = Request(url, headers={
            "Accept": "application/json",
            "Content-Type": "application/json",
        })
        for attempt in range(self.source.retry_count + 1):
            self._rate_limit()
            try:
                with self._opener(request, timeout=self.source.request_timeout_seconds) as response:
                    payload = json.loads(response.read().decode("utf-8"))
                if not isinstance(payload, dict) or not isinstance(payload.get("results"), list):
                    raise AdzunaRequestError("Adzuna returned an invalid response payload.")
                count = payload.get("count", len(payload["results"]))
                if isinstance(count, bool) or not isinstance(count, int) or count < 0:
                    raise AdzunaRequestError("Adzuna returned an invalid result count.")
                return payload
            except (HTTPError, URLError, TimeoutError) as error:
                if attempt >= self.source.retry_count or not self._retryable(error):
                    status = " HTTP %s" % error.code if isinstance(error, HTTPError) else " network"
                    raise AdzunaRequestError("Adzuna request failed (%s)." % status.strip()) from None
                self._sleep(self._retry_delay(error, attempt))
            except (UnicodeDecodeError, json.JSONDecodeError) as error:
                raise AdzunaRequestError("Adzuna returned invalid JSON.") from None
        raise AdzunaRequestError("Adzuna request failed.")

    @staticmethod
    def _inferred_mode(raw_job):
        explicit = raw_job.get("work_mode") or raw_job.get("modalidad")
        if explicit in MODES:
            return explicit
        text = " ".join(str(raw_job.get(key) or "") for key in ("title", "description")).lower()
        if re.search(r"\b(remote|work from home|wfh)\b", text):
            return "remote"
        if re.search(r"\bhybrid\b", text):
            return "hybrid"
        if re.search(r"\b(on[ -]?site|in[ -]?office)\b", text):
            return "onsite"
        return None

    def search(self, config):
        app_id, app_key = self._credentials()
        params = self._request_params(config, app_id, app_key)
        criteria = config.get_search_criteria()
        result_limit = self.source.result_limit
        page_size = self.source.default_page_size
        jobs = []
        seen_pages = set()
        page = 1
        while page not in seen_pages and len(jobs) < result_limit:
            seen_pages.add(page)
            payload = self._fetch_page(page, params)
            results = payload["results"]
            self.last_page = page
            for original in results:
                if not isinstance(original, dict):
                    jobs.append(original)
                    continue
                raw_job = dict(original)
                mode = self._inferred_mode(raw_job)
                if criteria["modalities"] and mode and mode not in criteria["modalities"]:
                    continue
                if mode:
                    raw_job["work_mode"] = mode
                raw_job.update({"page": page, "page_size": page_size, "result_limit": result_limit})
                jobs.append(raw_job)
                if len(jobs) >= result_limit:
                    break
            if not results or page * page_size >= payload["count"]:
                break
            page += 1
        return jobs

    def provenance(self, page=None):
        return {
            "queried_at": fields.Datetime.to_string(fields.Datetime.now()),
            "page": page or self.last_page, "page_size": self.source.default_page_size,
            "result_limit": self.source.result_limit,
        }


class JobHunterSearchConfig(models.Model):
    _name = "job.hunter.search.config"
    _description = "Job Hunter Search Configuration"
    _order = "name"

    name = fields.Char(required=True)
    active = fields.Boolean(default=True)
    keywords = fields.Char(help="Comma-separated search keywords.")
    roles = fields.Char(help="Comma-separated target roles.")
    location = fields.Char()
    modalidad = fields.Selection([(m, m.title()) for m in sorted(MODES)])
    salary_min = fields.Float()
    max_age_days = fields.Integer(default=30)
    source_ids = fields.Many2many("job.hunter.search.source", string="Enabled Sources")
    last_run_at = fields.Datetime(readonly=True)
    profile_id = fields.Many2one("job.hunter.profile", ondelete="set null", index=True)
    profile_roles = fields.Text(related="profile_id.target_roles", string="Target Roles", readonly=True)
    profile_location = fields.Char(related="profile_id.location", string="Profile Location", readonly=True)
    profile_salary_min = fields.Float(related="profile_id.target_salary", string="Target Salary", readonly=True)
    profile_salary_currency = fields.Char(related="profile_id.salary_currency", string="Salary Currency", readonly=True)
    profile_modalities = fields.Char(compute="_compute_profile_modalities", string="Modalities", readonly=True)
    profile_last_hermes_search_at = fields.Datetime(
        related="profile_id.last_hermes_search_at", string="Last Hermes Search", readonly=True,
    )

    _sql_constraints = [
        ("profile_unique", "unique(profile_id)",
         "A profile can only have one search configuration."),
    ]

    @api.depends("profile_id.remote_ok", "profile_id.hybrid_ok", "profile_id.onsite_ok")
    def _compute_profile_modalities(self):
        for config in self:
            config.profile_modalities = ", ".join(config._profile_modalities())

    def _profile_modalities(self):
        self.ensure_one()
        return [mode for mode in ("remote", "hybrid", "onsite")
                if self.profile_id and getattr(self.profile_id, "%s_ok" % mode)]

    def get_search_criteria(self):
        self.ensure_one()
        if self.profile_id:
            return {
                "keywords": self.profile_id.target_roles,
                "roles": self.profile_id.target_roles,
                "location": self.profile_id.location,
                "salary_min": self.profile_id.target_salary,
                "salary_currency": self.profile_id.salary_currency,
                "modalities": self._profile_modalities(),
                "max_age_days": self.max_age_days,
            }
        return {
            "keywords": self.keywords, "roles": self.roles, "location": self.location,
            "salary_min": self.salary_min, "salary_currency": False,
            "modalities": [self.modalidad] if self.modalidad else [],
            "max_age_days": self.max_age_days,
        }

    @api.constrains("salary_min", "max_age_days")
    def _check_filters(self):
        for record in self:
            if record.salary_min < 0 or record.max_age_days < 0:
                raise ValidationError(_("Salary and publication age filters cannot be negative."))

    def action_run(self):
        self.ensure_one()
        return self.env["job.hunter.search.run"].run_config(self)


class JobHunterSearchSource(models.Model):
    _name = "job.hunter.search.source"
    _description = "Job Hunter Search Source"
    _order = "name"

    name = fields.Char(required=True)
    code = fields.Selection([(k, v) for k, v in SOURCES.items()], required=True)
    active = fields.Boolean(default=True)
    adapter_type = fields.Selection([
        ("fixture", "Deterministic fixture"), ("adzuna", "Adzuna official API"),
    ], default="fixture", required=True)
    provider = fields.Char(default="fixture", required=True)
    default_page_size = fields.Integer(default=20)
    result_limit = fields.Integer(default=100)
    rate_limit_seconds = fields.Float(default=1.0)
    retry_count = fields.Integer(default=2)
    request_timeout_seconds = fields.Float(default=10.0)
    retry_after_max_seconds = fields.Float(default=30.0)

    _sql_constraints = [("job_hunter_source_code_unique", "unique(code)", "Source code must be unique.")]

    @api.constrains(
        "default_page_size", "result_limit", "rate_limit_seconds", "retry_count",
        "request_timeout_seconds", "retry_after_max_seconds",
    )
    def _check_limits(self):
        for source in self:
            if not 1 <= source.default_page_size <= 50 or not 1 <= source.result_limit <= 1000:
                raise ValidationError(_("Page size must be 1-50 and result limit must be 1-1000."))
            if source.rate_limit_seconds < 0 or not 0 <= source.retry_count <= 10:
                raise ValidationError(_("Rate limit must be non-negative and retries must be 0-10."))
            if source.request_timeout_seconds <= 0 or source.retry_after_max_seconds < 0:
                raise ValidationError(_("Timeout must be positive and Retry-After cap cannot be negative."))
            numeric = (
                source.rate_limit_seconds, source.request_timeout_seconds,
                source.retry_after_max_seconds,
            )
            if not all(math.isfinite(value) for value in numeric):
                raise ValidationError(_("HTTP timing values must be finite."))


class JobHunterSearchRun(models.Model):
    _name = "job.hunter.search.run"
    _description = "Job Hunter Search Execution"
    _order = "started_at desc, id desc"

    config_id = fields.Many2one("job.hunter.search.config", required=True, ondelete="cascade")
    profile_id = fields.Many2one("job.hunter.profile", ondelete="set null", index=True, readonly=True)
    started_at = fields.Datetime(required=True, default=fields.Datetime.now)
    finished_at = fields.Datetime()
    duration_seconds = fields.Float()
    state = fields.Selection([("running", "Running"), ("done", "Done"), ("partial", "Partial")], default="running", required=True)
    line_ids = fields.One2many("job.hunter.search.run.line", "run_id")
    total_found = fields.Integer(compute="_compute_totals", store=True)
    total_new = fields.Integer(compute="_compute_totals", store=True)
    total_duplicates = fields.Integer(compute="_compute_totals", store=True)
    total_errors = fields.Integer(compute="_compute_totals", store=True)

    @api.depends("line_ids.found", "line_ids.new_count", "line_ids.duplicate_count", "line_ids.error_count")
    def _compute_totals(self):
        for run in self:
            run.total_found = sum(run.line_ids.mapped("found"))
            run.total_new = sum(run.line_ids.mapped("new_count"))
            run.total_duplicates = sum(run.line_ids.mapped("duplicate_count"))
            run.total_errors = sum(run.line_ids.mapped("error_count"))

    @api.model
    def run_config(self, config, include_fixtures=True):
        started = time.monotonic()
        # Runs and their lines are audit records; users trigger the engine but do not forge them directly.
        run = self.sudo().create({"config_id": config.id, "profile_id": config.profile_id.id})
        source_records = config.source_ids.filtered("active")
        if not source_records:
            source_records = self.env["job.hunter.search.source"].search([("active", "=", True)])
        if not include_fixtures:
            source_records = source_records.filtered(lambda source: source.adapter_type != "fixture")
        partial = False
        for source in source_records:
            queried_at = fields.Datetime.now()
            values = {
                "run_id": run.id, "source": source.code, "provider": source.provider,
                "queried_at": queried_at, "availability": "available",
                "page_size": source.default_page_size, "result_limit": source.result_limit,
            }
            try:
                adapter = (
                    AdzunaAdapter(source) if source.adapter_type == "adzuna"
                    else FixtureAdapter(source.code)
                )
                raw_jobs = list(adapter.search(config) or [])
                new_count = duplicate_count = 0
                invalid_count = 0
                for raw_job in raw_jobs:
                    try:
                        provenance = (
                            adapter.provenance(raw_job.get("page")) if source.adapter_type == "adzuna"
                            else {"queried_at": fields.Datetime.to_string(queried_at),
                                  "page_size": source.default_page_size,
                                  "result_limit": source.result_limit}
                        )
                        job = normalize_job(raw_job, source.code, provenance)
                        if config.max_age_days:
                            cutoff = fields.Date.today() - timedelta(days=config.max_age_days)
                            if fields.Date.from_string(job["date_found"]) < cutoff:
                                continue
                        if self.env["job.application"].sync_normalized_job(job):
                            new_count += 1
                        else:
                            duplicate_count += 1
                    except (ValidationError, TypeError, ValueError) as error:
                        invalid_count += 1
                        partial = True
                        values["error_message"] = self._safe_error(error)
                values.update(
                    found=len(raw_jobs), new_count=new_count, duplicate_count=duplicate_count,
                    error_count=invalid_count,
                    availability="invalid" if invalid_count else "available",
                )
                if source.adapter_type == "adzuna":
                    values["page"] = adapter.last_page
            except Exception as error:
                partial = True
                _logger.warning("Job Hunter source %s failed: %s", source.code, self._safe_error(error))
                values.update(error_count=1, error_message=self._safe_error(error), availability="unavailable")
            self.env["job.hunter.search.run.line"].sudo().create(values)
        completed_at = fields.Datetime.now()
        run.write({"finished_at": completed_at, "duration_seconds": time.monotonic() - started,
                   "state": "partial" if partial else "done"})
        config.write({"last_run_at": completed_at})
        if config.profile_id:
            config.profile_id.write({"last_hermes_search_at": completed_at})
        return run

    @api.model
    def _safe_error(self, error):
        message = str(error)[:500]
        for marker in ("token", "secret", "password", "authorization", "api_key", "apikey", "app_id", "app_key"):
            message = re.sub(
                r"(?i)(%s\s*[=:]\s*)[^\s,;]+" % marker, r"\1[redacted]", message,
            )
        return message

    @api.model
    def cron_run_active_configs(self):
        for config in self.env["job.hunter.search.config"].search([("active", "=", True)]):
            self.run_config(config)


class JobHunterSearchRunLine(models.Model):
    _name = "job.hunter.search.run.line"
    _description = "Job Hunter Search Source Result"

    run_id = fields.Many2one("job.hunter.search.run", required=True, ondelete="cascade")
    source = fields.Selection([(k, v) for k, v in SOURCES.items()], required=True)
    provider = fields.Char(required=True, default="fixture")
    queried_at = fields.Datetime(required=True, default=fields.Datetime.now)
    availability = fields.Selection(
        [("available", "Available"), ("unavailable", "Unavailable"), ("invalid", "Invalid payload")],
        required=True, default="available",
    )
    page = fields.Integer()
    page_cursor = fields.Char()
    page_size = fields.Integer()
    result_limit = fields.Integer()
    found = fields.Integer(default=0)
    new_count = fields.Integer(default=0)
    duplicate_count = fields.Integer(default=0)
    error_count = fields.Integer(default=0)
    error_message = fields.Char()
