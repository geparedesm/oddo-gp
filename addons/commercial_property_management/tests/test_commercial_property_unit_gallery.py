import base64
import io

from PIL import Image as PILImage

from odoo import fields
from odoo.tests.common import TransactionCase


class TestCommercialPropertyUnitImage(TransactionCase):
    def setUp(self):
        super().setUp()
        self.today = fields.Date.today()
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
        # Create a property and unit for testing
        self.property = self.env["commercial.property"].with_user(self.manager).create(
            {
                "name": "Test Building",
                "area": 500,
                "monthly_rent": 10000,
            }
        )
        self.unit = self.property.default_unit_id

    def test_create_unit_image(self):
        """Test creating an image for a unit"""
        # Create a dummy image
        dummy_image = base64.b64encode(b"GIF89a\x01\x00\x01\x00\x00\x00\x00\x21\xf9\x04\x01\n\x00\x01\x00,\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;")
        
        image_record = self.env["commercial.property.unit.image"].with_user(self.manager).create(
            {
                "unit_id": self.unit.id,
                "image_1920": dummy_image,
                "sequence": 10,
                "name": "Main Photo",
            }
        )
        
        self.assertEqual(image_record.unit_id, self.unit)
        self.assertEqual(image_record.sequence, 10)
        self.assertEqual(image_record.name, "Main Photo")
        self.assertEqual(image_record.image_1920, dummy_image)

    def test_unit_image_ids_one2many(self):
        """Test that unit.image_ids one2many field works"""
        dummy_image = base64.b64encode(b"GIF89a\x01\x00\x01\x00\x00\x00\x00\x21\xf9\x04\x01\n\x00\x01\x00,\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;")
        
        # Create multiple images
        img1 = self.env["commercial.property.unit.image"].with_user(self.manager).create(
            {
                "unit_id": self.unit.id,
                "image_1920": dummy_image,
                "sequence": 10,
                "name": "Image 1",
            }
        )
        img2 = self.env["commercial.property.unit.image"].with_user(self.manager).create(
            {
                "unit_id": self.unit.id,
                "image_1920": dummy_image,
                "sequence": 20,
                "name": "Image 2",
            }
        )
        
        # Check that unit.image_ids contains both images
        self.unit.invalidate_cache()
        self.assertEqual(len(self.unit.image_ids), 2)
        sorted_images = self.unit.image_ids.sorted("sequence")
        self.assertEqual(sorted_images[0], img1)
        self.assertEqual(sorted_images[1], img2)

    def test_primary_image_compute(self):
        """Test that image_1920 computed field returns first image"""
        dummy_image = base64.b64encode(b"GIF89a\x01\x00\x01\x00\x00\x00\x00\x21\xf9\x04\x01\n\x00\x01\x00,\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;")
        
        # Create first image
        img1 = self.env["commercial.property.unit.image"].with_user(self.manager).create(
            {
                "unit_id": self.unit.id,
                "image_1920": dummy_image,
                "sequence": 10,
            }
        )
        
        # Refresh and check
        self.unit.invalidate_cache()
        self.assertEqual(self.unit.image_1920, dummy_image)

    def test_get_public_data_photo_urls(self):
        """Test that get_public_data returns photo_urls"""
        dummy_image = base64.b64encode(b"GIF89a\x01\x00\x01\x00\x00\x00\x00\x21\xf9\x04\x01\n\x00\x01\x00,\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;")
        
        # Set up required public fields
        self.unit.write({
            "public_name": "Test Unit",
            "public_description": "A test unit",
            "public_monthly_rent": 5000,
            "public_feature_ids": False,
            "public_location_hint": "Downtown",
            "virtual_tour_url": "https://example.com/tour",
        })
        
        # Create images
        self.env["commercial.property.unit.image"].with_user(self.manager).create(
            {
                "unit_id": self.unit.id,
                "image_1920": dummy_image,
                "sequence": 10,
            }
        )
        self.env["commercial.property.unit.image"].with_user(self.manager).create(
            {
                "unit_id": self.unit.id,
                "image_1920": dummy_image,
                "sequence": 20,
            }
        )
        
        public_data = self.unit.get_public_data()
        self.assertIn("photo_urls", public_data)
        self.assertEqual(len(public_data["photo_urls"]), 2)
        # Verify photo_url still works for backward compatibility
        self.assertIn("photo_url", public_data)

    def test_acl_manager_permissions(self):
        """Test that managers can create, read, write, and delete images"""
        dummy_image = base64.b64encode(b"GIF89a\x01\x00\x01\x00\x00\x00\x00\x21\xf9\x04\x01\n\x00\x01\x00,\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;")
        
        # Manager should be able to create
        img = self.env["commercial.property.unit.image"].with_user(self.manager).create(
            {
                "unit_id": self.unit.id,
                "image_1920": dummy_image,
                "sequence": 10,
            }
        )
        
        # Manager should be able to read
        read_img = self.env["commercial.property.unit.image"].with_user(self.manager).browse(img.id)
        self.assertTrue(read_img.exists())
        
        # Manager should be able to write
        read_img.with_user(self.manager).write({"sequence": 20})
        self.assertEqual(read_img.sequence, 20)
        
        # Manager should be able to delete
        read_img.with_user(self.manager).unlink()
        self.assertFalse(read_img.exists())

    def test_acl_user_permissions(self):
        """Test that regular users can only read images"""
        dummy_image = base64.b64encode(b"GIF89a\x01\x00\x01\x00\x00\x00\x00\x21\xf9\x04\x01\n\x00\x01\x00,\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;")
        
        # Manager creates image
        img = self.env["commercial.property.unit.image"].with_user(self.manager).create(
            {
                "unit_id": self.unit.id,
                "image_1920": dummy_image,
                "sequence": 10,
            }
        )
        
        # User should be able to read
        read_img = self.env["commercial.property.unit.image"].with_user(self.user).browse(img.id)
        self.assertTrue(read_img.exists())

    def test_migrate_images_to_gallery_basic(self):
        """Test that _migrate_images_to_gallery migrates existing images"""
        dummy_image = base64.b64encode(b"GIF89a\x01\x00\x01\x00\x00\x00\x00!\xf9\x04\x01\n\x00\x01\x00,\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;")
        
        # Create a second unit and set image_1920 directly on it
        unit2 = self.env["commercial.property.unit"].with_user(self.manager).create(
            {
                "property_id": self.property.id,
                "name": "Unit 2",
                "area": 100,
                "monthly_rent": 2000,
                "image_1920": dummy_image,
            }
        )
        
        # Verify unit has no gallery images yet
        self.assertEqual(len(unit2.image_ids), 0)
        
        # Run migration
        result = self.env["commercial.property.unit"]._migrate_images_to_gallery()
        self.assertTrue(result)
        
        # Refresh unit
        unit2.invalidate_cache()
        
        # Check that image was migrated
        self.assertEqual(len(unit2.image_ids), 1)
        migrated_image = unit2.image_ids[0]
        self.assertEqual(migrated_image.image_1920, dummy_image)
        self.assertEqual(migrated_image.sequence, 10)
        self.assertEqual(migrated_image.name, "Migrated image")

    def test_migrate_images_to_gallery_idempotent(self):
        """Test that migration is idempotent (safe to run multiple times)"""
        dummy_image = base64.b64encode(b"GIF89a\x01\x00\x01\x00\x00\x00\x00!\xf9\x04\x01\n\x00\x01\x00,\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;")
        
        # Create a unit with image
        unit3 = self.env["commercial.property.unit"].with_user(self.manager).create(
            {
                "property_id": self.property.id,
                "name": "Unit 3",
                "area": 100,
                "monthly_rent": 2000,
                "image_1920": dummy_image,
            }
        )
        
        # Run migration first time
        self.env["commercial.property.unit"]._migrate_images_to_gallery()
        unit3.invalidate_cache()
        self.assertEqual(len(unit3.image_ids), 1)
        
        # Run migration second time
        self.env["commercial.property.unit"]._migrate_images_to_gallery()
        unit3.invalidate_cache()
        
        # Should still have only one image (idempotent)
        self.assertEqual(len(unit3.image_ids), 1)

    def test_migrate_images_skips_units_without_images(self):
        """Test that units without image_1920 are not affected"""
        # Create a unit without image
        unit4 = self.env["commercial.property.unit"].with_user(self.manager).create(
            {
                "property_id": self.property.id,
                "name": "Unit 4",
                "area": 100,
                "monthly_rent": 2000,
            }
        )
        
        # Run migration
        self.env["commercial.property.unit"]._migrate_images_to_gallery()
        unit4.invalidate_cache()
        
        # Should still have no images
        self.assertEqual(len(unit4.image_ids), 0)

    def test_migrate_images_skips_units_with_existing_gallery_images(self):
        """Test that units with existing gallery images are not affected"""
        dummy_image = base64.b64encode(b"GIF89a\x01\x00\x01\x00\x00\x00\x00!\xf9\x04\x01\n\x00\x01\x00,\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;")
        
        # Create a unit with both primary image and gallery image
        unit5 = self.env["commercial.property.unit"].with_user(self.manager).create(
            {
                "property_id": self.property.id,
                "name": "Unit 5",
                "area": 100,
                "monthly_rent": 2000,
                "image_1920": dummy_image,
            }
        )
        
        # Create a gallery image with sequence 5 (which will be first)
        img = self.env["commercial.property.unit.image"].with_user(self.manager).create(
            {
                "unit_id": unit5.id,
                "image_1920": dummy_image,
                "sequence": 5,
                "name": "Existing Gallery Image",
            }
        )
        
        self.assertEqual(len(unit5.image_ids), 1)
        
        # Run migration
        self.env["commercial.property.unit"]._migrate_images_to_gallery()
        unit5.invalidate_cache()
        
        # Should still have only one image (the existing one)
        self.assertEqual(len(unit5.image_ids), 1)
        self.assertEqual(unit5.image_ids[0].id, img.id)

    @staticmethod
    def _make_large_png(size=(1920, 1920)):
        """Build a synthetic PNG large enough to trigger compression
        (random-ish content so PNG's own compression can't shrink it much
        on its own, unlike solid-color images)."""
        import random

        random.seed(42)
        img = PILImage.new("RGB", size)
        pixels = img.load()
        for x in range(0, size[0], 4):
            for y in range(0, size[1], 4):
                color = (random.randint(0, 255), random.randint(0, 255), random.randint(0, 255))
                for dx in range(4):
                    for dy in range(4):
                        if x + dx < size[0] and y + dy < size[1]:
                            pixels[x + dx, y + dy] = color
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return base64.b64encode(buf.getvalue())

    def test_create_large_image_is_compressed(self):
        """Creating a gallery image with a large synthetic PNG results in a
        smaller stored byte size."""
        large_image = self._make_large_png()
        original_size = len(base64.b64decode(large_image))
        # Sanity check the fixture is actually above the compression
        # threshold so the test is meaningful.
        self.assertGreater(
            original_size,
            self.env["commercial.property.unit.image"]._COMPRESSION_SIZE_THRESHOLD,
        )

        image_record = self.env["commercial.property.unit.image"].with_user(self.manager).create(
            {
                "unit_id": self.unit.id,
                "image_1920": large_image,
                "sequence": 10,
                "name": "Large Photo",
            }
        )

        stored_size = len(base64.b64decode(image_record.image_1920))
        self.assertLess(stored_size, original_size)
        # Verify the stored bytes are still a valid, decodable image.
        PILImage.open(io.BytesIO(base64.b64decode(image_record.image_1920))).verify()

    def test_write_large_image_is_compressed(self):
        """Writing a large synthetic PNG onto an existing record also
        triggers compression."""
        dummy_image = base64.b64encode(b"GIF89a\x01\x00\x01\x00\x00\x00\x00\x21\xf9\x04\x01\n\x00\x01\x00,\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;")
        image_record = self.env["commercial.property.unit.image"].with_user(self.manager).create(
            {
                "unit_id": self.unit.id,
                "image_1920": dummy_image,
                "sequence": 10,
                "name": "Placeholder",
            }
        )

        large_image = self._make_large_png()
        original_size = len(base64.b64decode(large_image))
        image_record.with_user(self.manager).write({"image_1920": large_image})

        stored_size = len(base64.b64decode(image_record.image_1920))
        self.assertLess(stored_size, original_size)

    def test_small_image_not_altered(self):
        """Small images (like the GIF test fixtures) are left untouched by
        the compression logic."""
        dummy_image = base64.b64encode(b"GIF89a\x01\x00\x01\x00\x00\x00\x00\x21\xf9\x04\x01\n\x00\x01\x00,\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;")
        image_record = self.env["commercial.property.unit.image"].with_user(self.manager).create(
            {
                "unit_id": self.unit.id,
                "image_1920": dummy_image,
                "sequence": 10,
                "name": "Small Photo",
            }
        )
        self.assertEqual(image_record.image_1920, dummy_image)

    def test_compress_existing_gallery_images_batch(self):
        """The batch method reduces the size of large existing images."""
        large_image = self._make_large_png()
        original_size = len(base64.b64decode(large_image))

        image_record = self.env["commercial.property.unit.image"].with_user(self.manager).create(
            {
                "unit_id": self.unit.id,
                "image_1920": large_image,
                "sequence": 10,
                "name": "Batch Photo",
            }
        )
        # It was already compressed on create(); this confirms the fixture
        # itself is meaningful and gives us a size to compare the batch
        # result against (should not grow).
        after_create_size = len(base64.b64decode(image_record.image_1920))
        self.assertLess(after_create_size, original_size)

        result = self.env["commercial.property.unit.image"]._compress_existing_gallery_images()
        self.assertIsInstance(result, int)

        image_record.invalidate_cache()
        after_batch_size = len(base64.b64decode(image_record.image_1920))
        self.assertLessEqual(after_batch_size, after_create_size)
        PILImage.open(io.BytesIO(base64.b64decode(image_record.image_1920))).verify()

    def test_compress_existing_gallery_images_idempotent(self):
        """Running the batch twice does not change the size the second
        time (idempotent)."""
        large_image = self._make_large_png()
        image_record = self.env["commercial.property.unit.image"].with_user(self.manager).create(
            {
                "unit_id": self.unit.id,
                "image_1920": large_image,
                "sequence": 10,
                "name": "Idempotent Photo",
            }
        )

        self.env["commercial.property.unit.image"]._compress_existing_gallery_images()
        image_record.invalidate_cache()
        first_pass_size = len(base64.b64decode(image_record.image_1920))

        self.env["commercial.property.unit.image"]._compress_existing_gallery_images()
        image_record.invalidate_cache()
        second_pass_size = len(base64.b64decode(image_record.image_1920))

        self.assertEqual(first_pass_size, second_pass_size)

    def test_compress_existing_gallery_images_cu2026_0009(self):
        """Real-data regression: unit CU2026-0009's gallery images are
        reduced in size by the batch and remain decodable with PIL."""
        unit = self.env["commercial.property.unit"].search([("code", "=", "CU2026-0009")], limit=1)
        if not unit:
            self.skipTest("Unit CU2026-0009 not present in this database")

        before_sizes = {
            image.id: len(base64.b64decode(image.image_1920))
            for image in unit.image_ids
            if image.image_1920
        }
        self.assertTrue(before_sizes, "Expected CU2026-0009 to have gallery images with content")

        self.env["commercial.property.unit.image"]._compress_existing_gallery_images()
        unit.invalidate_cache()

        for image in unit.image_ids:
            if image.id not in before_sizes:
                continue
            after_size = len(base64.b64decode(image.image_1920))
            self.assertLessEqual(after_size, before_sizes[image.id])
            # Must still be a valid, decodable image.
            PILImage.open(io.BytesIO(base64.b64decode(image.image_1920))).verify()
