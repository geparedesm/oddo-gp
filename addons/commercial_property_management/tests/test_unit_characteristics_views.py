"""
Functional tests for commercial property unit characteristics in views (Form, Kanban, Search, Tree).
Tests verify that characteristic fields are properly displayed and functional in all view modes.
"""
from odoo import fields
from odoo.tests.common import TransactionCase, HttpCase


class TestUnitCharacteristicsFormView(TransactionCase):
    """Test unit characteristics fields in Form view."""
    
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.manager = cls.env["res.users"].create({
            "name": "Property Manager",
            "login": "property.manager.test.views",
            "email": "pm.test@example.com",
            "groups_id": [(6, 0, [cls.env.ref("commercial_property_management.group_property_manager").id])],
        })
        cls.property = cls.env["commercial.property"].with_user(cls.manager).create({
            "name": "Test Building",
            "area": 500,
            "monthly_rent": 10000,
        })
    
    def setUp(self):
        super().setUp()
        self.unit = self.property.default_unit_id
    
    def test_form_view_has_characteristics_section(self):
        """Test that form view includes Unit Characteristics section."""
        form_view = self.env.ref("commercial_property_management.commercial_property_unit_form")
        self.assertIsNotNone(form_view, "Form view should exist")
        
        # Parse the XML to verify characteristics fields are present
        xml_doc = form_view.get_combined_arch()
        self.assertIn("Unit Characteristics", str(xml_doc))
        self.assertIn("bedrooms", str(xml_doc))
        self.assertIn("bathrooms", str(xml_doc))
        self.assertIn("parking_spaces", str(xml_doc))
        self.assertIn("furnished", str(xml_doc))
    
    def test_all_characteristic_fields_readable_writable(self):
        """Test that all characteristic fields can be read and written."""
        characteristic_fields = [
            "bedrooms", "bathrooms", "half_bathrooms", "parking_spaces",
            "floor_number", "total_floors", "storage_rooms", "balcony_area_sqm",
            "furnished", "has_balcony", "has_laundry", "pet_friendly",
        ]
        
        test_values = {
            "bedrooms": 2,
            "bathrooms": 1,
            "half_bathrooms": 1,
            "parking_spaces": 2,
            "floor_number": 3,
            "total_floors": 10,
            "storage_rooms": 1,
            "balcony_area_sqm": 5.5,
            "furnished": True,
            "has_balcony": True,
            "has_laundry": True,
            "pet_friendly": True,
        }
        
        # Write all fields
        self.unit.with_user(self.manager).write(test_values)
        
        # Read back and verify
        for field_name in characteristic_fields:
            self.assertEqual(
                getattr(self.unit, field_name),
                test_values[field_name],
                f"Field {field_name} should be readable/writable"
            )
    
    def test_characteristic_fields_with_default_values(self):
        """Test that characteristic fields have correct defaults on new unit."""
        new_unit = self.env["commercial.property.unit"].with_user(self.manager).create({
            "property_id": self.property.id,
            "name": "Default Unit",
            "area": 50,
            "monthly_rent": 1000,
        })
        
        # Numeric fields should default to 0
        self.assertEqual(new_unit.bedrooms, 0)
        self.assertEqual(new_unit.bathrooms, 0)
        self.assertEqual(new_unit.balcony_area_sqm, 0.0)
        
        # Boolean fields should default to False
        self.assertFalse(new_unit.furnished)
        self.assertFalse(new_unit.pet_friendly)


