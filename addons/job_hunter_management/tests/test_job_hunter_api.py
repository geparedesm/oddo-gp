import json

from odoo.tests import tagged
from odoo.tests.common import HttpCase


@tagged("post_install", "-at_install")
class TestJobHunterAPI(HttpCase):
    TOKEN = "job-hunter-http-test-token"
    PARAMETER = "job_hunter_management.hermes_api_token"

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._created_ids = []
        cls._parameter = cls.env["ir.config_parameter"].sudo()
        cls._previous_token = cls._parameter.get_param(cls.PARAMETER)
        cls._parameter.set_param(cls.PARAMETER, cls.TOKEN)
        cls.env.cr.commit()

    @classmethod
    def tearDownClass(cls):
        try:
            cls.env.cr.rollback()
            cls.env["job.application"].sudo().search([("id", "in", cls._created_ids)]).unlink()
            if cls._previous_token:
                cls._parameter.set_param(cls.PARAMETER, cls._previous_token)
            else:
                cls._parameter.search([("key", "=", cls.PARAMETER)]).unlink()
            cls.env.cr.commit()
        finally:
            super().tearDownClass()

    def _request(self, method, path, payload=None, token=TOKEN):
        headers = {"Authorization": "Bearer %s" % token, "Content-Type": "application/json"}
        url = self.base_url() + path
        return self.opener.request(method, url, data=json.dumps(payload).encode() if payload is not None else None, headers=headers)

    def _create_payload(self, suffix="one", **overrides):
        payload = {
            "external_id": "http-%s" % suffix,
            "source_job_id": "source-%s" % suffix,
            "name": "Odoo Developer %s" % suffix,
            "company_name": "HTTP Test Company %s" % suffix,
            "job_url": "https://api.test/jobs/%s" % suffix,
            "source": "seek",
            "sponsorship_status": "unknown",
            "match_score": 80,
            "job_description": "Public integration test description",
        }
        payload.update(overrides)
        return payload

    def test_requires_bearer_authentication(self):
        response = self._request("GET", "/api/job-hunter/jobs", token="wrong")
        self.assertEqual(response.status_code, 401)

    def test_create_duplicate_and_idempotent_retry(self):
        response = self._request("POST", "/api/job-hunter/jobs", self._create_payload())
        self.assertEqual(response.status_code, 201)
        job_id = json.loads(response.text)["job"]["id"]
        self.__class__._created_ids.append(job_id)

        retry = self._request("POST", "/api/job-hunter/jobs", self._create_payload())
        self.assertEqual(retry.status_code, 200)
        self.assertTrue(json.loads(retry.text)["idempotent"])

        conflict = self._request("POST", "/api/job-hunter/jobs", self._create_payload("other", external_id="other", job_url="https://api.test/jobs/%s" % "one"))
        self.assertEqual(conflict.status_code, 409)

    def test_list_filters_detail_and_update_allowlist(self):
        response = self._request("POST", "/api/job-hunter/jobs", self._create_payload("filter", company_name="Filter Co", match_score=91))
        self.assertEqual(response.status_code, 201)
        job_id = json.loads(response.text)["job"]["id"]
        self.__class__._created_ids.append(job_id)

        listing = self._request("GET", "/api/job-hunter/jobs?source=seek&match_score_min=90&company_name=Filter%20Co")
        self.assertEqual(listing.status_code, 200)
        self.assertEqual(json.loads(listing.text)["count"], 1)

        detail = self._request("GET", "/api/job-hunter/jobs/%s" % job_id)
        self.assertEqual(detail.status_code, 200)
        self.assertNotIn("cv_file", detail.text)
        self.assertNotIn("cover_letter", detail.text)
        self.assertNotIn("notes", detail.text)

        update = self._request("PATCH", "/api/job-hunter/jobs/%s" % job_id, {"state": "interview", "match_score": 95})
        self.assertEqual(update.status_code, 200)
        self.assertEqual(json.loads(update.text)["job"]["state"], "interview")

        denied = self._request("PATCH", "/api/job-hunter/jobs/%s" % job_id, {"notes": "must not be accepted"})
        self.assertEqual(denied.status_code, 400)

    def test_invalid_payload_and_missing_resource(self):
        invalid = self._request("POST", "/api/job-hunter/jobs", {"name": "missing fields", "unexpected": True})
        self.assertEqual(invalid.status_code, 400)
        missing = self._request("GET", "/api/job-hunter/jobs/999999999")
        self.assertEqual(missing.status_code, 404)
