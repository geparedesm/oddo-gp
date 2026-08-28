import base64

from odoo import fields
from odoo.exceptions import AccessError, ValidationError
from odoo.tests.common import TransactionCase


class TestJobApplication(TransactionCase):
    def _values(self, **overrides):
        test_slug = self._testMethodName.replace("test_", "")
        values = {
            "name": "Odoo Developer",
            "company_name": "Example Pty Ltd",
            "job_url": f"https://example.test/jobs/odoo-developer-{test_slug}",
        }
        values.update(overrides)
        return values

    def test_defaults(self):
        application = self.env["job.application"].create(self._values())

        self.assertEqual(application.state, "found")
        self.assertEqual(application.date_found, fields.Date.context_today(application))
        self.assertEqual(application.sponsorship_status, "unknown")
        self.assertEqual(application.source, "other")

    def test_api_fields_and_serializer_exclude_sensitive_fields(self):
        application = self.env["job.application"].create(
            self._values(
                external_id="external-test",
                source_job_id="source-test",
                raw_job_data={"private": "source payload"},
                cv_file=base64.b64encode(b"not returned"),
                cover_letter="not returned",
                notes="not returned",
                created_by_integration=True,
            )
        )
        data = application.get_api_data()
        self.assertEqual(data["external_id"], "external-test")
        self.assertTrue(data["created_by_integration"])
        for private_field in ("cv_file", "cover_letter", "notes", "raw_job_data"):
            self.assertNotIn(private_field, data)

    def test_match_score_rejects_invalid_create_and_write(self):
        with self.assertRaises(ValidationError), self.env.cr.savepoint():
            self.env["job.application"].create(self._values(match_score=101))

        application = self.env["job.application"].create(self._values(match_score=100))
        with self.assertRaises(ValidationError), self.env.cr.savepoint():
            application.write({"match_score": -1})

    def test_duplicate_url_rejected_on_create_and_write(self):
        original = self.env["job.application"].create(self._values())
        with self.assertRaises(ValidationError), self.env.cr.savepoint():
            self.env["job.application"].create(
                self._values(
                    name="Different Position",
                    company_name="Different Company",
                )
            )

        other = self.env["job.application"].create(
            self._values(
                name="Python Developer",
                company_name="Other Pty Ltd",
                job_url="https://example.test/jobs/python",
            )
        )
        with self.assertRaises(ValidationError), self.env.cr.savepoint():
            other.write({"job_url": original.job_url})

    def test_duplicate_company_position_rejected_on_create_and_write(self):
        original = self.env["job.application"].create(self._values())
        with self.assertRaises(ValidationError), self.env.cr.savepoint():
            self.env["job.application"].create(
                self._values(job_url="https://example.test/jobs/another-url")
            )

        other = self.env["job.application"].create(
            self._values(
                name="Python Developer",
                company_name="Other Pty Ltd",
                job_url="https://example.test/jobs/python",
            )
        )
        with self.assertRaises(ValidationError), self.env.cr.savepoint():
            other.write({"name": original.name, "company_name": original.company_name})

    def test_url_is_not_aggressively_normalized(self):
        original = self.env["job.application"].create(self._values())
        variant = self.env["job.application"].create(
            self._values(
                name="Odoo Developer II",
                job_url=f"{original.job_url}?ref=campaign",
            )
        )

        self.assertEqual(variant.job_url, f"{original.job_url}?ref=campaign")

    def test_required_identifiers_reject_whitespace(self):
        for field_name in ("name", "company_name", "job_url"):
            with self.assertRaises(ValidationError), self.env.cr.savepoint():
                self.env["job.application"].create(self._values(**{field_name: "   "}))

    def test_date_applied_state_validation_and_clear(self):
        with self.assertRaises(ValidationError), self.env.cr.savepoint():
            self.env["job.application"].create(
                self._values(date_applied="2026-08-28")
            )

        application = self.env["job.application"].create(
            self._values(state="applied", date_applied="2026-08-28")
        )
        application.write({"state": "interview"})
        self.assertEqual(application.date_applied, fields.Date.from_string("2026-08-28"))
        application.write({"date_applied": False, "state": "found"})
        self.assertFalse(application.date_applied)

    def test_date_applied_is_preserved_in_later_application_states(self):
        application = self.env["job.application"].create(
            self._values(state="applied", date_applied="2026-08-28")
        )

        for state in ("interview", "offer", "rejected"):
            application.write({"state": state})
            self.assertEqual(application.date_applied, fields.Date.from_string("2026-08-28"))

    def test_ignored_state_does_not_accept_date_applied(self):
        application = self.env["job.application"].create(
            self._values(state="ignored")
        )
        self.assertEqual(application.state, "ignored")
        with self.assertRaises(ValidationError), self.env.cr.savepoint():
            application.write({"date_applied": "2026-08-28"})

    def test_odoo_administrator_has_job_hunter_access(self):
        administrator = self.env.ref("base.user_admin")

        self.assertIn(
            self.env.ref("job_hunter_management.group_job_hunter_user"),
            administrator.groups_id,
        )
        self.env["job.application"].with_user(administrator).search([], limit=1)

    def test_unauthorized_user_has_no_job_hunter_access(self):
        unauthorized_user = self.env.ref("base.public_user")

        self.assertNotIn(
            self.env.ref("job_hunter_management.group_job_hunter_user"),
            unauthorized_user.groups_id,
        )
        with self.assertRaises(AccessError):
            self.env["job.application"].with_user(unauthorized_user).search([])

    def test_salary_range(self):
        application = self.env["job.application"].create(
            self._values(salary_min=100000, salary_max=120000)
        )
        self.assertEqual(application.salary_min, 100000)

        self.env["job.application"].create(
            self._values(
                name="Salary Open Ended",
                job_url="https://example.test/jobs/open",
                salary_min=130000,
            )
        )
        with self.assertRaises(ValidationError), self.env.cr.savepoint():
            self.env["job.application"].create(
                self._values(
                    name="Invalid Salary",
                    job_url="https://example.test/jobs/invalid-salary",
                    salary_min=130000,
                    salary_max=120000,
                )
            )
        with self.assertRaises(ValidationError), self.env.cr.savepoint():
            application.write({"salary_min": 130000})
