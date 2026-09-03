import re
from urllib.parse import urlsplit

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


SENSITIVE_QUESTION_CATEGORIES = {
    "salary", "legal", "health", "diversity", "migration",
    "security_clearance", "subjective", "personal",
}
SAFE_ERROR_PATTERN = re.compile(
    r"(?:bearer|token|secret|password|authorization|api[_ -]?key|cookie)", re.I
)


class ApplicationAdapter:
    """Side-effect-free platform adapter contract for Phase 8."""

    key = None
    platform = "manual"

    def execute(self, application, document, questions, safe_answers):
        raise NotImplementedError


class ManualApplicationAdapter(ApplicationAdapter):
    key = "manual"

    def execute(self, application, document, questions, safe_answers):
        return {
            "state": "manual_action_required",
            "result": "manual_action_required",
            "retryable": False,
            "error": False,
        }


class TestConfirmedAdapter(ApplicationAdapter):
    key = "test_confirmed"
    platform = "test"

    def execute(self, application, document, questions, safe_answers):
        return {
            "state": "confirmed", "result": "confirmed", "retryable": False,
            "confirmation_reference": "TEST-%s" % application.id,
        }


class TestFailureAdapter(ApplicationAdapter):
    platform = "test"

    def __init__(self, retryable):
        self.retryable = retryable
        self.key = "test_retryable_failure" if retryable else "test_terminal_failure"

    def execute(self, application, document, questions, safe_answers):
        return {
            "state": "failed", "result": "technical_failure",
            "retryable": self.retryable,
            "error": "Temporary platform timeout" if self.retryable else "Unsupported application form",
        }


ADAPTERS = {
    adapter.key: adapter
    for adapter in (
        ManualApplicationAdapter(), TestConfirmedAdapter(),
        TestFailureAdapter(True), TestFailureAdapter(False),
    )
}


class JobApplicationAttempt(models.Model):
    _name = "job.application.attempt"
    _description = "Job Application Attempt Audit"
    _order = "started_at desc, id desc"

    application_id = fields.Many2one("job.application", required=True, ondelete="cascade", index=True)
    approval_id = fields.Many2one("job.application.approval", required=True, ondelete="restrict", readonly=True)
    document_id = fields.Many2one("job.application.document", required=True, ondelete="restrict", readonly=True)
    retry_of_id = fields.Many2one("job.application.attempt", ondelete="restrict", readonly=True)
    initiated_by = fields.Many2one("res.users", required=True, readonly=True)
    adapter_key = fields.Char(required=True, readonly=True)
    platform = fields.Char(required=True, readonly=True)
    application_url = fields.Char(required=True, readonly=True)
    started_at = fields.Datetime(required=True, readonly=True)
    completed_at = fields.Datetime(readonly=True)
    submitted_at = fields.Datetime(readonly=True)
    state = fields.Selection([
        ("applying", "Applying"), ("manual_action_required", "Manual Action Required"),
        ("confirmed", "Applied"), ("failed", "Application Failed"),
    ], required=True, readonly=True, index=True)
    result = fields.Selection([
        ("started", "Started"), ("manual_action_required", "Manual Action Required"),
        ("confirmed", "Confirmed"), ("technical_failure", "Technical Failure"),
    ], required=True, readonly=True)
    confirmation_reference = fields.Char(readonly=True)
    safe_answers = fields.Json(readonly=True, default=dict)
    escalated_questions = fields.Json(readonly=True, default=list)
    error_message = fields.Char(readonly=True)
    retryable = fields.Boolean(readonly=True)

    @api.model_create_multi
    def create(self, values_list):
        if not self.env.context.get("controlled_application_attempt"):
            raise ValidationError(_("Application attempts can only be created by the controlled workflow."))
        return super().create(values_list)

    def write(self, values):
        if not self.env.context.get("controlled_application_attempt"):
            raise ValidationError(_("Application attempt audit records are immutable."))
        return super().write(values)

    def unlink(self):
        if not (self.env.context.get("controlled_application_cleanup") or self.env.is_superuser()):
            raise ValidationError(_("Application attempt audit records cannot be deleted."))
        return super().unlink()


