from psycopg2 import IntegrityError

from odoo import fields
from odoo.exceptions import ValidationError
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

    def test_match_score_rejects_invalid_create_and_write(self):
        with self.assertRaises(ValidationError), self.env.cr.savepoint():
            self.env["job.application"].create(self._values(match_score=101))

        application = self.env["job.application"].create(self._values(match_score=100))
        with self.assertRaises(ValidationError), self.env.cr.savepoint():
            application.write({"match_score": -1})

    def test_duplicate_rejected_on_create_and_write(self):
        self.env["job.application"].create(self._values())
        with self.assertRaises(IntegrityError), self.env.cr.savepoint():
            self.env["job.application"].create(self._values())

        other = self.env["job.application"].create(
            self._values(name="Python Developer", job_url="https://example.test/jobs/python")
        )
        with self.assertRaises(IntegrityError), self.env.cr.savepoint():
            other.write(
                {
                    "name": "Odoo Developer",
                    "job_url": self._values()["job_url"],
                }
            )

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
