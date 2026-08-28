from unittest.mock import patch

from odoo.tests.common import TransactionCase

from ..models.job_hunter_search import FixtureAdapter, normalize_job


class TestJobHunterSearch(TransactionCase):
    def tearDown(self):
        self.env["job.application"].sudo().search([("created_by_integration", "=", True)]).unlink()
        self.env["job.hunter.search.run"].sudo().search([]).unlink()
        self.env["job.hunter.search.config"].sudo().search([]).unlink()
        super().tearDown()

    def test_normalization_and_canonical_deduplication(self):
        job = normalize_job({"title": " Engineer ", "company": "Acme", "location": "Remote",
                             "url": "HTTPS://Jobs.Example/1/?utm_source=x", "description": "remote role",
                             "salary_min": 100, "currency": "AUD", "source_job_id": "a1"}, "seek")
        self.assertEqual(job["name"], "Engineer")
        self.assertEqual(job["modalidad"], "remote")
        self.assertEqual(job["salary_currency"], "AUD")
        self.assertTrue(self.env["job.application"].sync_normalized_job(job))
        variant = dict(job, job_url="https://jobs.example/1/?ref=other")
        self.assertFalse(self.env["job.application"].sync_normalized_job(variant))

    def test_config_fixture_sync_and_idempotency(self):
        source = self.env.ref("job_hunter_management.source_seek")
        config = self.env["job.hunter.search.config"].create({
            "name": "Fixture config", "keywords": "Python", "location": "Sydney",
            "modalidad": "hybrid", "max_age_days": 30, "source_ids": [(6, 0, source.ids)],
        })
        run = self.env["job.hunter.search.run"].run_config(config)
        self.assertEqual(run.state, "done")
        self.assertEqual(run.total_found, 1)
        self.assertEqual(run.total_new, 1)
        second = self.env["job.hunter.search.run"].run_config(config)
        self.assertEqual(second.total_duplicates, 1)
        self.assertEqual(self.env["job.application"].search_count([("created_by_integration", "=", True)]), 1)

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
