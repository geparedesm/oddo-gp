"""
Test for get_public_data() characteristics extension.
"""
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestGetPublicDataCharacteristics(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.property_model = cls.env['commercial.property']
        cls.unit_model = cls.env['commercial.property.unit']
        
        # Create a test property
        cls.property = cls.property_model.create({
            'name': 'Test Building',
            'address': 'Test Address',
            'property_type': 'apartment',
        })
    
    def test_get_public_data_no_characteristics(self):
        """Test that get_public_data() doesn't include empty characteristics."""
        unit = self.unit_model.create({
            'property_id': self.property.id,
            'name': 'Unit A',
            'area': 100.0,
            'code': 'TEST-A',
            'bedrooms': 0,
            'bathrooms': 0,
            'furnished': False,
            # All characteristics empty
        })
        
        public_data = unit.get_public_data()
        
        # characteristics key should not be present if all values are empty
        self.assertNotIn('characteristics', public_data, 
                         "characteristics should not be present when all fields are empty")
        self.assertNotIn('characteristics_summary', public_data,
                         "characteristics_summary should not be present when all fields are empty")
    
    def test_get_public_data_with_characteristics(self):
        """Test that get_public_data() includes non-empty characteristics."""
        unit = self.unit_model.create({
            'property_id': self.property.id,
            'name': 'Unit B',
            'area': 150.0,
            'code': 'TEST-B',
            'bedrooms': 2,
            'bathrooms': 1,
            'half_bathrooms': 1,
            'parking_spaces': 2,
            'furnished': True,
            'pet_friendly': True,
        })
        
        public_data = unit.get_public_data()
        
        # characteristics key should be present
        self.assertIn('characteristics', public_data,
                     "characteristics key should be present when fields are set")
        self.assertIn('characteristics_summary', public_data,
                     "characteristics_summary key should be present when fields are set")
        
        chars = public_data['characteristics']
        
        # Verify non-empty values are included
        self.assertEqual(chars['bedrooms'], 2)
        self.assertEqual(chars['bathrooms'], 1)
        self.assertEqual(chars['half_bathrooms'], 1)
        self.assertEqual(chars['parking_spaces'], 2)
        self.assertTrue(chars['furnished'])
        self.assertTrue(chars['pet_friendly'])
        
        # Verify empty values are not included
        self.assertNotIn('has_balcony', chars, "has_balcony should not be present if False")
        self.assertNotIn('has_laundry', chars, "has_laundry should not be present if False")
    
    def test_characteristics_summary_format(self):
        """Test that characteristics_summary generates correct format."""
        unit = self.unit_model.create({
            'property_id': self.property.id,
            'name': 'Unit C',
            'area': 200.0,
            'code': 'TEST-C',
            'bedrooms': 2,
            'bathrooms': 2,
            'parking_spaces': 1,
            'furnished': True,
        })
        
        public_data = unit.get_public_data()
        summary = public_data['characteristics_summary']
        
        # Verify summary contains expected elements (in Spanish)
        self.assertIn('2 hab.', summary, "Summary should contain bedrooms")
        self.assertIn('2 baños', summary, "Summary should contain bathrooms")
        self.assertIn('1 parking', summary, "Summary should contain parking")
        self.assertIn('Amueblado', summary, "Summary should contain furnished indicator")
        
        # Verify separator is used
        self.assertIn('·', summary, "Summary should use middot separator")
    
    def test_get_public_data_json_serializable(self):
        """Test that get_public_data() returns JSON-serializable data."""
        import json
        
        unit = self.unit_model.create({
            'property_id': self.property.id,
            'name': 'Unit D',
            'area': 175.0,
            'code': 'TEST-D',
            'bedrooms': 1,
            'bathrooms': 1,
            'balcony_area_sqm': 5.5,
        })
        
        public_data = unit.get_public_data()
        
        # This should not raise an exception
        json_str = json.dumps(public_data)
        self.assertIsInstance(json_str, str)
        
        # Verify we can parse it back
        parsed = json.loads(json_str)
        self.assertIsInstance(parsed, dict)
    
    def test_existing_fields_unchanged(self):
        """Test that existing get_public_data() fields are unchanged."""
        unit = self.unit_model.create({
            'property_id': self.property.id,
            'name': 'Unit E',
            'area': 120.0,
            'code': 'TEST-E',
            'public_name': 'Beautiful Unit',
            'public_description': 'A nice unit',
        })
        
        public_data = unit.get_public_data()
        
        # Verify existing fields are present and unchanged
        self.assertIn('code', public_data)
        self.assertEqual(public_data['code'], 'TEST-E')
        self.assertIn('name', public_data)
        self.assertEqual(public_data['name'], 'Beautiful Unit')
        self.assertIn('area', public_data)
        self.assertEqual(public_data['area'], 120.0)
        self.assertIn('currency', public_data)
        self.assertIn('city', public_data)