class TestUnitCharacteristicsKanbanView(TransactionCase):
    """Test unit characteristics in Kanban view."""
    
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.manager = cls.env["res.users"].create({
            "name": "Manager",
            "login": "manager.kanban.test",
            "groups_id": [(6, 0, [cls.env.ref("commercial_property_management.group_property_manager").id])],
        })
        cls.property = cls.env["commercial.property"].with_user(cls.manager).create({
            "name": "Kanban Test Building",
            "area": 500,
            "monthly_rent": 10000,
        })
    
    def setUp(self):
        super().setUp()
        self.unit = self.property.default_unit_id
    
    def test_kanban_view_exists(self):
        """Test that Kanban view for commercial.property.unit exists."""
        kanban_view = self.env["ir.ui.view"].search([
            ("model", "=", "commercial.property.unit"),
            ("type", "=", "kanban"),
            ("name", "ilike", "kanban"),
        ])
        self.assertTrue(kanban_view, "Kanban view for commercial.property.unit should exist")
    
    def test_unit_with_characteristics_displays_summary(self):
        """Test that unit with characteristics shows summary in Kanban."""
        self.unit.with_user(self.manager).write({
            "bedrooms": 2,
            "bathrooms": 2,
            "parking_spaces": 1,
            "furnished": True,
        })
        
        # Get public data which includes characteristics_summary
        public_data = self.unit.get_public_data()
        self.assertIn("characteristics_summary", public_data)
        self.assertGreater(len(public_data["characteristics_summary"]), 0)
    
    def test_unit_without_characteristics_displays_cleanly(self):
        """Test that unit without characteristics displays without errors."""
        # Ensure all characteristics are empty
        self.unit.with_user(self.manager).write({
            "bedrooms": 0,
            "bathrooms": 0,
            "parking_spaces": 0,
            "furnished": False,
        })
        
        # get_public_data should not include characteristics_summary if all empty
        public_data = self.unit.get_public_data()
        self.assertNotIn("characteristics_summary", public_data)


class TestUnitCharacteristicsSearchView(TransactionCase):
    """Test unit characteristics in Search view."""
    
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.manager = cls.env["res.users"].create({
            "name": "Search Manager",
            "login": "search.manager.test",
            "groups_id": [(6, 0, [cls.env.ref("commercial_property_management.group_property_manager").id])],
        })
        cls.property = cls.env["commercial.property"].with_user(cls.manager).create({
            "name": "Search Test Building",
            "area": 500,
            "monthly_rent": 10000,
        })
    
    def setUp(self):
        super().setUp()
        self.manager.with_user(self.manager)
    
    def test_search_view_has_characteristic_filters(self):
        """Test that search view includes characteristic filters."""
        search_view = self.env["ir.ui.view"].search([
            ("model", "=", "commercial.property.unit"),
            ("type", "=", "search"),
        ], limit=1)
        self.assertTrue(search_view, "Search view should exist")
        
        # Verify filter fields exist in XML
        xml_str = str(search_view.get_combined_arch())
        self.assertIn("furnished", xml_str)
        self.assertIn("pet_friendly", xml_str)
    
    def test_search_by_furnished_filter(self):
        """Test filtering units by furnished status."""
        furnished_unit = self.property.default_unit_id
        furnished_unit.with_user(self.manager).write({"furnished": True})
        
        unfurnished_unit = self.env["commercial.property.unit"].with_user(self.manager).create({
            "property_id": self.property.id,
            "name": "Unfurnished Unit",
            "area": 50,
            "monthly_rent": 500,
            "furnished": False,
        })
        
        # Search for furnished units
        furnished_results = self.env["commercial.property.unit"].search([("furnished", "=", True)])
        self.assertIn(furnished_unit, furnished_results)
        self.assertNotIn(unfurnished_unit, furnished_results)
        
        # Search for unfurnished units
        unfurnished_results = self.env["commercial.property.unit"].search([("furnished", "=", False)])
        self.assertIn(unfurnished_unit, unfurnished_results)
        self.assertNotIn(furnished_unit, unfurnished_results)
    
    def test_search_by_pet_friendly_filter(self):
        """Test filtering units by pet-friendly status."""
        pet_unit = self.property.default_unit_id
        pet_unit.with_user(self.manager).write({"pet_friendly": True})
        
        no_pet_unit = self.env["commercial.property.unit"].with_user(self.manager).create({
            "property_id": self.property.id,
            "name": "No Pets Unit",
            "area": 50,
            "monthly_rent": 500,
            "pet_friendly": False,
        })
        
        # Search for pet-friendly units
        pet_results = self.env["commercial.property.unit"].search([("pet_friendly", "=", True)])
        self.assertIn(pet_unit, pet_results)
        self.assertNotIn(no_pet_unit, pet_results)


