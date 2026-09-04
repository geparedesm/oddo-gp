from odoo import api, fields, models
from odoo.exceptions import ValidationError


class JobPilotWorkExperience(models.Model):
    _name = "job_pilot.work.experience"
    _description = "Work Experience"
    _order = "sequence, start_date desc, id desc"

    profile_id = fields.Many2one("job_pilot.profile", required=True, ondelete="cascade", index=True)
    sequence = fields.Integer(default=10)
    company_name = fields.Char(required=True)
    job_title = fields.Char(required=True)
    location = fields.Char()
    start_date = fields.Date(required=True)
    end_date = fields.Date()
    currently_working = fields.Boolean(string="I currently work here")
    description = fields.Text()
    project_ids = fields.One2many("job_pilot.work.experience.project", "experience_id", string="Projects")
    item_ids = fields.One2many(
        "job_pilot.work.experience.item", "experience_id", string="Responsibilities & Achievements"
    )

    @api.constrains("start_date", "end_date", "currently_working")
    def _check_dates(self):
        for experience in self:
            if experience.currently_working and experience.end_date:
                raise ValidationError("A current position cannot have an end date.")
            if experience.end_date and experience.start_date and experience.end_date < experience.start_date:
                raise ValidationError("The end date cannot be earlier than the start date.")


class JobPilotWorkExperienceProject(models.Model):
    _name = "job_pilot.work.experience.project"
    _description = "Work Experience Project"
    _order = "sequence, id"

    experience_id = fields.Many2one(
        "job_pilot.work.experience", required=True, ondelete="cascade", index=True
    )
    profile_id = fields.Many2one(
        "job_pilot.profile", related="experience_id.profile_id", store=True, index=True
    )
    sequence = fields.Integer(default=10)
    name = fields.Char(required=True)
    description = fields.Text()
    start_date = fields.Date()
    end_date = fields.Date()
    url = fields.Char(string="URL")
    item_ids = fields.One2many(
        "job_pilot.work.experience.item", "project_id", string="Responsibilities & Achievements"
    )


class JobPilotWorkExperienceItem(models.Model):
    _name = "job_pilot.work.experience.item"
    _description = "Work Experience Responsibility or Achievement"
    _order = "sequence, id"

    experience_id = fields.Many2one(
        "job_pilot.work.experience", required=True, ondelete="cascade", index=True
    )
    profile_id = fields.Many2one(
        "job_pilot.profile", related="experience_id.profile_id", store=True, index=True
    )
    project_id = fields.Many2one(
        "job_pilot.work.experience.project",
        string="Project",
        domain="[('experience_id', '=', experience_id)]",
    )
    sequence = fields.Integer(default=10)
    item_type = fields.Selection(
        [("responsibility", "Responsibility"), ("achievement", "Achievement")],
        required=True,
        default="responsibility",
    )
    description = fields.Text(required=True)
