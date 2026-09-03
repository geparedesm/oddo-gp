from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase


class TestJobWhatsAppApproval(TransactionCase):
    def setUp(self):
        super().setUp()
        self.parameters = self.env["ir.config_parameter"].sudo()
        self.previous = {
            key: self.parameters.get_param(key)
            for key in (
                "job_hunter_management.whatsapp_enabled",
                "job_hunter_management.whatsapp_authorized_number",
                "job_hunter_management.whatsapp_minimum_priority",
            )
        }
        self.parameters.set_param("job_hunter_management.whatsapp_enabled", "True")
        self.parameters.set_param(
            "job_hunter_management.whatsapp_authorized_number", "+61 (400) 123-456"
        )
        self.parameters.set_param("job_hunter_management.whatsapp_minimum_priority", "75")
        self.jobs = self.env["job.application"]
        self.created_jobs = self.jobs.browse()
        self.created_profiles = self.env["job.hunter.profile"].browse()
        self.created_rules = self.env["job.document.generation.rule"].browse()

    def tearDown(self):
        try:
            job_ids = self.created_jobs.ids
            notification_ids = self.env["job.whatsapp.notification"].sudo().search(
                [("application_id", "in", job_ids)]
            ).ids
            command_ids = self.env["job.whatsapp.command"].sudo().search(
                ["|", ("application_id", "in", job_ids), ("notification_id", "in", notification_ids)]
            ).ids
            approval_ids = self.env["job.application.approval"].sudo().search(
                [("application_id", "in", job_ids)]
            ).ids
            document_ids = self.env["job.application.document"].sudo().search(
                [("application_id", "in", job_ids)]
            ).ids
            self.created_jobs.sudo().unlink()
            self.env["job.whatsapp.command"].sudo().browse(command_ids).exists().unlink()
            self.env["job.whatsapp.notification"].sudo().browse(notification_ids).exists().unlink()
            self.env["job.application.approval"].sudo().browse(approval_ids).exists().unlink()
            self.created_rules.sudo().exists().unlink()
            self.created_profiles.sudo().exists().unlink()
            for key, value in self.previous.items():
                if value is False:
                    self.parameters.set_param(key, "")
                else:
                    self.parameters.set_param(key, value)
            self.assertFalse(self.env["job.application"].sudo().search_count([("id", "in", job_ids)]))
            self.assertFalse(self.env["job.whatsapp.notification"].sudo().search_count([("id", "in", notification_ids)]))
            self.assertFalse(self.env["job.whatsapp.command"].sudo().search_count([("id", "in", command_ids)]))
            self.assertFalse(self.env["job.application.approval"].sudo().search_count([("id", "in", approval_ids)]))
            self.assertFalse(self.env["job.application.document"].sudo().search_count([("id", "in", document_ids)]))
        finally:
            super().tearDown()

    def _job(self, suffix, priority=90):
        job = self.jobs.create({
            "name": "Senior Odoo Engineer",
            "company_name": "Phase 7 Employer %s" % suffix,
            "location": "Sydney",
            "job_url": "https://phase7.test/jobs/%s" % suffix,
            "source": "seek",
            "salary_min": 120000,
            "salary_max": 145000,
            "salary_currency": "AUD",
            "match_score": priority,
            "sponsorship_status": "yes",
            "sponsorship_priority_adjustment": 0,
            "sponsorship_reason": "Explicit visa sponsorship evidence was found.",
            "match_explanation": "Strong Odoo and Python match.",
            "job_description": "Build Odoo integrations with Python and PostgreSQL.",
            "state": "good_match",
        })
        self.created_jobs |= job
        return job

    def _notify(self, job):
        notification = job.action_queue_whatsapp_notification()
        self.assertEqual(len(notification), 1)
        return notification

    def _command(self, notification, command, event_id, **extra):
        payload = {
            "event_id": event_id,
            "sender": "+61400123456",
            "command": command,
            "job_ref": notification.job_ref,
            "notification_ref": notification.short_ref,
        }
        payload.update(extra)
        return self.env["job.whatsapp.command"].process_payload(payload)

    def test_only_prioritized_jobs_are_queued_with_complete_safe_summary(self):
        prioritized = self._job("priority", 90)
        low = self._job("low", 74)
        notification = self._notify(prioritized)

        self.assertFalse(low.action_queue_whatsapp_notification())
        self.assertEqual(notification.recipient, "+61400123456")
        self.assertEqual(notification.delivery_state, "pending")
        self.assertEqual(notification.priority_snapshot, prioritized.priority_score)
        self.assertRegex(notification.short_ref, r"^[A-Z0-9]{8}$")
        for value in (
            prioritized.name, prioritized.company_name, prioritized.location, "AUD 120000–145000",
            "90", "Yes", "SEEK", prioritized.job_url, prioritized.match_explanation,
            notification.short_ref,
        ):
            self.assertIn(value, notification.message_body)
        self.assertEqual(len(prioritized.whatsapp_notification_ids), 1)

    def test_disabled_or_missing_authorized_number_never_queues(self):
        job = self._job("disabled")
        self.parameters.set_param("job_hunter_management.whatsapp_enabled", "False")
        self.assertFalse(job.action_queue_whatsapp_notification())
        self.parameters.set_param("job_hunter_management.whatsapp_enabled", "True")
        self.parameters.set_param("job_hunter_management.whatsapp_authorized_number", "")
        self.assertFalse(job.action_queue_whatsapp_notification())

    def test_approve_is_explicit_current_and_idempotent_without_applying(self):
        job = self._job("approve")
        notification = self._notify(job)
        notification.mark_delivered("test-provider-message-%s" % notification.id)
        first = self._command(notification, "APPROVE", "evt-approve-1")
        replay = self._command(notification, "APPROVE", "evt-approve-1")
        repeated = self._command(notification, "APPROVE", "evt-approve-2")

        self.assertTrue(first["accepted"])
        self.assertTrue(replay["replay"])
        self.assertTrue(repeated["idempotent"])
        self.assertEqual(job.state, "ready_to_apply")
        self.assertFalse(job.date_applied)
        approvals = self.env["job.application.approval"].search([("application_id", "=", job.id)])
        self.assertEqual(len(approvals), 1)
        self.assertTrue(approvals.is_current)
        self.assertEqual(self.env["job.whatsapp.command"].search_count([
            ("application_id", "=", job.id), ("command", "=", "approve"), ("result", "=", "accepted")
        ]), 1)

    def test_approve_rejects_undelivered_or_ineligible_stale_notifications(self):
        job = self._job("stale")
        notification = job.action_queue_whatsapp_notification()
        pending_result = self._command(notification, "APPROVE", "evt-stale-pending")
        self.assertFalse(pending_result["accepted"])
        self.assertEqual(pending_result["code"], "notification_not_delivered")
        notification.mark_delivered("provider-stale")
        job.write({"state": "ignored"})
        ineligible_result = self._command(notification, "APPROVE", "evt-stale-ineligible")
        self.assertFalse(ineligible_result["accepted"])
        self.assertEqual(ineligible_result["code"], "job_not_eligible")
        self.assertFalse(self.env["job.application.approval"].search([("application_id", "=", job.id)]))

    def test_ignore_records_optional_reason(self):
        job = self._job("ignore")
        notification = self._notify(job)
        result = self._command(notification, "IGNORE", "evt-ignore", reason="Role is too far away")
        self.assertTrue(result["accepted"])
        self.assertEqual(job.state, "ignored")
        self.assertEqual(job.whatsapp_ignored_reason, "Role is too far away")
        self.assertTrue(job.whatsapp_ignored_at)

    def test_details_queues_extended_reply(self):
        job = self._job("details")
        notification = self._notify(job)
        result = self._command(notification, "DETAILS", "evt-details")
        reply = self.env["job.whatsapp.notification"].browse(result["notification_id"])
        self.assertEqual(reply.kind, "details")
        self.assertIn(job.job_description, reply.message_body)
        self.assertIn(job.match_explanation, reply.message_body)
        self.assertIn(job.sponsorship_reason, reply.message_body)

    def test_cv_identifies_only_approved_document_or_reports_unavailable(self):
        job = self._job("cv")
        notification = self._notify(job)
        unavailable = self._command(notification, "CV", "evt-cv-none")
        unavailable_reply = self.env["job.whatsapp.notification"].browse(unavailable["notification_id"])
        self.assertIn("not available", unavailable_reply.message_body.lower())

        profile = self.env["job.hunter.profile"].create({"name": "Phase 7 profile", "skills": "Odoo"})
        rule = self.env["job.document.generation.rule"].create({"name": "Phase 7 rule", "minimum_priority_score": 75})
        self.created_profiles |= profile
        self.created_rules |= rule
        job.action_generate_documents(profile=profile, rule=rule)
        document = job.document_ids
        document.action_review()
        document.action_approve()
        available = self._command(notification, "CV", "evt-cv-approved")
        reply = self.env["job.whatsapp.notification"].browse(available["notification_id"])
        self.assertIn("version %s" % document.version, reply.message_body.lower())
        self.assertEqual(reply.document_id, document)
        self.assertNotIn(document.tailored_cv, reply.message_body)

    def test_unauthorized_unknown_ambiguous_and_missing_job_are_rejected_and_audited(self):
        job = self._job("reject")
        notification = self._notify(job)
        cases = [
            ({"event_id": "evt-unauthorized", "sender": "+61400999999", "command": "APPROVE", "job_ref": notification.job_ref, "notification_ref": notification.short_ref}, "unauthorized_sender"),
            ({"event_id": "evt-command", "sender": "+61400123456", "command": "DELETE", "job_ref": notification.job_ref, "notification_ref": notification.short_ref}, "unknown_command"),
            ({"event_id": "evt-ambiguous", "sender": "+61400123456", "command": "APPROVE IGNORE", "job_ref": notification.job_ref, "notification_ref": notification.short_ref}, "unknown_command"),
            ({"event_id": "evt-ref", "sender": "+61400123456", "command": "APPROVE", "job_ref": notification.job_ref, "notification_ref": "ZZZZZZZZ"}, "unknown_notification"),
            ({"event_id": "evt-job", "sender": "+61400123456", "command": "APPROVE", "job_ref": "J99999999", "notification_ref": notification.short_ref}, "job_context_mismatch"),
            ({"event_id": "evt-extra", "sender": "+61400123456", "command": "APPROVE", "job_ref": notification.job_ref, "notification_ref": notification.short_ref, "secret": "no"}, "invalid_payload"),
        ]
        for payload, code in cases:
            result = self.env["job.whatsapp.command"].process_payload(payload)
            self.assertFalse(result["accepted"])
            self.assertEqual(result["code"], code)
        self.assertEqual(self.env["job.whatsapp.command"].search_count([
            ("event_id", "in", [payload["event_id"] for payload, _code in cases]),
            ("result", "=", "rejected"),
        ]), len(cases))
        self.assertEqual(job.state, "good_match")

    def test_delivery_adapter_tracks_success_and_non_sensitive_error(self):
        notification = self._notify(self._job("delivery"))
        notification.mark_delivered("provider-message-123")
        self.assertEqual(notification.delivery_state, "delivered")
        self.assertEqual(notification.provider_message_id, "provider-message-123")
        with self.assertRaises(ValidationError), self.env.cr.savepoint():
            notification.mark_failed("Bearer secret-token connection failed")
        notification.mark_failed("Provider timeout")
        self.assertEqual(notification.delivery_state, "failed")
        self.assertEqual(notification.delivery_error, "Provider timeout")
