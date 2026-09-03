from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class CommercialLease(models.Model):
    _name = "commercial.lease"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _description = "Commercial Lease"
    _order = "start_date desc, id desc"

    name = fields.Char(string="Lease Reference", required=True, copy=False, default=lambda self: _("New"), readonly=True)
    property_id = fields.Many2one("commercial.property", string="Property", required=True, ondelete="restrict", index=True)
    unit_id = fields.Many2one("commercial.property.unit", string="Commercial Unit", required=True, ondelete="restrict", index=True)
    tenant_id = fields.Many2one("res.partner", string="Tenant", required=True, ondelete="restrict", domain="[('is_commercial_tenant', '=', True)]", index=True)
    application_id = fields.Many2one("commercial.property.application", string="Source Application", ondelete="restrict", readonly=True, copy=False, index=True)
    start_date = fields.Date(required=True, default=fields.Date.context_today)
    end_date = fields.Date(required=True)
    monthly_rent = fields.Monetary(required=True)
    currency_id = fields.Many2one(related="property_id.currency_id", store=True, readonly=True)
    state = fields.Selection([("draft", "Draft"), ("active", "Active"), ("expired", "Expired"), ("cancelled", "Cancelled")], default="draft", required=True, index=True)
    days_to_expiry = fields.Integer(string="Days to Expiry", compute="_compute_days_to_expiry", help="Days remaining until an active lease ends.")
    deposit_amount = fields.Monetary()
    deposit_status = fields.Selection(
        [("pending", "Pending"), ("held", "Held"), ("refunded", "Refunded"), ("forfeited", "Forfeited")],
        default="pending", required=True, tracking=True,
    )
    deposit_received_date = fields.Date(readonly=True, copy=False)
    deposit_resolved_date = fields.Date(readonly=True, copy=False)
    rent_adjustment_ids = fields.One2many("commercial.lease.rent.adjustment", "lease_id", string="Rent Adjustments", copy=False)
    penalty_ids = fields.One2many("commercial.lease.penalty", "lease_id", string="Penalties", copy=False)
    pending_penalty_amount = fields.Monetary(compute="_compute_pending_penalty_amount", groups="commercial_property_management.group_property_manager")
    payment_ids = fields.One2many("commercial.lease.rent.payment", "lease_id", string="Rent Payments", copy=False)
    total_paid_amount = fields.Monetary(compute="_compute_total_paid_amount", groups="commercial_property_management.group_property_manager")
    renewed_from_id = fields.Many2one("commercial.lease", string="Renewed From", readonly=True, copy=False, ondelete="set null", index=True)
    renewal_ids = fields.One2many("commercial.lease", "renewed_from_id", string="Renewals", copy=False)
    is_renewal = fields.Boolean(compute="_compute_is_renewal", store=True)
    company_id = fields.Many2one(related="property_id.company_id", store=True, readonly=True, index=True)

    def init(self):
        self.env.cr.execute("DROP INDEX IF EXISTS commercial_lease_one_active_property_idx")
        self.env.cr.execute("""CREATE UNIQUE INDEX IF NOT EXISTS commercial_lease_one_active_unit_idx
            ON commercial_lease (unit_id) WHERE state = 'active'""")

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get("unit_id") and vals.get("property_id"):
                vals["unit_id"] = self.env["commercial.property"].browse(vals["property_id"]).default_unit_id.id
            if vals.get("name", _("New")) == _("New"):
                vals["name"] = self.env["ir.sequence"].next_by_code("commercial.lease") or _("New")
            if vals.get("state", "draft") == "active" and vals.get("unit_id"):
                self._ensure_unit_has_no_active_lease(vals["unit_id"])
                self._ensure_unit_has_no_approved_reservation(vals["unit_id"], vals.get("start_date"), vals.get("end_date"))
                self._ensure_lease_has_not_ended(vals.get("end_date"))
        leases = super().create(vals_list)
        leases._sync_unit_availability()
        return leases

    def write(self, vals):
        if vals.get("state") == "active" or "unit_id" in vals:
            for lease in self:
                unit_id = vals.get("unit_id", lease.unit_id.id)
                if vals.get("state", lease.state) == "active" and unit_id:
                    self._ensure_unit_has_no_active_lease(unit_id, exclude_lease=lease)
                    self._ensure_unit_has_no_approved_reservation(unit_id, vals.get("start_date", lease.start_date), vals.get("end_date", lease.end_date))
                if vals.get("state") == "active":
                    self._ensure_lease_has_not_ended(vals.get("end_date", lease.end_date))
        units = self.mapped("unit_id")
        result = super().write(vals)
        if {"state", "unit_id", "start_date", "end_date"}.intersection(vals):
            (units | self.mapped("unit_id"))._sync_availability_from_leases()
        return result

    def unlink(self):
        units = self.mapped("unit_id")
        result = super().unlink()
        units._sync_availability_from_leases()
        return result

    @api.onchange("property_id")
    def _onchange_property_id(self):
        for lease in self:
            if lease.property_id:
                lease.unit_id = lease.property_id.default_unit_id

    @api.onchange("unit_id")
    def _onchange_unit_id(self):
        for lease in self:
            if lease.unit_id:
                lease.property_id = lease.unit_id.property_id
                lease.monthly_rent = lease.unit_id.monthly_rent

    @api.depends("state", "end_date")
    def _compute_days_to_expiry(self):
        today = fields.Date.context_today(self)
        for lease in self:
            lease.days_to_expiry = (lease.end_date - today).days if lease.state == "active" and lease.end_date else 0

    @api.depends("penalty_ids.amount", "penalty_ids.state")
    def _compute_pending_penalty_amount(self):
        for lease in self:
            lease.pending_penalty_amount = sum(lease.penalty_ids.filtered(lambda penalty: penalty.state == "pending").mapped("amount"))

    @api.depends("payment_ids.amount", "payment_ids.state")
    def _compute_total_paid_amount(self):
        for lease in self:
            lease.total_paid_amount = sum(lease.payment_ids.filtered(lambda payment: payment.state == "confirmed").mapped("amount"))

    @api.depends("renewed_from_id")
    def _compute_is_renewal(self):
        for lease in self:
            lease.is_renewal = bool(lease.renewed_from_id)

    @api.constrains("start_date", "end_date")
    def _check_lease_dates(self):
        for lease in self:
            if lease.start_date and lease.end_date and lease.end_date < lease.start_date:
                raise ValidationError(_("The lease end date must be on or after the start date."))

    @api.constrains("property_id", "unit_id", "tenant_id")
    def _check_lease_relations(self):
        for lease in self:
            if lease.tenant_id and not lease.tenant_id.is_commercial_tenant:
                raise ValidationError(_("A lease tenant must be marked as a Commercial Tenant."))
            if lease.unit_id and lease.property_id != lease.unit_id.property_id:
                raise ValidationError(_("The commercial unit must belong to the selected property."))

    @api.constrains("deposit_amount")
    def _check_deposit_amount(self):
        for lease in self:
            if lease.deposit_amount < 0:
                raise ValidationError(_("The deposit amount cannot be negative."))

    @api.constrains("application_id")
    def _check_source_application(self):
        for lease in self.filtered("application_id"):
            if lease.application_id.state != "approved" or lease.application_id.proposal_state != "accepted":
                raise ValidationError(_("A source application must be approved with an accepted proposal."))
            if lease.application_id.unit_id != lease.unit_id:
                raise ValidationError(_("The source application must be for the same commercial unit."))

    def _ensure_unit_has_no_active_lease(self, unit_id, exclude_lease=None):
        domain = [("unit_id", "=", unit_id), ("state", "=", "active")]
        if exclude_lease:
            domain.append(("id", "!=", exclude_lease.id))
        if self.search_count(domain):
            raise ValidationError(_("A commercial unit can have only one active lease."))

    def _ensure_lease_has_not_ended(self, end_date):
        if end_date and fields.Date.to_date(end_date) < fields.Date.context_today(self):
            raise ValidationError(_("A lease that has already ended cannot be activated."))

    def _ensure_unit_has_no_approved_reservation(self, unit_id, start_date, end_date):
        if self.env["commercial.property.reservation"].search_count([("unit_id", "=", unit_id), ("state", "=", "approved"), ("start_date", "<=", end_date), ("end_date", ">=", start_date)]):
            raise ValidationError(_("This lease conflicts with an approved reservation for the commercial unit."))

    def _sync_unit_availability(self):
        self.mapped("unit_id")._sync_availability_from_leases()

    def action_activate(self):
        self.filtered(lambda lease: lease.state == "draft").write({"state": "active"})

    def action_expire(self):
        self.filtered(lambda lease: lease.state == "active").write({"state": "expired"})

    def action_cancel(self):
        self.filtered(lambda lease: lease.state in ("draft", "active")).write({"state": "cancelled"})

    def action_mark_deposit_held(self):
        if any(lease.deposit_status != "pending" for lease in self):
            raise ValidationError(_("Only a pending deposit can be marked as held."))
        if any(lease.deposit_amount <= 0 for lease in self):
            raise ValidationError(_("Set a deposit amount before marking it as held."))
        self.write({"deposit_status": "held", "deposit_received_date": fields.Date.context_today(self)})

    def action_refund_deposit(self):
        if any(lease.deposit_status != "held" for lease in self):
            raise ValidationError(_("Only a held deposit can be refunded."))
        self.write({"deposit_status": "refunded", "deposit_resolved_date": fields.Date.context_today(self)})

    def action_forfeit_deposit(self):
        if any(lease.deposit_status != "held" for lease in self):
            raise ValidationError(_("Only a held deposit can be forfeited."))
        self.write({"deposit_status": "forfeited", "deposit_resolved_date": fields.Date.context_today(self)})

    def action_renew(self):
        self.ensure_one()
        if self.state not in ("active", "expired"):
            raise ValidationError(_("Only an active or expired lease can be renewed."))
        if self.renewal_ids:
            raise ValidationError(_("This lease has already been renewed."))
        duration = (self.end_date - self.start_date).days
        new_start = fields.Date.add(self.end_date, days=1)
        new_end = fields.Date.add(new_start, days=duration)
        renewal = self.create(
            {
                "property_id": self.property_id.id,
                "unit_id": self.unit_id.id,
                "tenant_id": self.tenant_id.id,
                "start_date": new_start,
                "end_date": new_end,
                "monthly_rent": self.monthly_rent,
                "renewed_from_id": self.id,
            }
        )
        return {
            "type": "ir.actions.act_window",
            "name": _("Lease Renewal"),
            "res_model": "commercial.lease",
            "res_id": renewal.id,
            "view_mode": "form",
            "target": "current",
        }

    def _get_expiry_activity_user(self):
        self.ensure_one()
        managers = self.env.ref("commercial_property_management.group_property_manager").users.filtered(lambda user: user.active and not user.share)
        return managers[:1]

    @api.model
    def _cron_create_expiry_activities(self, today=None):
        current_date = fields.Date.to_date(today or fields.Date.context_today(self))
        activity_type = self.env.ref("mail.mail_activity_data_todo")
        activity_model = self.env["mail.activity"].sudo()
        for days in (90, 30, 7):
            for lease in self.search([("state", "=", "active"), ("end_date", "=", current_date + timedelta(days=days))]):
                user = lease._get_expiry_activity_user()
                summary = _("Lease expires in %s days") % days
                if user and not activity_model.search_count([("res_model", "=", lease._name), ("res_id", "=", lease.id), ("activity_type_id", "=", activity_type.id), ("summary", "=", summary)]):
                    lease.activity_schedule("mail.mail_activity_data_todo", user_id=user.id, date_deadline=lease.end_date, summary=summary, note=_("Review the lease renewal or closure before its end date."))

    @api.model
    def _cron_sync_availability(self):
        today = fields.Date.context_today(self)
        self.search([("state", "=", "active"), ("end_date", "<", today)]).write({"state": "expired"})
        self.search([("state", "=", "active")])._sync_unit_availability()
        self._cron_create_expiry_activities(today=today)


