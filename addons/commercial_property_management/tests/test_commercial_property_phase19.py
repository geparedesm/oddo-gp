from datetime import timedelta

from odoo import fields
from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase


class TestCommercialPropertyPhase19Navigation(TransactionCase):
    """Menu reorganization and unit-form contextual navigation (Phase 19)."""

    def setUp(self):
        super().setUp()
        self.today = fields.Date.today()
        self.manager = self.env["res.users"].create(
            {
                "name": "Phase19 Property Manager",
                "login": "phase19.manager.test",
                "email": "phase19.manager.test@example.com",
                "company_id": self.env.company.id,
                "company_ids": [(6, 0, self.env.company.ids)],
                "groups_id": [(6, 0, [self.env.ref("commercial_property_management.group_property_manager").id])],
            }
        )

    # Menu structure

    def test_functional_areas_exist_under_the_root_menu(self):
        root = self.env.ref("commercial_property_management.menu_commercial_property_root")
        areas = {
            "menu_commercial_property_area": "Properties",
            "menu_commercial_leasing": "Leasing",
            "menu_commercial_operations": "Operations",
            "menu_commercial_analytics": "Analytics",
            "menu_commercial_configuration": "Configuration",
        }
        for xml_id, expected_name in areas.items():
            menu = self.env.ref("commercial_property_management.%s" % xml_id)
            self.assertEqual(menu.parent_id, root)
            self.assertEqual(menu.name, expected_name)

    def test_properties_and_units_are_grouped_together(self):
        area = self.env.ref("commercial_property_management.menu_commercial_property_area")
        properties = self.env.ref("commercial_property_management.menu_commercial_property")
        units = self.env.ref("commercial_property_management.menu_commercial_property_unit")
        self.assertEqual(properties.parent_id, area)
        self.assertEqual(units.parent_id, area)
        self.assertEqual(units.name, "Units")

    def test_leasing_menu_children_follow_the_business_flow_order(self):
        leasing = self.env.ref("commercial_property_management.menu_commercial_leasing")
        expected_order = [
            ("menu_commercial_property_lead", "Enquiries"),
            ("menu_commercial_property_visit", "Inspections"),
            ("menu_commercial_property_reservation", "Reservations"),
            ("menu_commercial_property_application", "Lease Applications"),
            ("menu_commercial_tenant", "Tenants"),
            ("menu_commercial_lease", "Leases"),
        ]
        children = self.env["ir.ui.menu"].search([("parent_id", "=", leasing.id)], order="sequence, id")
        self.assertEqual(children.mapped("name"), [name for _xml_id, name in expected_order])
        for xml_id, expected_name in expected_order:
            menu = self.env.ref("commercial_property_management.%s" % xml_id)
            self.assertEqual(menu.parent_id, leasing)
            self.assertEqual(menu.name, expected_name)

    def test_operations_groups_maintenance_checklists_and_penalties(self):
        operations = self.env.ref("commercial_property_management.menu_commercial_operations")
        for xml_id in (
            "menu_commercial_property_maintenance",
            "menu_commercial_property_maintenance_dashboard",
            "menu_commercial_property_handover",
            "menu_commercial_lease_penalty",
        ):
            self.assertEqual(self.env.ref("commercial_property_management.%s" % xml_id).parent_id, operations)

    def test_analytics_groups_dashboards_and_reporting_only(self):
        analytics = self.env.ref("commercial_property_management.menu_commercial_analytics")
        for xml_id in (
            "menu_commercial_lease_operations_dashboard",
            "menu_commercial_property_portfolio",
            "menu_commercial_property_campaign_attribution",
        ):
            self.assertEqual(self.env.ref("commercial_property_management.%s" % xml_id).parent_id, analytics)
        # Distribution Channels is configuration data, not reporting: it must
        # not be duplicated under Analytics.
        distribution_channel_menu = self.env.ref("commercial_property_management.menu_commercial_property_distribution_channel")
        self.assertNotEqual(distribution_channel_menu.parent_id, analytics)

    def test_configuration_groups_integrations_and_settings_without_duplicates(self):
        configuration = self.env.ref("commercial_property_management.menu_commercial_configuration")
        for xml_id in (
            "menu_commercial_property_integration_alert",
            "menu_commercial_property_distribution_channel",
            "menu_commercial_property_settings",
        ):
            self.assertEqual(self.env.ref("commercial_property_management.%s" % xml_id).parent_id, configuration)
        # No duplicate action behind two different menu entries.
        actions = self.env["ir.ui.menu"].search([("parent_id", "=", configuration.id)]).mapped("action")
        action_refs = [(action.res_model, action.id) for action in actions if action]
        self.assertEqual(len(action_refs), len(set(action_refs)))

    def test_configuration_area_is_restricted_to_administrators(self):
        administrator_group = self.env.ref("commercial_property_management.group_property_administrator")
        manager_group = self.env.ref("commercial_property_management.group_property_manager")
        integration_alert_action = self.env.ref("commercial_property_management.action_commercial_property_integration_alert")
        distribution_channel_action = self.env.ref("commercial_property_management.action_commercial_property_distribution_channel")
        for action in (integration_alert_action, distribution_channel_action):
            self.assertIn(administrator_group, action.groups_id)
            self.assertNotIn(manager_group, action.groups_id)
        # A plain manager (not administrator) no longer sees these entries.
        self.assertNotIn(self.env.ref("commercial_property_management.group_property_administrator"), self.manager.groups_id)

    # Unit form contextual actions

    def _publish_available_unit(self, name):
        building = self.env["commercial.property"].with_user(self.manager).create(
            {
                "name": name,
                "area": 100,
                "monthly_rent": 1500,
                "public_name": name,
                "public_description": "Published for Phase 19 tests.",
                "public_monthly_rent": 1500,
                "is_published": True,
            }
        )
        return building, building.default_unit_id

    def test_create_enquiry_action_opens_lead_form_prefilled_with_the_unit(self):
        _building, unit = self._publish_available_unit("Phase19 Enquiry Unit")
        action = unit.with_user(self.manager).action_create_enquiry()
        self.assertEqual(action["res_model"], "commercial.property.lead")
        self.assertEqual(action["context"]["default_unit_id"], unit.id)

    def test_schedule_inspection_without_an_enquiry_raises(self):
        _building, unit = self._publish_available_unit("Phase19 No Enquiry Unit")
        with self.assertRaises(ValidationError):
            unit.with_user(self.manager).action_schedule_inspection()

    def test_create_reservation_without_an_enquiry_raises(self):
        _building, unit = self._publish_available_unit("Phase19 No Reservation Unit")
        with self.assertRaises(ValidationError):
            unit.with_user(self.manager).action_create_reservation()

    def _progress(self, unit):
        return unit.with_user(self.manager).commercial_progress_stage

    def test_full_commercial_progress_from_enquiry_to_lease(self):
        building, unit = self._publish_available_unit("Phase19 Full Flow Unit")
        self.assertEqual(self._progress(unit), "none")

        # Enquiry
        lead = self.env["commercial.property.lead"].with_user(self.manager).create(
            {
                "name": "Phase19 Prospect",
                "phone": "+15555550199",
                "unit_id": unit.id,
                "consent_at": fields.Datetime.now(),
                "source": "whatsapp",
            }
        )
        self.assertEqual(self._progress(unit), "enquiry")

        # Inspection: reuses lead.action_schedule_visit() via the unit shortcut.
        lead.action_qualify()
        visit_action = unit.with_user(self.manager).action_schedule_inspection()
        self.assertEqual(visit_action["res_model"], "commercial.property.visit")
        visit = self.env["commercial.property.visit"].browse(visit_action["res_id"])
        self.assertEqual(visit.lead_id, lead)
        visit.write({"scheduled_at": fields.Datetime.add(fields.Datetime.now(), days=1)})
        visit.action_schedule()
        visit.action_confirm()
        visit.action_complete()
        self.assertEqual(self._progress(unit), "inspection")

        # Reservation: unit shortcut reuses lead.action_create_reservation_request().
        lead.action_start_review()
        reservation_action = unit.with_user(self.manager).action_create_reservation()
        self.assertEqual(reservation_action["res_model"], "commercial.property.reservation")
        self.assertEqual(reservation_action["context"]["default_lead_id"], lead.id)
        reservation = self.env["commercial.property.reservation"].with_user(self.manager).create(
            {
                "lead_id": lead.id,
                "start_date": self.today + timedelta(days=10),
                "end_date": self.today + timedelta(days=40),
                "expires_at": fields.Datetime.add(fields.Datetime.now(), days=2),
            }
        )
        reservation.action_approve()
        self.assertEqual(unit.state, "reserved")
        self.assertEqual(self._progress(unit), "reservation")

        view_action = unit.with_user(self.manager).action_view_reservation()
        self.assertEqual(view_action["res_id"], reservation.id)

        # Lease Application: unit shortcut reuses lead.action_create_application().
        application_action = unit.with_user(self.manager).action_create_lease_application()
        self.assertEqual(application_action["res_model"], "commercial.property.application")
        self.assertEqual(application_action["context"]["default_lead_id"], lead.id)
        application = self.env["commercial.property.application"].with_user(self.manager).create(
            {
                "lead_id": lead.id,
                "identity_document_received": True,
                "financial_document_received": True,
            }
        )
        self.assertEqual(self._progress(unit), "application")

        application.action_submit()
        application.action_start_review()
        application.action_approve()
        application.write(
            {
                "proposed_monthly_rent": 1500,
                "proposed_start_date": self.today - timedelta(days=1),
                "proposed_end_date": self.today + timedelta(days=400),
                "proposal_terms": "Non-binding proposal terms.",
            }
        )
        application.action_offer_proposal()
        application.action_accept_proposal()
        lease_action = application.action_create_draft_lease()
        lease = self.env["commercial.lease"].browse(lease_action["res_id"])

        # Cancelling the (now superseded) reservation stays reusable and independent.
        unit.with_user(self.manager).action_cancel_reservation()
        self.assertEqual(reservation.state, "cancelled")

        # Lease: activating flips the unit to rented and the progress to lease.
        lease.action_activate()
        self.assertEqual(unit.state, "rented")
        self.assertEqual(self._progress(unit), "lease")

        lease_view_action = unit.with_user(self.manager).action_view_lease()
        self.assertEqual(lease_view_action["res_id"], lease.id)
        tenant_view_action = unit.with_user(self.manager).action_view_tenant()
        self.assertEqual(tenant_view_action["res_id"], lease.tenant_id.id)
        maintenance_view_action = unit.with_user(self.manager).action_view_maintenance()
        self.assertEqual(maintenance_view_action["domain"], [("unit_id", "=", unit.id)])

    def test_view_lease_and_view_tenant_raise_without_a_lease(self):
        _building, unit = self._publish_available_unit("Phase19 No Lease Unit")
        with self.assertRaises(ValidationError):
            unit.with_user(self.manager).action_view_lease()
        with self.assertRaises(ValidationError):
            unit.with_user(self.manager).action_view_tenant()

    def test_cancel_reservation_without_an_approved_reservation_raises(self):
        _building, unit = self._publish_available_unit("Phase19 No Reservation To Cancel Unit")
        with self.assertRaises(ValidationError):
            unit.with_user(self.manager).action_cancel_reservation()
