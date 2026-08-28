import hashlib
import logging
import time
from datetime import datetime, timedelta
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


SOURCES = {
    "seek": "SEEK", "linkedin": "LinkedIn", "indeed": "Indeed",
    "jora": "Jora", "company_careers": "Company Careers",
}
MODES = {"onsite", "hybrid", "remote"}


def canonical_url(url):
    parts = urlsplit((url or "").strip())
    query = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True)
             if not (k.lower().startswith("utm_") or k.lower() in {"ref", "source", "trk"})]
    path = parts.path.rstrip("/") or "/"
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), path, urlencode(query), ""))


def normalize_job(raw, source):
    """Convert an adapter payload into the narrow API contract."""
    raw = dict(raw or {})
    title = str(raw.get("title") or raw.get("name") or "").strip()
    company = str(raw.get("company") or raw.get("company_name") or "").strip()
    location = str(raw.get("location") or "").strip()
    url = str(raw.get("url") or raw.get("job_url") or "").strip()
    mode = str(raw.get("modalidad") or raw.get("work_mode") or "").lower().strip()
    if mode not in MODES:
        mode = "remote" if "remote" in (location + " " + str(raw.get("description", ""))).lower() else "onsite"
    found = raw.get("date_found") or fields.Date.today()
    if isinstance(found, datetime):
        found = found.date()
    raw["date_found"] = fields.Date.to_string(found)
    return {
        "name": title, "company_name": company, "location": location,
        "job_url": url, "source": source, "source_job_id": str(raw.get("source_job_id") or "").strip() or False,
        "job_description": str(raw.get("description") or raw.get("job_description") or "").strip(),
        "salary_min": float(raw.get("salary_min") or 0), "salary_max": float(raw.get("salary_max") or 0),
        "salary_currency": str(raw.get("currency") or raw.get("salary_currency") or "").strip() or False,
        "date_found": fields.Date.to_string(found), "modalidad": mode,
        "raw_job_data": raw,
    }


class FixtureAdapter:
    """Deterministic, non-scraping adapter used when external feeds are unavailable."""
    def __init__(self, source):
        self.source = source

    def search(self, config):
        keyword = (config.keywords or config.roles or "Software Engineer").split(",")[0].strip()
        slug = hashlib.sha1((self.source + keyword).encode()).hexdigest()[:10]
        return [{"source_job_id": "%s-%s" % (self.source, slug), "title": "%s (%s)" % (keyword, SOURCES[self.source]),
                 "company": "Fixture %s Pty Ltd" % SOURCES[self.source],
                 "location": config.location or "Australia", "url": "https://fixtures.example/%s/jobs/%s" % (self.source, slug),
                 "description": "Deterministic fixture opportunity for %s." % keyword,
                 "salary_min": config.salary_min or 90000, "salary_max": (config.salary_min or 90000) + 20000,
                 "currency": "AUD", "modalidad": config.modalidad or "remote", "date_found": fields.Date.today()}]


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
    adapter_type = fields.Selection([("fixture", "Deterministic fixture")], default="fixture", required=True)

    _sql_constraints = [("job_hunter_source_code_unique", "unique(code)", "Source code must be unique.")]


class JobHunterSearchRun(models.Model):
    _name = "job.hunter.search.run"
    _description = "Job Hunter Search Execution"
    _order = "started_at desc, id desc"

    config_id = fields.Many2one("job.hunter.search.config", required=True, ondelete="cascade")
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
    def run_config(self, config):
        started = time.monotonic()
        run = self.create({"config_id": config.id})
        source_records = config.source_ids.filtered("active")
        if not source_records:
            source_records = self.env["job.hunter.search.source"].search([("active", "=", True)])
        partial = False
        for source in source_records:
            values = {"run_id": run.id, "source": source.code}
            try:
                adapter = FixtureAdapter(source.code)
                jobs = [normalize_job(job, source.code) for job in adapter.search(config)]
                if config.max_age_days:
                    cutoff = fields.Date.today() - timedelta(days=config.max_age_days)
                    jobs = [job for job in jobs if fields.Date.from_string(job["date_found"]) >= cutoff]
                new_count = duplicate_count = 0
                for job in jobs:
                    if self.env["job.application"].sync_normalized_job(job):
                        new_count += 1
                    else:
                        duplicate_count += 1
                values.update(found=len(jobs), new_count=new_count, duplicate_count=duplicate_count)
            except Exception as error:
                partial = True
                _logger.exception("Job Hunter source %s failed", source.code)
                values.update(error_count=1, error_message=str(error)[:500])
            self.env["job.hunter.search.run.line"].create(values)
        run.write({"finished_at": fields.Datetime.now(), "duration_seconds": time.monotonic() - started,
                   "state": "partial" if partial else "done"})
        config.write({"last_run_at": fields.Datetime.now()})
        return run

    @api.model
    def cron_run_active_configs(self):
        for config in self.env["job.hunter.search.config"].search([("active", "=", True)]):
            self.run_config(config)


class JobHunterSearchRunLine(models.Model):
    _name = "job.hunter.search.run.line"
    _description = "Job Hunter Search Source Result"

    run_id = fields.Many2one("job.hunter.search.run", required=True, ondelete="cascade")
    source = fields.Selection([(k, v) for k, v in SOURCES.items()], required=True)
    found = fields.Integer(default=0)
    new_count = fields.Integer(default=0)
    duplicate_count = fields.Integer(default=0)
    error_count = fields.Integer(default=0)
    error_message = fields.Char()