class CommercialLeaseRentAdjustment(models.Model):
    _name = "commercial.lease.rent.adjustment"
    _description = "Commercial Lease Rent Adjustment"
    _order = "effective_date desc, id desc"

    lease_id = fields.Many2one("commercial.lease", required=True, ondelete="cascade", index=True)
    effective_date = fields.Date(required=True, default=fields.Date.context_today)
    previous_rent = fields.Monetary(readonly=True)
    new_rent = fields.Monetary(required=True)
    reason = fields.Text()
    state = fields.Selection([("draft", "Draft"), ("applied", "Applied")], default="draft", required=True)
    currency_id = fields.Many2one(related="lease_id.currency_id", store=True, readonly=True)
    company_id = fields.Many2one(related="lease_id.company_id", store=True, readonly=True, index=True)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if "previous_rent" not in vals and vals.get("lease_id"):
                vals["previous_rent"] = self.env["commercial.lease"].browse(vals["lease_id"]).monthly_rent
        return super().create(vals_list)

    @api.constrains("new_rent")
    def _check_new_rent(self):
        for adjustment in self:
            if adjustment.new_rent < 0:
                raise ValidationError(_("The new rent cannot be negative."))

    def action_apply(self):
        if any(adjustment.state != "draft" for adjustment in self):
            raise ValidationError(_("Only a draft rent adjustment can be applied."))
        if any(adjustment.lease_id.state not in ("draft", "active") for adjustment in self):
            raise ValidationError(_("Rent can only be adjusted on a draft or active lease."))
        for adjustment in self:
            adjustment.lease_id.message_post(
                body=_("Rent adjusted from %(previous)s to %(new)s effective %(date)s.")
                % {"previous": adjustment.previous_rent, "new": adjustment.new_rent, "date": adjustment.effective_date}
            )
            adjustment.lease_id.monthly_rent = adjustment.new_rent
        self.write({"state": "applied"})


