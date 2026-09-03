from lxml import etree

from odoo.exceptions import AccessError, ValidationError
from odoo.tests.common import TransactionCase


class TestCommercialPropertyRent(TransactionCase):
    def setUp(self):
        super().setUp()
        self.manager = self.env["res.users"].create({
            "name": "Rent Manager", "login": "rent.manager.test",
            "groups_id": [(6, 0, [self.env.ref("commercial_property_management.group_property_manager").id])],
        })
        self.user = self.env["res.users"].create({
            "name": "Rent User", "login": "rent.user.test",
            "groups_id": [(6, 0, [self.env.ref("commercial_property_management.group_property_user").id])],
        })

    def _property(self, **values):
        vals = {"name": "Yield Building", "area": 500, "monthly_rent": 1,
                "property_appraisal_value": 500000, "target_annual_yield": 6}
        vals.update(values)
        return self.env["commercial.property"].with_user(self.manager).create(vals)

    def test_recommendation_formula_and_ranges(self):
        prop = self._property()
        unit = prop.default_unit_id
        self.assertAlmostEqual(unit.area_share, 100.0)
        self.assertAlmostEqual(unit.estimated_property_value, 500000.0)
        self.assertAlmostEqual(unit.base_monthly_rent, 2500.0)
        self.assertAlmostEqual(unit.recommended_monthly_rent, 2500.0)
        self.assertAlmostEqual(unit.minimum_suggested_rent, 2250.0)
        self.assertAlmostEqual(unit.maximum_suggested_rent, 2750.0)

    def test_multiple_units_adjustments_and_inactive_area(self):
        prop = self._property(area=100, monthly_rent=1)
        second = self.env["commercial.property.unit"].with_user(self.manager).create({
            "property_id": prop.id, "name": "Second", "area": 100, "monthly_rent": 1,
            "unit_adjustment_factor": 1.2,
        })
        self.assertEqual(prop.total_rentable_area, 200)
        self.assertAlmostEqual(prop.default_unit_id.recommended_monthly_rent, 2500)
        self.assertAlmostEqual(second.recommended_monthly_rent, 3000)
        second.write({"active": False})
        self.assertEqual(prop.total_rentable_area, 100)
        self.assertAlmostEqual(prop.default_unit_id.recommended_monthly_rent, 2500)

    def test_three_units_keep_other_recommendations_when_area_changes(self):
        prop = self._property(area=100, monthly_rent=1)
        units = self.env["commercial.property.unit"].with_user(self.manager).create([
            {
                "property_id": prop.id,
                "name": "Unit 200",
                "area": 200,
                "monthly_rent": 1,
                "unit_adjustment_factor": 1.10,
            },
            {
                "property_id": prop.id,
                "name": "Unit 300",
                "area": 300,
                "monthly_rent": 1,
                "unit_adjustment_factor": 0.90,
            },
        ])
        first, second, third = prop.default_unit_id, units[0], units[1]

        self.assertEqual(prop.total_rentable_area, 600)
        self.assertAlmostEqual(first.area_share, 100 / 6, places=5)
        self.assertAlmostEqual(second.area_share, 100 / 3, places=5)
        self.assertAlmostEqual(third.area_share, 50, places=5)
        self.assertAlmostEqual(first.estimated_property_value, 500000, delta=0.01)
        self.assertAlmostEqual(second.estimated_property_value, 1000000, delta=0.01)
        self.assertAlmostEqual(third.estimated_property_value, 1500000, delta=0.01)
        self.assertAlmostEqual(first.recommended_monthly_rent, 2500, delta=0.01)
        self.assertAlmostEqual(second.recommended_monthly_rent, 5500, delta=0.01)
        self.assertAlmostEqual(third.recommended_monthly_rent, 6750, delta=0.01)

        first_before = (first.estimated_property_value, first.recommended_monthly_rent)
        third_before = (third.estimated_property_value, third.recommended_monthly_rent)

        second.write({"area": 300})

        self.assertEqual(prop.total_rentable_area, 700)
        self.assertAlmostEqual(first.area_share, 100 / 7, places=5)
        self.assertAlmostEqual(second.area_share, 300 / 7, places=5)
        self.assertAlmostEqual(third.area_share, 300 / 7, places=5)
        self.assertEqual((first.estimated_property_value, first.recommended_monthly_rent), first_before)
        self.assertEqual((third.estimated_property_value, third.recommended_monthly_rent), third_before)
        self.assertAlmostEqual(second.estimated_property_value, 1500000, delta=0.01)
        self.assertAlmostEqual(second.recommended_monthly_rent, 8250, delta=0.01)

    def test_financial_fields_are_visible_only_to_property_managers(self):
        property_view = self.env.ref("commercial_property_management.view_commercial_property_form")
        unit_view = self.env.ref("commercial_property_management.view_commercial_property_unit_form")
        financial_property_fields = (
            "property_appraisal_value", "total_rentable_area", "target_annual_yield",
            "minimum_rent_factor", "maximum_rent_factor",
        )
        financial_unit_fields = (
            "area_share", "estimated_property_value", "base_monthly_rent",
            "recommended_monthly_rent", "final_monthly_rent", "rent_status",
        )

        manager_property_arch = self.env["commercial.property"].with_user(self.manager).get_view(
            view_id=property_view.id, view_type="form"
        )["arch"]
        manager_unit_arch = self.env["commercial.property.unit"].with_user(self.manager).get_view(
            view_id=unit_view.id, view_type="form"
        )["arch"]
        user_property_arch = self.env["commercial.property"].with_user(self.user).get_view(
            view_id=property_view.id, view_type="form"
        )["arch"]
        user_unit_arch = self.env["commercial.property.unit"].with_user(self.user).get_view(
            view_id=unit_view.id, view_type="form"
        )["arch"]

        for field_name in financial_property_fields:
            self.assertIn(field_name, manager_property_arch)
            self.assertNotIn(field_name, user_property_arch)
        for field_name in financial_unit_fields:
            self.assertIn(field_name, manager_unit_arch)
            self.assertNotIn(field_name, user_unit_arch)

    def test_manager_rent_views_hide_legacy_and_keep_named_rents(self):
        property_view = self.env.ref("commercial_property_management.view_commercial_property_form")
        unit_view = self.env.ref("commercial_property_management.view_commercial_property_unit_form")
        property_arch = etree.fromstring(
            self.env["commercial.property"].with_user(self.manager).get_view(
                view_id=property_view.id, view_type="form"
            )["arch"].encode()
        )
        unit_arch = etree.fromstring(
            self.env["commercial.property.unit"].with_user(self.manager).get_view(
                view_id=unit_view.id, view_type="form"
            )["arch"].encode()
        )

        expected_rent_fields = {
            id(property_arch): (
                ("minimum_suggested_rent", "Minimum Suggested Rent"),
                ("maximum_suggested_rent", "Maximum Suggested Rent"),
                ("final_monthly_rent", "Final Monthly Rent"),
                ("public_monthly_rent", "Public Monthly Rent"),
            ),
            id(unit_arch): (
                ("recommended_monthly_rent", "Recommended Monthly Rent"),
                ("final_monthly_rent", "Final Monthly Rent"),
                ("public_monthly_rent", "Public Monthly Rent"),
            ),
        }

        for arch, main_section in (
            (property_arch, "Property Details"),
            (unit_arch, "Unit Details"),
        ):
            main_groups = arch.xpath(
                "//sheet//group[@string=$section]",
                section=main_section,
            )
            self.assertTrue(main_groups, "Expected %s section in manager view" % main_section)
            self.assertFalse(
                main_groups[0].xpath(".//field[@name='monthly_rent']"),
                "Legacy monthly_rent must not appear in %s" % main_section,
            )
            for field_name, label in expected_rent_fields[id(arch)]:
                fields = arch.xpath("//field[@name=$field_name]", field_name=field_name)
                self.assertTrue(fields, "Expected %s in manager view" % field_name)
                self.assertTrue(
                    any(field.get("string") == label for field in fields),
                    "Expected visible label %s" % label,
                )

    def test_manual_final_rent_is_preserved_and_legacy_is_synced(self):
        prop = self._property()
        unit = prop.default_unit_id
        unit.write({"final_monthly_rent": 3000})
        self.assertEqual(unit.monthly_rent, 3000)
        prop.write({"target_annual_yield": 8})
        self.assertEqual(unit.final_monthly_rent, 3000)
        self.assertEqual(unit.rent_status, "within")

    def test_invalid_rent_inputs_and_permissions(self):
        with self.assertRaises(ValidationError):
            self._property(property_appraisal_value=-1)
        prop = self._property()
        with self.assertRaises(ValidationError):
            prop.write({"minimum_rent_factor": 0})
        with self.assertRaises(ValidationError):
            prop.default_unit_id.write({"unit_adjustment_factor": 0})
        with self.assertRaises(AccessError):
            prop.with_user(self.user).write({"target_annual_yield": 7})
