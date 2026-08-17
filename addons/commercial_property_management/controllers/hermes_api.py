import hmac
import hashlib
import math
import os

import json

from odoo import fields, http
from odoo.http import request


class HermesPropertyController(http.Controller):
    _TOKEN_ENVIRONMENT_VARIABLE = "HERMES_API_TOKEN"
    _TOKEN_PARAMETER = "commercial_property_management.hermes_api_token"
    _MAX_LIMIT = 50
    _MAX_ENQUIRY_BYTES = 8192

    def _json_response(self, payload, status=200):
        return request.make_json_response(payload, status=status)

    def _error(self, status, code, message):
        channel = "mcp" if request.httprequest.headers.get("X-Hermes-Channel") == "mcp" else "api"
        if status >= 400 and status != 404:
            request.env["commercial.property.integration.alert"].raise_alert(request.env, channel, "%s-%s" % (channel, code), "Public integration request failed", "critical" if status >= 500 else "warning", code)
        return self._json_response({"error": {"code": code, "message": message}}, status=status)

    def _is_authenticated(self):
        expected_token = request.env["ir.config_parameter"].sudo().get_param(self._TOKEN_PARAMETER)
        expected_token = expected_token or os.environ.get(self._TOKEN_ENVIRONMENT_VARIABLE)
        authorization = request.httprequest.headers.get("Authorization", "")
        token_prefix = "Bearer "
        if not expected_token or not authorization.startswith(token_prefix):
            return False
        return hmac.compare_digest(authorization[len(token_prefix) :], expected_token)

    def _is_intake_enabled(self):
        return request.env["ir.config_parameter"].sudo().get_param("commercial_property_management.whatsapp_intake_enabled") == "True"

    def _request_hash(self, value):
        token = request.env["ir.config_parameter"].sudo().get_param(self._TOKEN_PARAMETER) or os.environ.get(self._TOKEN_ENVIRONMENT_VARIABLE, "")
        return hmac.new(token.encode(), value.encode(), hashlib.sha256).hexdigest()

    def _rate_limit_allows_request(self, source_hash):
        limit = request.env["ir.config_parameter"].sudo().get_param("commercial_property_management.whatsapp_public_rate_limit", "5")
        try:
            limit = max(1, int(limit))
        except (TypeError, ValueError):
            limit = 5
        return request.env["commercial.property.lead"].sudo().search_count([("source", "=", "whatsapp"), ("public_source_hash", "=", source_hash), ("create_date", ">=", fields.Datetime.subtract(fields.Datetime.now(), minutes=60))]) < limit

    def _parse_non_negative_number(self, value, parameter):
        if value in (None, ""):
            return None
        try:
            parsed_value = float(value)
        except (TypeError, ValueError):
            raise ValueError(parameter)
        if not math.isfinite(parsed_value) or parsed_value < 0:
            raise ValueError(parameter)
        return parsed_value

    @http.route("/api/hermes/properties", type="http", auth="none", methods=["GET"], csrf=False)
    def search_properties(self, **params):
        if not self._is_authenticated():
            return self._error(401, "unauthorized", "A valid bearer token is required.")
        if params.get("availability", "available") != "available":
            return self._error(400, "invalid_parameter", "availability must be available.")
        try:
            min_area = self._parse_non_negative_number(params.get("min_area"), "min_area")
            max_rent = self._parse_non_negative_number(params.get("max_rent"), "max_rent")
            limit = int(params.get("limit", 20))
            if limit < 1 or limit > self._MAX_LIMIT:
                raise ValueError("limit")
        except (TypeError, ValueError):
            return self._error(400, "invalid_parameter", "Use valid non-negative filters and a limit from 1 to 50.")

        units = request.env["commercial.property.unit"].sudo().search_public_units(
            min_area=min_area,
            max_rent=max_rent,
            limit=limit,
        )
        return self._json_response({"properties": [unit.get_public_data() for unit in units]})

    @http.route("/api/hermes/properties/<string:property_code>", type="http", auth="none", methods=["GET"], csrf=False)
    def get_property(self, property_code, **params):
        if not self._is_authenticated():
            return self._error(401, "unauthorized", "A valid bearer token is required.")
        unit = request.env["commercial.property.unit"].sudo().search_public_units(
            code=property_code,
            limit=1,
        )
        if not unit:
            return self._error(404, "not_found", "Public property not found.")
        return self._json_response({"property": unit.get_public_data()})

    @http.route("/api/hermes/properties/<string:property_code>/enquiries", type="http", auth="none", methods=["POST"], csrf=False)
    def submit_enquiry(self, property_code, **params):
        if not self._is_authenticated():
            return self._error(401, "unauthorized", "A valid bearer token is required.")
        if not self._is_intake_enabled():
            return self._error(503, "intake_disabled", "WhatsApp enquiry intake is awaiting administrator approval.")
        if request.httprequest.content_length and request.httprequest.content_length > self._MAX_ENQUIRY_BYTES:
            return self._error(413, "payload_too_large", "The enquiry payload is too large.")
        try:
            payload = json.loads(request.httprequest.data.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            payload = None
        if not isinstance(payload, dict):
            return self._error(400, "invalid_parameter", "A JSON object is required.")
        allowed = {"name", "phone", "email", "company_name", "business_activity", "desired_start_date", "message", "visit_requested", "consent", "website"}
        text_fields = allowed - {"consent", "visit_requested", "desired_start_date"}
        if (
            payload.get("consent") is not True
            or not isinstance(payload.get("name"), str)
            or not payload["name"].strip()
            or not isinstance(payload.get("phone"), str)
            or not payload["phone"].strip()
            or set(payload) - allowed
            or any(not isinstance(payload[field], str) for field in text_fields if field in payload)
            or ("visit_requested" in payload and not isinstance(payload["visit_requested"], bool))
            or ("website" in payload and not isinstance(payload["website"], str))
        ):
            return self._error(400, "invalid_parameter", "Name, phone and explicit consent are required.")
        if payload.get("website"):
            self.env["commercial.property.integration.alert"].raise_alert(request.env, "api", "api-abuse-honeypot", "Public enquiry abuse detected", "warning", "Honeypot field was populated.")
            return self._json_response({"message": "Your enquiry was received for manager review."}, status=202)
        if any(len(payload.get(field, "")) > maximum for field, maximum in {"name": 128, "phone": 64, "email": 254, "company_name": 256, "business_activity": 256, "message": 2000}.items()):
            return self._error(400, "invalid_parameter", "One or more enquiry fields are too long.")
        if payload.get("desired_start_date"):
            try:
                fields.Date.to_date(payload["desired_start_date"])
            except (TypeError, ValueError):
                return self._error(400, "invalid_parameter", "desired_start_date must be a valid date.")
        unit = request.env["commercial.property.unit"].sudo().search_public_units(code=property_code, limit=1)
        if not unit:
            return self._error(404, "not_found", "Public property not found.")
        idempotency_key = request.httprequest.headers.get("Idempotency-Key", "").strip()
        if not idempotency_key or len(idempotency_key) > 128:
            return self._error(400, "invalid_idempotency_key", "A valid Idempotency-Key header is required.")
        request_key_hash = self._request_hash(idempotency_key)
        existing = request.env["commercial.property.lead"].sudo().search([("public_request_key_hash", "=", request_key_hash)], limit=1)
        if existing:
            return self._json_response({"message": "Your enquiry was already received for manager review."})
        source_hash = self._request_hash(request.httprequest.remote_addr or "unknown")
        if not self._rate_limit_allows_request(source_hash):
            return self._error(429, "rate_limited", "Too many enquiry requests. Please try again later.")
        values = {
            field: payload[field].strip()
            for field in text_fields
            if payload.get(field)
        }
        if payload.get("desired_start_date"):
            values["desired_start_date"] = payload["desired_start_date"]
        values.update(
            {
                "unit_id": unit.id,
                "consent_at": request.env.cr.now(),
                "source": "whatsapp",
                "visit_requested_at": request.env.cr.now() if payload.get("visit_requested") else False,
                "public_request_key_hash": request_key_hash,
                "public_source_hash": source_hash,
            }
        )
        request.env["commercial.property.lead"].sudo().create(values)
        return self._json_response({"message": "Your enquiry was received for manager review."}, status=201)
