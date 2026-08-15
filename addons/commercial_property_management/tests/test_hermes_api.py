from odoo.tests.common import TransactionCase


class TestHermesPublicData(TransactionCase):
    def setUp(self):
        super().setUp()
        self.feature_name = "Meeting room %s" % self._testMethodName
        feature = self.env["commercial.property.feature"].create({"name": self.feature_name})
        self.public_property = self.env["commercial.property"].create(
            {
                "name": "Internal Tower Name",
                "area": 120,
                "monthly_rent": 2200,
                "notes": "Private operating note",
                "public_name": "Central Tower Office",
                "public_description": "Light-filled office close to public transport.",
                "public_monthly_rent": 2400,
                "public_feature_ids": [(6, 0, feature.ids)],
                "is_published": True,
            }
        )
        self.hidden_property = self.env["commercial.property"].create(
            {
                "name": "Private Warehouse",
                "area": 500,
                "monthly_rent": 5000,
                "public_name": "Hidden Warehouse",
                "public_description": "This must not be returned.",
                "public_monthly_rent": 5000,
            }
        )

    def test_search_returns_only_public_available_properties(self):
        properties = self.env["commercial.property"].search_public_properties(min_area=100, max_rent=2500)

        self.assertIn(self.public_property, properties)
        self.assertNotIn(self.hidden_property, properties)
        self.assertEqual(
            self.env["commercial.property"].search_public_properties(code=self.public_property.code),
            self.public_property,
        )

    def test_public_serializer_excludes_private_fields(self):
        public_data = self.public_property.get_public_data()

        self.assertEqual(public_data["features"], [self.feature_name])
        self.assertNotIn("notes", public_data)
        self.assertNotIn("tenant_id", public_data)
        self.assertNotIn("lease_ids", public_data)
        self.assertEqual(public_data["monthly_rent"], self.public_property.public_monthly_rent)
        self.assertNotEqual(public_data["monthly_rent"], self.public_property.monthly_rent)
        self.assertNotIn(self.hidden_property.code, [property_record.code for property_record in self.env["commercial.property"].search_public_properties()])
