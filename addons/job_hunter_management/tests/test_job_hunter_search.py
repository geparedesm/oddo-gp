from unittest.mock import patch

from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase

from ..models.job_hunter_search import FixtureAdapter, canonical_url, normalize_job


class TestJobHunterSearch(TransactionCase):
    def tearDown(self):
        self.env["job.application"].sudo().search([("created_by_integration", "=", True)]).unlink()
        self.env["job.hunter.search.run"].sudo().search([]).unlink()
        self.env["job.hunter.search.config"].sudo().search([]).unlink()
        self.env["job.hunter.profile"].sudo().search([("name", "like", "Hermes test %")]).unlink()
        super().tearDown()

    def _profile(self, suffix, **values):
        data = {
            "name": "Hermes test %s" % suffix, "skills": "Python",
            "target_roles": "Role %s" % suffix, "location": "Sydney %s" % suffix,
            "target_salary": 120000, "remote_ok": True, "hybrid_ok": True, "onsite_ok": False,
        }
        data.update(values)
        return self.env["job.hunter.profile"].create(data)

    def _payload(self, **values):
        payload = {
            "title": "Platform Engineer", "company": "Acme", "location": "Sydney",
            "url": "https://jobs.example/roles/42", "description": "Build reliable platforms.",
            "source_job_id": "job-42", "salary_min": 100000, "salary_max": 130000,
            "currency": "AUD", "work_mode": "hybrid", "published_at": "2026-08-20T10:30:00Z",
        }
        payload.update(values)
        return payload

    def test_provider_payloads_use_one_contract_without_external_calls(self):
        payloads = {
            "adzuna": {
                "id": "adz-1", "title": "Data Engineer", "company": {"display_name": "Adz Co"},
                "location": {"display_name": "Melbourne"}, "redirect_url": "https://adz.example/1",
                "description": "Data pipelines", "salary_min": 10, "salary_max": 20,
                "salary_currency": "aud", "work_mode": "remote", "created": "2026-08-20",
            },
            "greenhouse": {
                "id": 22, "title": "SRE", "company_name": "Green Co", "location": {"name": "Brisbane"},
                "absolute_url": "https://green.example/jobs/22", "content": "Keep systems healthy",
                "salary_min": 30, "salary_max": 40, "salary_currency": "USD",
                "work_mode": "on-site", "updated_at": "2026-08-21T01:00:00+00:00",
            },
            "lever": {
                "id": "lev-3", "text": "Backend Engineer", "company_name": "Lever Co",
                "categories": {"location": "Perth"}, "hostedUrl": "https://lever.example/3",
                "descriptionPlain": "Backend services", "salaryRange": {"min": 50, "max": 60, "currency": "AUD"},
                "workplaceType": "hybrid", "createdAt": 1787270400000,
            },
            "ashby": {
                "id": "ash-4", "title": "Frontend Engineer", "companyName": "Ashby Co", "location": "Remote",
                "jobUrl": "https://ashby.example/4", "descriptionPlain": "Web applications",
                "compensation": {"min": 70, "max": 80, "currency": "USD"},
                "workplaceType": "remote", "publishedAt": "2026-08-22",
            },
        }
        for source, payload in payloads.items():
            normalized = normalize_job(payload, source, {"queried_at": "2026-08-29 00:00:00", "page": 1})
            self.assertEqual(normalized["source"], source)
            self.assertTrue(normalized["name"])
            self.assertTrue(normalized["source_job_id"])
            self.assertEqual(normalized["raw_job_data"]["schema_version"], 1)
            self.assertEqual(normalized["raw_job_data"]["provider"], source)
            self.assertEqual(normalized["raw_job_data"]["page"], 1)

    def test_aliases_and_controlled_provenance_preserve_allowed_originals(self):
        raw = {
            "name": " Engineer ", "company_name": "Acme", "location": "Remote",
            "job_url": "HTTPS://Jobs.Example/1/?candidate=7&utm_source=x", "job_description": "Remote role",
            "salary_min": 100, "salary_max": 200, "salary_currency": "aud", "source_job_id": "a1",
            "modalidad": "remote", "date_found": "2026-08-20", "api_token": "must-not-survive",
        }
        job = normalize_job(raw, "seek")
        self.assertEqual(job["name"], "Engineer")
        self.assertEqual(job["job_url"], "https://jobs.example/1?candidate=7")
        self.assertEqual(job["salary_currency"], "AUD")
        self.assertEqual(job["raw_job_data"]["original"]["name"], " Engineer ")
        self.assertNotIn("api_token", job["raw_job_data"]["original"])

    def test_invalid_contract_values_are_rejected_without_application(self):
        invalid = (
            {"title": ""},
            {"url": "javascript:alert(1)"},
            {"salary_min": "100"},
            {"salary_min": 200, "salary_max": 100},
            {"published_at": "not-a-date"},
            {"work_mode": "sometimes"},
        )
        before = self.env["job.application"].search_count([])
        for changes in invalid:
            with self.assertRaises(ValidationError):
                normalize_job(self._payload(**changes), "seek")
        self.assertEqual(self.env["job.application"].search_count([]), before)

    def test_missing_work_mode_is_allowed_for_provider_payloads(self):
        payload = self._payload()
        payload.pop("work_mode")
        normalized = normalize_job(payload, "adzuna")
        self.assertFalse(normalized["modalidad"])

    def test_canonical_url_preserves_functional_query_deterministically(self):
        first = canonical_url("HTTPS://Jobs.Example:443/role/?b=2&utm_medium=email&a=1#apply")
        second = canonical_url("https://jobs.example/role?a=1&b=2&gclid=tracking")
        self.assertEqual(first, "https://jobs.example/role?a=1&b=2")
        self.assertEqual(first, second)
        for invalid in ("ftp://jobs.example/1", "javascript:alert(1)", "/relative"):
            with self.assertRaises(ValidationError):
                canonical_url(invalid)

    def test_explicit_cross_source_deduplication_keys_and_idempotency(self):
        first = normalize_job(self._payload(), "seek")
        self.assertTrue(self.env["job.application"].sync_normalized_job(first))
        application = self.env["job.application"].search([("source_job_id", "=", "job-42")])
        self.assertEqual(application.dedup_source_key, "seek:job-42")
        self.assertEqual(application.dedup_url_key, "https://jobs.example/roles/42")
        self.assertEqual(application.dedup_content_key, "acme | platform engineer | sydney")
        self.assertFalse(self.env["job.application"].sync_normalized_job(first))
        other_source = normalize_job(self._payload(source_job_id="other-1", url="https://jobs.example/other"), "jora")
        self.assertFalse(self.env["job.application"].sync_normalized_job(other_source))

    def test_normalization_and_canonical_deduplication(self):
        job = normalize_job({"title": " Engineer ", "company": "Acme", "location": "Remote",
                             "url": "HTTPS://Jobs.Example/1/?utm_source=x", "description": "remote role",
                             "salary_min": 100, "currency": "AUD", "source_job_id": "a1",
                             "date_found": "2026-08-20", "modalidad": "remote"}, "seek")
        self.assertEqual(job["name"], "Engineer")
        self.assertEqual(job["modalidad"], "remote")
        self.assertEqual(job["salary_currency"], "AUD")
        self.assertTrue(self.env["job.application"].sync_normalized_job(job))
        variant = dict(job, job_url="https://jobs.example/1/?ref=other")
        self.assertFalse(self.env["job.application"].sync_normalized_job(variant))

    def test_config_fixture_sync_and_idempotency(self):
        source = self.env.ref("job_hunter_management.source_seek")
        config = self.env["job.hunter.search.config"].create({
            "name": "Fixture config", "keywords": "Unique Fixture Search Test", "location": "Sydney",
            "modalidad": "hybrid", "max_age_days": 30, "source_ids": [(6, 0, source.ids)],
        })
        run = self.env["job.hunter.search.run"].run_config(config)
        self.assertEqual(run.state, "done")
        self.assertEqual(run.total_found, 1)
        self.assertEqual(run.total_new, 1)
        second = self.env["job.hunter.search.run"].run_config(config)
        self.assertEqual(second.total_duplicates, 1)
        self.assertEqual(self.env["job.application"].search_count([
            ("created_by_integration", "=", True), ("name", "=", "Unique Fixture Search Test (SEEK)"),
        ]), 1)

    def test_source_failure_is_partial_and_other_sources_continue(self):
        config = self.env["job.hunter.search.config"].create({"name": "Partial config", "keywords": "Go"})
        original = FixtureAdapter.search

        def failing(adapter, current_config):
            if adapter.source == "seek":
                raise RuntimeError("fixture unavailable")
            return original(adapter, current_config)

        with patch.object(FixtureAdapter, "search", failing):
            run = self.env["job.hunter.search.run"].run_config(config)
        self.assertEqual(run.state, "partial")
        self.assertGreater(run.total_new, 0)
        self.assertGreater(run.total_errors, 0)
        failed = run.line_ids.filtered(lambda line: line.source == "seek")
        self.assertEqual(failed.availability, "unavailable")
        self.assertTrue(failed.queried_at)
        self.assertEqual(failed.provider, "fixture")

    def test_invalid_payload_is_recorded_and_next_source_continues(self):
        sources = self.env["job.hunter.search.source"].search([("code", "in", ["seek", "jora"])])
        config = self.env["job.hunter.search.config"].create({
            "name": "Invalid payload", "source_ids": [(6, 0, sources.ids)],
        })
        original = FixtureAdapter.search

        def invalid_seek(adapter, current_config):
            if adapter.source == "seek":
                return [{"title": "Missing required contract fields", "token": "do-not-log"}]
            return original(adapter, current_config)

        with patch.object(FixtureAdapter, "search", invalid_seek):
            run = self.env["job.hunter.search.run"].run_config(config)
        self.assertEqual(run.state, "partial")
        invalid_line = run.line_ids.filtered(lambda line: line.source == "seek")
        self.assertEqual(invalid_line.availability, "invalid")
        self.assertEqual(invalid_line.error_count, 1)
        self.assertNotIn("do-not-log", invalid_line.error_message or "")
        self.assertGreater(run.line_ids.filtered(lambda line: line.source == "jora").new_count, 0)

    def test_profile_manual_search_derives_criteria_and_is_idempotent(self):
        profile = self._profile("manual")
        run = profile.run_hermes_search()
        profile.invalidate_recordset(["last_hermes_search_at"])
        self.assertEqual(run.profile_id, profile)
        self.assertEqual(run.config_id.get_search_criteria(), {
            "keywords": "Role manual", "roles": "Role manual", "location": "Sydney manual",
            "salary_min": 120000.0, "salary_currency": "AUD", "modalities": ["remote", "hybrid"],
            "max_age_days": 30,
        })
        self.assertTrue(profile.last_hermes_search_at)
        first_timestamp = profile.last_hermes_search_at
        action = profile.action_run_hermes_search()
        self.assertEqual(action["tag"], "reload")
        second = self.env["job.hunter.search.run"].search([("profile_id", "=", profile.id)], limit=1)
        self.assertEqual(second.config_id, run.config_id)
        self.assertEqual(self.env["job.hunter.search.config"].search_count([("profile_id", "=", profile.id)]), 1)
        self.assertEqual(second.total_duplicates, second.total_found)
        self.assertGreaterEqual(profile.last_hermes_search_at, first_timestamp)

    def test_global_search_runs_every_active_profile(self):
        first = self._profile("global one")
        second = self._profile("global two")
        inactive = self._profile("inactive", active=False)
        summary = self.env["job.hunter.profile"].run_all_hermes_searches()
        self.assertGreaterEqual(summary["profiles_processed"], 2)
        self.assertEqual(self.env["job.hunter.search.run"].search_count([("profile_id", "in", (first | second).ids)]), 2)
        self.assertTrue(first.last_hermes_search_at)
        self.assertTrue(second.last_hermes_search_at)
        self.assertFalse(inactive.last_hermes_search_at)

    def test_hermes_search_excludes_fixture_sources(self):
        profile = self._profile("real sources only")
        fixture_source = self.env.ref("job_hunter_management.source_seek")
        fixture_source.write({"active": True})
        run = profile.run_hermes_search()
        self.assertFalse(run.line_ids.filtered(lambda line: line.source == "seek"))

    def test_profile_partial_run_persists_timestamp(self):
        profile = self._profile("partial")

        def failing(adapter, current_config):
            raise RuntimeError("controlled fixture failure")

        with patch.object(FixtureAdapter, "search", failing):
            config = profile._hermes_search_config()
            run = self.env["job.hunter.search.run"].run_config(config, include_fixtures=True)
        profile.invalidate_recordset(["last_hermes_search_at"])
        self.assertEqual(run.state, "partial")
        self.assertGreater(run.total_errors, 0)
        self.assertTrue(profile.last_hermes_search_at)

    def test_legacy_configuration_remains_supported(self):
        config = self.env["job.hunter.search.config"].create({
            "name": "Legacy", "roles": "Legacy Engineer", "location": "Melbourne",
            "modalidad": "onsite", "salary_min": 100000,
        })
        self.assertFalse(config.profile_id)
        self.assertEqual(config.get_search_criteria()["roles"], "Legacy Engineer")
        self.assertEqual(self.env["job.hunter.search.run"].run_config(config).state, "done")
