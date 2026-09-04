from odoo import fields, models


class JobPilotResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    job_pilot_codex_api_key = fields.Char(
        string="Codex API Key",
        config_parameter="job_pilot.codex_api_key",
        help="Secret key used by the CV extraction action. It is never shown in logs.",
    )
    job_pilot_codex_endpoint = fields.Char(
        string="Codex Responses Endpoint",
        config_parameter="job_pilot.codex_endpoint",
        default="https://api.openai.com/v1/responses",
    )
    job_pilot_codex_model = fields.Char(
        string="Codex Model",
        config_parameter="job_pilot.codex_model",
        default="gpt-5.3-codex",
    )
