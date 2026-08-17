from odoo.exceptions import AccessError, ValidationError
from odoo.tests.common import TransactionCase


class TestCommercialPropertyMaintenance(TransactionCase):
    def setUp(self):
        super().setUp()
        self.manager = self.env["res.users"].create(
            {
                "name": "Maintenance Manager",
                "login": "maintenance.manager.test",
                "email": "maintenance.manager.test@example.com",
                "company_id": self.env.company.id,
                "company_ids": [(6, 0, self.env.company.ids)],
                "groups_id": [(6, 0, [self.env.ref("commercial_property_management.group_property_manager").id])],
            }
        )
        self.user = self.env["res.users"].create(
            {
                "name": "Maintenance Property User",
                "login": "maintenance.user.test",
                "email": "maintenance.user.test@example.com",
                "company_id": self.env.company.id,
                "company_ids": [(6, 0, self.env.company.ids)],
                "groups_id": [(6, 0, [self.env.ref("commercial_property_management.group_property_user").id])],
            }
        )
        self.building = self.env["commercial.property"].with_user(self.manager).create(
            {"name": "Maintenance Building", "area": 300, "monthly_rent": 3000}
        )
        self.unit = self.building.default_unit_id

    def _create_ticket(self, **extra):
        values = {
            "property_id": self.building.id,
            "unit_id": self.unit.id,
            "category": "repair",
            "description": "Leaking faucet in the kitchenette",
        }
        values.update(extra)
        return self.env["commercial.property.maintenance"].with_user(self.manager).create(values)

    def test_manager_creates_ticket_with_sequence(self):
        ticket = self._create_ticket()

        self.assertRegex(ticket.name, r"^MT[0-9]{4}-[0-9]{4}$")
        self.assertEqual(ticket.state, "new")
        self.assertEqual(ticket.company_id, self.building.company_id)

    def test_unit_must_belong_to_selected_building(self):
        other_building = self.env["commercial.property"].with_user(self.manager).create(
            {"name": "Other Building", "area": 100, "monthly_rent": 1000}
        )
        with self.assertRaises(ValidationError):
            self._create_ticket(property_id=other_building.id)

    def test_ticket_cannot_be_assigned_to_both_internal_and_external(self):
        provider = self.env["res.partner"].create({"name": "External Repair Co", "is_company": True})
        with self.assertRaises(ValidationError):
            self._create_ticket(assigned_user_id=self.manager.id, provider_id=provider.id)

    def test_assign_requires_an_assignee(self):
        ticket = self._create_ticket()
        with self.assertRaises(ValidationError):
            ticket.action_assign()

    def test_state_machine_assign_start_complete(self):
        ticket = self._create_ticket(assigned_user_id=self.manager.id)
        ticket.action_assign()
        self.assertEqual(ticket.state, "assigned")

        ticket.action_start()
        self.assertEqual(ticket.state, "in_progress")

        with self.assertRaises(ValidationError):
            ticket.action_complete()

        ticket.completion_notes = "Fixed the faucet and tested the water pressure."
        ticket.action_complete()
        self.assertEqual(ticket.state, "completed")
        self.assertEqual(ticket.closed_by_id, self.manager)
        self.assertTrue(ticket.closed_at)

    def test_completed_or_cancelled_ticket_cannot_be_cancelled_again(self):
        ticket = self._create_ticket()
        ticket.action_cancel()
        self.assertEqual(ticket.state, "cancelled")
        with self.assertRaises(ValidationError):
            ticket.action_cancel()

    def test_negative_costs_are_rejected(self):
        with self.assertRaises(ValidationError):
            self._create_ticket(cost_estimate=-10)

    def test_property_user_cannot_create_maintenance_ticket(self):
        with self.assertRaises(AccessError):
            self.env["commercial.property.maintenance"].with_user(self.user).create(
                {
                    "property_id": self.building.id,
                    "unit_id": self.unit.id,
                    "category": "repair",
                    "description": "Should not be creatable by a Property User",
                }
            )

    def test_unit_operational_status_reflects_open_maintenance(self):
        self.assertEqual(self.unit.operational_status, "operational")

        ticket = self._create_ticket(assigned_user_id=self.manager.id)
        ticket.action_assign()
        self.assertEqual(self.unit.operational_status, "under_maintenance")
        self.assertEqual(self.unit.open_maintenance_count, 1)

        ticket.completion_notes = "Resolved."
        ticket.action_complete()
        self.assertEqual(self.unit.operational_status, "operational")

    def test_building_wide_ticket_sets_property_operational_status_only(self):
        ticket = self._create_ticket(unit_id=False, assigned_user_id=self.manager.id)
        ticket.action_assign()

        self.assertEqual(self.building.operational_status, "under_maintenance")
        self.assertEqual(self.unit.operational_status, "operational")

    def test_get_public_data_excludes_operational_fields(self):
        ticket = self._create_ticket(assigned_user_id=self.manager.id)
        ticket.action_assign()
        self.unit.write({"is_published": True, "public_name": "Public Suite", "public_description": "Bright office.", "public_monthly_rent": 1800})

        public_data = self.unit.get_public_data()

        self.assertNotIn("operational_status", public_data)
        self.assertNotIn("maintenance_ids", public_data)
        self.assertNotIn("open_maintenance_count", public_data)


class TestCommercialPropertyHandover(TransactionCase):
    def setUp(self):
        super().setUp()
        self.manager = self.env["res.users"].create(
            {
                "name": "Handover Manager",
                "login": "handover.manager.test",
                "email": "handover.manager.test@example.com",
                "company_id": self.env.company.id,
                "company_ids": [(6, 0, self.env.company.ids)],
                "groups_id": [(6, 0, [self.env.ref("commercial_property_management.group_property_manager").id])],
            }
        )
        self.building = self.env["commercial.property"].with_user(self.manager).create(
            {"name": "Handover Building", "area": 200, "monthly_rent": 2000}
        )
        self.unit = self.building.default_unit_id

    def test_manager_creates_handover_with_sequence(self):
        handover = self.env["commercial.property.handover"].with_user(self.manager).create(
            {"handover_type": "delivery", "unit_id": self.unit.id}
        )
        self.assertRegex(handover.name, r"^HC[0-9]{4}-[0-9]{4}$")
        self.assertEqual(handover.state, "draft")

    def test_complete_requires_at_least_one_line(self):
        handover = self.env["commercial.property.handover"].with_user(self.manager).create(
            {"handover_type": "delivery", "unit_id": self.unit.id}
        )
        with self.assertRaises(ValidationError):
            handover.action_complete()

    def test_complete_sets_performed_at_and_unit_awaits_handover_before_completion(self):
        handover = self.env["commercial.property.handover"].with_user(self.manager).create(
            {
                "handover_type": "delivery",
                "unit_id": self.unit.id,
                "line_ids": [(0, 0, {"description": "Walls", "condition": "good"})],
            }
        )
        self.assertEqual(self.unit.operational_status, "awaiting_handover")

        handover.action_complete()

        self.assertEqual(handover.state, "completed")
        self.assertTrue(handover.performed_at)
        self.assertEqual(self.unit.operational_status, "operational")

    def test_completed_handover_cannot_be_completed_again(self):
        handover = self.env["commercial.property.handover"].with_user(self.manager).create(
            {
                "handover_type": "return",
                "unit_id": self.unit.id,
                "line_ids": [(0, 0, {"description": "Flooring", "condition": "fair"})],
            }
        )
        handover.action_complete()
        with self.assertRaises(ValidationError):
            handover.action_complete()
