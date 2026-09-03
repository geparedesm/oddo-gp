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
        cls._search_baseline = {
            model: cls.env[model].sudo().search([]).ids
            for model in ("job.application", "job.hunter.search.run", "job.hunter.search.config")
        }
        cls._parameter = cls.env["ir.config_parameter"].sudo()
        cls._previous_token = cls._parameter.get_param(cls.PARAMETER)
        cls._parameter.set_param(cls.PARAMETER, cls.TOKEN)
        cls._search_profile = cls.env["job.hunter.profile"].create({
            "name": "HTTP Hermes profile success", "skills": "Python",
            "target_roles": "HTTP Engineer", "location": "Brisbane",
        })
        cls.env.cr.commit()

    @classmethod
    def tearDownClass(cls):
        try:
            cls.env.cr.rollback()
            for model in ("job.hunter.search.run", "job.hunter.search.config", "job.application"):
                cls.env[model].sudo().search([("id", "not in", cls._search_baseline[model])]).unlink()
            profiles = cls.env["job.hunter.profile"].sudo().search([("name", "like", "HTTP Hermes profile %")])
            cls.env["job.hunter.search.run"].sudo().search([("profile_id", "in", profiles.ids)]).unlink()
            cls.env["job.hunter.search.config"].sudo().search([("profile_id", "in", profiles.ids)]).unlink()
            profiles.unlink()
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

    def test_search_endpoint_auth_success_and_strict_payload(self):
        profile = self._search_profile
        denied = self._request("POST", "/api/job-hunter/search/run", {}, token="wrong")
        self.assertEqual(denied.status_code, 401)
        invalid = self._request("POST", "/api/job-hunter/search/run", {"profile_id": profile.id})
        self.assertEqual(invalid.status_code, 400)
        response = self._request("POST", "/api/job-hunter/search/run", {})
        self.assertEqual(response.status_code, 200)
        payload = json.loads(response.text)
        self.assertEqual(set(payload), {"runs", "profiles_processed", "timestamp", "errors"})
        self.assertGreaterEqual(payload["runs"], 1)
        profile.invalidate_recordset(["last_hermes_search_at"])
        self.assertTrue(profile.last_hermes_search_at)
        self.assertEqual(self.env["job.hunter.search.config"].search_count([("profile_id", "=", profile.id)]), 1)