class CommercialLeasePenalty(models.Model):
    _name = "commercial.lease.penalty"
    _description = "Commercial Lease Penalty"
    _order = "date desc, id desc"

    lease_id = fields.Many2one("commercial.lease", required=True, ondelete="cascade", index=True)
    date = fields.Date(required=True, default=fields.Date.context_today)
    reason = fields.Selection(
        [("late_payment", "Late Payment"), ("damage", "Damage"), ("contract_breach", "Contract Breach"), ("other", "Other")],
        required=True, default="late_payment",
    )
    amount = fields.Monetary(required=True)
    notes = fields.Text()
    state = fields.Selection([("pending", "Pending"), ("collected", "Collected"), ("waived", "Waived")], default="pending", required=True, index=True)
    currency_id = fields.Many2one(related="lease_id.currency_id", store=True, readonly=True)
    property_id = fields.Many2one(related="lease_id.property_id", store=True, readonly=True, index=True)
    unit_id = fields.Many2one(related="lease_id.unit_id", store=True, readonly=True, index=True)
    company_id = fields.Many2one(related="lease_id.company_id", store=True, readonly=True, index=True)

    @api.constrains("amount")
    def _check_amount(self):
        for penalty in self:
            if penalty.amount <= 0:
                raise ValidationError(_("A penalty amount must be greater than zero."))

    def action_mark_collected(self):
        if any(penalty.state != "pending" for penalty in self):
            raise ValidationError(_("Only a pending penalty can be marked as collected."))
        self.write({"state": "collected"})

    def action_waive(self):
        if any(penalty.state != "pending" for penalty in self):
            raise ValidationError(_("Only a pending penalty can be waived."))
        self.write({"state": "waived"})


