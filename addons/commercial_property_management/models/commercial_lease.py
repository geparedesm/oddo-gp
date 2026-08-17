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
