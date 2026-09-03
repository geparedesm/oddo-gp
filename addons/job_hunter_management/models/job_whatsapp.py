import os
import re
import secrets

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, ValidationError


PHONE_PATTERN = re.compile(r"^\+?[0-9][0-9\s().-]{5,30}[0-9]$")
SAFE_ERROR_PATTERN = re.compile(r"(?:bearer|token|secret|password|authorization|api[_ -]?key)", re.I)
ALLOWED_COMMANDS = {"APPROVE", "IGNORE", "DETAILS", "CV"}


def normalize_whatsapp_number(value):
    value = (value or "").strip()
    if not value or not PHONE_PATTERN.fullmatch(value):
        return False
    digits = re.sub(r"\D", "", value)
    if not 7 <= len(digits) <= 15:
        return False
    return "+" + digits


class JobWhatsAppNotification(models.Model):
    _name = "job.whatsapp.notification"
    _description = "Job WhatsApp Notification Outbox"
    _order = "priority_snapshot desc, create_date, id"

    application_id = fields.Many2one("job.application", required=True, ondelete="cascade", index=True)
    document_id = fields.Many2one("job.application.document", ondelete="set null", readonly=True)
    short_ref = fields.Char(required=True, readonly=True, index=True)
    job_ref = fields.Char(required=True, readonly=True, index=True)
    recipient = fields.Char(required=True, readonly=True)
    kind = fields.Selection(
        [("opportunity", "Opportunity"), ("details", "Details"), ("cv", "CV"),
         ("application_result", "Application Result")],
        required=True, default="opportunity", readonly=True, index=True,
    )
    message_body = fields.Text(required=True, readonly=True)
    priority_snapshot = fields.Float(required=True, readonly=True, index=True)
    delivery_state = fields.Selection(
        [("pending", "Pending"), ("delivered", "Delivered"), ("failed", "Failed")],
        required=True, default="pending", readonly=True, index=True,
    )
    delivered_at = fields.Datetime(readonly=True)
    provider_message_id = fields.Char(readonly=True)
    delivery_error = fields.Char(readonly=True)

    _sql_constraints = [
        ("short_ref_unique", "unique(short_ref)", "WhatsApp notification references must be unique."),
    ]

    def mark_delivered(self, provider_message_id):
        if not self.env.is_superuser():
            raise AccessError(_("Only the authenticated integration adapter can update delivery state."))
        if not isinstance(provider_message_id, str) or not provider_message_id.strip() or len(provider_message_id) > 128:
            raise ValidationError(_("A valid provider message identifier is required."))
        return self.with_context(controlled_whatsapp_delivery=True).write({
            "delivery_state": "delivered", "delivered_at": fields.Datetime.now(),
            "provider_message_id": provider_message_id.strip(), "delivery_error": False,
        })

    def mark_failed(self, error):
        if not self.env.is_superuser():
            raise AccessError(_("Only the authenticated integration adapter can update delivery state."))
        error = (error or "").strip()
        if not error or len(error) > 256 or SAFE_ERROR_PATTERN.search(error):
            raise ValidationError(_("Delivery errors must be concise and contain no credentials or secrets."))
        return self.with_context(controlled_whatsapp_delivery=True).write({
            "delivery_state": "failed", "delivery_error": error,
        })

    def write(self, values):
        protected = {
            "application_id", "document_id", "short_ref", "job_ref", "recipient", "kind",
            "message_body", "priority_snapshot", "delivery_state", "delivered_at", "provider_message_id", "delivery_error",
        }
        if protected.intersection(values) and not self.env.context.get("controlled_whatsapp_delivery"):
            raise ValidationError(_("WhatsApp outbox records are immutable outside the delivery adapter."))
        return super().write(values)


class JobApplicationApproval(models.Model):
    _name = "job.application.approval"
    _description = "Explicit Job Application Approval"
    _order = "approved_at desc, id desc"

    application_id = fields.Many2one("job.application", required=True, ondelete="cascade", index=True)
    notification_id = fields.Many2one("job.whatsapp.notification", required=True, ondelete="restrict")
    command_id = fields.Many2one("job.whatsapp.command", ondelete="restrict")
    approved_at = fields.Datetime(required=True, default=fields.Datetime.now, readonly=True)
    approved_by_number = fields.Char(required=True, readonly=True)
    is_current = fields.Boolean(required=True, default=True, readonly=True, index=True)

    _sql_constraints = [
        ("application_approval_unique", "unique(application_id)", "A job can have only one current explicit approval."),
    ]


