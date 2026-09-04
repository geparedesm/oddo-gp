from odoo import api, fields, models
from odoo.exceptions import ValidationError


class JobPilotEducation(models.Model):
    _name = "job_pilot.education"
    _description = "Education"
    _order = "sequence, start_date desc, id desc"

    profile_id = fields.Many2one("job_pilot.profile", required=True, ondelete="cascade", index=True)
    sequence = fields.Integer(default=10)
    institution = fields.Char(required=True)
    degree = fields.Char()
    field_of_study = fields.Char()
    start_date = fields.Date()
    end_date = fields.Date()
    currently_studying = fields.Boolean(string="I am currently studying here")
    grade = fields.Char()
    description = fields.Text()

    @api.constrains("start_date", "end_date")
    def _check_dates(self):
        for record in self:
            if record.end_date and record.start_date and record.end_date < record.start_date:
                raise ValidationError("The end date cannot be earlier than the start date.")


class JobPilotCertification(models.Model):
    _name = "job_pilot.certification"
    _description = "Certification"
    _order = "sequence, issue_date desc, id desc"

    profile_id = fields.Many2one("job_pilot.profile", required=True, ondelete="cascade", index=True)
    sequence = fields.Integer(default=10)
    name = fields.Char(required=True)
    issuing_organization = fields.Char()
    issue_date = fields.Date()
    expiration_date = fields.Date()
    credential_id = fields.Char(string="Credential ID")
    credential_url = fields.Char(string="Credential URL")

    @api.constrains("issue_date", "expiration_date")
    def _check_dates(self):
        for record in self:
            if record.expiration_date and record.issue_date and record.expiration_date < record.issue_date:
                raise ValidationError("The expiration date cannot be earlier than the issue date.")


class JobPilotLanguage(models.Model):
    _name = "job_pilot.language"
    _description = "Language"
    _order = "sequence, id"

    profile_id = fields.Many2one("job_pilot.profile", required=True, ondelete="cascade", index=True)
    sequence = fields.Integer(default=10)
    name = fields.Char(required=True)
    proficiency = fields.Selection(
        [
            ("basic", "Basic"),
            ("conversational", "Conversational"),
            ("fluent", "Fluent"),
            ("native", "Native"),
        ],
        default="conversational",
        required=True,
    )


class JobPilotLeadershipVolunteering(models.Model):
    _name = "job_pilot.leadership.volunteering"
    _description = "Leadership & Volunteering"
    _order = "sequence, start_date desc, id desc"

    profile_id = fields.Many2one("job_pilot.profile", required=True, ondelete="cascade", index=True)
    sequence = fields.Integer(default=10)
    organization = fields.Char(required=True)
    role = fields.Char()
    cause = fields.Char()
    start_date = fields.Date()
    end_date = fields.Date()
    currently_active = fields.Boolean(string="I am currently active here")
    description = fields.Text()


class JobPilotReference(models.Model):
    _name = "job_pilot.reference"
    _description = "Reference"
    _order = "sequence, id"

    profile_id = fields.Many2one("job_pilot.profile", required=True, ondelete="cascade", index=True)
    sequence = fields.Integer(default=10)
    name = fields.Char(required=True)
    relationship = fields.Char()
    company = fields.Char()
    job_title = fields.Char()
    phone = fields.Char()
    email = fields.Char()
    notes = fields.Text()
