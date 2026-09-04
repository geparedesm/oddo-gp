from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestJobPilotProfile(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user = cls.env["res.users"].create(
            {"name": "Career User", "login": "career_user", "email": "career.user@example.com"}
        )
        cls.profile = cls.env["job_pilot.profile"].create(
            {"name": "Career User", "user_id": cls.user.id, "email": "career.user@example.com"}
        )

    def test_one_profile_per_user(self):
        with self.assertRaises(Exception):
            self.env["job_pilot.profile"].create({"name": "Duplicate", "user_id": self.user.id})

    def test_work_experience_current_position_cannot_have_end_date(self):
        with self.assertRaises(ValidationError):
            self.env["job_pilot.work.experience"].create(
                {
                    "profile_id": self.profile.id,
                    "company_name": "Acme",
                    "job_title": "Engineer",
                    "start_date": "2020-01-01",
                    "end_date": "2021-01-01",
                    "currently_working": True,
                }
            )

    def test_work_experience_end_before_start_rejected(self):
        with self.assertRaises(ValidationError):
            self.env["job_pilot.work.experience"].create(
                {
                    "profile_id": self.profile.id,
                    "company_name": "Acme",
                    "job_title": "Engineer",
                    "start_date": "2021-01-01",
                    "end_date": "2020-01-01",
                }
            )

    def test_cv_upload_count_computed(self):
        self.assertEqual(self.profile.cv_upload_count, 0)
        self.env["job_pilot.cv.upload"].create(
            {
                "profile_id": self.profile.id,
                "filename": "cv.pdf",
                "file": b"ZmFrZSBwZGYgY29udGVudA==",
            }
        )
        self.assertEqual(self.profile.cv_upload_count, 1)
