from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class CommercialPropertyUnit(models.Model):
    _name = "commercial.property.unit"
    _description = "Commercial Property Unit"
    _order = "property_id, sequence, name, id"

    property_id = fields.Many2one("commercial.property", string="Building", required=True, ondelete="cascade", index=True)
    name = fields.Char(string="Unit Name", required=True, translate=True)
    code = fields.Char(string="Unit Reference", required=True, copy=False, readonly=True, index=True)
    sequence = fields.Integer(default=10)
    is_default = fields.Boolean(default=False, copy=False, index=True)
    active = fields.Boolean(default=True)
    state = fields.Selection(
        [("available", "Available"), ("reserved", "Reserved"), ("rented", "Rented"), ("maintenance", "Maintenance"), ("inactive", "Inactive")],
        default="available",
        required=True,
        index=True,
        help="Availability is updated automatically from confirmed lease contracts.",
    )
    property_type = fields.Selection(related="property_id.property_type", readonly=False)
    floor = fields.Char()
    entrance_description = fields.Char(string="Entrance / Facade Description", translate=True)
    area = fields.Float(string="Area", required=True, digits=(16, 2), help="Usable area in square meters.")
    monthly_rent = fields.Monetary(required=True)
    currency_id = fields.Many2one(related="property_id.currency_id", store=True, readonly=True)
    available_date = fields.Date(string="Available From")
    image_1920 = fields.Image(string="Photo", max_width=1920, max_height=1920)
    notes = fields.Text(string="Internal Notes")
    public_name = fields.Char(string="Public Name", translate=True)
    public_description = fields.Text(string="Public Description", translate=True)
    public_monthly_rent = fields.Monetary(string="Public Monthly Rent")
    public_feature_ids = fields.Many2many("commercial.property.feature", string="Public Features")
    is_published = fields.Boolean(string="Published", help="Make this available unit visible through the Hermes public API.")
    lease_ids = fields.One2many("commercial.lease", "unit_id", string="Lease History", copy=False)
    reservation_ids = fields.One2many("commercial.property.reservation", "unit_id", string="Reservations", copy=False)
    current_lease_id = fields.Many2one("commercial.lease", compute="_compute_current_lease", groups="commercial_property_management.group_property_manager")
    current_tenant_id = fields.Many2one("res.partner", compute="_compute_current_lease", groups="commercial_property_management.group_property_manager")
    company_id = fields.Many2one(related="property_id.company_id", store=True, readonly=True, index=True)

    _sql_constraints = [("commercial_property_unit_code_unique", "unique(code)", "The unit reference must be unique.")]

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get("code"):
                vals["code"] = self.env["ir.sequence"].next_by_code("commercial.property.unit") or _("New")
        return super().create(vals_list)

    @api.constrains("area", "monthly_rent")
    def _check_unit_values(self):
        for unit in self:
            if unit.area <= 0:
                raise ValidationError(_("The area must be greater than zero."))
            if unit.monthly_rent < 0:
                raise ValidationError(_("The monthly rent cannot be negative."))

    @api.constrains("is_published", "public_name", "public_description", "public_monthly_rent")
    def _check_public_listing(self):
        for unit in self.filtered("is_published"):
            if not unit.public_name or not unit.public_description:
                raise ValidationError(_("Published properties need a public name and description."))
            if unit.public_monthly_rent <= 0:
                raise ValidationError(_("Published properties need a public monthly rent greater than zero."))

    @api.depends("lease_ids.state", "lease_ids.tenant_id")
    def _compute_current_lease(self):
        for unit in self:
            lease = unit.lease_ids.filtered(lambda item: item.state == "active")[:1]
            unit.current_lease_id = lease
            unit.current_tenant_id = lease.tenant_id

    def _sync_availability_from_leases(self):
        today = fields.Date.context_today(self)
        for unit in self:
            active_lease = unit.lease_ids.filtered(
                lambda lease: lease.state == "active" and lease.end_date >= today
            )[:1]
            state = "available"
            if active_lease:
                state = "reserved" if active_lease.start_date > today else "rented"
            elif unit.reservation_ids.filtered(lambda reservation: reservation.state == "approved" and reservation.end_date >= today):
                state = "reserved"
            if unit.state != state:
                unit.state = state
            if unit.is_default and unit.property_id.state != state:
                unit.property_id.state = state

    def get_public_data(self):
        self.ensure_one()
        property_type_label = dict(self.property_id._fields["property_type"].selection).get(self.property_type)
        return {
            "code": self.code,
            "name": self.public_name,
            "description": self.public_description,
            "monthly_rent": self.public_monthly_rent,
            "currency": self.currency_id.name,
            "area": self.area,
            "property_type": property_type_label,
            "features": self.public_feature_ids.mapped("name"),
            "city": self.property_id.city or None,
            "building_name": self.property_id.name,
            "unit_name": self.name,
            "entrance_description": self.entrance_description or None,
            "available_from": fields.Date.to_string(self.available_date) if self.available_date else None,
        }

    @api.model
    def search_public_units(self, min_area=None, max_rent=None, code=None, limit=None):
        domain = [("active", "=", True), ("is_published", "=", True), ("state", "=", "available")]
        if min_area is not None:
            domain.append(("area", ">=", min_area))
        if max_rent is not None:
            domain.append(("public_monthly_rent", "<=", max_rent))
        if code:
            domain.append(("code", "=", code))
        return self.search(domain, limit=limit, order="public_monthly_rent asc, id")
