from datetime import timedelta

from odoo import fields
from odoo.exceptions import AccessError, ValidationError
from odoo.tests.common import TransactionCase


class TestCommercialLeaseFinancial(TransactionCase):
    def setUp(self):
        super().setUp()
        self.today = fields.Date.today()
        self.manager = self.env["res.users"].create(
            {
                "name": "Financial Manager",
                "login": "financial.manager.test",
                "email": "financial.manager.test@example.com",
                "company_id": self.env.company.id,
                "company_ids": [(6, 0, self.env.company.ids)],
                "groups_id": [(6, 0, [self.env.ref("commercial_property_management.group_property_manager").id])],
            }
        )
        self.user = self.env["res.users"].create(
            {
                "name": "Financial Property User",
                "login": "financial.user.test",
                "email": "financial.user.test@example.com",
                "company_id": self.env.company.id,
                "company_ids": [(6, 0, self.env.company.ids)],
                "groups_id": [(6, 0, [self.env.ref("commercial_property_management.group_property_user").id])],
            }
        )
        self.building = self.env["commercial.property"].with_user(self.manager).create(
            {"name": "Financial Building", "area": 300, "monthly_rent": 3000}
        )
        self.unit = self.building.default_unit_id
        self.tenant = self.env["res.partner"].with_user(self.manager).create(
            {"name": "Financial Tenant", "is_commercial_tenant": True}
        )
        self.lease = self.env["commercial.lease"].with_user(self.manager).create(
            {
                "property_id": self.building.id,
                "unit_id": self.unit.id,
                "tenant_id": self.tenant.id,
                "start_date": self.today - timedelta(days=10),
                "end_date": self.today + timedelta(days=20),
                "monthly_rent": 1500,
            }
        )
        self.lease.action_activate()

    def _penalty(self, **extra):
        values = {"lease_id": self.lease.id, "amount": 100}
        values.update(extra)
        return self.env["commercial.lease.penalty"].with_user(self.manager).create(values)

    def _adjustment(self, **extra):
        values = {"lease_id": self.lease.id, "new_rent": 1600}
        values.update(extra)
        return self.env["commercial.lease.rent.adjustment"].with_user(self.manager).create(values)

    def _payment(self, **extra):
        values = {"lease_id": self.lease.id, "amount": 1500}
        values.update(extra)
        return self.env["commercial.lease.rent.payment"].with_user(self.manager).create(values)

    # Deposit lifecycle

    def test_deposit_lifecycle_held_then_refunded(self):
        self.lease.deposit_amount = 500
        self.lease.action_mark_deposit_held()
        self.assertEqual(self.lease.deposit_status, "held")
        self.assertEqual(self.lease.deposit_received_date, self.today)

        self.lease.action_refund_deposit()
        self.assertEqual(self.lease.deposit_status, "refunded")
        self.assertEqual(self.lease.deposit_resolved_date, self.today)

    def test_deposit_lifecycle_held_then_forfeited(self):
        self.lease.deposit_amount = 500
        self.lease.action_mark_deposit_held()
        self.lease.action_forfeit_deposit()
        self.assertEqual(self.lease.deposit_status, "forfeited")

    def test_deposit_cannot_be_held_without_amount(self):
        with self.assertRaises(ValidationError):
            self.lease.action_mark_deposit_held()

    def test_deposit_cannot_be_refunded_before_held(self):
        self.lease.deposit_amount = 500
        with self.assertRaises(ValidationError):
            self.lease.action_refund_deposit()

    def test_negative_deposit_is_rejected(self):
        with self.assertRaises(ValidationError):
            self.lease.deposit_amount = -1

    # Rent adjustments

    def test_rent_adjustment_apply_changes_monthly_rent(self):
        adjustment = self._adjustment(new_rent=1800)
        self.assertEqual(adjustment.previous_rent, 1500)

        adjustment.action_apply()
        self.assertEqual(adjustment.state, "applied")
        self.assertEqual(self.lease.monthly_rent, 1800)

    def test_rent_adjustment_cannot_be_applied_twice(self):
        adjustment = self._adjustment(new_rent=1800)
        adjustment.action_apply()
        with self.assertRaises(ValidationError):
            adjustment.action_apply()

    def test_negative_new_rent_is_rejected(self):
        with self.assertRaises(ValidationError):
            self._adjustment(new_rent=-1)

    # Penalties

    def test_penalty_collect_and_waive(self):
        penalty = self._penalty()
        self.assertEqual(self.lease.pending_penalty_amount, 100)

        penalty.action_mark_collected()
        self.assertEqual(penalty.state, "collected")
        self.assertEqual(self.lease.pending_penalty_amount, 0)

        other_penalty = self._penalty()
        other_penalty.action_waive()
        self.assertEqual(other_penalty.state, "waived")
        self.assertEqual(self.lease.pending_penalty_amount, 0)

    def test_penalty_amount_must_be_positive(self):
        with self.assertRaises(ValidationError):
            self._penalty(amount=0)

    def test_collected_penalty_cannot_be_collected_again(self):
        penalty = self._penalty()
        penalty.action_mark_collected()
        with self.assertRaises(ValidationError):
            penalty.action_mark_collected()

    def test_property_user_cannot_create_penalty(self):
        with self.assertRaises(AccessError):
            self.env["commercial.lease.penalty"].with_user(self.user).create(
                {"lease_id": self.lease.id, "amount": 50}
            )

    # Rent payments

    def test_payment_confirm_updates_total_paid_amount(self):
        payment = self._payment()
        self.assertEqual(self.lease.total_paid_amount, 0)

        payment.action_confirm()
        self.assertEqual(payment.state, "confirmed")
        self.assertEqual(self.lease.total_paid_amount, 1500)

        other_payment = self._payment(amount=200)
        self.assertEqual(self.lease.total_paid_amount, 1500)
        other_payment.action_confirm()
        self.assertEqual(self.lease.total_paid_amount, 1700)

    def test_payment_amount_must_be_positive(self):
        with self.assertRaises(ValidationError):
            self._payment(amount=0)

    def test_confirmed_payment_cannot_be_confirmed_again(self):
        payment = self._payment()
        payment.action_confirm()
        with self.assertRaises(ValidationError):
            payment.action_confirm()

    def test_property_user_cannot_create_payment(self):
        with self.assertRaises(AccessError):
            self.env["commercial.lease.rent.payment"].with_user(self.user).create(
                {"lease_id": self.lease.id, "amount": 500}
            )

    # Renewal

    def test_renew_creates_draft_lease_with_continued_dates(self):
        result = self.lease.action_renew()
        renewal = self.env["commercial.lease"].browse(result["res_id"])

        self.assertEqual(renewal.state, "draft")
        self.assertEqual(renewal.renewed_from_id, self.lease)
        self.assertEqual(renewal.start_date, self.lease.end_date + timedelta(days=1))
        self.assertTrue(renewal.is_renewal)
        self.assertIn(renewal, self.lease.renewal_ids)

    def test_lease_cannot_be_renewed_twice(self):
        self.lease.action_renew()
        with self.assertRaises(ValidationError):
            self.lease.action_renew()

    def test_draft_lease_cannot_be_renewed(self):
        draft_lease = self.env["commercial.lease"].with_user(self.manager).create(
            {
                "property_id": self.building.id,
                "unit_id": self.env["commercial.property.unit"].with_user(self.manager).create(
                    {"property_id": self.building.id, "name": "Second Unit", "area": 90, "monthly_rent": 1200}
                ).id,
                "tenant_id": self.tenant.id,
                "start_date": self.today,
                "end_date": self.today + timedelta(days=30),
                "monthly_rent": 1200,
            }
        )
        with self.assertRaises(ValidationError):
            draft_lease.action_renew()

    # Portfolio and vacancy metrics

    def test_unit_vacancy_days_tracks_time_since_available(self):
        second_unit = self.env["commercial.property.unit"].with_user(self.manager).create(
            {"property_id": self.building.id, "name": "Vacant Unit", "area": 60, "monthly_rent": 900}
        )
        self.assertEqual(second_unit.state, "available")
        self.assertEqual(second_unit.vacancy_days, 0)

        second_unit.vacant_since = self.today - timedelta(days=5)
        self.assertEqual(second_unit.vacancy_days, 5)

    def test_property_portfolio_metrics(self):
        second_unit = self.env["commercial.property.unit"].with_user(self.manager).create(
            {"property_id": self.building.id, "name": "Second Metric Unit", "area": 60, "monthly_rent": 900}
        )

        self.assertEqual(self.building.unit_count, 2)
        self.assertEqual(self.building.occupied_unit_count, 1)
        self.assertEqual(self.building.vacant_unit_count, 1)
        self.assertAlmostEqual(self.building.occupancy_rate, 50.0)
        self.assertEqual(self.building.expected_monthly_income, self.lease.monthly_rent)
        self.assertTrue(second_unit)

    def test_expected_monthly_income_reflects_rent_adjustment(self):
        self.assertEqual(self.building.expected_monthly_income, 1500)

        self._adjustment(new_rent=1750).action_apply()

        self.assertEqual(self.building.expected_monthly_income, 1750)
