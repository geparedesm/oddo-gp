from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class CommercialProperty(models.Model):
    _name = "commercial.property"
    _description = "Commercial Property"
    _order = "code, name, id"

    name = fields.Char(required=True, translate=True)
    code = fields.Char(
        required=True,
        copy=False,
        default=lambda self: _("New"),
        readonly=True,
        index=True,
    )
    active = fields.Boolean(default=True)
    state = fields.Selection(
        selection=[
            ("available", "Available"),
            ("reserved", "Reserved"),
            ("rented", "Rented"),
            ("maintenance", "Maintenance"),
            ("inactive", "Inactive"),
        ],
        default="available",
        required=True,
        index=True,
        help="Availability is updated automatically from confirmed lease contracts.",
    )
    property_type = fields.Selection(
        selection=[
            ("office", "Office"),
            ("retail", "Retail"),
            ("warehouse", "Warehouse"),
            ("industrial", "Industrial"),
            ("other", "Other"),
        ],
        default="office",
        required=True,
    )
    street = fields.Char()
    street2 = fields.Char()
    city = fields.Char()
    state_id = fields.Many2one("res.country.state", string="State / Province")
    zip = fields.Char(string="ZIP")
    country_id = fields.Many2one("res.country", string="Country")
    area = fields.Float(string="Area", required=True, digits=(16, 2), help="Usable area in square meters.")
    monthly_rent = fields.Monetary(required=True)
    currency_id = fields.Many2one(
        "res.currency",
        required=True,
        default=lambda self: self.env.company.currency_id,
    )
    available_date = fields.Date(string="Available From")
    image_1920 = fields.Image(
        string="Photo",
        max_width=1920,
        max_height=1920,
        help="Primary photo used to identify this property in Kanban and form views.",
    )
    notes = fields.Text(string="Internal Notes")
    lease_ids = fields.One2many("commercial.lease", "property_id", string="Lease History", copy=False)
    current_lease_id = fields.Many2one(
        "commercial.lease",
        string="Current Lease",
        compute="_compute_current_lease",
        groups="commercial_property_management.group_property_manager",
    )
    current_tenant_id = fields.Many2one(
        "res.partner",
        string="Current Tenant",
        compute="_compute_current_lease",
        groups="commercial_property_management.group_property_manager",
    )
    company_id = fields.Many2one(
        "res.company",
        required=True,
        default=lambda self: self.env.company,
        index=True,
    )

    _sql_constraints = [
        ("commercial_property_code_unique", "unique(code)", "The property code must be unique."),
    ]

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("code", _("New")) == _("New"):
                vals["code"] = self.env["ir.sequence"].next_by_code("commercial.property") or _("New")
        return super().create(vals_list)

    @api.constrains("area", "monthly_rent")
    def _check_property_values(self):
        for property_record in self:
            if property_record.area <= 0:
                raise ValidationError(_("The area must be greater than zero."))
            if property_record.monthly_rent < 0:
                raise ValidationError(_("The monthly rent cannot be negative."))

    @api.depends("lease_ids.state", "lease_ids.tenant_id")
    def _compute_current_lease(self):
        for property_record in self:
            current_lease = property_record.lease_ids.filtered(lambda lease: lease.state == "active")[:1]
            property_record.current_lease_id = current_lease
            property_record.current_tenant_id = current_lease.tenant_id

    def _sync_availability_from_leases(self):
        """Keep the inventory status aligned with the property's confirmed lease."""
        today = fields.Date.context_today(self)
        for property_record in self:
            active_lease = property_record.lease_ids.filtered(lambda lease: lease.state == "active")[:1]
            state = "available"
            if active_lease:
                if active_lease.start_date > today:
                    state = "reserved"
                elif active_lease.end_date >= today:
                    state = "rented"
            if property_record.state != state:
                property_record.state = state
