from odoo import fields
from odoo.tests.common import TransactionCase

from odoo.addons.commercial_property_management.controllers.hermes_api import HermesPropertyController


class TestCommercialPropertyPhase18(TransactionCase):
    def setUp(self):
        super().setUp()
        self.eur = self.env.ref("base.EUR")
        self.usd = self.env.ref("base.USD")
        self.env["ir.config_parameter"].sudo().set_param(
            "commercial_property_management.hermes_public_currency_id", self.usd.id
        )

    def _create_published_unit(self, name=None, location_hint=None, currency_id=None, public_monthly_rent=1500, city=None):
        name = name or ("Phase18 Unit %s" % self._testMethodName)
        building = self.env["commercial.property"].create(
            {
                "name": name,
                "area": 100,
                "monthly_rent": 1000,
                "city": city,
                "currency_id": currency_id or self.eur.id,
                "public_name": name,
                "public_description": "Published for Phase 18 tests.",
                "public_monthly_rent": public_monthly_rent,
                "is_published": True,
            }
        )
        if location_hint:
            building.default_unit_id.public_location_hint = location_hint
        return building.default_unit_id

    # Currency conversion

    def test_get_public_data_converts_price_to_public_currency(self):
        unit = self._create_published_unit(public_monthly_rent=1000)
        self.env["res.currency.rate"].create(
            {"currency_id": self.usd.id, "company_id": self.env.company.id, "name": fields.Date.today(), "rate": 1.1}
        )

        public_data = unit.get_public_data()

        self.assertEqual(public_data["currency"], "USD")
        self.assertAlmostEqual(public_data["monthly_rent"], self.usd.round(1100.0))

    def test_get_public_data_amount_unchanged_when_already_public_currency(self):
        unit = self._create_published_unit(currency_id=self.usd.id, public_monthly_rent=900)

        public_data = unit.get_public_data()

        self.assertEqual(public_data["monthly_rent"], 900)
        self.assertEqual(public_data["currency"], "USD")

    # Photo and virtual tour link

    def test_get_public_data_omits_photo_url_without_a_photo(self):
        unit = self._create_published_unit()
        self.assertFalse(unit.image_1920)

        public_data = unit.get_public_data()

        self.assertIsNone(public_data["photo_url"])
        self.assertIsNone(public_data["virtual_tour_url"])

    # Zone filtering

    def test_search_public_units_filters_by_zone(self):
        downtown = self._create_published_unit(name="Downtown Unit", location_hint="Near the central plaza")
        uptown = self._create_published_unit(name="Uptown Unit", location_hint="Close to the north bridge")

        results = self.env["commercial.property.unit"].search_public_units(zone="central plaza")

        self.assertIn(downtown, results)
        self.assertNotIn(uptown, results)

    def test_search_public_units_zone_matches_city(self):
        matching = self._create_published_unit(name="City Match Unit", city="Guayaquil")
        other = self._create_published_unit(name="Other City Unit", city="Quito")

        results = self.env["commercial.property.unit"].search_public_units(zone="guayaquil")

        self.assertIn(matching, results)
        self.assertNotIn(other, results)

    # max_rent is expressed in the public (USD) currency

    def test_search_public_units_max_rent_is_interpreted_in_public_currency(self):
        self.env["res.currency.rate"].create(
            {"currency_id": self.usd.id, "company_id": self.env.company.id, "name": fields.Date.today(), "rate": 2.0}
        )
        unit = self._create_published_unit(public_monthly_rent=400)  # 400 EUR -> 800 USD public price

        self.assertIn(unit, self.env["commercial.property.unit"].search_public_units(max_rent=900))
        self.assertNotIn(unit, self.env["commercial.property.unit"].search_public_units(max_rent=100))

    # Budget capture

    def test_lead_stores_stated_budget(self):
        unit = self._create_published_unit()
        lead = self.env["commercial.property.lead"].create(
            {
                "name": "Budget Prospect",
                "phone": "+15555550100",
                "unit_id": unit.id,
                "consent_at": fields.Datetime.now(),
                "budget": 1200,
            }
        )

        self.assertEqual(lead.budget, 1200)
        self.assertEqual(lead.currency_id, self.usd)

    # Controller-level validation reused for the budget parameter

    def test_controller_parses_budget_values(self):
        controller = HermesPropertyController()

        self.assertEqual(controller._parse_non_negative_number("1200", "budget"), 1200.0)
        self.assertIsNone(controller._parse_non_negative_number(None, "budget"))
        with self.assertRaises(ValueError):
            controller._parse_non_negative_number("-5", "budget")
        with self.assertRaises(ValueError):
            controller._parse_non_negative_number("not-a-number", "budget")
