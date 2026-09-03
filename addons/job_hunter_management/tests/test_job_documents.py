import base64

from odoo.exceptions import UserError, ValidationError
from odoo.tests.common import TransactionCase


class TestJobDocuments(TransactionCase):
    def setUp(self):
        super().setUp()
        self.jobs = self.env["job.application"]
        self.profile = self.env["job.hunter.profile"].create({
            "name": "Phase 6 approved profile",
            "skills": "Python, Odoo, PostgreSQL",
            "technologies": "Docker, Git",
            "years_experience": 7,
            "work_experience": "Built Odoo services at Acme Pty Ltd from 2019 to 2024.",
            "education": "Bachelor of Computer Science",
            "certifications": "AWS Cloud Practitioner",
            "languages": "English: fluent\nSpanish: native",
            "target_roles": "Odoo Developer",
            "location": "Sydney",
            "primary_cv": base64.b64encode(b"MASTER CV MUST REMAIN UNCHANGED"),
            "primary_cv_filename": "master.pdf",
        })
        self.rule = self.env["job.document.generation.rule"].create({
            "name": "Phase 6 threshold", "minimum_priority_score": 75,
        })

    def tearDown(self):
        try:
            job_ids = self.jobs.ids
            document_ids = self.env["job.application.document"].sudo().search([
                ("application_id", "in", job_ids),
            ]).ids
            self.jobs.sudo().unlink()
            self.env["job.application.document"].sudo().browse(document_ids).exists().unlink()
            self.rule.exists().sudo().unlink()
            self.profile.exists().sudo().unlink()
            self.assertFalse(self.env["job.application"].sudo().search_count([("id", "in", job_ids)]))
            self.assertFalse(self.env["job.application.document"].sudo().search_count([("id", "in", document_ids)]))
        finally:
            super().tearDown()

    def _job(self, suffix, priority=80):
        job = self.env["job.application"].create({
            "name": "Senior Odoo Developer",
            "company_name": "Legitimate Employer %s" % suffix,
            "job_url": "https://phase6.test/%s" % suffix,
            "job_description": "Seeking Python, Odoo, Kubernetes and Docker experience.",
            "mandatory_skills": "Python, Odoo, Kubernetes",
            "desired_skills": "PostgreSQL",
            "required_technologies": "Docker",
            "match_score": priority,
            "sponsorship_priority_adjustment": 0,
        })
        self.jobs |= job
        return job

    def test_prioritized_job_generates_versioned_documents_and_preserves_master(self):
        job = self._job("prioritized")
        master_before = self.profile.primary_cv

        job.action_generate_documents(profile=self.profile, rule=self.rule)
        document = job.document_ids

        self.assertEqual(len(document), 1)
        self.assertEqual(document.application_id, job)
        self.assertEqual(document.profile_id, self.profile)
        self.assertEqual(document.profile_version, self.profile.version)
        self.assertEqual(document.version, 1)
        self.assertEqual(document.state, "draft")
        self.assertTrue(document.tailored_cv)
        self.assertTrue(document.cover_letter)
        self.assertTrue(document.generated_at)
        self.assertEqual(document.generator_model, "deterministic-structured-v1")
        self.assertTrue(document.prompt_version)
        self.assertTrue(document.source_snapshot)
        self.assertTrue(document.change_summary)
        self.assertEqual(document.validation_state, "passed")
        self.assertEqual(self.profile.primary_cv, master_before)
        self.assertFalse(job.cv_file)

        job.action_generate_documents(profile=self.profile, rule=self.rule)
        self.assertEqual(sorted(job.document_ids.mapped("version")), [1, 2])

    def test_non_prioritized_job_is_rejected(self):
        job = self._job("below-threshold", priority=74)
        with self.assertRaises(UserError), self.env.cr.savepoint():
            job.action_generate_documents(profile=self.profile, rule=self.rule)
        self.assertFalse(job.document_ids)

    def test_only_approved_profile_facts_and_legitimate_matching_keywords_are_used(self):
        job = self._job("facts")
        job.action_generate_documents(profile=self.profile, rule=self.rule)
        document = job.document_ids
        combined = "%s\n%s" % (document.tailored_cv, document.cover_letter)

        for approved_fact in ("Acme Pty Ltd", "2019", "2024", "Python", "Odoo", "PostgreSQL", "Docker"):
            self.assertIn(approved_fact, combined)
        self.assertNotIn("Kubernetes", combined, "A vacancy keyword absent from the profile must not be claimed")
        self.assertNotIn("Legitimate Employer facts", document.tailored_cv)

    def test_review_and_approval_are_explicit_and_tampering_stays_draft(self):
        job = self._job("states")
        job.action_generate_documents(profile=self.profile, rule=self.rule)
        document = job.document_ids

        with self.assertRaises(ValidationError), self.env.cr.savepoint():
            document.action_approve()
        document.action_review()
        self.assertEqual(document.state, "reviewed")
        document.action_approve()
        self.assertEqual(document.state, "approved")
        self.assertTrue(document.approved_at)

        job.action_generate_documents(profile=self.profile, rule=self.rule)
        tampered = job.document_ids.filtered(lambda item: item.version == 2)
        tampered.write({"cover_letter": tampered.cover_letter + " I led Google for ten years."})
        self.assertFalse(tampered.action_review())
        self.assertEqual(tampered.state, "draft")
        self.assertEqual(tampered.validation_state, "blocked")
        self.assertIn("source of truth", tampered.validation_message.lower())