class TestUnitCharacteristicsTreeView(TransactionCase):
    """Test unit characteristics in Tree (list) view."""
    
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.manager = cls.env["res.users"].create({
            "name": "Tree Manager",
            "login": "tree.manager.test",
            "groups_id": [(6, 0, [cls.env.ref("commercial_property_management.group_property_manager").id])],
        })
        cls.property = cls.env["commercial.property"].with_user(cls.manager).create({
            "name": "Tree Test Building",
            "area": 500,
            "monthly_rent": 10000,
        })
    
    def setUp(self):
        super().setUp()
        self.unit = self.property.default_unit_id
    
    def test_tree_view_has_characteristic_columns(self):
        """Test that tree view includes characteristic columns."""
        tree_view = self.env["ir.ui.view"].search([
            ("model", "=", "commercial.property.unit"),
            ("type", "=", "tree"),
        ], limit=1)
        self.assertTrue(tree_view, "Tree view should exist")
        
        # Verify characteristic fields are in XML
        xml_str = str(tree_view.get_combined_arch())
        self.assertIn("bedrooms", xml_str)
        self.assertIn("bathrooms", xml_str)
        self.assertIn("parking_spaces", xml_str)
    
    def test_tree_view_displays_characteristic_values(self):
        """Test that tree view correctly displays characteristic values."""
        self.unit.with_user(self.env["res.users"].create({
            "name": "Test User",
            "login": "test.user.tree",
            "groups_id": [(6, 0, [self.env.ref("commercial_property_management.group_property_manager").id])],
        })).write({
            "bedrooms": 3,
            "bathrooms": 2,
            "parking_spaces": 2,
        })
        
        # Reload unit to verify values persisted
        self.unit.refresh()
        self.assertEqual(self.unit.bedrooms, 3)
        self.assertEqual(self.unit.bathrooms, 2)
        self.assertEqual(self.unit.parking_spaces, 2)


class TestCharacteristicValidation(TransactionCase):
    """Test validation rules for characteristic fields."""
    
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.manager = cls.env["res.users"].create({
            "name": "Validation Manager",
            "login": "validation.manager.test",
            "groups_id": [(6, 0, [cls.env.ref("commercial_property_management.group_property_manager").id])],
        })
        cls.property = cls.env["commercial.property"].with_user(cls.manager).create({
            "name": "Validation Test Building",
            "area": 500,
            "monthly_rent": 10000,
        })
    
    def setUp(self):
        super().setUp()
        self.unit = self.property.default_unit_id
    
    def test_negative_bedrooms_rejected(self):
        """Test that negative bedroom count is rejected."""
        from odoo.exceptions import ValidationError
        with self.assertRaises(ValidationError):
            self.unit.with_user(self.manager).bedrooms = -1
            self.unit.with_user(self.manager)._check_physical_characteristics()
    
    def test_negative_parking_rejected(self):
        """Test that negative parking count is rejected."""
        from odoo.exceptions import ValidationError
        with self.assertRaises(ValidationError):
            self.unit.with_user(self.manager).parking_spaces = -1
            self.unit.with_user(self.manager)._check_physical_characteristics()
    
    def test_negative_area_rejected(self):
        """Test that negative balcony area is rejected."""
        from odoo.exceptions import ValidationError
        with self.assertRaises(ValidationError):
            self.unit.with_user(self.manager).balcony_area_sqm = -1.0
            self.unit.with_user(self.manager)._check_physical_characteristics()
    
    def test_zero_values_accepted(self):
        """Test that zero values for numeric fields are accepted."""
        self.unit.with_user(self.manager).write({
            "bedrooms": 0,
            "bathrooms": 0,
            "parking_spaces": 0,
            "balcony_area_sqm": 0.0,
        })
        # Should not raise any exception
        self.unit.with_user(self.manager)._check_physical_characteristics()
