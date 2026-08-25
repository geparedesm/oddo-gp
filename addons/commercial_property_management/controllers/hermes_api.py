import base64
import binascii
import hmac
import hashlib
import math
import os

import json

from odoo import fields, http
from odoo.http import request
from odoo.tools.mimetypes import guess_mimetype

from ..models.commercial_property_lead import normalize_whatsapp_sender


class HermesPropertyController(http.Controller):
    _TOKEN_ENVIRONMENT_VARIABLE = "HERMES_API_TOKEN"
    _TOKEN_PARAMETER = "commercial_property_management.hermes_api_token"
    _MCP_TOKEN_ENVIRONMENT_VARIABLE = "HERMES_MCP_CHANNEL_TOKEN"
    _MCP_TOKEN_PARAMETER = (
        "commercial_property_management.hermes_mcp_channel_token"
    )
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

    def _is_mcp_request(self):
        if request.httprequest.headers.get("X-Hermes-Channel") != "mcp":
            return False
        expected_token = request.env["ir.config_parameter"].sudo().get_param(
            self._MCP_TOKEN_PARAMETER
        ) or os.environ.get(self._MCP_TOKEN_ENVIRONMENT_VARIABLE)
        api_token = request.env["ir.config_parameter"].sudo().get_param(
            self._TOKEN_PARAMETER
        ) or os.environ.get(self._TOKEN_ENVIRONMENT_VARIABLE)
        provided_token = request.httprequest.headers.get(
            "X-Hermes-MCP-Token", ""
        )
        if (
            not expected_token
            or not api_token
            or not provided_token
            or hmac.compare_digest(expected_token, api_token)
        ):
            return False
        return hmac.compare_digest(provided_token, expected_token)

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
        zone = (params.get("zone") or "").strip()[:128] or None
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
            zone=zone,
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

    @http.route("/api/hermes/properties/<string:property_code>/photo", type="http", auth="none", methods=["GET"], csrf=False)
    def get_property_photo(self, property_code, **params):
        if not self._is_authenticated():
            return self._error(401, "unauthorized", "A valid bearer token is required.")
        unit = request.env["commercial.property.unit"].sudo().search_public_units(code=property_code, limit=1)
        if not unit or not unit.image_ids:
            return self._error(404, "not_found", "Public property photo not found.")
        
        # Get index from query param, default to 0 (first image)
        try:
            index = int(params.get('index', 0))
        except (TypeError, ValueError):
            return self._error(400, "invalid_parameter", "index must be a valid integer.")
        
        images = unit.image_ids.sorted('sequence')
        if index < 0 or index >= len(images):
            return self._error(404, "not_found", "Image index out of range.")
        
        image = images[index]
        if not image.image_1920:
            return self._error(404, "not_found", "Public property photo not found.")
        
        try:
            image_bytes = base64.b64decode(image.image_1920, validate=True)
        except (binascii.Error, ValueError):
            return self._error(404, "not_found", "Public property photo not found.")
        
        mimetype = guess_mimetype(image_bytes, default="image/png")
        return request.make_response(image_bytes, headers=[("Content-Type", mimetype)])

    @http.route("/api/hermes/properties/<string:property_code>/photos", type="http", auth="none", methods=["GET"], csrf=False)
    def get_property_photos_metadata(self, property_code, **params):
        if not self._is_authenticated():
            return self._error(401, "unauthorized", "A valid bearer token is required.")
        
        unit = request.env["commercial.property.unit"].sudo().search_public_units(code=property_code, limit=1)
        if not unit:
            return self._error(404, "not_found", "Public property not found.")
        
        images = unit.image_ids.sorted('sequence')
        photos = [
            {
                "index": idx,
                "url": "/api/hermes/properties/%s/photo?index=%d" % (property_code, idx),
                "name": image.name or None,
            }
            for idx, image in enumerate(images)
        ]
        
        return self._json_response({"photos": photos, "count": len(photos)})


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
        allowed = {"name", "phone", "whatsapp_sender", "email", "company_name", "business_activity", "desired_start_date", "message", "visit_requested", "consent", "website", "channel", "budget"}
        text_fields = allowed - {"consent", "visit_requested", "desired_start_date", "channel", "budget"}
        normalized_sender = normalize_whatsapp_sender(payload.get("whatsapp_sender"))
        if (
            payload.get("consent") is not True
            or not isinstance(payload.get("name"), str)
            or not payload["name"].strip()
            or (
                not (
                    isinstance(payload.get("phone"), str)
                    and payload["phone"].strip()
                )
                and not normalized_sender
            )
            or (
                "whatsapp_sender" in payload
                and (not self._is_mcp_request() or not normalized_sender)
            )
            or set(payload) - allowed
            or any(not isinstance(payload[field], str) for field in text_fields if field in payload)
            or ("visit_requested" in payload and not isinstance(payload["visit_requested"], bool))
            or ("website" in payload and not isinstance(payload["website"], str))
            or ("channel" in payload and not isinstance(payload["channel"], str))
        ):
            return self._error(400, "invalid_parameter", "Name, a verified contact number and explicit consent are required.")
        try:
            budget = self._parse_non_negative_number(payload.get("budget"), "budget")
        except ValueError:
            return self._error(400, "invalid_parameter", "budget must be a valid non-negative number.")
        if payload.get("website"):
            self.env["commercial.property.integration.alert"].raise_alert(request.env, "api", "api-abuse-honeypot", "Public enquiry abuse detected", "warning", "Honeypot field was populated.")
            return self._json_response({"message": "Your enquiry was received for manager review."}, status=202)
        if any(len(payload.get(field, "")) > maximum for field, maximum in {"name": 128, "phone": 64, "whatsapp_sender": 64, "email": 254, "company_name": 256, "business_activity": 256, "message": 2000, "channel": 128}.items()):
            return self._error(400, "invalid_parameter", "One or more enquiry fields are too long.")
        if normalized_sender:
            payload["whatsapp_sender"] = normalized_sender
            payload["phone"] = normalized_sender
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
        if budget is not None:
            values["budget"] = budget
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
        if payload.get("channel"):
            channel = request.env["commercial.property.distribution.channel"].sudo().search(
                [("name", "=", payload["channel"].strip()), ("active", "=", True)], limit=1
            )
            if channel:
                values["source_channel_id"] = channel.id
        request.env["commercial.property.lead"].sudo().create(values)
        return self._json_response({"message": "Your enquiry was received for manager review."}, status=201)
