from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class CommercialPropertyLead(models.Model):
    _name = "commercial.property.lead"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _description = "Commercial Property Lead"
    _order = "create_date desc, id desc"

    name = fields.Char(string="Contact Name", required=True, tracking=True)
    phone = fields.Char(required=True, tracking=True)
    email = fields.Char(tracking=True)
    company_name = fields.Char(tracking=True)
    business_activity = fields.Char()
    desired_start_date = fields.Date()
    message = fields.Text()
    unit_id = fields.Many2one("commercial.property.unit", string="Commercial Unit", required=True, ondelete="restrict", index=True, tracking=True)
    property_id = fields.Many2one(related="unit_id.property_id", string="Property", store=True, readonly=True, index=True)
    tenant_id = fields.Many2one("res.partner", string="Tenant Draft", readonly=True, copy=False)
    visit_ids = fields.One2many("commercial.property.visit", "lead_id", string="Visits", copy=False)
    reservation_ids = fields.One2many("commercial.property.reservation", "lead_id", string="Reservations", copy=False)
    application_ids = fields.One2many("commercial.property.application", "lead_id", string="Applications", copy=False)
    consent_at = fields.Datetime(string="Consent Given At", required=True, readonly=True, copy=False)
    consent_policy_version = fields.Char(string="Consent Policy Version", readonly=True, copy=False)
    consent_purpose = fields.Char(string="Consent Purpose", readonly=True, copy=False)
    retention_deadline = fields.Datetime(string="Personal Data Retention Deadline", readonly=True, copy=False, index=True)
    anonymized_at = fields.Datetime(string="Personal Data Anonymized At", readonly=True, copy=False, index=True)
    public_request_key_hash = fields.Char(string="Public Request Idempotency Hash", readonly=True, copy=False, index=True)
    public_source_hash = fields.Char(string="Public Source Hash", readonly=True, copy=False, index=True)
    sla_alerted_at = fields.Datetime(string="SLA Alerted At", readonly=True, copy=False)
    source = fields.Selection([("whatsapp", "WhatsApp"), ("manual", "Manual")], required=True, default="manual", index=True)
    source_channel_id = fields.Many2one(
        "commercial.property.distribution.channel", string="Campaign / Channel", index=True,
        help="Which website, property portal or social campaign this enquiry is attributed to.",
    )
    visit_requested_at = fields.Datetime(string="Visit Requested At", readonly=True, copy=False)
    assigned_user_id = fields.Many2one("res.users", string="Assigned Manager", tracking=True, index=True)
    state = fields.Selection(
        [("new", "New"), ("qualified", "Qualified"), ("visit_scheduled", "Visit Scheduled"), ("under_review", "Under Review"), ("rejected", "Rejected"), ("converted", "Converted")],
        default="new", required=True, tracking=True, index=True,
    )
    lost_reason = fields.Selection([("price", "Price"), ("location", "Location"), ("timing", "Timing"), ("requirements", "Requirements"), ("no_response", "No Response"), ("other", "Other")], string="Lost Reason", tracking=True, index=True)
    company_id = fields.Many2one(related="unit_id.company_id", store=True, readonly=True, index=True)

    def _policy_int(self, key, default):
        value = self.env["ir.config_parameter"].sudo().get_param(key, default)
        try:
            return max(int(value), 1)
        except (TypeError, ValueError):
            return default

    def _retention_deadline(self, state="new"):
        parameter = "commercial_property_management.whatsapp_rejected_retention_days" if state == "rejected" else "commercial_property_management.whatsapp_lead_retention_days"
        default = 30 if state == "rejected" else 180
        return fields.Datetime.add(fields.Datetime.now(), days=self._policy_int(parameter, default))

    @api.constrains("unit_id")
    def _check_unit_is_available(self):
        for lead in self:
            if lead.unit_id.state != "available" or not lead.unit_id.is_published:
                raise ValidationError(_("Leads can only be created for published available commercial units."))

    def _check_transition(self, target_state):
        allowed_transitions = {
            "new": {"qualified", "rejected"},
            "qualified": {"visit_scheduled", "under_review", "rejected"},
            "visit_scheduled": {"under_review", "rejected"},
            "under_review": {"converted", "rejected"},
        }
        for lead in self:
            if target_state not in allowed_transitions.get(lead.state, set()):
                raise ValidationError(_("This enquiry cannot move from %(from_state)s to %(to_state)s.", from_state=lead.state, to_state=target_state))

    @api.model_create_multi
    def create(self, vals_list):
        manager = self.env.ref("commercial_property_management.group_property_manager").users.filtered(lambda user: user.active and not user.share)[:1]
        for vals in vals_list:
            if vals.get("state", "new") != "new":
                raise ValidationError(_("New enquiries must start in the New state."))
            vals.setdefault("assigned_user_id", manager.id)
            if vals.get("source") == "whatsapp":
                vals.setdefault("consent_policy_version", self.env["ir.config_parameter"].sudo().get_param("commercial_property_management.whatsapp_consent_policy_version", "EC-2026-1"))
                vals.setdefault("consent_purpose", _("Commercial property enquiry and visit coordination"))
                vals.setdefault("retention_deadline", self._retention_deadline())
        leads = super().create(vals_list)
        for lead in leads:
            if lead.assigned_user_id:
                lead.activity_schedule(
                    "mail.mail_activity_data_todo",
                    user_id=lead.assigned_user_id.id,
                    summary=_("Review new commercial property enquiry"),
                    note=_("Contact the prospect and review their visit request."),
                    date_deadline=fields.Date.add(fields.Date.today(), days=1) if lead.source == "whatsapp" else False,
                )
        return leads

    def write(self, vals):
        if "state" in vals:
            self._check_transition(vals["state"])
            if vals["state"] == "rejected":
                if not vals.get("lost_reason") and any(not lead.lost_reason for lead in self):
                    raise ValidationError(_("Select a lost reason before rejecting an enquiry."))
                vals["retention_deadline"] = self._retention_deadline("rejected")
        return super().write(vals)

    def _cron_anonymize_expired_personal_data(self):
        leads = self.sudo().search([("anonymized_at", "=", False), ("retention_deadline", "!=", False), ("retention_deadline", "<=", fields.Datetime.now())])
        for lead in leads:
            lead.write({"name": _("Anonymized prospect"), "phone": False, "email": False, "company_name": False, "business_activity": False, "desired_start_date": False, "message": False, "visit_requested_at": False, "public_source_hash": False, "anonymized_at": fields.Datetime.now()})

    @api.model
    def _cron_alert_overdue_public_enquiries(self):
        hours = self._policy_int("commercial_property_management.whatsapp_response_sla_business_hours", 8)
        deadline = fields.Datetime.subtract(fields.Datetime.now(), hours=hours)
        overdue = self.sudo().search([("source", "=", "whatsapp"), ("state", "=", "new"), ("create_date", "<=", deadline), ("sla_alerted_at", "=", False)])
        for lead in overdue:
            self.env["commercial.property.integration.alert"].raise_alert(self.env, "queue", "lead-sla-%s" % lead.id, _("Public enquiry response SLA exceeded"), "critical", _("A WhatsApp enquiry remains unreviewed after the configured response SLA."))
        overdue.write({"sla_alerted_at": fields.Datetime.now()})

    def action_qualify(self):
        self._check_transition("qualified")
        self.write({"state": "qualified"})

    def action_schedule_visit(self):
        self.ensure_one()
        self._check_transition("visit_scheduled")
        visit = self.env["commercial.property.visit"].create({"lead_id": self.id, "assigned_user_id": self.assigned_user_id.id or self.env.user.id})
        self.write({"state": "visit_scheduled"})
        return {"type": "ir.actions.act_window", "name": _("Visit Request"), "res_model": "commercial.property.visit", "res_id": visit.id, "view_mode": "form", "target": "current"}

    def action_create_reservation_request(self):
        self.ensure_one()
        if self.state not in ("qualified", "visit_scheduled", "under_review"):
            raise ValidationError(_("Only qualified or reviewed enquiries can request a reservation."))
        return {"type": "ir.actions.act_window", "name": _("Reservation Request"), "res_model": "commercial.property.reservation", "view_mode": "form", "target": "current", "context": {"default_lead_id": self.id}}

    def action_create_application(self):
        self.ensure_one()
        if self.state != "under_review":
            raise ValidationError(_("Only reviewed enquiries can start an application."))
        return {"type": "ir.actions.act_window", "name": _("Application"), "res_model": "commercial.property.application", "view_mode": "form", "target": "current", "context": {"default_lead_id": self.id}}

    def action_start_review(self):
        self._check_transition("under_review")
        self.write({"state": "under_review"})

    def action_reject(self):
        self._check_transition("rejected")
        self.write({"state": "rejected"})

    def action_convert_to_tenant_draft(self):
        self.ensure_one()
        self._check_transition("converted")
        tenant = self.env["res.partner"].create(
            {
                "name": self.company_name or self.name,
                "company_type": "company" if self.company_name else "person",
                "phone": self.phone,
                "email": self.email,
                "is_commercial_tenant": True,
            }
        )
        self.write({"state": "converted", "tenant_id": tenant.id})
        action = self.env.ref("commercial_property_management.action_commercial_tenant").sudo().read()[0]
        action.update({"res_id": tenant.id, "view_mode": "form", "views": [(False, "form")]})
        return action
