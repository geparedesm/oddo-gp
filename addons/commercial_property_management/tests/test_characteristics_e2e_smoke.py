"""
End-to-end smoke test for characteristics feature.
Tests the complete flow: model creation -> API response -> UI display.
Requires running Odoo instance with web interface.
"""
from odoo import fields
from odoo.tests.common import TransactionCase, HttpCase
import json


class TestCharacteristicsE2ESmokeTransactionCase(TransactionCase):
    """E2E smoke test using TransactionCase for non-HTTP flows."""
    
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.manager = cls.env["res.users"].create({
            "name": "E2E Test Manager",
            "login": "e2e.manager.test",
            "groups_id": [(6, 0, [cls.env.ref("commercial_property_management.group_property_manager").id])],
        })
        cls.property = cls.env["commercial.property"].with_user(cls.manager).create({
            "name": "E2E Test Building",
            "area": 1000,
            "monthly_rent": 50000,
            "public_name": "E2E Test Building Public",
            "public_description": "Test building for E2E validation",
            "public_monthly_rent": 52000,
            "is_published": True,
        })
    
    def test_e2e_complete_flow_create_unit_with_all_characteristics(self):
        """
        E2E smoke test: Create unit with all characteristics and verify end-to-end.
        
        Flow:
        1. Create unit with full characteristics via ORM
        2. Verify characteristics stored correctly
        3. Verify get_public_data() returns complete characteristics
        4. Verify JSON serialization works
        5. Verify search finds unit by characteristics
        """
        # Step 1: Create unit with all characteristics
        unit = self.env["commercial.property.unit"].with_user(self.manager).create({
            "property_id": self.property.id,
            "name": "E2E Test Unit",
            "area": 150,
            "monthly_rent": 2000,
            "public_name": "E2E Gorgeous Apartment",
            "public_description": "A beautiful 3BR, 2BA apartment with parking",
            "public_monthly_rent": 2100,
            "is_published": True,
            # Physical characteristics - all filled
            "bedrooms": 3,
            "bathrooms": 2,
            "half_bathrooms": 1,
            "parking_spaces": 2,
            "floor_number": 5,
            "total_floors": 15,
            "storage_rooms": 1,
            "balcony_area_sqm": 15.0,
            "furnished": True,
            "has_balcony": True,
            "has_laundry": True,
            "pet_friendly": True,
        })
        
        # Step 2: Verify storage
        self.assertEqual(unit.bedrooms, 3)
        self.assertEqual(unit.bathrooms, 2)
        self.assertEqual(unit.half_bathrooms, 1)
        self.assertEqual(unit.parking_spaces, 2)
        self.assertTrue(unit.furnished)
        self.assertTrue(unit.pet_friendly)
        
        # Step 3: Verify get_public_data() response
        public_data = unit.get_public_data()
        
        # Characteristics should be present
        self.assertIn("characteristics", public_data)
        self.assertIn("characteristics_summary", public_data)
        
        # Verify all values are in characteristics
        chars = public_data["characteristics"]
        self.assertEqual(chars["bedrooms"], 3)
        self.assertEqual(chars["bathrooms"], 2)
        self.assertEqual(chars["half_bathrooms"], 1)
        self.assertEqual(chars["parking_spaces"], 2)
        self.assertEqual(chars["floor_number"], 5)
        self.assertEqual(chars["total_floors"], 15)
        self.assertEqual(chars["storage_rooms"], 1)
        self.assertEqual(chars["balcony_area_sqm"], 15.0)
        self.assertTrue(chars["furnished"])
        self.assertTrue(chars["has_balcony"])
        self.assertTrue(chars["has_laundry"])
        self.assertTrue(chars["pet_friendly"])
        
        # Step 4: Verify JSON serialization
        json_str = json.dumps(public_data)
        self.assertIsInstance(json_str, str)
        parsed = json.loads(json_str)
        self.assertEqual(parsed["characteristics"]["bedrooms"], 3)
        
        # Step 5: Verify search/filter works
        results = self.env["commercial.property.unit"].search([
            ("property_id", "=", self.property.id),
            ("furnished", "=", True),
            ("pet_friendly", "=", True),
        ])
        self.assertIn(unit, results)
    
    def test_e2e_partial_characteristics(self):
        """
        E2E smoke test with partial characteristics.
        
        Verifies that:
        1. Empty fields are not included in get_public_data()
        2. Summary only contains non-empty fields
        3. Existing fields still work (backward compatibility)
        """
        unit = self.env["commercial.property.unit"].with_user(self.manager).create({
            "property_id": self.property.id,
            "name": "E2E Partial Unit",
            "area": 75,
            "monthly_rent": 1000,
            "public_name": "Cozy Studio",
            "public_description": "Small studio",
            "public_monthly_rent": 1050,
            "is_published": True,
            # Only some characteristics
            "bedrooms": 1,
            "bathrooms": 1,
            "furnished": False,
            # Everything else defaults to 0/False
        })
        
        public_data = unit.get_public_data()
        chars = public_data.get("characteristics", {})
        
        # Verify only non-empty are present
        self.assertIn("bedrooms", chars)
        self.assertIn("bathrooms", chars)
        self.assertNotIn("parking_spaces", chars)
        self.assertNotIn("furnished", chars)
        
        # Verify summary is correct
        summary = public_data.get("characteristics_summary", "")
        self.assertIn("1 hab.", summary)
        self.assertIn("baño", summary)
        self.assertNotIn("parking", summary)
    
    def test_e2e_unit_without_characteristics(self):
        """
        E2E smoke test: Unit without any characteristics (backward compatibility).
        
        Verifies that:
        1. Unit can still be created without characteristics
        2. get_public_data() doesn't include characteristics key if all empty
        3. Existing functionality is not broken
        """
        unit = self.env["commercial.property.unit"].with_user(self.manager).create({
            "property_id": self.property.id,
            "name": "Legacy Unit",
            "area": 100,
            "monthly_rent": 1200,
            "public_name": "Basic Unit",
            "public_description": "No frills",
            "public_monthly_rent": 1250,
            "is_published": True,
            # No characteristics specified
        })
        
        # Verify defaults
        self.assertEqual(unit.bedrooms, 0)
        self.assertFalse(unit.furnished)
        
        public_data = unit.get_public_data()
        
        # Characteristics key should NOT be present if all empty
        self.assertNotIn("characteristics", public_data)
        self.assertNotIn("characteristics_summary", public_data)
        
        # But existing fields should still be there
        self.assertIn("code", public_data)
        self.assertIn("name", public_data)
        self.assertIn("area", public_data)
        self.assertIn("features", public_data)
    
    def test_e2e_characteristics_summary_formatting(self):
        """
        E2E smoke test: Verify characteristics_summary formatting is consistent.
        
        Tests:
        1. Spanish abbreviations are used
        2. Middot separator is present
        3. Summary matches expected pattern
        4. Complex scenarios with multiple characteristics
        """
        unit = self.env["commercial.property.unit"].with_user(self.manager).create({
            "property_id": self.property.id,
            "name": "Summary Test Unit",
            "area": 200,
            "monthly_rent": 2500,
            "public_name": "Premium Apartment",
            "public_description": "Luxury living",
            "public_monthly_rent": 2600,
            "is_published": True,
            "bedrooms": 4,
            "bathrooms": 3,
            "parking_spaces": 2,
            "furnished": True,
            "pet_friendly": True,
        })
        
        public_data = unit.get_public_data()
        summary = public_data.get("characteristics_summary", "")
        
        # Verify Spanish labels
        self.assertIn("4 hab.", summary, "Should show bedroom count in Spanish")
        self.assertIn("baños", summary, "Should show bathrooms in Spanish")
        self.assertIn("2 parking", summary, "Should show parking in Spanish")
        self.assertIn("Amueblado", summary, "Should show furnished in Spanish")
        self.assertIn("Mascotas", summary, "Should show pet-friendly in Spanish")
        
        # Verify separator
        parts = summary.split(" · ")
        self.assertGreater(len(parts), 1, "Should use middot separator between fields")
        
        # Verify no trailing spaces or separators
        self.assertFalse(summary.startswith(" · "))
        self.assertFalse(summary.endswith(" · "))


