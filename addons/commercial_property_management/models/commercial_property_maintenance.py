from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class CommercialPropertyMaintenance(models.Model):
    _name = "commercial.property.maintenance"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _description = "Commercial Property Maintenance Ticket"
    _order = "create_date desc, id desc"

    name = fields.Char(string="Reference", required=True, copy=False, readonly=True, default=lambda self: _("New"))
    property_id = fields.Many2one("commercial.property", string="Building", required=True, ondelete="cascade", index=True)
    unit_id = fields.Many2one(
        "commercial.property.unit",
        string="Commercial Unit",
        ondelete="cascade",
        index=True,
        domain="[('property_id', '=', property_id)]",
        help="Leave empty for a building-wide ticket, such as a common area or shared facility.",
    )
    category = fields.Selection(
        [
            ("inspection", "Inspection"),
            ("damage", "Damage"),
            ("cleaning", "Cleaning"),
            ("utilities", "Utilities"),
            ("repair", "Repair"),
            ("preventive", "Preventive Maintenance"),
        ],
        required=True,
        default="inspection",
        tracking=True,
    )
    description = fields.Text(required=True)
    state = fields.Selection(
        [
            ("new", "New"),
            ("assigned", "Assigned"),
            ("in_progress", "In Progress"),
            ("completed", "Completed"),
            ("cancelled", "Cancelled"),
        ],
        default="new",
        required=True,
        tracking=True,
        index=True,
    )
    assigned_user_id = fields.Many2one("res.users", string="Internal Owner", tracking=True)
    provider_id = fields.Many2one("res.partner", string="External Provider", tracking=True)
    due_date = fields.Date(tracking=True)
    cost_estimate = fields.Monetary()
    actual_cost = fields.Monetary()
    currency_id = fields.Many2one(related="property_id.currency_id", store=True, readonly=True)
    completion_notes = fields.Text()
    closed_by_id = fields.Many2one("res.users", string="Closed By", readonly=True, copy=False)
    closed_at = fields.Datetime(string="Closed At", readonly=True, copy=False)
    company_id = fields.Many2one(related="property_id.company_id", store=True, readonly=True, index=True)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", _("New")) == _("New"):
                vals["name"] = self.env["ir.sequence"].next_by_code("commercial.property.maintenance") or _("New")
        return super().create(vals_list)

    @api.constrains("property_id", "unit_id")
    def _check_unit_belongs_to_property(self):
        for ticket in self:
            if ticket.unit_id and ticket.unit_id.property_id != ticket.property_id:
                raise ValidationError(_("The commercial unit must belong to the selected building."))

    @api.constrains("assigned_user_id", "provider_id")
    def _check_single_assignee(self):
        for ticket in self:
            if ticket.assigned_user_id and ticket.provider_id:
                raise ValidationError(_("Assign a maintenance ticket to either an internal owner or an external provider, not both."))

    @api.constrains("cost_estimate", "actual_cost")
    def _check_costs(self):
        for ticket in self:
            if ticket.cost_estimate < 0 or ticket.actual_cost < 0:
                raise ValidationError(_("Maintenance costs cannot be negative."))

    def action_assign(self):
        if any(ticket.state != "new" for ticket in self):
            raise ValidationError(_("Only new tickets can be assigned."))
        if any(not (ticket.assigned_user_id or ticket.provider_id) for ticket in self):
            raise ValidationError(_("Set an internal owner or an external provider before assigning a ticket."))
        self.write({"state": "assigned"})
        for ticket in self.filtered("assigned_user_id"):
            ticket.activity_schedule(
                "mail.mail_activity_data_todo",
                user_id=ticket.assigned_user_id.id,
                date_deadline=ticket.due_date,
                summary=_("Maintenance ticket assigned"),
                note=_("Complete or update the assigned maintenance ticket."),
            )

    def action_start(self):
        if any(ticket.state != "assigned" for ticket in self):
            raise ValidationError(_("Only assigned tickets can start work."))
        self.write({"state": "in_progress"})

    def action_complete(self):
        if any(ticket.state not in ("assigned", "in_progress") for ticket in self):
            raise ValidationError(_("Only assigned or in-progress tickets can be completed."))
        if any(not ticket.completion_notes for ticket in self):
            raise ValidationError(_("Add completion notes before closing a maintenance ticket."))
        self.write({"state": "completed", "closed_by_id": self.env.user.id, "closed_at": fields.Datetime.now()})

    def action_cancel(self):
        if any(ticket.state in ("completed", "cancelled") for ticket in self):
            raise ValidationError(_("Completed or cancelled tickets cannot be cancelled again."))
        self.write({"state": "cancelled"})
