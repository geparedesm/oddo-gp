import base64

from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase


class TestJobMatching(TransactionCase):
    def setUp(self):
        super().setUp()
        self.created_applications = self.env["job.application"]
        self.profile = self.env["job.hunter.profile"].create({
            "name": "Primary professional profile", "skills": "Python, Odoo, PostgreSQL, REST APIs",
            "technologies": "Docker, Git, Linux", "years_experience": 7,
            "work_experience": "7 years building Odoo and Python systems",
            "education": "Bachelor of Computer Science", "certifications": "AWS Cloud Practitioner",
            "languages": "English: fluent\nSpanish: native", "target_roles": "Odoo Developer, Python Developer",
            "location": "Sydney", "remote_ok": True, "hybrid_ok": True, "onsite_ok": False,
            "target_salary": 130000, "salary_currency": "AUD",
            "primary_cv": base64.b64encode(b"master cv fixture"), "primary_cv_filename": "master-cv.pdf",
        })
        self.rule = self.env["job.hunter.match.rule"].create({
            "name": "Test thresholds", "high_score": 75, "medium_score": 50,
            "medium_state": "analysing", "low_state": "keep",
        })

    def tearDown(self):
        try:
            self.created_applications.sudo().unlink()
            self.profile.sudo().unlink()
            self.rule.sudo().unlink()
        finally:
            super().tearDown()

    def _job(self, suffix, **values):
        defaults = {"name": "Odoo Developer", "company_name": "Matching Fixture %s" % suffix,
                    "job_url": "https://matching.test/jobs/%s" % suffix, "location": "Sydney", "modalidad": "hybrid"}
        defaults.update(values)
        job = self.env["job.application"].create(defaults)
        self.created_applications |= job
        return job

    def test_high_medium_low_fixtures_are_deterministic_and_traced(self):
        high = self._job("high", mandatory_skills="Python, Odoo", desired_skills="PostgreSQL, REST APIs",
                         required_technologies="Docker, Git", required_years_experience=5,
                         required_seniority="senior", required_education="Bachelor",
                         required_languages="English", target_role="Odoo Developer")
        medium = self._job("medium", mandatory_skills="Python, Java", desired_skills="Odoo, Kubernetes",
                           required_technologies="Docker, Azure", required_years_experience=8,
                           required_seniority="senior", required_education="Bachelor",
                           required_languages="English", target_role="Backend Developer",
                           location="Melbourne", modalidad="remote")
        low = self._job("low", mandatory_skills="Java, SAP, ABAP", desired_skills="Kotlin",
                        required_technologies="HANA", required_years_experience=12,
                        required_seniority="lead", required_education="PhD Physics",
                        required_languages="German", target_role="SAP Architect",
                        location="Berlin", modalidad="onsite")
        (high | medium | low).action_analyze_match(self.profile, self.rule)
        self.assertGreaterEqual(high.match_score, 75)
        self.assertGreaterEqual(medium.match_score, 50)
        self.assertLess(medium.match_score, 75)
        self.assertLess(low.match_score, 50)
        self.assertEqual((high.state, medium.state, low.state), ("good_match", "analysing", "found"))
        self.assertEqual(high.matched_skills, "Odoo\nPostgreSQL\nPython\nREST APIs")
        self.assertIn("Java", medium.missing_mandatory_requirements)
        self.assertIn("SAP", low.missing_skills)
        self.assertTrue(high.match_explanation)
        self.assertEqual(high.match_profile_version, self.profile.version)
        self.assertEqual(high.match_cv_checksum, self.profile.cv_checksum)
        self.assertFalse(high.cv_file, "The master CV must be referenced, not copied")
        self.assertEqual(len(high.match_analysis_ids), 1)
        self.assertIn("mandatory_skills", high.match_analysis_ids.criteria)

    def test_profile_change_versions_future_analysis_without_recopying_cv(self):
        job = self._job("version", mandatory_skills="Python")
        job.action_analyze_match(self.profile, self.rule)
        old_version, old_checksum = job.match_profile_version, job.match_cv_checksum
        self.profile.write({"skills": self.profile.skills + ", Kubernetes"})
        job.action_analyze_match(self.profile, self.rule)
        self.assertEqual(job.match_profile_version, old_version + 1)
        self.assertEqual(job.match_cv_checksum, old_checksum)
        self.assertEqual(len(job.match_analysis_ids), 2)
        self.assertFalse(job.cv_file)

    def test_manual_decision_is_not_overwritten(self):
        job = self._job("manual", state="ready_to_apply", mandatory_skills="Python")
        job.action_analyze_match(self.profile, self.rule)
        self.assertEqual(job.state, "ready_to_apply", "Legacy manual workflow states must remain untouched")
        job.write({"state": "ignored"})
        job.action_analyze_match(self.profile, self.rule)
        self.assertEqual(job.state, "ignored")
        self.assertTrue(job.manual_state_locked)
        latest = self.env["job.match.analysis"].search([("application_id", "=", job.id)], order="id desc", limit=1)
        self.assertEqual(latest.state_after, "ignored")

    def test_thresholds_and_profile_are_validated(self):
        with self.assertRaises(ValidationError), self.env.cr.savepoint():
            self.env["job.hunter.match.rule"].create({"name": "Invalid", "high_score": 40, "medium_score": 60})
        with self.assertRaises(ValidationError), self.env.cr.savepoint():
            self.profile.write({"years_experience": -1})