class JobWhatsAppCommand(models.Model):
    _name = "job.whatsapp.command"
    _description = "Job WhatsApp Command Audit"
    _order = "received_at desc, id desc"

    event_id = fields.Char(required=True, readonly=True, index=True)
    sender = fields.Char(required=True, readonly=True)
    command = fields.Selection(
        [("approve", "Approve"), ("ignore", "Ignore"), ("details", "Details"),
         ("cv", "CV"), ("unknown", "Unknown")],
        required=True, readonly=True,
    )
    raw_command = fields.Char(required=True, readonly=True)
    requested_job_ref = fields.Char(readonly=True)
    requested_notification_ref = fields.Char(readonly=True)
    application_id = fields.Many2one("job.application", ondelete="set null", readonly=True, index=True)
    notification_id = fields.Many2one("job.whatsapp.notification", ondelete="set null", readonly=True)
    result = fields.Selection(
        [("accepted", "Accepted"), ("idempotent", "Idempotent"), ("rejected", "Rejected")],
        required=True, readonly=True, index=True,
    )
    result_code = fields.Char(required=True, readonly=True)
    reason = fields.Char(readonly=True)
    received_at = fields.Datetime(required=True, default=fields.Datetime.now, readonly=True)

    _sql_constraints = [
        ("sender_event_unique", "unique(sender, event_id)", "WhatsApp command events cannot be replayed."),
    ]

    @api.model
    def _audit(self, payload, *, result, code, notification=None, command=None):
        sender = normalize_whatsapp_number(payload.get("sender")) or str(payload.get("sender") or "invalid")[:32]
        raw_command = str(payload.get("command") or "")[:32]
        command = command or (raw_command.lower() if raw_command in ALLOWED_COMMANDS else "unknown")
        event_id = payload.get("event_id")
        if not isinstance(event_id, str) or not event_id.strip():
            event_id = "invalid-%s" % secrets.token_hex(8)
        values = {
            "event_id": event_id.strip()[:128],
            "sender": sender,
            "command": command,
            "raw_command": raw_command or "missing",
            "requested_job_ref": str(payload.get("job_ref") or "")[:32],
            "requested_notification_ref": str(payload.get("notification_ref") or "")[:32],
            "application_id": notification.application_id.id if notification else False,
            "notification_id": notification.id if notification else False,
            "result": result, "result_code": code,
            "reason": str(payload.get("reason") or "")[:256] or False,
        }
        return self.sudo().create(values)

    @api.model
    def process_payload(self, payload):
        if not self.env.is_superuser():
            raise AccessError(_("Only the authenticated integration adapter can process commands."))
        if not isinstance(payload, dict):
            payload = {}
        allowed = {"event_id", "sender", "command", "job_ref", "notification_ref", "reason"}
        required = {"event_id", "sender", "command", "job_ref", "notification_ref"}
        candidate_sender = normalize_whatsapp_number(payload.get("sender")) if isinstance(payload.get("sender"), str) else False
        candidate_event = payload.get("event_id") if isinstance(payload.get("event_id"), str) else False
        if candidate_sender and candidate_event:
            existing = self.sudo().search([
                ("sender", "=", candidate_sender), ("event_id", "=", candidate_event.strip()[:128]),
            ], limit=1)
            if existing:
                return {"accepted": existing.result != "rejected", "replay": True, "code": existing.result_code}
        if set(payload) - allowed or any(not isinstance(payload.get(key), str) or not payload[key].strip() for key in required):
            self._audit(payload, result="rejected", code="invalid_payload")
            return {"accepted": False, "code": "invalid_payload"}
        sender = normalize_whatsapp_number(payload["sender"])
        parameters = self.env["ir.config_parameter"].sudo()
        authorized = normalize_whatsapp_number(parameters.get_param("job_hunter_management.whatsapp_authorized_number"))
        if not sender or not authorized or sender != authorized:
            self._audit(payload, result="rejected", code="unauthorized_sender")
            return {"accepted": False, "code": "unauthorized_sender"}
        raw_command = payload["command"].strip().upper()
        if raw_command not in ALLOWED_COMMANDS:
            self._audit(payload, result="rejected", code="unknown_command")
            return {"accepted": False, "code": "unknown_command"}
        notification = self.env["job.whatsapp.notification"].sudo().search([
            ("short_ref", "=", payload["notification_ref"].strip().upper()),
            ("kind", "=", "opportunity"),
        ], limit=1)
        if not notification:
            self._audit(payload, result="rejected", code="unknown_notification", command=raw_command.lower())
            return {"accepted": False, "code": "unknown_notification"}
        if notification.recipient != sender or notification.job_ref != payload["job_ref"].strip().upper():
            self._audit(payload, result="rejected", code="job_context_mismatch", notification=notification, command=raw_command.lower())
            return {"accepted": False, "code": "job_context_mismatch"}
        job = notification.application_id.exists()
        if not job:
            self._audit(payload, result="rejected", code="job_not_found", notification=notification, command=raw_command.lower())
            return {"accepted": False, "code": "job_not_found"}

        if raw_command == "APPROVE":
            approval = self.env["job.application.approval"].sudo().search([("application_id", "=", job.id)], limit=1)
            if approval:
                self._audit(payload, result="idempotent", code="already_approved", notification=notification, command="approve")
                return {"accepted": True, "idempotent": True, "code": "already_approved"}
            audit = self._audit(payload, result="accepted", code="approved", notification=notification, command="approve")
            approval = self.env["job.application.approval"].sudo().create({
                "application_id": job.id, "notification_id": notification.id,
                "command_id": audit.id, "approved_by_number": sender,
            })
            job.with_context(whatsapp_explicit_decision=True).write({"state": "ready_to_apply"})
            return {"accepted": True, "approval_id": approval.id, "code": "approved"}
        if raw_command == "IGNORE":
            reason = (payload.get("reason") or "").strip()
            job.with_context(whatsapp_explicit_decision=True).write({
                "state": "ignored", "whatsapp_ignored_at": fields.Datetime.now(),
                "whatsapp_ignored_reason": reason or False,
            })
            self._audit(payload, result="accepted", code="ignored", notification=notification, command="ignore")
            return {"accepted": True, "code": "ignored"}
        body, kind, document = job._whatsapp_response(raw_command)
        reply = job._queue_whatsapp_outbox(kind, body, document=document)
        self._audit(payload, result="accepted", code=kind, notification=notification, command=raw_command.lower())
        return {"accepted": True, "code": kind, "notification_id": reply.id}


