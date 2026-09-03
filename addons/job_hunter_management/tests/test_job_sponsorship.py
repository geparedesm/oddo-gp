from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase


class TestJobSponsorship(TransactionCase):
    def setUp(self):
        super().setUp()
        self.created_applications = self.env["job.application"]
        self.rule = self.env["job.sponsorship.rule"].create({
            "name": "Phase 5 test priority",
            "yes_adjustment": 20,
            "unknown_adjustment": 0,
            "no_adjustment": -50,
        })

    def tearDown(self):
        try:
            applications = self.created_applications.exists().sudo()
            application_ids = applications.ids
            applications.unlink()
            self.env["job.sponsorship.analysis"].sudo().search([
                ("application_id", "in", application_ids),
            ]).unlink()
            self.rule.exists().sudo().unlink()
            self.assertFalse(self.env["job.application"].sudo().search_count([
                ("id", "in", application_ids),
            ]))
            self.assertFalse(self.env["job.sponsorship.analysis"].sudo().search_count([
                ("application_id", "in", application_ids),
            ]))
        finally:
            super().tearDown()

    def _job(self, suffix, description="", match_score=70):
        job = self.env["job.application"].create({
            "name": "Sponsorship Fixture %s" % suffix,
            "company_name": "Phase 5 Company %s" % suffix,
            "job_url": "https://sponsorship.test/jobs/%s" % suffix,
            "job_description": description,
            "match_score": match_score,
        })
        self.created_applications |= job
        return job

    def test_yes_no_unknown_and_audit_history(self):
        yes = self._job("yes", "Visa sponsorship available for the right candidate, including 482 sponsorship.")
        no = self._job("no", "No sponsorship available. Australian citizen or permanent resident only.")
        unknown = self._job("unknown", "Build reliable Odoo services in Sydney.")

        (yes | no | unknown).action_analyze_sponsorship(rule=self.rule)

        self.assertEqual((yes.sponsorship_status, no.sponsorship_status, unknown.sponsorship_status),
                         ("yes", "no", "unknown"))
        self.assertIn("visa sponsorship available", yes.sponsorship_evidence.lower())
        self.assertIn("no sponsorship available", no.sponsorship_evidence.lower())
        self.assertFalse(unknown.sponsorship_evidence)
        self.assertEqual(unknown.sponsorship_confidence, 0)
        for job in yes | no | unknown:
            self.assertGreaterEqual(job.sponsorship_confidence, 0)
            self.assertLessEqual(job.sponsorship_confidence, 100)
            self.assertTrue(job.sponsorship_reason)
            self.assertEqual(job.sponsorship_evidence_source, "job_description")
            self.assertTrue(job.sponsorship_analyzed_at)
            self.assertEqual(len(job.sponsorship_analysis_ids), 1)

        yes.action_analyze_sponsorship(rule=self.rule)
        self.assertEqual(len(yes.sponsorship_analysis_ids), 2)

    def test_negative_wins_conflict_and_work_rights_is_not_sponsorship(self):
        conflict = self._job(
            "conflict",
            "We are an employer sponsored business, but no sponsorship available for this role.",
        )
        work_rights = self._job(
            "work-rights",
            "Applicants must have full working rights in Australia.",
        )

        (conflict | work_rights).action_analyze_sponsorship(rule=self.rule)

        self.assertEqual(conflict.sponsorship_status, "no")
        self.assertIn("explicit negative", conflict.sponsorship_reason.lower())
        self.assertEqual(work_rights.sponsorship_status, "unknown")
        self.assertIn("work rights", work_rights.sponsorship_reason.lower())
        self.assertNotIn("must have full working rights", work_rights.sponsorship_evidence.lower())

    def test_priority_combines_match_without_changing_it_and_orders_statuses(self):
        yes = self._job("priority-yes", "Employer sponsored role.", match_score=70)
        unknown = self._job("priority-unknown", "No visa information supplied.", match_score=70)
        no = self._job("priority-no", "No sponsorship available.", match_score=95)

        (yes | unknown | no).action_analyze_sponsorship(rule=self.rule)

        self.assertEqual(no.match_score, 95)
        self.assertGreater(yes.priority_score, unknown.priority_score)
        self.assertGreater(unknown.priority_score, no.priority_score)
        ordered = self.env["job.application"].search([
            ("id", "in", (yes | unknown | no).ids),
        ], order="sponsorship_rank desc, priority_score desc")
        self.assertEqual(ordered, yes | unknown | no)
        self.assertTrue(no.exists(), "A sponsorship No result must never delete the vacancy")

    def test_confidence_and_rule_adjustments_are_validated(self):
        with self.assertRaises(ValidationError), self.env.cr.savepoint():
            self.rule.write({"yes_adjustment": 101})
        job = self._job("confidence", "482 sponsorship is available.")
        job.action_analyze_sponsorship(rule=self.rule)
        with self.assertRaises(ValidationError), self.env.cr.savepoint():
            job.write({"sponsorship_confidence": -1})
