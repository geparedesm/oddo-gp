from odoo import fields, models


class CommercialPropertyFeature(models.Model):
    _name = "commercial.property.feature"
    _description = "Commercial Property Public Feature"
    _order = "name, id"

    name = fields.Char(required=True, translate=True)
    active = fields.Boolean(default=True)

    _sql_constraints = [
        ("commercial_property_feature_name_unique", "unique(name)", "The feature name must be unique."),
    ]
