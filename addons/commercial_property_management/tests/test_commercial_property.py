from odoo.exceptions import AccessError, ValidationError
from odoo.tests.common import TransactionCase


class TestCommercialProperty(TransactionCase):
    def setUp(self):
        super().setUp()
        self.manager = self.env["res.users"].create(
            {
                "name": "Property Manager",
                "login": "property.manager.test",
                "email": "property.manager.test@example.com",
                "company_id": self.env.company.id,
                "company_ids": [(6, 0, self.env.company.ids)],
                "groups_id": [(6, 0, [self.env.ref("commercial_property_management.group_property_manager").id])],
            }
        )
        self.user = self.env["res.users"].create(
            {
                "name": "Property User",
                "login": "property.user.test",
                "email": "property.user.test@example.com",
                "company_id": self.env.company.id,
                "company_ids": [(6, 0, self.env.company.ids)],
                "groups_id": [(6, 0, [self.env.ref("commercial_property_management.group_property_user").id])],
            }
        )

    def test_manager_creates_property_with_sequence(self):
        property_record = self.env["commercial.property"].with_user(self.manager).create(
            {
                "name": "Harbor Office",
                "area": 250,
                "monthly_rent": 5000,
            }
        )

        self.assertRegex(property_record.code, r"^CP[0-9]{4}-[0-9]{4}$")
        self.assertEqual(property_record.state, "available")

    def test_invalid_property_values_are_rejected(self):
        with self.assertRaises(ValidationError):
            self.env["commercial.property"].with_user(self.manager).create(
                {"name": "Invalid Area", "area": 0, "monthly_rent": 1000}
            )

        with self.assertRaises(ValidationError):
            self.env["commercial.property"].with_user(self.manager).create(
                {"name": "Invalid Rent", "area": 100, "monthly_rent": -1}
            )

    def test_property_user_can_read_but_cannot_change_inventory(self):
        property_record = self.env["commercial.property"].with_user(self.manager).create(
            {"name": "Read Only Property", "area": 100, "monthly_rent": 1500}
        )

        self.assertEqual(property_record.with_user(self.user).name, "Read Only Property")
        property_record.with_user(self.manager).write({"active": False})
        self.assertFalse(property_record.active)
        with self.assertRaises(AccessError):
            property_record.with_user(self.user).write({"name": "Changed"})
