from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class CommercialPropertyUnit(models.Model):
    _name = "commercial.property.unit"
    _description = "Commercial Property Unit"
    _order = "property_id, sequence, name, id"

    property_id = fields.Many2one("commercial.property", string="Building", required=True, ondelete="cascade", index=True)
    name = fields.Char(string="Unit Name", required=True, translate=True)

    code = fields.Char(
        string="Unit Reference", required=True, copy=False, readonly=True, index=True,
        default=lambda self: _("New"),
    )
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
    image_ids = fields.One2many("commercial.property.unit.image", "unit_id", string="Images")
    image_1920 = fields.Image(
        string="Photo",
        compute="_compute_primary_image",
        inverse="_inverse_primary_image",
        store=True,
    )
    notes = fields.Text(string="Internal Notes")
    public_name = fields.Char(string="Public Name", translate=True)
    public_description = fields.Text(string="Public Description", translate=True)
    public_monthly_rent = fields.Monetary(string="Public Monthly Rent")
    public_feature_ids = fields.Many2many("commercial.property.feature", string="Public Features")
    public_location_hint = fields.Char(
        string="Public Location Description", translate=True,
        help="Non-sensitive location description for prospects, such as a nearby landmark. Never the exact address.",
    )
    virtual_tour_url = fields.Char(
        string="Virtual Tour URL",
        help="Link to a digital/virtual visit, shared with the prospect alongside the photo before offering a physical visit.",
    )
    is_published = fields.Boolean(string="Published", help="Make this available unit visible through the Hermes public API.")
    publication_quality_ok = fields.Boolean(
        string="Quality Checklist Passed",
        compute="_compute_publication_quality_ok", groups="commercial_property_management.group_property_manager",
        help="True when the listing has a photo, name, description, features, location hint and a positive public rent.",
    )
    publication_date = fields.Date(readonly=True, copy=False)
    publication_approved_by_id = fields.Many2one("res.users", string="Approved By", readonly=True, copy=False)
    publication_expiry_date = fields.Date(
        string="Publication Expiry", help="The listing is automatically unpublished after this date.",
    )
    unpublish_reason = fields.Selection(
        [("manager_decision", "Manager Decision"), ("leased", "Leased"), ("quality_issue", "Quality Issue"), ("expired", "Expired"), ("other", "Other")],
        copy=False,
    )
    unpublish_notes = fields.Text(copy=False)
    distribution_channel_ids = fields.Many2many(
        "commercial.property.distribution.channel",
        relation="commercial_property_unit_distribution_channel_rel",
        string="Distribution Channels",
        groups="commercial_property_management.group_property_manager",
        help="Channels this unit has been shared to, such as a website, property portal or social campaign.",
    )
    lease_ids = fields.One2many("commercial.lease", "unit_id", string="Lease History", copy=False)
    lead_ids = fields.One2many(
        "commercial.property.lead", "unit_id", string="Enquiries", copy=False,
        groups="commercial_property_management.group_property_manager",
    )
    reservation_ids = fields.One2many("commercial.property.reservation", "unit_id", string="Reservations", copy=False)
    maintenance_ids = fields.One2many(
        "commercial.property.maintenance", "unit_id", string="Maintenance Tickets", copy=False,
        groups="commercial_property_management.group_property_manager",
    )
    handover_ids = fields.One2many(
        "commercial.property.handover", "unit_id", string="Delivery/Return Checklists", copy=False,
        groups="commercial_property_management.group_property_manager",
    )
    open_maintenance_count = fields.Integer(
        compute="_compute_operational_status", groups="commercial_property_management.group_property_manager",
    )
    operational_status = fields.Selection(
        [("operational", "Operational"), ("under_maintenance", "Under Maintenance"), ("awaiting_handover", "Awaiting Handover")],
        compute="_compute_operational_status",
        groups="commercial_property_management.group_property_manager",
        help="Internal operational condition. Never exposed through public listings or WhatsApp.",
    )
    vacant_since = fields.Date(readonly=True, copy=False, default=fields.Date.context_today)
    vacancy_days = fields.Integer(
        compute="_compute_vacancy_days", groups="commercial_property_management.group_property_manager",
        help="Days since this unit last became available. Zero when the unit is not currently available.",
    )
    current_lease_id = fields.Many2one("commercial.lease", compute="_compute_current_lease", groups="commercial_property_management.group_property_manager")
    current_tenant_id = fields.Many2one("res.partner", compute="_compute_current_lease", groups="commercial_property_management.group_property_manager")
    enquiry_count = fields.Integer(compute="_compute_acquisition_metrics", groups="commercial_property_management.group_property_manager")
    responded_enquiry_count = fields.Integer(compute="_compute_acquisition_metrics", groups="commercial_property_management.group_property_manager")
    completed_visit_count = fields.Integer(compute="_compute_acquisition_metrics", groups="commercial_property_management.group_property_manager")
    approved_reservation_count = fields.Integer(compute="_compute_acquisition_metrics", groups="commercial_property_management.group_property_manager")
    contract_count = fields.Integer(compute="_compute_acquisition_metrics", groups="commercial_property_management.group_property_manager")
    lost_enquiry_count = fields.Integer(compute="_compute_acquisition_metrics", groups="commercial_property_management.group_property_manager")
    commercial_progress_stage = fields.Selection(
        [
            ("none", "No Activity"),
            ("enquiry", "Enquiry"),
            ("inspection", "Inspection"),
            ("reservation", "Reservation"),
            ("application", "Application"),
            ("lease", "Lease"),
        ],
        compute="_compute_commercial_progress_stage",
        groups="commercial_property_management.group_property_manager",
        help="Furthest stage reached in the commercial process for this unit, derived from "
        "its existing enquiries, visits, reservations, applications and leases. Independent "
        "from the unit's availability `state` above.",
    )
    company_id = fields.Many2one(related="property_id.company_id", store=True, readonly=True, index=True)

    _sql_constraints = [("commercial_property_unit_code_unique", "unique(code)", "The unit reference must be unique.")]

    @api.model_create_multi
    def create(self, vals_list):
        today = fields.Date.context_today(self)
        for vals in vals_list:
            if not vals.get("code"):
                vals["code"] = self.env["ir.sequence"].next_by_code("commercial.property.unit") or _("New")
            if vals.get("is_published"):
                vals.setdefault("publication_date", today)
                vals.setdefault("publication_approved_by_id", self.env.user.id)
        return super().create(vals_list)

    def write(self, vals):
        if "is_published" in vals and not vals["is_published"]:
            if not vals.get("unpublish_reason") and self.filtered("is_published"):
                raise ValidationError(_("Select an unpublish reason before unpublishing a listing."))
        elif vals.get("is_published"):
            vals.setdefault("publication_date", fields.Date.context_today(self))
            vals.setdefault("publication_approved_by_id", self.env.user.id)
            vals.setdefault("unpublish_reason", False)
            vals.setdefault("unpublish_notes", False)
        return super().write(vals)

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

    def _compute_acquisition_metrics(self):
        Lead = self.env["commercial.property.lead"]
        Visit = self.env["commercial.property.visit"]
        Reservation = self.env["commercial.property.reservation"]
        Lease = self.env["commercial.lease"]
        for unit in self:
            domain = [("unit_id", "=", unit.id)]
            unit.enquiry_count = Lead.search_count(domain)
            unit.responded_enquiry_count = Lead.search_count(domain + [("state", "!=", "new")])
            unit.completed_visit_count = Visit.search_count(domain + [("state", "=", "completed")])
            unit.approved_reservation_count = Reservation.search_count(domain + [("state", "=", "approved")])
            unit.contract_count = Lease.search_count(domain + [("state", "in", ("draft", "active", "expired"))])
            unit.lost_enquiry_count = Lead.search_count(domain + [("state", "=", "rejected")])

    @api.depends("maintenance_ids.state", "handover_ids.state")
    def _compute_operational_status(self):
        for unit in self:
            open_tickets = unit.maintenance_ids.filtered(lambda ticket: ticket.state in ("assigned", "in_progress"))
            unit.open_maintenance_count = len(open_tickets)
            if open_tickets:
                unit.operational_status = "under_maintenance"
            elif unit.handover_ids.filtered(lambda handover: handover.state == "draft"):
                unit.operational_status = "awaiting_handover"
            else:
                unit.operational_status = "operational"

    @api.depends(
        "lead_ids.state",
        "lead_ids.visit_ids.state",
        "lead_ids.reservation_ids.state",
        "lead_ids.application_ids.state",
        "current_lease_id",
    )
    def _compute_commercial_progress_stage(self):
        for unit in self:
            stage = "none"
            if unit.lead_ids:
                stage = "enquiry"
            if unit.lead_ids.visit_ids.filtered(lambda visit: visit.state == "completed"):
                stage = "inspection"
            if unit.lead_ids.reservation_ids.filtered(lambda reservation: reservation.state == "approved"):
                stage = "reservation"
            if unit.lead_ids.application_ids:
                stage = "application"
            if unit.current_lease_id:
                stage = "lease"
            unit.commercial_progress_stage = stage

    @api.depends("state", "vacant_since")
    def _compute_vacancy_days(self):
        today = fields.Date.context_today(self)
        for unit in self:
            unit.vacancy_days = (today - unit.vacant_since).days if unit.state == "available" and unit.vacant_since else 0

    @api.depends("image_ids.image_1920", "image_ids.sequence")
    def _compute_primary_image(self):
        for unit in self:
            first_image = unit.image_ids.sorted("sequence")[:1]
            unit.image_1920 = first_image.image_1920 if first_image else False

    def _inverse_primary_image(self):
        for unit in self:
            if unit.image_1920:
                # Update or create first image with the new image data
                first_image = unit.image_ids.sorted("sequence")[:1]
                if first_image:
                    first_image.image_1920 = unit.image_1920
                else:
                    # Create new image if none exists
                    self.env["commercial.property.unit.image"].create({
                        "unit_id": unit.id,
                        "image_1920": unit.image_1920,
                        "sequence": 10,
                    })

    @api.depends(
        "image_ids", "public_name", "public_description", "public_monthly_rent",
        "public_feature_ids", "public_location_hint", "virtual_tour_url",
    )
    def _compute_publication_quality_ok(self):
        for unit in self:
            unit.publication_quality_ok = bool(
                unit.image_ids
                and unit.public_name
                and unit.public_description
                and unit.public_monthly_rent > 0
                and unit.public_feature_ids
                and unit.public_location_hint
                and unit.virtual_tour_url
            )

    @api.model
    def _migrate_images_to_gallery(self):
        """Migrate existing image_1920 to gallery. Safe to run multiple times."""
        units_with_image = self.search([('image_1920', '!=', False)])
        for unit in units_with_image:
            # Only migrate if no gallery images exist yet
            if not unit.image_ids:
                self.env['commercial.property.unit.image'].create({
                    'unit_id': unit.id,
                    'image_1920': unit.image_1920,
                    'sequence': 10,
                    'name': 'Migrated image',
                })
        return True

    @api.model
    def _cron_expire_publications(self):
        today = fields.Date.context_today(self)
        expired = self.search(
            [("is_published", "=", True), ("publication_expiry_date", "!=", False), ("publication_expiry_date", "<", today)]
        )
        expired.write({"is_published": False, "unpublish_reason": "expired"})

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
            if state == "available" and unit.state != "available":
                unit.vacant_since = today
            elif state != "available" and unit.vacant_since:
                unit.vacant_since = False
            if unit.state != state:
                unit.state = state
            if unit.is_default and unit.property_id.state != state:
                unit.property_id.state = state

    def _get_current_lead(self):
        self.ensure_one()
        candidates = self.lead_ids.filtered(lambda lead: lead.state not in ("rejected", "converted"))
        return candidates.sorted("create_date", reverse=True)[:1]

    def _get_current_reservation(self):
        self.ensure_one()
        return self.reservation_ids.filtered(lambda reservation: reservation.state == "approved")[:1]

    def action_create_enquiry(self):
        """Contextual shortcut for an available unit: open a new enquiry pre-filled
        with this unit, reusing the standard commercial.property.lead form."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("New Enquiry"),
            "res_model": "commercial.property.lead",
            "view_mode": "form",
            "target": "current",
            "context": {"default_unit_id": self.id},
        }

    def action_schedule_inspection(self):
        self.ensure_one()
        lead = self._get_current_lead()
        if not lead:
            raise ValidationError(_("Create an enquiry for this unit before scheduling an inspection."))
        return lead.action_schedule_visit()

    def action_create_reservation(self):
        self.ensure_one()
        lead = self._get_current_lead()
        if not lead:
            raise ValidationError(_("Create an enquiry for this unit before requesting a reservation."))
        return lead.action_create_reservation_request()

    def action_view_reservation(self):
        self.ensure_one()
        reservation = self._get_current_reservation() or self.reservation_ids[:1]
        if not reservation:
            raise ValidationError(_("This unit has no reservation on record."))
        action = self.env.ref("commercial_property_management.action_commercial_property_reservation").sudo().read()[0]
        action.update({"res_id": reservation.id, "view_mode": "form", "views": [(False, "form")]})
        return action

    def action_cancel_reservation(self):
        self.ensure_one()
        reservation = self._get_current_reservation()
        if not reservation:
            raise ValidationError(_("This unit has no approved reservation to cancel."))
        reservation.action_cancel()

    def action_create_lease_application(self):
        self.ensure_one()
        lead = self._get_current_lead()
        if not lead:
            raise ValidationError(_("This unit has no enquiry to start a lease application from."))
        return lead.action_create_application()

    def action_view_lease(self):
        self.ensure_one()
        lease = self.current_lease_id or self.lease_ids[:1]
        if not lease:
            raise ValidationError(_("This unit has no lease on record."))
        action = self.env.ref("commercial_property_management.action_commercial_lease").sudo().read()[0]
        action.update({"res_id": lease.id, "view_mode": "form", "views": [(False, "form")]})
        return action

    def action_view_tenant(self):
        self.ensure_one()
        if not self.current_tenant_id:
            raise ValidationError(_("This unit has no tenant on record."))
        action = self.env.ref("commercial_property_management.action_commercial_tenant").sudo().read()[0]
        action.update({"res_id": self.current_tenant_id.id, "view_mode": "form", "views": [(False, "form")]})
        return action

    def action_view_maintenance(self):
        self.ensure_one()
        action = self.env.ref("commercial_property_management.action_commercial_property_maintenance").sudo().read()[0]
        action.update({"domain": [("unit_id", "=", self.id)], "context": {"default_unit_id": self.id}})
        return action

    @api.model
    def _get_public_currency(self):
        """The currency prospect-facing amounts are converted to. Configurable via
        Settings > Commercial Properties (defaults to USD) so a market change never
        requires a code change."""
        currency_id = self.env["ir.config_parameter"].sudo().get_param("commercial_property_management.hermes_public_currency_id")
        if currency_id:
            currency = self.env["res.currency"].browse(int(currency_id)).exists()
            if currency:
                return currency
        return self.env.ref("base.USD", raise_if_not_found=False) or self.env.company.currency_id

    @api.model
    def _get_operating_company(self):
        """The company used for currency conversion. ``env.company`` is empty for
        auth=none requests (no user session), so fall back to a real company
        instead of letting ``res.currency._convert`` raise on an empty recordset."""
        return self.env.company or self.env["res.company"].sudo().search([], limit=1)

    def get_public_data(self):
        self.ensure_one()
        property_type_label = dict(self.property_id._fields["property_type"].selection).get(self.property_type)
        public_currency = self._get_public_currency()
        company = self.company_id or self.env.company
        converted_rent = self.currency_id._convert(self.public_monthly_rent, public_currency, company, fields.Date.context_today(self))
        return {
            "code": self.code,
            "name": self.public_name,
            "description": self.public_description,
            "monthly_rent": converted_rent,
            "currency": public_currency.name,
            "area": self.area,
            "property_type": property_type_label,
            "features": self.public_feature_ids.mapped("name"),
            "city": self.property_id.city or None,
            "building_name": self.property_id.name,
            "unit_name": self.name,
            "entrance_description": self.entrance_description or None,
            "location_hint": self.public_location_hint or None,
            "available_from": fields.Date.to_string(self.available_date) if self.available_date else None,
            "photo_url": "/api/hermes/properties/%s/photo" % self.code if self.image_ids else None,
            "photo_urls": [
                "/api/hermes/properties/%s/photo?index=%d" % (self.code, idx)
                for idx, img in enumerate(self.image_ids.sorted("sequence"))
            ] if self.image_ids else [],
            "virtual_tour_url": self.virtual_tour_url or None,
        }

    @api.model
    def search_public_units(self, min_area=None, max_rent=None, code=None, limit=None, zone=None):
        domain = [("active", "=", True), ("is_published", "=", True), ("state", "=", "available")]
        if min_area is not None:
            domain.append(("area", ">=", min_area))
        if max_rent is not None:
            # max_rent is expressed in the public display currency (see get_public_data);
            # convert it back to the operating currency stored on public_monthly_rent.
            public_currency = self._get_public_currency()
            company = self._get_operating_company()
            operating_currency = company.currency_id
            max_rent = public_currency._convert(max_rent, operating_currency, company, fields.Date.context_today(self))
            domain.append(("public_monthly_rent", "<=", max_rent))
        if code:
            domain.append(("code", "=", code))
        if zone:
            domain += [
                "|", "|", "|", "|",
                ("public_location_hint", "ilike", zone),
                ("property_id.city", "ilike", zone),
                ("property_id.name", "ilike", zone),
                ("name", "ilike", zone),
                ("public_name", "ilike", zone),
            ]
        return self.search(domain, limit=limit, order="public_monthly_rent asc, id")
