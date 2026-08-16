from datetime import timedelta

from odoo import fields
from odoo.exceptions import AccessError, ValidationError
from odoo.tests.common import TransactionCase


class TestCommercialProperty(TransactionCase):
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
        self.assertEqual(len(property_record.unit_ids), 1)
        self.assertEqual(property_record.default_unit_id.code, property_record.code)

    def test_active_lease_for_one_unit_does_not_change_other_unit_availability(self):
        building = self.env["commercial.property"].with_user(self.manager).create(
            {"name": "Multi-unit Building", "area": 100, "monthly_rent": 1500}
        )
        second_unit = self.env["commercial.property.unit"].with_user(self.manager).create(
            {"property_id": building.id, "name": "Corner Unit", "area": 80, "monthly_rent": 2200}
        )
        tenant = self.env["res.partner"].with_user(self.manager).create(
            {"name": "Multi-unit Tenant", "is_commercial_tenant": True}
        )
        lease = self.env["commercial.lease"].with_user(self.manager).create(
            {"property_id": building.id, "unit_id": building.default_unit_id.id, "tenant_id": tenant.id,
             "start_date": self.today, "end_date": self.today + timedelta(days=30), "monthly_rent": 1500}
        )
        lease.action_activate()

        self.assertEqual(building.default_unit_id.state, "rented")
        self.assertEqual(second_unit.state, "available")
        self.assertEqual(lease.unit_id, building.default_unit_id)

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

    def test_manager_can_create_person_or_company_tenants(self):
        person_tenant = self.env["res.partner"].with_user(self.manager).create(
            {
                "name": "Tenant Person",
                "is_commercial_tenant": True,
                "tenant_identification_number": "P-100",
            }
        )
        company_tenant = self.env["res.partner"].with_user(self.manager).create(
            {
                "name": "Tenant Company",
                "company_type": "company",
                "is_commercial_tenant": True,
            }
        )

        tenants = self.env["res.partner"].with_user(self.manager).search(
            [("is_commercial_tenant", "=", True)]
        )
        self.assertIn(person_tenant, tenants)
        self.assertIn(company_tenant, tenants)
        self.assertEqual(company_tenant.company_type, "company")

    def test_property_user_cannot_read_private_tenant_identification(self):
        tenant = self.env["res.partner"].with_user(self.manager).create(
            {
                "name": "Private Tenant",
                "is_commercial_tenant": True,
                "tenant_identification_number": "PRIVATE-100",
            }
        )

        with self.assertRaises(AccessError):
            tenant.with_user(self.user).read(["tenant_identification_number"])

    def test_manager_activates_lease_and_property_shows_history(self):
        property_record = self.env["commercial.property"].with_user(self.manager).create(
            {"name": "Lease History Property", "area": 150, "monthly_rent": 3000}
        )
        tenant = self.env["res.partner"].with_user(self.manager).create(
            {"name": "Lease History Tenant", "is_commercial_tenant": True}
        )
        lease = self.env["commercial.lease"].with_user(self.manager).create(
            {
                "property_id": property_record.id,
                "tenant_id": tenant.id,
                "start_date": self.today,
                "end_date": self.today + timedelta(days=30),
                "monthly_rent": 3000,
            }
        )

        lease.action_activate()
        property_record.invalidate_recordset(["lease_ids", "current_lease_id", "current_tenant_id"])

        self.assertRegex(lease.name, r"^CL[0-9]{4}-[0-9]{4}$")
        self.assertEqual(lease.state, "active")
        self.assertEqual(property_record.state, "rented")
        self.assertEqual(property_record.current_lease_id, lease)
        self.assertEqual(property_record.current_tenant_id, tenant)
        self.assertIn(lease, property_record.lease_ids)

    def test_property_cannot_have_two_active_leases(self):
        property_record = self.env["commercial.property"].with_user(self.manager).create(
            {"name": "Single Active Lease Property", "area": 120, "monthly_rent": 2000}
        )
        tenant = self.env["res.partner"].with_user(self.manager).create(
            {"name": "Single Active Lease Tenant", "is_commercial_tenant": True}
        )
        active_lease = self.env["commercial.lease"].with_user(self.manager).create(
            {
                "property_id": property_record.id,
                "tenant_id": tenant.id,
                "start_date": self.today,
                "end_date": self.today + timedelta(days=30),
                "monthly_rent": 2000,
                "state": "active",
            }
        )
        second_lease = self.env["commercial.lease"].with_user(self.manager).create(
            {
                "property_id": property_record.id,
                "tenant_id": tenant.id,
                "start_date": self.today + timedelta(days=31),
                "end_date": self.today + timedelta(days=60),
                "monthly_rent": 2100,
            }
        )

        with self.assertRaises(ValidationError):
            second_lease.action_activate()

        self.assertEqual(active_lease.state, "active")
        self.assertEqual(second_lease.state, "draft")

    def test_future_active_lease_reserves_property_and_cancellation_releases_it(self):
        property_record = self.env["commercial.property"].with_user(self.manager).create(
            {"name": "Future Lease Property", "area": 100, "monthly_rent": 1800}
        )
        tenant = self.env["res.partner"].with_user(self.manager).create(
            {"name": "Future Lease Tenant", "is_commercial_tenant": True}
        )
        lease = self.env["commercial.lease"].with_user(self.manager).create(
            {
                "property_id": property_record.id,
                "tenant_id": tenant.id,
                "start_date": self.today + timedelta(days=14),
                "end_date": self.today + timedelta(days=365),
                "monthly_rent": 1800,
            }
        )

        lease.action_activate()
        self.assertEqual(property_record.state, "reserved")

        lease.action_cancel()
        self.assertEqual(property_record.state, "available")

    def test_expired_lease_releases_property_and_cron_marks_it_expired(self):
        property_record = self.env["commercial.property"].with_user(self.manager).create(
            {"name": "Expired Lease Property", "area": 100, "monthly_rent": 1800}
        )
        tenant = self.env["res.partner"].with_user(self.manager).create(
            {"name": "Expired Lease Tenant", "is_commercial_tenant": True}
        )
        lease = self.env["commercial.lease"].with_user(self.manager).create(
            {
                "property_id": property_record.id,
                "tenant_id": tenant.id,
                "start_date": self.today - timedelta(days=30),
                "end_date": self.today + timedelta(days=1),
                "monthly_rent": 1800,
            }
        )
        lease.action_activate()
        lease.write({"end_date": self.today - timedelta(days=1)})

        self.assertEqual(property_record.state, "available")
        self.env["commercial.lease"]._cron_sync_availability()
        self.assertEqual(lease.state, "expired")

    def test_lease_cannot_be_activated_after_its_end_date(self):
        property_record = self.env["commercial.property"].with_user(self.manager).create(
            {"name": "Ended Lease Property", "area": 100, "monthly_rent": 1800}
        )
        tenant = self.env["res.partner"].with_user(self.manager).create(
            {"name": "Ended Lease Tenant", "is_commercial_tenant": True}
        )
        lease = self.env["commercial.lease"].with_user(self.manager).create(
            {
                "property_id": property_record.id,
                "tenant_id": tenant.id,
                "start_date": self.today - timedelta(days=30),
                "end_date": self.today - timedelta(days=1),
                "monthly_rent": 1800,
            }
        )

        with self.assertRaises(ValidationError):
            lease.action_activate()

    def test_lease_rejects_invalid_dates_and_non_tenant_contacts(self):
        property_record = self.env["commercial.property"].with_user(self.manager).create(
            {"name": "Lease Validation Property", "area": 90, "monthly_rent": 1000}
        )
        contact = self.env["res.partner"].with_user(self.manager).create({"name": "Not A Tenant"})

        with self.assertRaises(ValidationError):
            self.env["commercial.lease"].with_user(self.manager).create(
                {
                    "property_id": property_record.id,
                    "tenant_id": contact.id,
                    "start_date": "2026-12-31",
                    "end_date": "2026-01-01",
                    "monthly_rent": 1000,
                }
            )

        with self.assertRaises(ValidationError):
            self.env["commercial.lease"].with_user(self.manager).create(
                {
                    "property_id": property_record.id,
                    "tenant_id": contact.id,
                    "start_date": "2026-01-01",
                    "end_date": "2026-12-31",
                    "monthly_rent": 1000,
                }
            )

    def test_property_user_cannot_access_leases(self):
        with self.assertRaises(AccessError):
            self.env["commercial.lease"].with_user(self.user).search([])

    def test_expiry_cron_creates_one_activity_at_each_reminder_threshold(self):
        tenant = self.env["res.partner"].with_user(self.manager).create(
            {"name": "Expiry Reminder Tenant", "is_commercial_tenant": True}
        )
        leases = self.env["commercial.lease"]

        for days in (90, 30, 7):
            property_record = self.env["commercial.property"].with_user(self.manager).create(
                {
                    "name": "Expiry Reminder Property %s" % days,
                    "area": 100,
                    "monthly_rent": 1500,
                }
            )
            lease = self.env["commercial.lease"].with_user(self.manager).create(
                {
                    "property_id": property_record.id,
                    "tenant_id": tenant.id,
                    "start_date": self.today,
                    "end_date": self.today + timedelta(days=days),
                    "monthly_rent": 1500,
                }
            )
            lease.action_activate()
            self.assertEqual(lease.days_to_expiry, days)
            leases |= lease

        self.env["commercial.lease"]._cron_create_expiry_activities(today=self.today)
        activities = self.env["mail.activity"].sudo().search(
            [
                ("res_model", "=", "commercial.lease"),
                ("res_id", "in", leases.ids),
            ]
        )

        self.assertEqual(len(activities), 3)
        self.assertEqual(
            set(activities.mapped("summary")),
            {"Lease expires in 90 days", "Lease expires in 30 days", "Lease expires in 7 days"},
        )
        self.assertEqual(set(activities.mapped("date_deadline")), set(leases.mapped("end_date")))

        self.env["commercial.lease"]._cron_create_expiry_activities(today=self.today)
        self.assertEqual(
            self.env["mail.activity"].sudo().search_count(
                [
                    ("res_model", "=", "commercial.lease"),
                    ("res_id", "in", leases.ids),
                ]
            ),
            3,
        )