class JobApplicationSubmission(models.Model):
    _inherit = "job.application"

    application_attempt_ids = fields.One2many(
        "job.application.attempt", "application_id", readonly=True,
    )
    application_attempt_count = fields.Integer(compute="_compute_application_attempt_count")
    cover_letter_required = fields.Boolean(
        string="Cover Letter Required", default=True,
        help="Disable only when the target application explicitly does not request a cover letter.",
    )

    @api.depends("application_attempt_ids")
    def _compute_application_attempt_count(self):
        for application in self:
            application.application_attempt_count = len(application.application_attempt_ids)

    def _submission_preconditions(self, retry_of=None):
        self.ensure_one()
        confirmed = self.application_attempt_ids.filtered(
            lambda item: item.state == "confirmed" or item.submitted_at
        )
        if confirmed:
            return False, False, confirmed.sorted(key=lambda item: item.id)[-1]
        expected_state = "application_failed" if retry_of else "ready_to_apply"
        if self.state != expected_state:
            raise UserError(_("The job must be in %(state)s before an application can start.") % {
                "state": dict(self._fields["state"].selection)[expected_state],
            })
        approval = self.whatsapp_approval_ids.filtered("is_current").sorted(
            key=lambda item: (item.approved_at, item.id), reverse=True,
        )[:1]
        if not approval:
            raise UserError(_("A current explicit approval is required for this job."))
        document = self.document_ids.filtered(lambda item: item.state == "approved").sorted(
            key=lambda item: (item.version, item.id), reverse=True,
        )[:1]
        if not document or not document.tailored_cv:
            raise UserError(_("An approved CV document is required."))
        if self.cover_letter_required and not document.cover_letter:
            raise UserError(_("An approved cover letter is required for this workflow."))
        parts = urlsplit((self.job_url or "").strip())
        if parts.scheme not in {"http", "https"} or not parts.netloc or parts.username or parts.password:
            raise UserError(_("A valid HTTP(S) application URL without embedded credentials is required."))
        return approval, document, False

    @staticmethod
    def _classify_answers(questions):
        safe_answers, escalated = {}, []
        for question in questions or []:
            if not isinstance(question, dict):
                escalated.append({"label": "Unknown question", "category": "unknown"})
                continue
            category = str(question.get("category") or "unknown").strip().lower()
            key = str(question.get("key") or "").strip()
            answer = question.get("approved_answer")
            explicitly_safe = question.get("authorized_safe") is True
            if category in SENSITIVE_QUESTION_CATEGORIES or not key or answer in (None, "") or not explicitly_safe:
                escalated.append({
                    "key": key or None,
                    "label": str(question.get("label") or "Unknown question")[:256],
                    "category": category,
                })
            else:
                safe_answers[key] = str(answer)[:512]
        return safe_answers, escalated

    def action_start_application(self, adapter_key="manual", questions=None, retry_of=None):
        self.ensure_one()
        self.env.cr.execute("SELECT id FROM job_application WHERE id = %s FOR UPDATE", [self.id])
        self.invalidate_cache()
        approval, document, prior_confirmation = self._submission_preconditions(retry_of=retry_of)
        if prior_confirmation:
            return prior_confirmation
        adapter = ADAPTERS.get(adapter_key)
        if not adapter:
            raise UserError(_("The requested application adapter is not available."))
        if adapter_key == "test_confirmed" and self.env["ir.config_parameter"].sudo().get_param(
            "job_hunter_management.allow_test_submission"
        ) != "True":
            raise UserError(_("The simulated submission adapter requires explicit test configuration."))
        safe_answers, escalated = self._classify_answers(questions)
        attempt = self.env["job.application.attempt"].sudo().with_context(
            controlled_application_attempt=True
        ).create({
            "application_id": self.id, "approval_id": approval.id,
            "document_id": document.id, "retry_of_id": retry_of.id if retry_of else False,
            "adapter_key": adapter.key, "platform": adapter.platform,
            "application_url": self.job_url, "started_at": fields.Datetime.now(),
            "initiated_by": self.env.user.id,
            "state": "applying", "result": "started", "safe_answers": safe_answers,
            "escalated_questions": escalated,
        })
        self.write({"state": "applying"})
        if escalated:
            outcome = {
                "state": "manual_action_required", "result": "manual_action_required",
                "retryable": False, "error": False,
            }
        else:
            try:
                outcome = adapter.execute(self, document, questions or [], safe_answers)
            except Exception:
                outcome = {
                    "state": "failed", "result": "technical_failure", "retryable": False,
                    "error": _("The adapter was interrupted; submission status is unknown and automatic retry is blocked."),
                }
        error = outcome.get("error") or False
        if error and (len(error) > 256 or SAFE_ERROR_PATTERN.search(error)):
            error = _("Application adapter failed; sensitive details were suppressed.")
        now = fields.Datetime.now()
        attempt.with_context(controlled_application_attempt=True).write({
            "state": outcome["state"], "result": outcome["result"],
            "completed_at": now, "submitted_at": now if outcome["state"] == "confirmed" else False,
            "confirmation_reference": outcome.get("confirmation_reference") or False,
            "retryable": bool(outcome.get("retryable")), "error_message": error,
        })
        target_state = {
            "confirmed": "applied", "manual_action_required": "manual_action_required",
            "failed": "application_failed",
        }[outcome["state"]]
        values = {"state": target_state}
        if outcome["state"] == "confirmed":
            values["date_applied"] = fields.Date.context_today(self)
        self.write(values)
        if outcome["state"] == "confirmed":
            self._queue_whatsapp_outbox(
                "application_result",
                _("Application %(job)s was confirmed with reference %(reference)s.") % {
                    "job": self._job_ref(self),
                    "reference": outcome.get("confirmation_reference"),
                },
                document=document,
            )
        return self.env["job.application.attempt"].browse(attempt.id)

    def action_retry_application(self):
        self.ensure_one()
        latest = self.application_attempt_ids.sorted(key=lambda item: item.id, reverse=True)[:1]
        if not latest or latest.state != "failed" or not latest.retryable:
            raise UserError(_("Only an explicitly retryable technical failure can be retried."))
        return self.action_start_application(adapter_key=latest.adapter_key, retry_of=latest)

    def action_open_application_attempts(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window", "name": _("Application Attempts"),
            "res_model": "job.application.attempt", "view_mode": "tree,form",
            "domain": [("application_id", "=", self.id)],
            "context": {"default_application_id": self.id},
        }

    def get_api_data(self):
        data = super().get_api_data()
        self.ensure_one()
        latest = self.application_attempt_ids.sorted(key=lambda item: item.id, reverse=True)[:1]
        data.update({
            "application_attempt_count": self.application_attempt_count,
            "latest_application_attempt": {
                "id": latest.id,
                "platform": latest.platform,
                "state": latest.state,
                "result": latest.result,
                "started_at": fields.Datetime.to_string(latest.started_at),
                "completed_at": fields.Datetime.to_string(latest.completed_at) if latest.completed_at else None,
                "submitted_at": fields.Datetime.to_string(latest.submitted_at) if latest.submitted_at else None,
                "confirmation_reference": latest.confirmation_reference or None,
                "retryable": latest.retryable,
            } if latest else None,
        })
        return data
