import hmac
import math
import os

from odoo import http
from odoo.http import request


class HermesPropertyController(http.Controller):
    _TOKEN_ENVIRONMENT_VARIABLE = "HERMES_API_TOKEN"
    _TOKEN_PARAMETER = "commercial_property_management.hermes_api_token"
    _MAX_LIMIT = 50

    def _json_response(self, payload, status=200):
        return request.make_json_response(payload, status=status)

    def _error(self, status, code, message):
        return self._json_response({"error": {"code": code, "message": message}}, status=status)

    def _is_authenticated(self):
        expected_token = request.env["ir.config_parameter"].sudo().get_param(self._TOKEN_PARAMETER)
        expected_token = expected_token or os.environ.get(self._TOKEN_ENVIRONMENT_VARIABLE)
        authorization = request.httprequest.headers.get("Authorization", "")
        token_prefix = "Bearer "
        if not expected_token or not authorization.startswith(token_prefix):
            return False
        return hmac.compare_digest(authorization[len(token_prefix) :], expected_token)

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

        properties = request.env["commercial.property"].sudo().search_public_properties(
            min_area=min_area,
            max_rent=max_rent,
            limit=limit,
        )
        return self._json_response({"properties": [property_record.get_public_data() for property_record in properties]})

    @http.route("/api/hermes/properties/<string:property_code>", type="http", auth="none", methods=["GET"], csrf=False)
    def get_property(self, property_code, **params):
        if not self._is_authenticated():
            return self._error(401, "unauthorized", "A valid bearer token is required.")
        property_record = request.env["commercial.property"].sudo().search_public_properties(
            code=property_code,
            limit=1,
        )
        if not property_record:
            return self._error(404, "not_found", "Public property not found.")
        return self._json_response({"property": property_record.get_public_data()})
