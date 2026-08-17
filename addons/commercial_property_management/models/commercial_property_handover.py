from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class CommercialPropertyHandover(models.Model):
    _name = "commercial.property.handover"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _description = "Commercial Property Delivery/Return Checklist"
    _order = "create_date desc, id desc"

    name = fields.Char(string="Reference", required=True, copy=False, readonly=True, default=lambda self: _("New"))
    handover_type = fields.Selection([("delivery", "Delivery"), ("return", "Return")], required=True, default="delivery", tracking=True)
    unit_id = fields.Many2one("commercial.property.unit", string="Commercial Unit", required=True, ondelete="cascade", index=True)
    property_id = fields.Many2one(related="unit_id.property_id", store=True, readonly=True, index=True)
    lease_id = fields.Many2one("commercial.lease", domain="[('unit_id', '=', unit_id)]")
    state = fields.Selection([("draft", "Draft"), ("completed", "Completed")], default="draft", required=True, tracking=True, index=True)
    performed_by_id = fields.Many2one("res.users", string="Performed By", default=lambda self: self.env.user, tracking=True)
    performed_at = fields.Datetime(readonly=True, copy=False)
    overall_notes = fields.Text()
    line_ids = fields.One2many("commercial.property.handover.line", "handover_id", string="Checklist Items", copy=True)
    company_id = fields.Many2one(related="unit_id.company_id", store=True, readonly=True, index=True)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", _("New")) == _("New"):
                vals["name"] = self.env["ir.sequence"].next_by_code("commercial.property.handover") or _("New")
        return super().create(vals_list)

    def action_complete(self):
        if any(handover.state != "draft" for handover in self):
            raise ValidationError(_("Only draft checklists can be completed."))
        if any(not handover.line_ids for handover in self):
            raise ValidationError(_("Add at least one checklist item before completing a handover."))
        self.write({"state": "completed", "performed_at": fields.Datetime.now()})


class CommercialPropertyHandoverLine(models.Model):
    _name = "commercial.property.handover.line"
    _description = "Commercial Property Delivery/Return Checklist Item"
    _order = "id"

    handover_id = fields.Many2one("commercial.property.handover", required=True, ondelete="cascade", index=True)
    description = fields.Char(required=True)
    condition = fields.Selection(
        [("good", "Good"), ("fair", "Fair"), ("damaged", "Damaged"), ("missing", "Missing")],
        required=True,
        default="good",
    )
    notes = fields.Text()
    photo = fields.Image(max_width=1920, max_height=1920)
    company_id = fields.Many2one(related="handover_id.company_id", store=True, readonly=True, index=True)
