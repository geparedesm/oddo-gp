from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class CommercialPropertyReservation(models.Model):
    _name = "commercial.property.reservation"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _description = "Commercial Property Reservation"
    _order = "start_date asc, id desc"

    lead_id = fields.Many2one("commercial.property.lead", required=True, ondelete="restrict", index=True)
    unit_id = fields.Many2one(related="lead_id.unit_id", store=True, readonly=True, index=True)
    property_id = fields.Many2one(related="lead_id.property_id", store=True, readonly=True, index=True)
    start_date = fields.Date(required=True, default=fields.Date.context_today)
    end_date = fields.Date(required=True)
    expires_at = fields.Datetime(string="Approval Expires At", required=True, copy=False)
    approved_by_id = fields.Many2one("res.users", string="Approved By", readonly=True, copy=False)
    state = fields.Selection([("requested", "Requested"), ("approved", "Approved"), ("expired", "Expired"), ("cancelled", "Cancelled")], default="requested", required=True, tracking=True, index=True)
    notes = fields.Text()
    company_id = fields.Many2one(related="lead_id.company_id", store=True, readonly=True, index=True)

    @api.constrains("start_date", "end_date", "expires_at")
    def _check_dates(self):
        for reservation in self:
            if reservation.end_date < reservation.start_date:
                raise ValidationError(_("A reservation end date must be on or after its start date."))
            if reservation.expires_at and fields.Datetime.to_datetime(reservation.expires_at) <= fields.Datetime.to_datetime(fields.Datetime.now()):
                raise ValidationError(_("A reservation approval expiry must be in the future."))

    def _check_conflicts(self):
        for reservation in self:
            lease_conflict = self.env["commercial.lease"].search_count([("unit_id", "=", reservation.unit_id.id), ("state", "=", "active"), ("start_date", "<=", reservation.end_date), ("end_date", ">=", reservation.start_date)])
            reservation_conflict = self.search_count([("id", "!=", reservation.id), ("unit_id", "=", reservation.unit_id.id), ("state", "=", "approved"), ("start_date", "<=", reservation.end_date), ("end_date", ">=", reservation.start_date)])
            if lease_conflict or reservation_conflict:
                raise ValidationError(_("This reservation conflicts with an active or future lease, or another approved reservation."))

    def action_approve(self):
        if any(reservation.state != "requested" for reservation in self):
            raise ValidationError(_("Only requested reservations can be approved."))
        self._check_conflicts()
        self.write({"state": "approved", "approved_by_id": self.env.user.id})
        for reservation in self:
            reservation.activity_schedule("mail.mail_activity_data_todo", user_id=self.env.user.id, date_deadline=fields.Datetime.to_datetime(reservation.expires_at).date(), summary=_("Reservation approval expires"), note=_("Confirm a lease or release this reservation before expiry."))
        self.mapped("unit_id")._sync_availability_from_leases()

    def action_cancel(self):
        if any(reservation.state not in ("requested", "approved") for reservation in self):
            raise ValidationError(_("Only requested or approved reservations can be cancelled."))
        units = self.mapped("unit_id")
        self.write({"state": "cancelled"})
        units._sync_availability_from_leases()

    @api.model
    def _cron_expire_reservations(self):
        reservations = self.search([("state", "=", "approved"), ("expires_at", "<=", fields.Datetime.now())])
        units = reservations.mapped("unit_id")
        reservations.write({"state": "expired"})
        units._sync_availability_from_leases()