from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class JobApplication(models.Model):
    _name = "job.application"
    _description = "Job Application"
    _order = "date_found desc, id desc"

    name = fields.Char(string="Position", required=True)
    company_name = fields.Char(string="Company", required=True)
    location = fields.Char()
    job_url = fields.Char(string="Job URL", required=True)
    source = fields.Selection(
        [
            ("seek", "SEEK"),
            ("linkedin", "LinkedIn"),
            ("indeed", "Indeed"),
            ("jora", "Jora"),
            ("company_careers", "Company Careers"),
            ("other", "Other"),
        ],
        required=True,
        default="other",
    )
    salary_min = fields.Float(string="Minimum Salary")
    salary_max = fields.Float(string="Maximum Salary")
    salary_currency = fields.Char(string="Salary Currency")
    sponsorship_status = fields.Selection(
        [("yes", "Yes"), ("no", "No"), ("unknown", "Unknown")],
        string="Sponsorship Status",
        required=True,
        default="unknown",
    )
    match_score = fields.Float(string="Match Score (%)")
    state = fields.Selection(
        [
            ("found", "Found"),
            ("analysing", "Analysing"),
            ("good_match", "Good Match"),
            ("ready_to_apply", "Ready to Apply"),
            ("applied", "Applied"),
            ("interview", "Interview"),
            ("offer", "Offer"),
            ("rejected", "Rejected"),
        ],
        required=True,
        default="found",
    )
    job_description = fields.Text(string="Job Description")
    cv_file = fields.Binary(string="CV", attachment=True)
    cv_filename = fields.Char(string="CV Filename")
    cover_letter = fields.Text(string="Cover Letter")
    date_found = fields.Date(string="Date Found", required=True, default=fields.Date.context_today)
    date_applied = fields.Date(string="Date Applied")
    notes = fields.Text()

    _sql_constraints = [
        (
            "job_application_company_position_url_unique",
            "unique(company_name, name, job_url)",
            "An application for this company, position, and job URL already exists.",
        ),
    ]

    @api.constrains("name", "company_name", "job_url")
    def _check_required_text(self):
        for application in self:
            if not all(
                value and value.strip()
                for value in (application.name, application.company_name, application.job_url)
            ):
                raise ValidationError(
                    _("Position, company, and job URL cannot be empty or contain only spaces.")
                )

    @api.constrains("match_score")
    def _check_match_score(self):
        for application in self:
            if not 0 <= application.match_score <= 100:
                raise ValidationError(_("Match score must be between 0 and 100."))

    @api.constrains("date_applied", "state")
    def _check_date_applied(self):
        allowed_states = {"applied", "interview", "offer", "rejected"}
        for application in self:
            if application.date_applied and application.state not in allowed_states:
                raise ValidationError(
                    _("Date applied can only be set for an applied, interview, offer, or rejected application.")
                )

    @api.constrains("salary_min", "salary_max")
    def _check_salary_range(self):
        for application in self:
            if (
                application.salary_min
                and application.salary_max
                and application.salary_min > application.salary_max
            ):
                raise ValidationError(_("Minimum salary cannot exceed maximum salary."))
