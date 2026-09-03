import hmac
import json
import os

from odoo import http
from odoo.exceptions import ValidationError
from odoo.http import request


class JobWhatsAppAdapterController(http.Controller):
    """Transport-neutral internal contract for an authenticated n8n/WuzAPI adapter."""

    _TOKEN_ENVIRONMENT_VARIABLE = "HERMES_API_TOKEN"
    _TOKEN_PARAMETER = "job_hunter_management.hermes_api_token"

    def _authenticated(self):
        expected = request.env["ir.config_parameter"].sudo().get_param(
            self._TOKEN_PARAMETER
        ) or os.environ.get(self._TOKEN_ENVIRONMENT_VARIABLE)
        authorization = request.httprequest.headers.get("Authorization", "")
        return bool(
            expected
            and authorization.startswith("Bearer ")
            and hmac.compare_digest(authorization[7:], expected)
        )

    @staticmethod
    def _response(payload, status=200):
        return request.make_json_response(payload, status=status)

    def _read_json(self):
        try:
            value = json.loads(request.httprequest.data.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return None
        return value if isinstance(value, dict) else None

    @http.route("/api/job-hunter/whatsapp/outbox", type="http", auth="none", methods=["GET"], csrf=False)
    def outbox(self, **params):
        if not self._authenticated():
            return self._response({"error": {"code": "unauthorized"}}, 401)
        records = request.env["job.whatsapp.notification"].sudo().search(
            [("delivery_state", "=", "pending")], order="priority_snapshot desc, create_date, id", limit=50,
        )
        return self._response({"notifications": [{
            "id": item.id, "recipient": item.recipient, "message": item.message_body,
            "reference": item.short_ref, "job_ref": item.job_ref, "kind": item.kind,
            "priority": item.priority_snapshot,
        } for item in records]})

    @http.route("/api/job-hunter/whatsapp/commands", type="http", auth="none", methods=["POST"], csrf=False)
    def command(self, **params):
        if not self._authenticated():
            return self._response({"error": {"code": "unauthorized"}}, 401)
        payload = self._read_json()
        if payload is None:
            return self._response({"error": {"code": "invalid_payload"}}, 400)
        result = request.env["job.whatsapp.command"].sudo().process_payload(payload)
        return self._response(result, 200 if result.get("accepted") or result.get("replay") else 400)

    @http.route("/api/job-hunter/whatsapp/outbox/<int:notification_id>", type="http", auth="none", methods=["PATCH"], csrf=False)
    def delivery(self, notification_id, **params):
        if not self._authenticated():
            return self._response({"error": {"code": "unauthorized"}}, 401)
        payload = self._read_json()
        if payload is None or set(payload) - {"state", "provider_message_id", "error"}:
            return self._response({"error": {"code": "invalid_payload"}}, 400)
        notification = request.env["job.whatsapp.notification"].sudo().browse(notification_id).exists()
        if not notification:
            return self._response({"error": {"code": "not_found"}}, 404)
        try:
            if payload.get("state") == "delivered" and set(payload) == {"state", "provider_message_id"}:
                notification.mark_delivered(payload["provider_message_id"])
            elif payload.get("state") == "failed" and set(payload) == {"state", "error"}:
                notification.mark_failed(payload["error"])
            else:
                return self._response({"error": {"code": "invalid_payload"}}, 400)
        except ValidationError:
            return self._response({"error": {"code": "invalid_delivery_result"}}, 400)
        return self._response({"id": notification.id, "state": notification.delivery_state})