class JobApplicationWhatsApp(models.Model):
    _inherit = "job.application"

    whatsapp_notification_ids = fields.One2many("job.whatsapp.notification", "application_id", readonly=True)
    whatsapp_approval_ids = fields.One2many("job.application.approval", "application_id", readonly=True)
    whatsapp_ignored_at = fields.Datetime(readonly=True, copy=False)
    whatsapp_ignored_reason = fields.Char(readonly=True, copy=False)

    @staticmethod
    def _job_ref(application):
        return "J%08d" % application.id

    @api.model
    def _next_notification_ref(self):
        model = self.env["job.whatsapp.notification"].sudo()
        for _attempt in range(20):
            reference = secrets.token_hex(4).upper()
            if not model.search_count([("short_ref", "=", reference)]):
                return reference
        raise ValidationError(_("A unique WhatsApp notification reference could not be generated."))

    def _queue_whatsapp_outbox(self, kind, body, document=None):
        self.ensure_one()
        recipient = normalize_whatsapp_number(self.env["ir.config_parameter"].sudo().get_param(
            "job_hunter_management.whatsapp_authorized_number"
        ))
        if not recipient:
            return self.env["job.whatsapp.notification"]
        return self.env["job.whatsapp.notification"].sudo().create({
            "application_id": self.id, "document_id": document.id if document else False,
            "short_ref": self._next_notification_ref(), "job_ref": self._job_ref(self),
            "recipient": recipient, "kind": kind, "message_body": body,
            "priority_snapshot": self.priority_score,
        })

    def _whatsapp_summary(self):
        self.ensure_one()
        source_label = dict(self._fields["source"].selection).get(self.source, self.source)
        sponsorship_label = dict(self._fields["sponsorship_status"].selection).get(
            self.sponsorship_status, self.sponsorship_status
        )
        salary = _("Not provided")
        if self.salary_min or self.salary_max:
            amounts = "–".join("%g" % value for value in (self.salary_min, self.salary_max) if value)
            salary = "%s %s" % (self.salary_currency or "", amounts)
        reason = self.match_explanation or self.sponsorship_reason or _("Meets the configured priority criteria.")
        return _(
            "Job %(job_ref)s / notification %(notification_ref)s\n"
            "Position: %(position)s\nCompany: %(company)s\nLocation: %(location)s\n"
            "Salary: %(salary)s\nMatch: %(match).2f%%\nSponsorship: %(sponsorship)s\n"
            "Source: %(source)s\nLink: %(url)s\nWhy: %(reason)s\n"
            "Reply with COMMAND %(job_ref)s %(notification_ref)s."
        ) % {
            "job_ref": self._job_ref(self), "notification_ref": "{notification_ref}",
            "position": self.name, "company": self.company_name,
            "location": self.location or _("Not provided"), "salary": salary.strip(),
            "match": self.match_score, "sponsorship": sponsorship_label,
            "source": source_label, "url": self.job_url, "reason": reason,
        }

    def action_queue_whatsapp_notification(self):
        notifications = self.env["job.whatsapp.notification"]
        parameters = self.env["ir.config_parameter"].sudo()
        if parameters.get_param("job_hunter_management.whatsapp_enabled") != "True":
            return notifications
        if not normalize_whatsapp_number(parameters.get_param("job_hunter_management.whatsapp_authorized_number")):
            return notifications
        try:
            threshold = float(parameters.get_param("job_hunter_management.whatsapp_minimum_priority", "75"))
        except (TypeError, ValueError):
            return notifications
        for application in self:
            existing = application.whatsapp_notification_ids.filtered(lambda item: item.kind == "opportunity")
            if application.priority_score < threshold or application.state not in {"good_match", "analysing", "found"} or existing:
                continue
            reference = application._next_notification_ref()
            body = application._whatsapp_summary().format(notification_ref=reference)
            notifications |= self.env["job.whatsapp.notification"].sudo().create({
                "application_id": application.id, "short_ref": reference,
                "job_ref": application._job_ref(application),
                "recipient": normalize_whatsapp_number(parameters.get_param("job_hunter_management.whatsapp_authorized_number")),
                "kind": "opportunity", "message_body": body,
                "priority_snapshot": application.priority_score,
            })
        return notifications

    def _whatsapp_response(self, command):
        self.ensure_one()
        if command == "DETAILS":
            body = _(
                "Details %(job_ref)s\n%(position)s at %(company)s\nLocation: %(location)s\n"
                "Requirements: %(description)s\nMatch: %(match)s\nSponsorship: %(sponsorship)s\nLink: %(url)s"
            ) % {
                "job_ref": self._job_ref(self), "position": self.name, "company": self.company_name,
                "location": self.location or _("Not provided"),
                "description": self.job_description or _("Not provided"),
                "match": self.match_explanation or _("Not available"),
                "sponsorship": self.sponsorship_reason or _("Not available"), "url": self.job_url,
            }
            return body, "details", False
        document = self.document_ids.filtered(lambda item: item.state == "approved").sorted(
            key=lambda item: (item.version, item.id), reverse=True
        )[:1]
        if document:
            return _("Approved CV for %(job_ref)s: document version %(version)s (record %(record)s).") % {
                "job_ref": self._job_ref(self), "version": document.version, "record": document.id,
            }, "cv", document
        return _("Approved CV for %(job_ref)s is not available.") % {"job_ref": self._job_ref(self)}, "cv", False


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    job_adzuna_app_id = fields.Char(
        string="Adzuna App ID",
        config_parameter="job_hunter_management.adzuna_app_id",
        groups="base.group_system",
    )
    job_adzuna_app_key = fields.Char(
        string="Adzuna App Key",
        config_parameter="job_hunter_management.adzuna_app_key",
        groups="base.group_system",
    )
    job_adzuna_enabled = fields.Boolean(
        string="Enable Adzuna Australia",
        default=lambda self: self.env["job.hunter.search.source"].sudo().with_context(
            active_test=False
        ).search([("code", "=", "adzuna")], limit=1).active,
    )

    job_whatsapp_enabled = fields.Boolean(
        string="Enable Job WhatsApp Notifications",
        config_parameter="job_hunter_management.whatsapp_enabled",
    )
    job_whatsapp_authorized_number = fields.Char(
        string="Authorized WhatsApp Number",
        config_parameter="job_hunter_management.whatsapp_authorized_number",
    )
    job_whatsapp_minimum_priority = fields.Float(
        string="Minimum Notification Priority",
        default=75,
        config_parameter="job_hunter_management.whatsapp_minimum_priority",
    )

    @api.constrains("job_whatsapp_authorized_number", "job_whatsapp_minimum_priority")
    def _check_job_whatsapp_settings(self):
        for settings in self:
            if settings.job_whatsapp_authorized_number and not normalize_whatsapp_number(settings.job_whatsapp_authorized_number):
                raise ValidationError(_("Enter an authorized WhatsApp number in international format."))
            if not 0 <= settings.job_whatsapp_minimum_priority <= 100:
                raise ValidationError(_("The WhatsApp priority threshold must be between 0 and 100."))

    def set_values(self):
        for settings in self:
            app_id = settings.job_adzuna_app_id or os.environ.get("ADZUNA_APP_ID")
            app_key = settings.job_adzuna_app_key or os.environ.get("ADZUNA_APP_KEY")
            if settings.job_adzuna_enabled and not (app_id and app_key):
                raise ValidationError(_("Both Adzuna credentials are required before enabling the source."))
            adzuna = self.env["job.hunter.search.source"].sudo().with_context(
                active_test=False
            ).search([("code", "=", "adzuna")], limit=1)
            if adzuna:
                adzuna.write({"active": settings.job_adzuna_enabled})
            if settings.job_whatsapp_enabled and not normalize_whatsapp_number(settings.job_whatsapp_authorized_number):
                raise ValidationError(_("An authorized WhatsApp number is required before notifications can be enabled."))
            if settings.job_whatsapp_authorized_number:
                settings.job_whatsapp_authorized_number = normalize_whatsapp_number(settings.job_whatsapp_authorized_number)
        return super().set_values()
