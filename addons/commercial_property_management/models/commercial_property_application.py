from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class CommercialPropertyApplication(models.Model):
    _name = "commercial.property.application"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _description = "Commercial Property Application"
    _order = "create_date desc, id desc"

    name = fields.Char(string="Application Reference", required=True, copy=False, readonly=True, default=lambda self: _("New"))
    lead_id = fields.Many2one("commercial.property.lead", required=True, ondelete="restrict", index=True)
    unit_id = fields.Many2one(related="lead_id.unit_id", store=True, readonly=True, index=True)
    property_id = fields.Many2one(related="lead_id.property_id", store=True, readonly=True, index=True)
    applicant_type = fields.Selection([("person", "Person"), ("company", "Company")], required=True, default="person")
    identity_document_received = fields.Boolean()
    financial_document_received = fields.Boolean()
    commercial_reference_received = fields.Boolean()
    document_ids = fields.One2many("commercial.property.application.document", "application_id", string="Private Documents")
    state = fields.Selection([("draft", "Draft"), ("submitted", "Submitted"), ("under_review", "Under Review"), ("approved", "Approved"), ("rejected", "Rejected")], default="draft", required=True, tracking=True, index=True)
    approved_by_id = fields.Many2one("res.users", readonly=True, copy=False)
    approved_at = fields.Datetime(readonly=True, copy=False)
    proposed_monthly_rent = fields.Monetary(string="Proposed Monthly Rent")
    proposed_start_date = fields.Date(string="Proposed Start Date")
    proposed_end_date = fields.Date(string="Proposed End Date")
    currency_id = fields.Many2one(related="unit_id.currency_id", store=True, readonly=True)
    proposal_terms = fields.Text(string="Non-binding Proposal Terms")
    proposal_state = fields.Selection([("draft", "Draft"), ("offered", "Offered"), ("accepted", "Accepted"), ("declined", "Declined")], default="draft", required=True, tracking=True)
    proposal_sent_at = fields.Datetime(readonly=True, copy=False)
    tenant_id = fields.Many2one("res.partner", readonly=True, copy=False)
    lease_id = fields.Many2one("commercial.lease", readonly=True, copy=False)
    company_id = fields.Many2one(related="lead_id.company_id", store=True, readonly=True, index=True)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", _("New")) == _("New"):
                vals["name"] = self.env["ir.sequence"].next_by_code("commercial.property.application") or _("New")
        return super().create(vals_list)

    def _require_state(self, state):
        if any(application.state != state for application in self):
            raise ValidationError(_("This action is not available in the current application state."))

    def _check_checklist_complete(self):
        for application in self:
            required = application.identity_document_received and application.financial_document_received
            if application.applicant_type == "company":
                required = required and application.commercial_reference_received
            if not required:
                raise ValidationError(_("Complete the required application checklist before approval."))

    def action_submit(self):
        self._require_state("draft")
        self.write({"state": "submitted"})

    def action_start_review(self):
        self._require_state("submitted")
        self.write({"state": "under_review"})

    def action_approve(self):
        self._require_state("under_review")
        self._check_checklist_complete()
        self.write({"state": "approved", "approved_by_id": self.env.user.id, "approved_at": fields.Datetime.now()})

    def action_reject(self):
        if any(application.state not in ("submitted", "under_review") for application in self):
            raise ValidationError(_("Only submitted or reviewed applications can be rejected."))
        self.write({"state": "rejected"})

    def action_offer_proposal(self):
        self._require_state("approved")
        for application in self:
            if not application.proposed_monthly_rent or not application.proposed_start_date or not application.proposed_end_date or not application.proposal_terms:
                raise ValidationError(_("Set proposed rent, dates, and non-binding terms before offering a proposal."))
            if application.proposed_end_date < application.proposed_start_date:
                raise ValidationError(_("The proposed end date must be on or after the proposed start date."))
        self.write({"proposal_state": "offered", "proposal_sent_at": fields.Datetime.now()})

    def action_accept_proposal(self):
        if any(application.proposal_state != "offered" for application in self):
            raise ValidationError(_("Only offered proposals can be accepted."))
        self.write({"proposal_state": "accepted"})

    def action_create_draft_lease(self):
        self.ensure_one()
        if self.state != "approved" or self.proposal_state != "accepted" or self.lease_id:
            raise ValidationError(_("Only an approved application with an accepted proposal can create one draft lease."))
        lead = self.lead_id
        tenant = self.env["res.partner"].create({"name": lead.company_name or lead.name, "company_type": "company" if lead.company_name else "person", "phone": lead.phone, "email": lead.email, "is_commercial_tenant": True})
        lease = self.env["commercial.lease"].create({"property_id": self.property_id.id, "unit_id": self.unit_id.id, "tenant_id": tenant.id, "start_date": self.proposed_start_date, "end_date": self.proposed_end_date, "monthly_rent": self.proposed_monthly_rent, "application_id": self.id})
        self.write({"tenant_id": tenant.id, "lease_id": lease.id})
        return {"type": "ir.actions.act_window", "name": _("Draft Lease"), "res_model": "commercial.lease", "res_id": lease.id, "view_mode": "form", "target": "current"}


class CommercialPropertyApplicationDocument(models.Model):
    _name = "commercial.property.application.document"
    _description = "Commercial Property Application Document"
    _order = "id desc"

    application_id = fields.Many2one("commercial.property.application", required=True, ondelete="cascade", index=True)
    document_type = fields.Selection([("identity", "Identity"), ("financial", "Financial"), ("reference", "Commercial Reference"), ("other", "Other")], required=True)
    file = fields.Binary(required=True, attachment=True)
    filename = fields.Char(required=True)
    company_id = fields.Many2one(related="application_id.company_id", store=True, readonly=True, index=True)