class TestCharacteristicsWhatsAppIntegration(TransactionCase):
    """Test characteristics in WhatsApp message context."""
    
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.manager = cls.env["res.users"].create({
            "name": "WhatsApp Manager",
            "login": "whatsapp.manager.test",
            "groups_id": [(6, 0, [cls.env.ref("commercial_property_management.group_property_manager").id])],
        })
        cls.property = cls.env["commercial.property"].with_user(cls.manager).create({
            "name": "WhatsApp Test Building",
            "area": 800,
            "monthly_rent": 40000,
            "public_name": "WhatsApp Test Building",
            "public_description": "Building for WhatsApp messaging tests",
            "public_monthly_rent": 42000,
            "is_published": True,
        })
    
    def test_characteristics_in_public_api_response_for_whatsapp(self):
        """
        Test that get_public_data() returns characteristics in format suitable for WhatsApp.
        
        WhatsApp messages should include:
        1. Compact characteristic summary
        2. Individual characteristics dict for advanced formatting
        3. JSON-serializable format
        """
        unit = self.env["commercial.property.unit"].with_user(self.manager).create({
            "property_id": self.property.id,
            "name": "WhatsApp Unit",
            "area": 120,
            "monthly_rent": 1800,
            "public_name": "Beautiful 2BR",
            "public_description": "Spacious apartment with parking",
            "public_monthly_rent": 1900,
            "is_published": True,
            "bedrooms": 2,
            "bathrooms": 2,
            "parking_spaces": 1,
            "furnished": True,
            "pet_friendly": False,
        })
        
        public_data = unit.get_public_data()
        
        # Verify data is suitable for WhatsApp message
        # 1. Has compact summary for quick display
        self.assertIn("characteristics_summary", public_data)
        summary = public_data["characteristics_summary"]
        # Summary should be concise (typically < 100 chars)
        self.assertLess(len(summary), 100, "Summary should be concise for WhatsApp")
        
        # 2. Has structured characteristics for detailed info
        self.assertIn("characteristics", public_data)
        
        # 3. JSON-serializable
        json_str = json.dumps(public_data)
        self.assertIsInstance(json_str, str)
        
        # 4. Can be embedded in message template
        message_template = f"""
*{public_data['name']}*
{public_data['description']}
💰 {public_data['monthly_rent']} {public_data['currency']}
📏 {public_data['area']}m²
{summary}
"""
        self.assertIn("2 hab.", message_template)
        self.assertIn("2 baños", message_template)
