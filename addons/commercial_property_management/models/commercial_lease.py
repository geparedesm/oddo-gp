from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class CommercialLease(models.Model):
    _name = "commercial.lease"
    _description = "Commercial Lease"
    _order = "start_date desc, id desc"

    name = fields.Char(
        string="Lease Reference",
        required=True,
        copy=False,
        default=lambda self: _("New"),
        readonly=True,
    )
    property_id = fields.Many2one(
        "commercial.property",
        string="Property",
        required=True,
        ondelete="restrict",
        index=True,
    )
    tenant_id = fields.Many2one(
        "res.partner",
        string="Tenant",
        required=True,
        ondelete="restrict",
        domain="[('is_commercial_tenant', '=', True)]",
        index=True,
    )
    start_date = fields.Date(required=True, default=fields.Date.context_today)
    end_date = fields.Date(required=True)
    monthly_rent = fields.Monetary(required=True)
    currency_id = fields.Many2one(related="property_id.currency_id", store=True, readonly=True)
    state = fields.Selection(
        selection=[
            ("draft", "Draft"),
            ("active", "Active"),
            ("expired", "Expired"),
            ("cancelled", "Cancelled"),
        ],
        default="draft",
        required=True,
        index=True,
    )
    company_id = fields.Many2one(related="property_id.company_id", store=True, readonly=True, index=True)

    def init(self):
        # ORM constraints provide a clear message; this index also prevents concurrent activations.
        self.env.cr.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS commercial_lease_one_active_property_idx
            ON commercial_lease (property_id)
            WHERE state = 'active'
            """
        )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", _("New")) == _("New"):
                vals["name"] = self.env["ir.sequence"].next_by_code("commercial.lease") or _("New")
            if vals.get("state", "draft") == "active" and vals.get("property_id"):
                self._ensure_property_has_no_active_lease(vals["property_id"])
                self._ensure_lease_has_not_ended(vals.get("end_date"))
        leases = super().create(vals_list)
        leases._sync_property_availability()
        return leases

    def write(self, vals):
        if vals.get("state") == "active" or "property_id" in vals:
            for lease in self:
                state = vals.get("state", lease.state)
                property_id = vals.get("property_id", lease.property_id.id)
                if state == "active" and property_id:
                    self._ensure_property_has_no_active_lease(property_id, exclude_lease=lease)
                if vals.get("state") == "active":
                    self._ensure_lease_has_not_ended(vals.get("end_date", lease.end_date))
        properties = self.mapped("property_id")
        result = super().write(vals)
        if {"state", "property_id", "start_date", "end_date"}.intersection(vals):
            (properties | self.mapped("property_id"))._sync_availability_from_leases()
        return result

    def unlink(self):
        properties = self.mapped("property_id")
        result = super().unlink()
        properties._sync_availability_from_leases()
        return result

    @api.onchange("property_id")
    def _onchange_property_id(self):
        for lease in self:
            if lease.property_id:
                lease.monthly_rent = lease.property_id.monthly_rent

    @api.constrains("start_date", "end_date")
    def _check_lease_dates(self):
        for lease in self:
            if lease.start_date and lease.end_date and lease.end_date < lease.start_date:
                raise ValidationError(_("The lease end date must be on or after the start date."))

    @api.constrains("property_id", "tenant_id")
    def _check_tenant_is_commercial_tenant(self):
        for lease in self:
            if lease.tenant_id and not lease.tenant_id.is_commercial_tenant:
                raise ValidationError(_("A lease tenant must be marked as a Commercial Tenant."))

    def _ensure_property_has_no_active_lease(self, property_id, exclude_lease=None):
        domain = [("property_id", "=", property_id), ("state", "=", "active")]
        if exclude_lease:
            domain.append(("id", "!=", exclude_lease.id))
        if self.search_count(domain):
            raise ValidationError(_("A property can have only one active lease."))

    def _ensure_lease_has_not_ended(self, end_date):
        if end_date and fields.Date.to_date(end_date) < fields.Date.context_today(self):
            raise ValidationError(_("A lease that has already ended cannot be activated."))

    def _sync_property_availability(self):
        self.mapped("property_id")._sync_availability_from_leases()

    def action_activate(self):
        self.filtered(lambda lease: lease.state == "draft").write({"state": "active"})

    def action_expire(self):
        self.filtered(lambda lease: lease.state == "active").write({"state": "expired"})

    def action_cancel(self):
        self.filtered(lambda lease: lease.state in ("draft", "active")).write({"state": "cancelled"})

    @api.model
    def _cron_sync_availability(self):
        today = fields.Date.context_today(self)
        expired_leases = self.search([("state", "=", "active"), ("end_date", "<", today)])
        expired_leases.write({"state": "expired"})
        self.search([("state", "=", "active")])._sync_property_availability()
