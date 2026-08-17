import base64
from datetime import timedelta

from odoo import fields
from odoo.exceptions import AccessError, ValidationError
from odoo.tests.common import TransactionCase

ONE_BY_ONE_PNG = base64.b64encode(
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00"
    b"\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\xcf\xc0\x00\x00\x03\x01\x01\x00\x18\xdd\x8d\xb0"
    b"\x00\x00\x00\x00IEND\xaeB`\x82"
)


class TestCommercialPropertyListingQuality(TransactionCase):
    def setUp(self):
        super().setUp()
        self.manager = self.env["res.users"].create(
            {
                "name": "Listing Manager",
                "login": "listing.manager.test",
                "email": "listing.manager.test@example.com",
                "company_id": self.env.company.id,
                "company_ids": [(6, 0, self.env.company.ids)],
                "groups_id": [(6, 0, [self.env.ref("commercial_property_management.group_property_manager").id])],
            }
        )
        self.user = self.env["res.users"].create(
            {
                "name": "Listing Property User",
                "login": "listing.user.test",
                "email": "listing.user.test@example.com",
                "company_id": self.env.company.id,
                "company_ids": [(6, 0, self.env.company.ids)],
                "groups_id": [(6, 0, [self.env.ref("commercial_property_management.group_property_user").id])],
            }
        )
        self.building = self.env["commercial.property"].with_user(self.manager).create(
            {"name": "Listing Building", "area": 200, "monthly_rent": 2000}
        )
        self.unit = self.building.default_unit_id
        self.feature = self.env["commercial.property.feature"].create({"name": "Elevator %s" % self._testMethodName})

    def _fill_quality_fields(self, unit):
        unit.write(
            {
                "image_1920": ONE_BY_ONE_PNG,
                "public_name": "Bright downtown suite",
                "public_description": "A bright, well-connected office suite.",
                "public_monthly_rent": 1800,
                "public_feature_ids": [(6, 0, self.feature.ids)],
                "public_location_hint": "Near the central plaza, 5 minutes from the main avenue",
            }
        )

    # Quality checklist

    def test_publication_quality_ok_requires_all_checklist_fields(self):
        self.assertFalse(self.unit.publication_quality_ok)
        self._fill_quality_fields(self.unit)
        self.assertTrue(self.unit.publication_quality_ok)

    def test_publication_quality_ok_false_without_photo(self):
        self._fill_quality_fields(self.unit)
        self.unit.image_1920 = False
        self.assertFalse(self.unit.publication_quality_ok)

    # Approval / publication lifecycle

    def test_publishing_records_approval_audit(self):
        self._fill_quality_fields(self.unit)
        self.unit.with_user(self.manager).write({"is_published": True})

        self.assertEqual(self.unit.publication_date, fields.Date.today())
        self.assertEqual(self.unit.publication_approved_by_id, self.manager)
        self.assertFalse(self.unit.unpublish_reason)

    def test_unpublishing_requires_a_reason(self):
        self._fill_quality_fields(self.unit)
        self.unit.with_user(self.manager).write({"is_published": True})

        with self.assertRaises(ValidationError):
            self.unit.with_user(self.manager).write({"is_published": False})

        self.unit.with_user(self.manager).write({"is_published": False, "unpublish_reason": "leased"})
        self.assertFalse(self.unit.is_published)
        self.assertEqual(self.unit.unpublish_reason, "leased")

    def test_republishing_clears_previous_unpublish_reason(self):
        self._fill_quality_fields(self.unit)
        self.unit.with_user(self.manager).write({"is_published": True})
        self.unit.with_user(self.manager).write({"is_published": False, "unpublish_reason": "quality_issue"})

        self.unit.with_user(self.manager).write({"is_published": True})
        self.assertFalse(self.unit.unpublish_reason)

    def test_cron_expires_publications_past_expiry_date(self):
        self._fill_quality_fields(self.unit)
        self.unit.with_user(self.manager).write(
            {"is_published": True, "publication_expiry_date": fields.Date.today() - timedelta(days=1)}
        )

        self.env["commercial.property.unit"]._cron_expire_publications()

        self.assertFalse(self.unit.is_published)
        self.assertEqual(self.unit.unpublish_reason, "expired")

    def test_cron_does_not_expire_units_without_expiry_date(self):
        self._fill_quality_fields(self.unit)
        self.unit.with_user(self.manager).write({"is_published": True})

        self.env["commercial.property.unit"]._cron_expire_publications()

        self.assertTrue(self.unit.is_published)

    # Public data boundary

    def test_get_public_data_includes_location_hint_and_excludes_manager_fields(self):
        self._fill_quality_fields(self.unit)
        self.unit.with_user(self.manager).write({"is_published": True})

        public_data = self.unit.get_public_data()

        self.assertEqual(public_data["location_hint"], self.unit.public_location_hint)
        self.assertNotIn("publication_quality_ok", public_data)
        self.assertNotIn("publication_approved_by_id", public_data)
        self.assertNotIn("distribution_channel_ids", public_data)


class TestCommercialPropertyDistributionChannel(TransactionCase):
    def setUp(self):
        super().setUp()
        self.manager = self.env["res.users"].create(
            {
                "name": "Channel Manager",
                "login": "channel.manager.test",
                "email": "channel.manager.test@example.com",
                "company_id": self.env.company.id,
                "company_ids": [(6, 0, self.env.company.ids)],
                "groups_id": [(6, 0, [self.env.ref("commercial_property_management.group_property_manager").id])],
            }
        )
        self.user = self.env["res.users"].create(
            {
                "name": "Channel Property User",
                "login": "channel.user.test",
                "email": "channel.user.test@example.com",
                "company_id": self.env.company.id,
                "company_ids": [(6, 0, self.env.company.ids)],
                "groups_id": [(6, 0, [self.env.ref("commercial_property_management.group_property_user").id])],
            }
        )

    def test_manager_creates_channel(self):
        channel = self.env["commercial.property.distribution.channel"].with_user(self.manager).create(
            {"name": "Downtown Portal %s" % self._testMethodName, "channel_type": "portal"}
        )
        self.assertTrue(channel)

    def test_channel_name_must_be_unique(self):
        name = "Unique Portal %s" % self._testMethodName
        self.env["commercial.property.distribution.channel"].with_user(self.manager).create({"name": name})
        with self.assertRaises(Exception):
            self.env["commercial.property.distribution.channel"].with_user(self.manager).create({"name": name})

    def test_property_user_cannot_create_channel(self):
        with self.assertRaises(AccessError):
            self.env["commercial.property.distribution.channel"].with_user(self.user).create(
                {"name": "Blocked Portal %s" % self._testMethodName}
            )

    def test_lead_can_be_attributed_to_a_channel(self):
        channel = self.env["commercial.property.distribution.channel"].with_user(self.manager).create(
            {"name": "Social Campaign %s" % self._testMethodName, "channel_type": "social"}
        )
        building = self.env["commercial.property"].with_user(self.manager).create(
            {
                "name": "Attribution Building",
                "area": 100,
                "monthly_rent": 1500,
                "public_name": "Attribution unit",
                "public_description": "Published",
                "public_monthly_rent": 1500,
                "is_published": True,
            }
        )
        lead = self.env["commercial.property.lead"].with_user(self.manager).create(
            {
                "name": "Prospect",
                "phone": "+15550000",
                "unit_id": building.default_unit_id.id,
                "consent_at": fields.Datetime.now(),
                "source_channel_id": channel.id,
            }
        )
        self.assertEqual(lead.source_channel_id, channel)
