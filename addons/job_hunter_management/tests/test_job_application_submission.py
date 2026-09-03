import base64

from odoo.exceptions import UserError, ValidationError
from odoo.tests.common import TransactionCase


class TestJobApplicationSubmission(TransactionCase):
    def setUp(self):
        super().setUp()
        self.params = self.env["ir.config_parameter"].sudo()
        self.old_simulation = self.params.get_param(
            "job_hunter_management.allow_test_submission"
        )
        self.jobs = self.env["job.application"].browse()
        self.profile = self.env["job.hunter.profile"].create({
            "name": "Phase 8 profile", "skills": "Odoo, Python",
            "work_experience": "Approved Odoo experience.",
            "primary_cv": base64.b64encode(b"approved master cv"),
            "primary_cv_filename": "approved.pdf",
        })
        self.rule = self.env["job.document.generation.rule"].create({
            "name": "Phase 8 document rule", "minimum_priority_score": 0,
        })

    def tearDown(self):
        try:
            ids = self.jobs.ids
            self.jobs.sudo().unlink()
            self.env["job.application.attempt"].sudo().search([
                ("application_id", "in", ids)
            ]).unlink()
            self.env["job.application.approval"].sudo().search([
                ("application_id", "in", ids)
            ]).unlink()
            self.env["job.whatsapp.notification"].sudo().search([
                ("application_id", "in", ids)
            ]).unlink()
            self.rule.sudo().exists().unlink()
            self.profile.sudo().exists().unlink()
            self.params.set_param(
                "job_hunter_management.allow_test_submission",
                self.old_simulation if self.old_simulation is not False else "",
            )
            self.assertFalse(self.env["job.application.attempt"].sudo().search_count([
                ("application_id", "in", ids)
            ]))
        finally:
            super().tearDown()

    def _job(self, suffix, *, approve=True, document=True, url=None):
        job = self.env["job.application"].create({
            "name": "Phase 8 Engineer", "company_name": "Phase 8 %s" % suffix,
            "job_url": url or "https://phase8.test/jobs/%s" % suffix,
            "source": "other", "state": "ready_to_apply", "match_score": 90,
        })
        self.jobs |= job
        if document:
            job.action_generate_documents(profile=self.profile, rule=self.rule)
            job.document_ids.action_review()
            job.document_ids.action_approve()
        if approve:
            notification = self.env["job.whatsapp.notification"].sudo().create({
                "application_id": job.id, "short_ref": ("P8%06d" % job.id)[-8:],
                "job_ref": "J%08d" % job.id, "recipient": "+61400123456",
                "kind": "opportunity", "message_body": "Explicit approval request",
                "priority_snapshot": 90,
            })
            self.env["job.application.approval"].sudo().create({
                "application_id": job.id, "notification_id": notification.id,
                "approved_by_number": "+61400123456", "is_current": True,
            })
        return job

    def test_blocks_without_current_approval_or_approved_cv(self):
        for job in (self._job("no-approval", approve=False), self._job("no-cv", document=False)):
            with self.assertRaises(UserError), self.env.cr.savepoint():
                job.action_start_application(adapter_key="manual")
            self.assertFalse(job.application_attempt_ids)

    def test_manual_adapter_stops_at_last_safe_step_and_audits(self):
        job = self._job("manual")
        attempt = job.action_start_application(adapter_key="manual")
        self.assertEqual(job.state, "manual_action_required")
        self.assertEqual(attempt.state, "manual_action_required")
        self.assertEqual(attempt.result, "manual_action_required")
        self.assertFalse(attempt.submitted_at)
        self.assertFalse(job.date_applied)
        self.assertEqual(attempt.document_id, job.document_ids)
        self.assertTrue(attempt.started_at)
        self.assertTrue(attempt.completed_at)

    def test_simulated_applied_requires_explicit_test_configuration(self):
        job = self._job("simulated")
        with self.assertRaises(UserError), self.env.cr.savepoint():
            job.action_start_application(adapter_key="test_confirmed")
        self.params.set_param("job_hunter_management.allow_test_submission", "True")
        attempt = job.action_start_application(adapter_key="test_confirmed")
        self.assertEqual(job.state, "applied")
        self.assertTrue(job.date_applied)
        self.assertEqual(attempt.result, "confirmed")
        self.assertTrue(attempt.submitted_at)
        self.assertTrue(attempt.confirmation_reference)

    def test_sensitive_or_unknown_question_never_invents_an_answer(self):
        job = self._job("sensitive")
        attempt = job.action_start_application(adapter_key="manual", questions=[
            {"key": "salary_expectation", "label": "Expected salary", "category": "salary"},
            {"key": "motivation", "label": "Why should we hire you?", "category": "subjective"},
        ])
        self.assertEqual(attempt.state, "manual_action_required")
        self.assertEqual(attempt.safe_answers or {}, {})
        self.assertEqual(len(attempt.escalated_questions), 2)

    def test_duplicate_replay_never_creates_second_submission(self):
        self.params.set_param("job_hunter_management.allow_test_submission", "True")
        job = self._job("duplicate")
        first = job.action_start_application(adapter_key="test_confirmed")
        replay = job.action_start_application(adapter_key="test_confirmed")
        self.assertEqual(replay, first)
        self.assertEqual(len(job.application_attempt_ids), 1)

    def test_only_explicit_retryable_technical_failure_can_retry(self):
        retryable = self._job("retryable")
        failed = retryable.action_start_application(adapter_key="test_retryable_failure")
        self.assertEqual(failed.state, "failed")
        self.assertTrue(failed.retryable)
        retried = retryable.action_retry_application()
        self.assertNotEqual(retried, failed)
        self.assertEqual(retried.retry_of_id, failed)

        terminal = self._job("terminal")
        failed_terminal = terminal.action_start_application(adapter_key="test_terminal_failure")
        self.assertFalse(failed_terminal.retryable)
        with self.assertRaises(UserError), self.env.cr.savepoint():
            terminal.action_retry_application()

    def test_invalid_url_and_protected_audit_are_rejected(self):
        job = self._job("invalid-url", url="javascript:alert(1)")
        with self.assertRaises(UserError), self.env.cr.savepoint():
            job.action_start_application(adapter_key="manual")
        valid = self._job("immutable")
        attempt = valid.action_start_application(adapter_key="manual")
        with self.assertRaises(ValidationError), self.env.cr.savepoint():
            attempt.write({"confirmation_reference": "forged"})
