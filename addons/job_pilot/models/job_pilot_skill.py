from odoo import fields, models


class JobPilotSkillCategory(models.Model):
    _name = "job_pilot.skill.category"
    _description = "Skill Category"
    _order = "sequence, name"

    name = fields.Char(required=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)

    _sql_constraints = [
        ("name_unique", "unique(name)", "A skill category with this name already exists."),
    ]


class JobPilotSkill(models.Model):
    _name = "job_pilot.skill"
    _description = "Career Profile Skill"
    _order = "sequence, id"

    profile_id = fields.Many2one("job_pilot.profile", required=True, ondelete="cascade", index=True)
    sequence = fields.Integer(default=10)
    name = fields.Char(required=True)
    category_id = fields.Many2one("job_pilot.skill.category", required=True, string="Category")
    level = fields.Selection(
        [
            ("beginner", "Beginner"),
            ("intermediate", "Intermediate"),
            ("advanced", "Advanced"),
            ("expert", "Expert"),
        ],
        default="intermediate",
    )
