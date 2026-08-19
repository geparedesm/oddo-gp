from odoo import _, fields, models


class CommercialPropertyIntegrationAlert(models.Model):
    _name = "commercial.property.integration.alert"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _description = "Commercial Property Integration Alert"
    _order = "create_date desc, id desc"

    name = fields.Char(required=True, readonly=True)
    channel = fields.Selection([("api", "Public API"), ("mcp", "Hermes MCP"), ("queue", "Operational Queue")], required=True, index=True)
    severity = fields.Selection([("warning", "Warning"), ("critical", "Critical")], default="warning", required=True, index=True)
    fingerprint = fields.Char(required=True, index=True, copy=False)
    details = fields.Char(readonly=True)
    state = fields.Selection([("open", "Open"), ("resolved", "Resolved")], default="open", required=True, tracking=True, index=True)
    company_id = fields.Many2one("res.company", required=True, default=lambda self: self.env.company, index=True)

    _sql_constraints = [("commercial_property_integration_alert_fingerprint_unique", "unique(fingerprint, company_id)", "This operational alert is already open.")]

    @classmethod
    def raise_alert(cls, env, channel, fingerprint, name, severity="warning", details=False):
        # ``env.company`` is empty for the public/anonymous env used by
        # auth="none" controllers (no res.users context), so fall back to the
        # first configured company rather than crashing on a required field.
        company = env.company or env["res.company"].sudo().search([], limit=1)
        alert = env[cls._name].sudo().search([("fingerprint", "=", fingerprint), ("company_id", "=", company.id)], limit=1)
        if alert:
            if alert.state == "resolved":
                alert.write({"state": "open", "severity": severity, "details": details})
            return alert
        alert = env[cls._name].sudo().create({"name": name, "channel": channel, "severity": severity, "fingerprint": fingerprint, "details": details, "company_id": company.id})
        manager = env.ref("commercial_property_management.group_property_manager").sudo().users.filtered(lambda user: user.active and not user.share)[:1]
        if manager:
            alert.activity_schedule("mail.mail_activity_data_todo", user_id=manager.id, summary=_("Review property integration alert"), note=name)
        return alert

    def action_resolve(self):
        self.write({"state": "resolved"})