class CommercialLeaseRentPayment(models.Model):
    _name = "commercial.lease.rent.payment"
    _description = "Commercial Lease Rent Payment"
    _order = "payment_date desc, id desc"

    lease_id = fields.Many2one("commercial.lease", required=True, ondelete="cascade", index=True)
    payment_date = fields.Date(required=True, default=fields.Date.context_today)
    amount = fields.Monetary(required=True)
    method = fields.Selection(
        [("cash", "Cash"), ("transfer", "Bank Transfer"), ("check", "Check"), ("other", "Other")],
        default="transfer", required=True,
    )
    reference = fields.Char()
    notes = fields.Text()
    state = fields.Selection([("draft", "Draft"), ("confirmed", "Confirmed")], default="draft", required=True)
    currency_id = fields.Many2one(related="lease_id.currency_id", store=True, readonly=True)
    property_id = fields.Many2one(related="lease_id.property_id", store=True, readonly=True, index=True)
    unit_id = fields.Many2one(related="lease_id.unit_id", store=True, readonly=True, index=True)
    company_id = fields.Many2one(related="lease_id.company_id", store=True, readonly=True, index=True)

    @api.constrains("amount")
    def _check_amount(self):
        for payment in self:
            if payment.amount <= 0:
                raise ValidationError(_("A rent payment amount must be greater than zero."))

    def action_confirm(self):
        if any(payment.state != "draft" for payment in self):
            raise ValidationError(_("Only a draft payment can be confirmed."))
        for payment in self:
            payment.lease_id.message_post(
                body=_("Rent payment of %(amount)s received on %(date)s.")
                % {"amount": payment.amount, "date": payment.payment_date}
            )
        self.write({"state": "confirmed"})
