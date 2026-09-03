import json
import os
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlsplit
from unittest.mock import patch

from odoo import fields
from odoo.tests.common import TransactionCase

from ..models.job_hunter_search import AdzunaAdapter, AdzunaCredentialsError, FixtureAdapter


class FakeResponse:
    def __init__(self, payload, headers=None):
        self.payload = payload
        self.headers = headers or {}

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self):
        return json.dumps(self.payload).encode()


class TestAdzunaAdapter(TransactionCase):
    def setUp(self):
        super().setUp()
        self.existing_application_ids = set(self.env["job.application"].sudo().search([]).ids)
        self.source = self.env.ref("job_hunter_management.source_adzuna")
        self.fixture_source = self.env.ref("job_hunter_management.source_seek")
        self.profile = self.env["job.hunter.profile"].create({
            "name": "Adzuna Phase 10 profile", "skills": "Python",
            "target_roles": "Platform Engineer, SRE", "location": "Sydney NSW",
            "target_salary": 125000, "remote_ok": True, "hybrid_ok": False,
            "onsite_ok": False,
        })
        self.config = self.env["job.hunter.search.config"].create({
            "name": "Adzuna Phase 10 config", "profile_id": self.profile.id,
            "max_age_days": 7, "source_ids": [(6, 0, (self.source | self.fixture_source).ids)],
        })

    def tearDown(self):
        created = self.env["job.application"].sudo().search([]).filtered(
            lambda application: application.id not in self.existing_application_ids
        )
        created.unlink()
        self.env["job.hunter.search.run"].sudo().search([
            ("config_id", "=", self.config.id),
        ]).unlink()
        self.config.unlink()
        self.profile.unlink()
        super().tearDown()

    def _result(self, suffix, **changes):
        result = {
            "id": "phase10-%s" % suffix, "title": "Platform Engineer",
            "company": {"display_name": "Example Pty Ltd"},
            "location": {"display_name": "Sydney NSW"},
            "redirect_url": "https://jobs.example/adzuna/%s" % suffix,
            "description": "Fully remote platform role",
            "salary_min": 130000, "salary_max": 150000,
            "created": fields.Datetime.to_string(fields.Datetime.now()),
        }
        result.update(changes)
        return result

    def test_source_is_explicitly_inactive_and_credentials_are_required_without_network(self):
        self.source.write({"active": False})
        self.assertFalse(self.source.active)
        self.assertEqual(self.source.adapter_type, "adzuna")
        parameters = self.env["ir.config_parameter"].sudo()
        parameters.set_param("job_hunter_management.adzuna_app_id", "")
        parameters.set_param("job_hunter_management.adzuna_app_key", "")
        opener_calls = []
        adapter = AdzunaAdapter(self.source, opener=lambda *args, **kwargs: opener_calls.append(args))
        with patch.dict(os.environ, {}, clear=True), self.assertRaises(AdzunaCredentialsError):
            adapter.search(self.config)
        self.assertFalse(opener_calls)

    def test_admin_settings_store_credentials_and_enable_source(self):
        with patch.dict(os.environ, {}, clear=True):
            settings = self.env["res.config.settings"].create({
                "job_adzuna_app_id": "settings-test-id",
                "job_adzuna_app_key": "settings-test-key",
                "job_adzuna_enabled": True,
            })
            settings.set_values()

        parameters = self.env["ir.config_parameter"].sudo()
        self.assertEqual(parameters.get_param("job_hunter_management.adzuna_app_id"), "settings-test-id")
        self.assertEqual(parameters.get_param("job_hunter_management.adzuna_app_key"), "settings-test-key")
        self.source.invalidate_recordset(["active"])
        self.assertTrue(self.source.active)

    def test_au_request_criteria_secret_redaction_pagination_limit_and_aliases(self):
        self.source.write({"default_page_size": 2, "result_limit": 3, "rate_limit_seconds": 0})
        requests = []
        payloads = [
            {"count": 5, "results": [self._result("1"), self._result("2")]},
            {"count": 5, "results": [self._result("3"), self._result("4")]},
        ]

        def opener(request, timeout):
            requests.append((request.full_url, timeout))
            return FakeResponse(payloads[len(requests) - 1])

        adapter = AdzunaAdapter(self.source, opener=opener)
        with patch.dict(os.environ, {"ADZUNA_APP_ID": "phase10-id", "ADZUNA_APP_KEY": "phase10-key"}, clear=True):
            jobs = adapter.search(self.config)
        self.assertEqual(len(jobs), 3)
        self.assertEqual([urlsplit(item[0]).path for item in requests], [
            "/v1/api/jobs/au/search/1", "/v1/api/jobs/au/search/2",
        ])
        params = parse_qs(urlsplit(requests[0][0]).query)
        self.assertEqual(params["what"], ["Platform Engineer"])
        self.assertEqual(params["where"], ["Sydney NSW"])
        self.assertEqual(params["salary_min"], ["125000"])
        self.assertEqual(params["results_per_page"], ["2"])
        self.assertEqual(params["max_days_old"], ["7"])
        self.assertNotIn("full_time", params)
        self.assertNotIn("permanent", params)
        normalized = adapter.provenance(2)
        self.assertNotIn("phase10-id", repr(normalized))
        self.assertNotIn("phase10-key", repr(normalized))
        self.assertEqual(normalized["page"], 2)

    def test_retry_policy_retry_after_timeout_network_and_monotonic_rate_limit(self):
        self.source.write({
            "default_page_size": 1, "result_limit": 1, "rate_limit_seconds": 0.5,
            "retry_count": 3, "request_timeout_seconds": 4, "retry_after_max_seconds": 2,
        })
        attempts = []
        sleeps = []
        clock = iter([0.0, 0.1, 0.6, 0.7, 1.2, 1.3, 1.8, 1.9])

        def opener(request, timeout):
            attempts.append(timeout)
            if len(attempts) == 1:
                raise HTTPError(request.full_url, 429, "rate phase10-key", {"Retry-After": "99"}, None)
            if len(attempts) == 2:
                raise HTTPError(request.full_url, 500, "server", {}, None)
            if len(attempts) == 3:
                raise URLError("timeout phase10-key")
            return FakeResponse({"count": 1, "results": [self._result("retry")]})

        adapter = AdzunaAdapter(
            self.source, opener=opener, sleeper=sleeps.append,
            monotonic=lambda: next(clock),
        )
        with patch.dict(os.environ, {"ADZUNA_APP_ID": "phase10-id", "ADZUNA_APP_KEY": "phase10-key"}, clear=True):
            self.assertEqual(len(adapter.search(self.config)), 1)
        self.assertEqual(attempts, [4.0, 4.0, 4.0, 4.0])
        self.assertIn(2.0, sleeps)
        self.assertTrue(any(delay > 0 for delay in sleeps))

    def test_non_retryable_4xx_and_partial_failure_continue_fixture_without_secret_leak(self):
        self.source.write({"active": True, "retry_count": 2})
        self.fixture_source.write({"active": True})
        calls = []

        def opener(request, timeout):
            calls.append(request.full_url)
            raise HTTPError(request.full_url, 400, "bad app_key=phase10-key", {}, None)

        with patch.object(AdzunaAdapter, "_default_opener", staticmethod(opener)), patch.dict(
            os.environ, {"ADZUNA_APP_ID": "phase10-id", "ADZUNA_APP_KEY": "phase10-key"}, clear=True,
        ):
            run = self.env["job.hunter.search.run"].run_config(self.config)
        self.assertEqual(len(calls), 1)
        self.assertEqual(run.state, "partial")
        failed = run.line_ids.filtered(lambda line: line.source == "adzuna")
        self.assertEqual(failed.availability, "unavailable")
        self.assertNotIn("phase10-key", failed.error_message or "")
        self.assertNotIn("phase10-id", failed.error_message or "")
        self.assertGreater(run.line_ids.filtered(lambda line: line.source == "seek").new_count, 0)

    def test_invalid_url_is_invalid_no_application_and_valid_results_are_idempotent(self):
        self.source.write({"active": True, "default_page_size": 10, "result_limit": 10})
        payload = {"count": 2, "results": [
            self._result("invalid", redirect_url="javascript:alert(1)"), self._result("valid"),
        ]}
        with patch.object(AdzunaAdapter, "_default_opener", staticmethod(lambda request, timeout: FakeResponse(payload))), patch.dict(
            os.environ, {"ADZUNA_APP_ID": "phase10-id", "ADZUNA_APP_KEY": "phase10-key"}, clear=True,
        ):
            first = self.env["job.hunter.search.run"].run_config(self.config)
            second = self.env["job.hunter.search.run"].run_config(self.config)
        adzuna_first = first.line_ids.filtered(lambda line: line.source == "adzuna")
        self.assertEqual(adzuna_first.error_count, 1)
        self.assertEqual(adzuna_first.new_count, 1)
        self.assertEqual(second.line_ids.filtered(lambda line: line.source == "adzuna").duplicate_count, 1)
        self.assertFalse(self.env["job.application"].search([("source_job_id", "=", "phase10-invalid")]))
        application = self.env["job.application"].search([("source_job_id", "=", "phase10-valid")])
        self.assertEqual(application.modalidad, "remote")
        self.assertNotIn("phase10-key", repr(application.raw_job_data))

    def test_legacy_fixture_adapter_stays_selected(self):
        self.assertEqual(self.fixture_source.adapter_type, "fixture")
        self.assertIsInstance(FixtureAdapter(self.fixture_source.code), FixtureAdapter)
