import base64
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

    def test_manager_creates_consent_based_lead_and_property_user_cannot_read_it(self):
        building = self.env["commercial.property"].with_user(self.manager).create(
            {"name": "Lead Building", "area": 100, "monthly_rent": 1500, "public_name": "Lead unit", "public_description": "Available unit", "public_monthly_rent": 1500, "is_published": True}
        )
        lead = self.env["commercial.property.lead"].with_user(self.manager).create(
            {"name": "WhatsApp Prospect", "phone": "+15550100", "unit_id": building.default_unit_id.id, "consent_at": fields.Datetime.now(), "source": "whatsapp", "visit_requested_at": fields.Datetime.now()}
        )
        self.assertEqual(lead.state, "new")
        self.assertEqual(lead.property_id, building)
        self.assertTrue(lead.activity_ids)
        with self.assertRaises(AccessError):
            lead.with_user(self.user).read()

    def test_lead_requires_a_published_available_unit_and_manager_transition(self):
        building = self.env["commercial.property"].with_user(self.manager).create(
            {"name": "Lead Transition Building", "area": 100, "monthly_rent": 1500}
        )
        with self.assertRaises(ValidationError):
            self.env["commercial.property.lead"].with_user(self.manager).create(
                {"name": "Prospect", "phone": "+15550000000", "unit_id": building.default_unit_id.id, "consent_at": fields.Datetime.now()}
            )

        building.default_unit_id.write(
            {"is_published": True, "public_name": "Published unit", "public_description": "A published unit", "public_monthly_rent": 1500}
        )
        lead = self.env["commercial.property.lead"].with_user(self.manager).create(
            {"name": "Prospect", "phone": "+15550000000", "unit_id": building.default_unit_id.id, "consent_at": fields.Datetime.now(), "source": "whatsapp"}
        )
        with self.assertRaises(ValidationError):
            lead.action_convert_to_tenant_draft()

        lead.action_qualify()
        lead.action_start_review()
        tenant_action = lead.action_convert_to_tenant_draft()
        self.assertEqual(lead.state, "converted")
        self.assertTrue(lead.tenant_id.is_commercial_tenant)
        self.assertEqual(tenant_action["res_id"], lead.tenant_id.id)
        self.assertFalse(self.env["commercial.lease"].with_user(self.manager).search_count([("unit_id", "=", building.default_unit_id.id)]))

    def test_whatsapp_lead_uses_ecuador_policy_and_anonymizes_on_retention_expiry(self):
        parameters = self.env["ir.config_parameter"].sudo()
        parameters.set_param("commercial_property_management.whatsapp_lead_retention_days", 180)
        parameters.set_param("commercial_property_management.whatsapp_rejected_retention_days", 30)
        parameters.set_param("commercial_property_management.whatsapp_consent_policy_version", "EC-2026-1")
        building = self.env["commercial.property"].with_user(self.manager).create(
            {"name": "Retention Building", "area": 100, "monthly_rent": 1500, "public_name": "Retention unit", "public_description": "Published", "public_monthly_rent": 1500, "is_published": True}
        )
        lead = self.env["commercial.property.lead"].with_user(self.manager).create(
            {"name": "Retention Prospect", "phone": "+155****0200", "email": "prospect@example.test", "company_name": "Retention Company", "message": "Please call me", "unit_id": building.default_unit_id.id, "consent_at": fields.Datetime.now(), "source": "whatsapp", "visit_requested_at": fields.Datetime.now()}
        )
        self.assertEqual(lead.consent_policy_version, "EC-2026-1")
        self.assertEqual(lead.consent_purpose, "Commercial property enquiry and visit coordination")
        self.assertTrue(lead.retention_deadline)
        self.assertEqual(lead.activity_ids.date_deadline, fields.Date.add(fields.Date.today(), days=1))
        lead.write({"retention_deadline": fields.Datetime.subtract(fields.Datetime.now(), days=1)})
        self.env["commercial.property.lead"]._cron_anonymize_expired_personal_data()
        self.assertEqual(lead.name, "Anonymized prospect")
        self.assertFalse(lead.phone or lead.email or lead.company_name or lead.message or lead.visit_requested_at)
        self.assertTrue(lead.anonymized_at)

    def test_manager_schedules_confirms_and_completes_a_visit(self):
        building = self.env["commercial.property"].with_user(self.manager).create(
            {"name": "Visit Building", "area": 100, "monthly_rent": 1500, "public_name": "Visit unit", "public_description": "Published", "public_monthly_rent": 1500, "is_published": True}
        )
        lead = self.env["commercial.property.lead"].with_user(self.manager).create(
            {"name": "Visit Prospect", "phone": "+155****0300", "unit_id": building.default_unit_id.id, "consent_at": fields.Datetime.now(), "source": "whatsapp"}
        )
        lead.action_qualify()
        action = lead.action_schedule_visit()
        visit = self.env["commercial.property.visit"].browse(action["res_id"])
        visit.write({"scheduled_at": fields.Datetime.add(fields.Datetime.now(), days=1)})
        visit.action_schedule()
        visit.action_confirm()
        self.assertEqual(visit.state, "confirmed")
        self.assertTrue(visit.activity_ids)
        visit.action_complete()
        self.assertEqual(visit.state, "completed")

    def test_manager_approves_non_conflicting_reservation_and_expiry_releases_unit(self):
        building = self.env["commercial.property"].with_user(self.manager).create(
            {"name": "Reservation Building", "area": 100, "monthly_rent": 1500, "public_name": "Reservation unit", "public_description": "Published", "public_monthly_rent": 1500, "is_published": True}
        )
        unit = building.default_unit_id
        lead = self.env["commercial.property.lead"].with_user(self.manager).create(
            {"name": "Reservation Prospect", "phone": "+155****0400", "unit_id": unit.id, "consent_at": fields.Datetime.now(), "source": "whatsapp"}
        )
        lead.action_qualify()
        reservation = self.env["commercial.property.reservation"].with_user(self.manager).create(
            {"lead_id": lead.id, "start_date": self.today + timedelta(days=10), "end_date": self.today + timedelta(days=20), "expires_at": fields.Datetime.add(fields.Datetime.now(), days=2)}
        )
        reservation.action_approve()
        self.assertEqual(reservation.state, "approved")
        self.assertEqual(unit.state, "reserved")
        self.assertTrue(reservation.activity_ids)
        conflicting = self.env["commercial.property.reservation"].with_user(self.manager).create(
            {"lead_id": lead.id, "start_date": self.today + timedelta(days=15), "end_date": self.today + timedelta(days=25), "expires_at": fields.Datetime.add(fields.Datetime.now(), days=2)}
        )
        with self.assertRaises(ValidationError):
            conflicting.action_approve()
        tenant = self.env["res.partner"].with_user(self.manager).create({"name": "Reservation Tenant", "is_commercial_tenant": True})
        lease = self.env["commercial.lease"].with_user(self.manager).create(
            {"property_id": building.id, "unit_id": unit.id, "tenant_id": tenant.id, "start_date": self.today + timedelta(days=10), "end_date": self.today + timedelta(days=30), "monthly_rent": 1500}
        )
        with self.assertRaises(ValidationError):
            lease.action_activate()
        self.env.cr.execute("UPDATE commercial_property_reservation SET expires_at = %s WHERE id = %s", (fields.Datetime.subtract(fields.Datetime.now(), hours=1), reservation.id))
        reservation.invalidate_recordset(["expires_at"])
        self.env["commercial.property.reservation"]._cron_expire_reservations()
        self.assertEqual(reservation.state, "expired")
        self.assertEqual(unit.state, "available")

    def test_approved_application_with_private_document_creates_traceable_draft_lease(self):
        building = self.env["commercial.property"].with_user(self.manager).create(
            {"name": "Application Building", "area": 100, "monthly_rent": 1500, "public_name": "Application unit", "public_description": "Published", "public_monthly_rent": 1500, "is_published": True}
        )
        lead = self.env["commercial.property.lead"].with_user(self.manager).create(
            {"name": "Application Prospect", "phone": "+155****0500", "email": "application@example.test", "unit_id": building.default_unit_id.id, "consent_at": fields.Datetime.now(), "source": "whatsapp"}
        )
        lead.action_qualify()
        lead.action_start_review()
        application = self.env["commercial.property.application"].with_user(self.manager).create(
            {"lead_id": lead.id, "identity_document_received": True, "financial_document_received": True, "proposed_monthly_rent": 1600, "proposed_start_date": self.today + timedelta(days=1), "proposed_end_date": self.today + timedelta(days=365), "proposal_terms": "Non-binding terms approved by the manager."}
        )
        self.env["commercial.property.application.document"].with_user(self.manager).create(
            {"application_id": application.id, "document_type": "identity", "filename": "identity.pdf", "file": base64.b64encode(b"private application document")}
        )
        application.action_submit()
        application.action_start_review()
        application.action_approve()
        self.assertEqual(application.state, "approved")
        application.action_offer_proposal()
        application.action_accept_proposal()
        action = application.action_create_draft_lease()
        lease = self.env["commercial.lease"].browse(action["res_id"])
        self.assertEqual(lease.state, "draft")
        self.assertEqual(lease.application_id, application)
        self.assertEqual(application.lease_id, lease)
        with self.assertRaises(AccessError):
            application.with_user(self.user).read()
        lease.action_activate()
        self.assertEqual(lease.state, "active")

    def test_application_cannot_be_approved_until_its_checklist_is_complete(self):
        building = self.env["commercial.property"].with_user(self.manager).create(
            {"name": "Incomplete Application Building", "area": 100, "monthly_rent": 1500, "public_name": "Incomplete application unit", "public_description": "Published", "public_monthly_rent": 1500, "is_published": True}
        )
        lead = self.env["commercial.property.lead"].with_user(self.manager).create(
            {"name": "Incomplete Prospect", "phone": "+155****0600", "unit_id": building.default_unit_id.id, "consent_at": fields.Datetime.now(), "source": "whatsapp"}
        )
        lead.action_qualify()
        lead.action_start_review()
        application = self.env["commercial.property.application"].with_user(self.manager).create({"lead_id": lead.id})
        application.action_submit()
        application.action_start_review()
        with self.assertRaises(ValidationError):
            application.action_approve()

    def test_default_unit_receives_legacy_property_public_listing_updates(self):
        building = self.env["commercial.property"].with_user(self.manager).create(
            {"name": "Legacy Public Listing Building", "area": 100, "monthly_rent": 1500}
        )
        building.write(
            {"is_published": True, "public_name": "Corner office", "public_description": "Next to the pharmacy", "public_monthly_rent": 1750}
        )
        self.assertTrue(building.default_unit_id.is_published)
        self.assertEqual(building.default_unit_id.public_name, "Corner office")
        self.assertEqual(building.default_unit_id.public_monthly_rent, 1750)

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
