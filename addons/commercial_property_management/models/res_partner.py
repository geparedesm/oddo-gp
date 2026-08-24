from odoo import fields, models


class ResPartner(models.Model):
    _inherit = "res.partner"

    is_commercial_tenant = fields.Boolean(
        string="Commercial Tenant",
        help="Marks this contact as a tenant managed by Commercial Properties.",
    )
    tenant_identification_number = fields.Char(
        string="Identification Number",
        groups="commercial_property_management.group_property_manager",
        help="Private identification number used for commercial lease administration.",
    )
    tenant_internal_notes = fields.Text(
        string="Tenant Internal Notes",
        groups="commercial_property_management.group_property_manager",
        help="Private operational notes. These are not visible to Property Users or portal users.",
    )
    tenant_id_document = fields.Binary(
        string="Cédula / Documento de Identidad",
        attachment=True,
        groups="commercial_property_management.group_property_manager",
        help="Upload the tenant's identification document (PDF).",
    )
    tenant_id_document_filename = fields.Char(
        string="ID Document Filename",
        groups="commercial_property_management.group_property_manager",
    )
