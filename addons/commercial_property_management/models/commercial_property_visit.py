from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class CommercialPropertyVisit(models.Model):
    _name = "commercial.property.visit"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _description = "Commercial Property Visit"
    _order = "scheduled_at asc, id desc"

    lead_id = fields.Many2one("commercial.property.lead", required=True, ondelete="restrict", index=True)
    unit_id = fields.Many2one(related="lead_id.unit_id", store=True, readonly=True, index=True)
    property_id = fields.Many2one(related="lead_id.property_id", store=True, readonly=True, index=True)
    scheduled_at = fields.Datetime(string="Scheduled For", tracking=True)
    assigned_user_id = fields.Many2one("res.users", string="Assigned Manager", required=True, default=lambda self: self.env.user, tracking=True)
    state = fields.Selection([("requested", "Requested"), ("scheduled", "Scheduled"), ("confirmed", "Confirmed"), ("completed", "Completed"), ("cancelled", "Cancelled")], default="requested", required=True, tracking=True)
    notes = fields.Text()
    company_id = fields.Many2one(related="lead_id.company_id", store=True, readonly=True, index=True)

    @api.constrains("scheduled_at")
    def _check_scheduled_at(self):
        for visit in self:
            if visit.state in ("scheduled", "confirmed") and not visit.scheduled_at:
                raise ValidationError(_("A scheduled visit needs an appointment date and time."))

    def action_schedule(self):
        for visit in self:
            if visit.state != "requested" or not visit.scheduled_at:
                raise ValidationError(_("Only requested visits with a date and time can be scheduled."))
        self.write({"state": "scheduled"})

    def action_confirm(self):
        for visit in self:
            if visit.state != "scheduled":
                raise ValidationError(_("Only scheduled visits can be confirmed."))
        self.write({"state": "confirmed"})
        for visit in self:
            visit.activity_schedule("mail.mail_activity_data_todo", user_id=visit.assigned_user_id.id, date_deadline=fields.Datetime.to_datetime(visit.scheduled_at).date(), summary=_("Follow up commercial property visit"), note=_("Record the outcome of the confirmed visit."))

    def action_complete(self):
        if any(visit.state != "confirmed" for visit in self):
            raise ValidationError(_("Only confirmed visits can be completed."))
        self.write({"state": "completed"})

    def action_cancel(self):
        if any(visit.state in ("completed", "cancelled") for visit in self):
            raise ValidationError(_("Completed or cancelled visits cannot be cancelled again."))
        self.write({"state": "cancelled"})