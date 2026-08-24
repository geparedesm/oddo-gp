"""Unit tests for commercial property unit physical characteristics and validations."""
from odoo import fields
from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase


class TestCommercialPropertyUnitCharacteristics(TransactionCase):
    """Test suite for physical characteristic fields on commercial.property.unit model."""

    def setUp(self):
        """Set up test data: property manager, property, and unit."""
        super().setUp()
        self.today = fields.Date.today()
        self.manager = self.env["res.users"].create(
            {
                "name": "Property Manager",
                "login": "property.manager.test",
                "email": "property.manager.test@example.com",
                "company_id": self.env.company.id,
                "company_ids": [(6, 0, self.env.company.ids)],
                "groups_id": [
                    (
                        6,
                        0,
                        [
                            self.env.ref(
                                "commercial_property_management.group_property_manager"
                            ).id
                        ],
                    )
                ],
            }
        )
        # Create a test property
        self.property = self.env["commercial.property"].with_user(self.manager).create(
            {
                "name": "Test Building",
                "area": 500,
                "monthly_rent": 10000,
            }
        )
        # Use the default unit created with the property
        self.unit = self.property.default_unit_id

    def test_characteristic_fields_exist(self):
        """Verify all 12 physical characteristic fields exist and are accessible."""
        characteristic_fields = [
            "bedrooms",
            "bathrooms",
            "half_bathrooms",
            "parking_spaces",
            "floor_number",
            "total_floors",
            "storage_rooms",
            "balcony_area_sqm",
            "furnished",
            "has_balcony",
            "has_laundry",
            "pet_friendly",
        ]

        # Check that all fields exist in the model
        model_fields = self.env["commercial.property.unit"].fields_get(
            characteristic_fields
        )
        for field_name in characteristic_fields:
            self.assertIn(
                field_name,
                model_fields,
                f"Field '{field_name}' not found in model metadata",
            )

    def test_characteristic_fields_readable_writable(self):
        """Test that all characteristic fields are readable and writable."""
        # Test with property manager
        self.unit.with_user(self.manager).bedrooms = 2
        self.assertEqual(self.unit.bedrooms, 2)

        self.unit.with_user(self.manager).bathrooms = 1
        self.assertEqual(self.unit.bathrooms, 1)

        self.unit.with_user(self.manager).has_balcony = True
        self.assertTrue(self.unit.has_balcony)

    def test_characteristics_default_values(self):
        """Test that default values for characteristic fields are correct."""
        # Create a new unit without specifying characteristics
        new_unit = self.env["commercial.property.unit"].with_user(self.manager).create(
            {
                "property_id": self.property.id,
                "name": "Unit with Defaults",
                "area": 50,
                "monthly_rent": 1000,
            }
        )

        # Verify numeric fields default to 0
        self.assertEqual(new_unit.bedrooms, 0)
        self.assertEqual(new_unit.bathrooms, 0)
        self.assertEqual(new_unit.half_bathrooms, 0)
        self.assertEqual(new_unit.parking_spaces, 0)
        self.assertEqual(new_unit.floor_number, 0)
        self.assertEqual(new_unit.total_floors, 0)
        self.assertEqual(new_unit.storage_rooms, 0)
        self.assertEqual(new_unit.balcony_area_sqm, 0.0)

        # Verify boolean fields default to False
        self.assertFalse(new_unit.furnished)
        self.assertFalse(new_unit.has_balcony)
        self.assertFalse(new_unit.has_laundry)
        self.assertFalse(new_unit.pet_friendly)

    def test_characteristic_field_types(self):
        """Test that characteristic fields have correct field types."""
        model = self.env["commercial.property.unit"]

        # Integer fields
        self.assertEqual(model._fields["bedrooms"].type, "integer")
        self.assertEqual(model._fields["bathrooms"].type, "integer")
        self.assertEqual(model._fields["half_bathrooms"].type, "integer")
        self.assertEqual(model._fields["parking_spaces"].type, "integer")
        self.assertEqual(model._fields["floor_number"].type, "integer")
        self.assertEqual(model._fields["total_floors"].type, "integer")
        self.assertEqual(model._fields["storage_rooms"].type, "integer")

        # Float field
        self.assertEqual(model._fields["balcony_area_sqm"].type, "float")

        # Boolean fields
        self.assertEqual(model._fields["furnished"].type, "boolean")
        self.assertEqual(model._fields["has_balcony"].type, "boolean")
        self.assertEqual(model._fields["has_laundry"].type, "boolean")
        self.assertEqual(model._fields["pet_friendly"].type, "boolean")

    def test_negative_bedrooms_rejected_on_create(self):
        """Test that creating a unit with negative bedrooms raises ValidationError."""
        with self.assertRaises(ValidationError) as cm:
            self.env["commercial.property.unit"].with_user(self.manager).create(
                {
                    "property_id": self.property.id,
                    "name": "Negative Bedroom Unit",
                    "area": 50,
                    "monthly_rent": 1000,
                    "bedrooms": -1,
                }
            )
        self.assertIn("bedroom", str(cm.exception).lower())

    def test_negative_bathrooms_rejected_on_create(self):
        """Test that creating a unit with negative bathrooms raises ValidationError."""
        with self.assertRaises(ValidationError) as cm:
            self.env["commercial.property.unit"].with_user(self.manager).create(
                {
                    "property_id": self.property.id,
                    "name": "Negative Bathroom Unit",
                    "area": 50,
                    "monthly_rent": 1000,
                    "bathrooms": -1,
                }
            )
        self.assertIn("bathroom", str(cm.exception).lower())

    def test_negative_half_bathrooms_rejected_on_create(self):
        """Test that creating a unit with negative half bathrooms raises ValidationError."""
        with self.assertRaises(ValidationError) as cm:
            self.env["commercial.property.unit"].with_user(self.manager).create(
                {
                    "property_id": self.property.id,
                    "name": "Negative Half Bathroom Unit",
                    "area": 50,
                    "monthly_rent": 1000,
                    "half_bathrooms": -1,
                }
            )
        self.assertIn("half", str(cm.exception).lower())

    def test_negative_parking_spaces_rejected_on_create(self):
        """Test that creating a unit with negative parking spaces raises ValidationError."""
        with self.assertRaises(ValidationError) as cm:
            self.env["commercial.property.unit"].with_user(self.manager).create(
                {
                    "property_id": self.property.id,
                    "name": "Negative Parking Unit",
                    "area": 50,
                    "monthly_rent": 1000,
                    "parking_spaces": -1,
                }
            )
        self.assertIn("parking", str(cm.exception).lower())

    def test_negative_floor_number_rejected_on_create(self):
        """Test that creating a unit with negative floor number raises ValidationError."""
        with self.assertRaises(ValidationError) as cm:
            self.env["commercial.property.unit"].with_user(self.manager).create(
                {
                    "property_id": self.property.id,
                    "name": "Negative Floor Unit",
                    "area": 50,
                    "monthly_rent": 1000,
                    "floor_number": -1,
                }
            )
        self.assertIn("floor", str(cm.exception).lower())

    def test_negative_total_floors_rejected_on_create(self):
        """Test that creating a unit with negative total floors raises ValidationError."""
        with self.assertRaises(ValidationError) as cm:
            self.env["commercial.property.unit"].with_user(self.manager).create(
                {
                    "property_id": self.property.id,
                    "name": "Negative Total Floors Unit",
                    "area": 50,
                    "monthly_rent": 1000,
                    "total_floors": -1,
                }
            )
        self.assertIn("total", str(cm.exception).lower())

    def test_negative_storage_rooms_rejected_on_create(self):
        """Test that creating a unit with negative storage rooms raises ValidationError."""
        with self.assertRaises(ValidationError) as cm:
            self.env["commercial.property.unit"].with_user(self.manager).create(
                {
                    "property_id": self.property.id,
                    "name": "Negative Storage Unit",
                    "area": 50,
                    "monthly_rent": 1000,
                    "storage_rooms": -1,
                }
            )
        self.assertIn("storage", str(cm.exception).lower())

    def test_negative_balcony_area_rejected_on_create(self):
        """Test that creating a unit with negative balcony area raises ValidationError."""
        with self.assertRaises(ValidationError) as cm:
            self.env["commercial.property.unit"].with_user(self.manager).create(
                {
                    "property_id": self.property.id,
                    "name": "Negative Balcony Unit",
                    "area": 50,
                    "monthly_rent": 1000,
                    "balcony_area_sqm": -1.5,
                }
            )
        self.assertIn("balcony", str(cm.exception).lower())

    def test_negative_bedrooms_rejected_on_write(self):
        """Test that updating a unit with negative bedrooms raises ValidationError."""
        with self.assertRaises(ValidationError) as cm:
            self.unit.with_user(self.manager).bedrooms = -1
        self.assertIn("bedroom", str(cm.exception).lower())

    def test_negative_bathrooms_rejected_on_write(self):
        """Test that updating a unit with negative bathrooms raises ValidationError."""
        with self.assertRaises(ValidationError) as cm:
            self.unit.with_user(self.manager).bathrooms = -1
        self.assertIn("bathroom", str(cm.exception).lower())

    def test_negative_half_bathrooms_rejected_on_write(self):
        """Test that updating a unit with negative half bathrooms raises ValidationError."""
        with self.assertRaises(ValidationError) as cm:
            self.unit.with_user(self.manager).half_bathrooms = -1
        self.assertIn("half", str(cm.exception).lower())

    def test_negative_parking_spaces_rejected_on_write(self):
        """Test that updating a unit with negative parking spaces raises ValidationError."""
        with self.assertRaises(ValidationError) as cm:
            self.unit.with_user(self.manager).parking_spaces = -1
        self.assertIn("parking", str(cm.exception).lower())

    def test_negative_floor_number_rejected_on_write(self):
        """Test that updating a unit with negative floor number raises ValidationError."""
        with self.assertRaises(ValidationError) as cm:
            self.unit.with_user(self.manager).floor_number = -1
        self.assertIn("floor", str(cm.exception).lower())

    def test_negative_total_floors_rejected_on_write(self):
        """Test that updating a unit with negative total floors raises ValidationError."""
        with self.assertRaises(ValidationError) as cm:
            self.unit.with_user(self.manager).total_floors = -1
        self.assertIn("total", str(cm.exception).lower())

    def test_negative_storage_rooms_rejected_on_write(self):
        """Test that updating a unit with negative storage rooms raises ValidationError."""
        with self.assertRaises(ValidationError) as cm:
            self.unit.with_user(self.manager).storage_rooms = -1
        self.assertIn("storage", str(cm.exception).lower())

    def test_negative_balcony_area_rejected_on_write(self):
        """Test that updating a unit with negative balcony area raises ValidationError."""
        with self.assertRaises(ValidationError) as cm:
            self.unit.with_user(self.manager).balcony_area_sqm = -1.5
        self.assertIn("balcony", str(cm.exception).lower())

    def test_zero_values_accepted(self):
        """Test that zero values are accepted for all numeric characteristic fields."""
        # Create a unit with all zero values
        unit = self.env["commercial.property.unit"].with_user(self.manager).create(
            {
                "property_id": self.property.id,
                "name": "Unit with Zeros",
                "area": 50,
                "monthly_rent": 1000,
                "bedrooms": 0,
                "bathrooms": 0,
                "half_bathrooms": 0,
                "parking_spaces": 0,
                "floor_number": 0,
                "total_floors": 0,
                "storage_rooms": 0,
                "balcony_area_sqm": 0.0,
            }
        )
        # Verify they were created without error
        self.assertEqual(unit.bedrooms, 0)
        self.assertEqual(unit.bathrooms, 0)
        self.assertEqual(unit.half_bathrooms, 0)
        self.assertEqual(unit.parking_spaces, 0)
        self.assertEqual(unit.floor_number, 0)
        self.assertEqual(unit.total_floors, 0)
        self.assertEqual(unit.storage_rooms, 0)
        self.assertEqual(unit.balcony_area_sqm, 0.0)

    def test_positive_values_accepted(self):
        """Test that positive values are accepted for all numeric characteristic fields."""
        # Create a unit with positive values
        unit = self.env["commercial.property.unit"].with_user(self.manager).create(
            {
                "property_id": self.property.id,
                "name": "Unit with Positive Values",
                "area": 100,
                "monthly_rent": 2000,
                "bedrooms": 3,
                "bathrooms": 2,
                "half_bathrooms": 1,
                "parking_spaces": 2,
                "floor_number": 5,
                "total_floors": 10,
                "storage_rooms": 1,
                "balcony_area_sqm": 15.5,
            }
        )
        # Verify they were created correctly
        self.assertEqual(unit.bedrooms, 3)
        self.assertEqual(unit.bathrooms, 2)
        self.assertEqual(unit.half_bathrooms, 1)
        self.assertEqual(unit.parking_spaces, 2)
        self.assertEqual(unit.floor_number, 5)
        self.assertEqual(unit.total_floors, 10)
        self.assertEqual(unit.storage_rooms, 1)
        self.assertEqual(unit.balcony_area_sqm, 15.5)

    def test_create_unit_with_all_characteristics(self):
        """Test creating a unit with all characteristics specified."""
        unit = self.env["commercial.property.unit"].with_user(self.manager).create(
            {
                "property_id": self.property.id,
                "name": "Fully Described Unit",
                "area": 150,
                "monthly_rent": 3000,
                "bedrooms": 4,
                "bathrooms": 3,
                "half_bathrooms": 1,
                "parking_spaces": 3,
                "floor_number": 8,
                "total_floors": 20,
                "storage_rooms": 2,
                "balcony_area_sqm": 25.0,
                "furnished": True,
                "has_balcony": True,
                "has_laundry": True,
                "pet_friendly": True,
            }
        )

        # Verify all characteristics are stored correctly
        self.assertEqual(unit.name, "Fully Described Unit")
        self.assertEqual(unit.bedrooms, 4)
        self.assertEqual(unit.bathrooms, 3)
        self.assertEqual(unit.half_bathrooms, 1)
        self.assertEqual(unit.parking_spaces, 3)
        self.assertEqual(unit.floor_number, 8)
        self.assertEqual(unit.total_floors, 20)
        self.assertEqual(unit.storage_rooms, 2)
        self.assertEqual(unit.balcony_area_sqm, 25.0)
        self.assertTrue(unit.furnished)
        self.assertTrue(unit.has_balcony)
        self.assertTrue(unit.has_laundry)
        self.assertTrue(unit.pet_friendly)

    def test_update_characteristics_on_existing_unit(self):
        """Test updating characteristic fields on an existing unit."""
        # Start with default values
        self.assertEqual(self.unit.bedrooms, 0)
        self.assertEqual(self.unit.bathrooms, 0)

        # Update via write
        self.unit.with_user(self.manager).write(
            {
                "bedrooms": 2,
                "bathrooms": 1,
                "has_balcony": True,
                "balcony_area_sqm": 12.5,
            }
        )

        # Verify updates
        self.assertEqual(self.unit.bedrooms, 2)
        self.assertEqual(self.unit.bathrooms, 1)
        self.assertTrue(self.unit.has_balcony)
        self.assertEqual(self.unit.balcony_area_sqm, 12.5)

    def test_search_by_bedrooms(self):
        """Test filtering/searching units by bedroom count."""
        # Create units with different bedroom counts
        unit_2bed = self.env["commercial.property.unit"].with_user(self.manager).create(
            {
                "property_id": self.property.id,
                "name": "2-Bedroom Unit",
                "area": 75,
                "monthly_rent": 1500,
                "bedrooms": 2,
            }
        )
        unit_3bed = self.env["commercial.property.unit"].with_user(self.manager).create(
            {
                "property_id": self.property.id,
                "name": "3-Bedroom Unit",
                "area": 100,
                "monthly_rent": 2000,
                "bedrooms": 3,
            }
        )

        # Search for 2-bedroom units
        two_bed_units = self.env["commercial.property.unit"].search(
            [("bedrooms", "=", 2)]
        )
        self.assertIn(unit_2bed, two_bed_units)
        self.assertNotIn(unit_3bed, two_bed_units)

    def test_search_by_pet_friendly(self):
        """Test filtering/searching units by pet_friendly flag."""
        # Create units with and without pet friendly
        unit_pet_friendly = self.env["commercial.property.unit"].with_user(
            self.manager
        ).create(
            {
                "property_id": self.property.id,
                "name": "Pet Friendly Unit",
                "area": 50,
                "monthly_rent": 1000,
                "pet_friendly": True,
            }
        )
        unit_no_pets = self.env["commercial.property.unit"].with_user(
            self.manager
        ).create(
            {
                "property_id": self.property.id,
                "name": "No Pets Unit",
                "area": 50,
                "monthly_rent": 1000,
                "pet_friendly": False,
            }
        )

        # Search for pet-friendly units
        pet_units = self.env["commercial.property.unit"].search(
            [("pet_friendly", "=", True)]
        )
        self.assertIn(unit_pet_friendly, pet_units)
        self.assertNotIn(unit_no_pets, pet_units)

    def test_search_by_furnished_status(self):
        """Test filtering/searching units by furnished status."""
        # Create furnished and unfurnished units
        unit_furnished = self.env["commercial.property.unit"].with_user(
            self.manager
        ).create(
            {
                "property_id": self.property.id,
                "name": "Furnished Unit",
                "area": 60,
                "monthly_rent": 1200,
                "furnished": True,
            }
        )
        unit_unfurnished = self.env["commercial.property.unit"].with_user(
            self.manager
        ).create(
            {
                "property_id": self.property.id,
                "name": "Unfurnished Unit",
                "area": 60,
                "monthly_rent": 1200,
                "furnished": False,
            }
        )

        # Search for furnished units
        furnished_units = self.env["commercial.property.unit"].search(
            [("furnished", "=", True)]
        )
        self.assertIn(unit_furnished, furnished_units)
        self.assertNotIn(unit_unfurnished, furnished_units)

    def test_search_by_balcony_area_range(self):
        """Test filtering/searching units by balcony area range."""
        # Create units with different balcony areas
        unit_small_balcony = self.env["commercial.property.unit"].with_user(
            self.manager
        ).create(
            {
                "property_id": self.property.id,
                "name": "Small Balcony Unit",
                "area": 70,
                "monthly_rent": 1400,
                "balcony_area_sqm": 5.0,
            }
        )
        unit_large_balcony = self.env["commercial.property.unit"].with_user(
            self.manager
        ).create(
            {
                "property_id": self.property.id,
                "name": "Large Balcony Unit",
                "area": 100,
                "monthly_rent": 2000,
                "balcony_area_sqm": 30.0,
            }
        )

        # Search for units with balcony area >= 10
        large_balcony_units = self.env["commercial.property.unit"].search(
            [("balcony_area_sqm", ">=", 10.0)]
        )
        self.assertIn(unit_large_balcony, large_balcony_units)
        self.assertNotIn(unit_small_balcony, large_balcony_units)

    def test_multiple_characteristic_constraints_simultaneously(self):
        """Test that constraint validation works with multiple negative fields."""
        # Try to create with multiple negative values
        with self.assertRaises(ValidationError):
            self.env["commercial.property.unit"].with_user(self.manager).create(
                {
                    "property_id": self.property.id,
                    "name": "Multiple Negatives Unit",
                    "area": 50,
                    "monthly_rent": 1000,
                    "bedrooms": -1,
                    "bathrooms": -2,
                    "parking_spaces": -1,
                }
            )

    def test_characteristic_fields_with_write_batch(self):
        """Test updating multiple units' characteristics in batch."""
        # Create multiple units
        units_list = [
            self.env["commercial.property.unit"].with_user(self.manager).create(
                {
                    "property_id": self.property.id,
                    "name": f"Unit {i}",
                    "area": 50,
                    "monthly_rent": 1000,
                }
            )
            for i in range(3)
        ]

        # Convert list to recordset
        units = self.env["commercial.property.unit"].browse(
            [unit.id for unit in units_list]
        )

        # Batch update all units
        units.write({"bedrooms": 2, "bathrooms": 1})

        # Verify all units were updated
        for unit in units:
            self.assertEqual(unit.bedrooms, 2)
            self.assertEqual(unit.bathrooms, 1)

    def test_float_precision_for_balcony_area(self):
        """Test that balcony area float field maintains precision."""
        unit = self.env["commercial.property.unit"].with_user(self.manager).create(
            {
                "property_id": self.property.id,
                "name": "Precision Test Unit",
                "area": 80,
                "monthly_rent": 1600,
                "balcony_area_sqm": 12.75,
            }
        )
        # Verify precision is maintained (digits=(16, 2))
        self.assertAlmostEqual(unit.balcony_area_sqm, 12.75, places=2)

    def test_large_values_accepted(self):
        """Test that large positive values are accepted (boundary test)."""
        unit = self.env["commercial.property.unit"].with_user(self.manager).create(
            {
                "property_id": self.property.id,
                "name": "Large Values Unit",
                "area": 5000,
                "monthly_rent": 100000,
                "bedrooms": 50,
                "bathrooms": 25,
                "parking_spaces": 100,
                "floor_number": 99,
                "total_floors": 150,
                "storage_rooms": 20,
                "balcony_area_sqm": 999.99,
            }
        )
        # Verify large values are stored correctly
        self.assertEqual(unit.bedrooms, 50)
        self.assertEqual(unit.bathrooms, 25)
        self.assertEqual(unit.parking_spaces, 100)
        self.assertEqual(unit.floor_number, 99)
        self.assertEqual(unit.total_floors, 150)
        self.assertEqual(unit.storage_rooms, 20)
        self.assertEqual(unit.balcony_area_sqm, 999.99)

    def test_constraint_method_exists(self):
        """Test that the _check_physical_characteristics constraint method exists."""
        model = self.env["commercial.property.unit"]
        self.assertTrue(
            hasattr(model, "_check_physical_characteristics"),
            "_check_physical_characteristics method not found on model",
        )
