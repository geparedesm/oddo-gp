from odoo import api, fields, models
from odoo.exceptions import ValidationError


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    whatsapp_intake_enabled = fields.Boolean(string="Enable WhatsApp Enquiry Intake", config_parameter="commercial_property_management.whatsapp_intake_enabled")
    whatsapp_jurisdiction = fields.Char(string="Jurisdiction", config_parameter="commercial_property_management.whatsapp_jurisdiction")
    whatsapp_consent_policy_version = fields.Char(string="Consent Policy Version", config_parameter="commercial_property_management.whatsapp_consent_policy_version")
    whatsapp_lead_retention_days = fields.Integer(string="Open Lead Retention (days)", config_parameter="commercial_property_management.whatsapp_lead_retention_days")
    whatsapp_rejected_retention_days = fields.Integer(string="Rejected Lead Retention (days)", config_parameter="commercial_property_management.whatsapp_rejected_retention_days")
    whatsapp_consent_audit_retention_days = fields.Integer(string="Consent Audit Retention (days)", config_parameter="commercial_property_management.whatsapp_consent_audit_retention_days")
    whatsapp_response_sla_business_hours = fields.Integer(string="First Response SLA (business hours)", config_parameter="commercial_property_management.whatsapp_response_sla_business_hours")
    whatsapp_visit_hours = fields.Char(string="Visit Hours", config_parameter="commercial_property_management.whatsapp_visit_hours")
    whatsapp_public_rate_limit = fields.Integer(string="Public Enquiry Rate Limit (per hour)", config_parameter="commercial_property_management.whatsapp_public_rate_limit")
    hermes_public_currency_id = fields.Many2one(
        "res.currency", string="Hermes Public Price Currency",
        config_parameter="commercial_property_management.hermes_public_currency_id",
        default=lambda self: self.env.ref("base.USD", raise_if_not_found=False),
        help="Currency Hermes shows to WhatsApp prospects, converted from each property's operating currency.",
    )

    @api.constrains("whatsapp_lead_retention_days", "whatsapp_rejected_retention_days", "whatsapp_consent_audit_retention_days", "whatsapp_response_sla_business_hours", "whatsapp_public_rate_limit")
    def _check_positive_policy_intervals(self):
        for settings in self:
            if any(value < 1 for value in [settings.whatsapp_lead_retention_days, settings.whatsapp_rejected_retention_days, settings.whatsapp_consent_audit_retention_days, settings.whatsapp_response_sla_business_hours, settings.whatsapp_public_rate_limit]):
                raise ValidationError("Retention periods and SLA must be at least one day or hour.")