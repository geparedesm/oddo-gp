import hmac
import json
import logging
import math
import os

from psycopg2 import IntegrityError

from odoo import fields, http
from odoo.exceptions import ValidationError
from odoo.http import request

_logger = logging.getLogger(__name__)


class HermesJobHunterController(http.Controller):
    _TOKEN_ENVIRONMENT_VARIABLE = "HERMES_API_TOKEN"
    _TOKEN_PARAMETER = "job_hunter_management.hermes_api_token"
    _MAX_LIMIT = 100
    _CREATE_FIELDS = {
        "external_id", "source_job_id", "name", "company_name", "location", "job_url",
        "source", "salary_min", "salary_max", "salary_currency", "sponsorship_status",
        "match_score", "state", "job_description", "date_found", "date_applied",
        "raw_job_data",
    }
    _UPDATE_FIELDS = _CREATE_FIELDS - {"external_id", "job_url", "company_name", "name"}
    _SELECTIONS = {
        "source": {"seek", "linkedin", "indeed", "jora", "company_careers", "other"},
        "sponsorship_status": {"yes", "no", "unknown"},
        "state": {"found", "analysing", "good_match", "ready_to_apply", "applied", "interview", "offer", "rejected", "ignored"},
    }
    _NUMERIC_FIELDS = {"salary_min", "salary_max", "match_score"}

    def _json_response(self, payload, status=200):
        return request.make_json_response(payload, status=status)

    def _error(self, status, code, message):
        return self._json_response({"error": {"code": code, "message": message}}, status=status)

    def _is_authenticated(self):
        parameter = request.env["ir.config_parameter"].sudo()
        expected = parameter.get_param(self._TOKEN_PARAMETER) or os.environ.get(self._TOKEN_ENVIRONMENT_VARIABLE)
        authorization = request.httprequest.headers.get("Authorization", "")
        prefix = "Bearer "
        if not expected or not authorization.startswith(prefix):
            return False
        return hmac.compare_digest(authorization[len(prefix):], expected)

    def _read_json(self):
        try:
            body = request.httprequest.data.decode("utf-8")
            payload = json.loads(body)
        except (UnicodeDecodeError, json.JSONDecodeError):
            return None
        return payload if isinstance(payload, dict) else None

    def _validate_payload(self, payload, allowed, required=()):
        unknown = set(payload) - allowed
        missing = [field for field in required if field not in payload]
        if unknown or missing:
            return "Only supported fields are accepted; required fields are missing."
        for field in required:
            if not isinstance(payload[field], str) or not payload[field].strip():
                return "%s must be a non-empty string." % field
        for field in ("external_id", "source_job_id", "name", "company_name", "location", "job_url", "salary_currency", "job_description"):
            if field in payload and payload[field] is not None and not isinstance(payload[field], str):
                return "%s must be a string or null." % field
        for field, choices in self._SELECTIONS.items():
            if field in payload and payload[field] not in choices:
                return "%s is invalid." % field
        for field in self._NUMERIC_FIELDS:
            if field in payload and (isinstance(payload[field], bool) or not isinstance(payload[field], (int, float)) or not math.isfinite(payload[field])):
                return "%s must be a finite number." % field
        if "match_score" in payload and not 0 <= payload["match_score"] <= 100:
            return "match_score must be between 0 and 100."
        if "raw_job_data" in payload and not isinstance(payload["raw_job_data"], (dict, list, str, int, float, bool, type(None))):
            return "raw_job_data must be JSON data."
        for field in ("date_found", "date_applied"):
            if field in payload and payload[field] is not None:
                try:
                    fields.Date.from_string(payload[field])
                except (TypeError, ValueError):
                    return "%s must be an ISO date." % field
        return None

    def _values(self, payload, *, integration=False):
        values = dict(payload)
        if integration:
            values.update({"created_by_integration": True, "last_sync_at": fields.Datetime.now()})
        return values

    def _create(self, payload):
        model = request.env["job.application"].sudo()
        external_id = payload.get("external_id")
        if external_id:
            existing = model.search([("external_id", "=", external_id)], limit=1)
            if existing:
                return existing, True, None
        try:
            record = model.create(self._values(payload, integration=True))
        except (ValidationError, IntegrityError) as error:
            request.env.cr.rollback()
            return None, False, str(error).split("\n", 1)[0]
        except Exception:
            _logger.exception("Unexpected job application API creation failure")
            return None, False, "internal_error"
        return record, False, None

    def _record_response(self, record, status=200, idempotent=False):
        return self._json_response({"job": record.get_api_data(), "idempotent": idempotent}, status=status)

    @http.route("/api/job-hunter/jobs", type="http", auth="none", methods=["POST"], csrf=False)
    def create_job(self, **params):
        if not self._is_authenticated():
            return self._error(401, "unauthorized", "A valid bearer token is required.")
        payload = self._read_json()
        if payload is None:
            return self._error(400, "invalid_payload", "A JSON object is required.")
        error = self._validate_payload(payload, self._CREATE_FIELDS, required=("name", "company_name", "job_url"))
        if error:
            return self._error(400, "invalid_payload", error)
        record, idempotent, error = self._create(payload)
        if error:
            if error == "internal_error":
                return self._error(500, "internal_error", "The job could not be created.")
            return self._error(409, "conflict", error)
        return self._record_response(record, status=200 if idempotent else 201, idempotent=idempotent)

    @http.route("/api/job-hunter/jobs", type="http", auth="none", methods=["GET"], csrf=False)
    def list_jobs(self, **params):
        if not self._is_authenticated():
            return self._error(401, "unauthorized", "A valid bearer token is required.")
        domain = []
        for field in ("state", "source", "sponsorship_status", "company_name", "date_found"):
            if params.get(field):
                value = params[field].strip()
                if field in self._SELECTIONS and value not in self._SELECTIONS[field]:
                    return self._error(400, "invalid_parameter", "%s is invalid." % field)
                if field == "date_found":
                    try:
                        fields.Date.from_string(value)
                    except (TypeError, ValueError):
                        return self._error(400, "invalid_parameter", "date_found must be an ISO date.")
                domain.append((field, "=", value))
        if params.get("match_score_min") or params.get("min_match_score"):
            try:
                score = float(params.get("match_score_min", params.get("min_match_score")))
                if not math.isfinite(score) or score < 0 or score > 100:
                    raise ValueError
            except (TypeError, ValueError):
                return self._error(400, "invalid_parameter", "match_score_min must be between 0 and 100.")
            domain.append(("match_score", ">=", score))
        try:
            limit = int(params.get("limit", 50))
            if limit < 1 or limit > self._MAX_LIMIT:
                raise ValueError
        except (TypeError, ValueError):
            return self._error(400, "invalid_parameter", "limit must be between 1 and 100.")
        records = request.env["job.application"].sudo().search(domain, limit=limit)
        return self._json_response({"jobs": [record.get_api_data() for record in records], "count": len(records)})

    @http.route("/api/job-hunter/jobs/<int:job_id>", type="http", auth="none", methods=["GET"], csrf=False)
    def get_job(self, job_id, **params):
        if not self._is_authenticated():
            return self._error(401, "unauthorized", "A valid bearer token is required.")
        record = request.env["job.application"].sudo().browse(job_id).exists()
        if not record:
            return self._error(404, "not_found", "Job application not found.")
        return self._record_response(record)

    @http.route("/api/job-hunter/jobs/<int:job_id>", type="http", auth="none", methods=["PATCH"], csrf=False)
    def update_job(self, job_id, **params):
        if not self._is_authenticated():
            return self._error(401, "unauthorized", "A valid bearer token is required.")
        record = request.env["job.application"].sudo().browse(job_id).exists()
        if not record:
            return self._error(404, "not_found", "Job application not found.")
        payload = self._read_json()
        if payload is None or not payload:
            return self._error(400, "invalid_payload", "A non-empty JSON object is required.")
        error = self._validate_payload(payload, self._UPDATE_FIELDS)
        if error:
            return self._error(400, "invalid_payload", error)
        try:
            payload["last_sync_at"] = fields.Datetime.now()
            record.write(payload)
        except (ValidationError, IntegrityError) as error:
            request.env.cr.rollback()
            return self._error(409, "conflict", str(error).split("\n", 1)[0])
        except Exception:
            _logger.exception("Unexpected job application API update failure for record %s", job_id)
            return self._error(500, "internal_error", "The job could not be updated.")
        return self._record_response(record)
