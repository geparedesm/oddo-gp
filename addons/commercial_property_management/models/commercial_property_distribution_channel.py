from odoo import fields, models


class CommercialPropertyDistributionChannel(models.Model):
    _name = "commercial.property.distribution.channel"
    _description = "Commercial Property Distribution Channel"
    _order = "name, id"

    name = fields.Char(required=True, translate=True)
    channel_type = fields.Selection(
        [("website", "Website"), ("portal", "Property Portal"), ("social", "Social Campaign"), ("other", "Other")],
        required=True,
        default="website",
    )
    active = fields.Boolean(default=True)
    notes = fields.Text()

    _sql_constraints = [
        ("commercial_property_distribution_channel_name_unique", "unique(name)", "The channel name must be unique."),
    ]
