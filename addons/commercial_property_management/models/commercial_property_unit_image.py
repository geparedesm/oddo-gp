from odoo import api, fields, models


class CommercialPropertyUnitImage(models.Model):
    _name = "commercial.property.unit.image"
    _description = "Commercial Property Unit Image"
    _order = "sequence, id"

    unit_id = fields.Many2one(
        "commercial.property.unit",
        string="Unit",
        required=True,
        ondelete="cascade",
        index=True,
    )
    image_1920 = fields.Image(string="Photo", max_width=1920, max_height=1920)
    sequence = fields.Integer(default=10)
    name = fields.Char(string="Description")
    create_date = fields.Datetime(readonly=True)
