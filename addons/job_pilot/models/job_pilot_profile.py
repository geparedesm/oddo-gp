from odoo import api, fields, models


class JobPilotProfile(models.Model):
    _name = "job_pilot.profile"
    _description = "Career Profile"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _rec_name = "name"

    active = fields.Boolean(default=True)
    name = fields.Char(required=True, tracking=True)
    user_id = fields.Many2one(
        "res.users",
        string="User",
        required=True,
        default=lambda self: self.env.user.id,
        ondelete="cascade",
        index=True,
        tracking=True,
    )
    partner_id = fields.Many2one("res.partner", string="Related Contact")
    photo = fields.Binary(string="Photo", attachment=True)

    professional_title = fields.Char(tracking=True)
    professional_summary = fields.Text()
    attribute_ids = fields.One2many("job_pilot.profile.attribute", "profile_id", string="Attributes")

    birthdate = fields.Date(string="Date of Birth")
    gender = fields.Selection(
        [
            ("male", "Male"),
            ("female", "Female"),
            ("other", "Other"),
            ("not_specified", "Prefer not to say"),
        ],
    )
    nationality_id = fields.Many2one("res.country", string="Nationality")
    phone = fields.Char()
    mobile = fields.Char()
    email = fields.Char()
    street = fields.Char()
    street2 = fields.Char()
    city = fields.Char()
    state_id = fields.Many2one("res.country.state", string="State")
    zip = fields.Char(string="ZIP")
    country_id = fields.Many2one("res.country", string="Country")

    skill_ids = fields.One2many("job_pilot.skill", "profile_id", string="Skills")
    experience_ids = fields.One2many("job_pilot.work.experience", "profile_id", string="Work Experience")
    education_ids = fields.One2many("job_pilot.education", "profile_id", string="Education")
    certification_ids = fields.One2many("job_pilot.certification", "profile_id", string="Certifications")
    language_ids = fields.One2many("job_pilot.language", "profile_id", string="Languages")
    leadership_ids = fields.One2many(
        "job_pilot.leadership.volunteering", "profile_id", string="Leadership & Volunteering"
    )
    reference_ids = fields.One2many("job_pilot.reference", "profile_id", string="References")
    additional_info_ids = fields.One2many(
        "job_pilot.additional.info", "profile_id", string="Additional Information"
    )
    cv_upload_ids = fields.One2many("job_pilot.cv.upload", "profile_id", string="CV Uploads")
    cv_upload_count = fields.Integer(compute="_compute_cv_upload_count")

    _sql_constraints = [
        ("user_id_unique", "unique(user_id)", "Each user can have only one career profile."),
    ]

    @api.depends("cv_upload_ids")
    def _compute_cv_upload_count(self):
        for profile in self:
            profile.cv_upload_count = len(profile.cv_upload_ids)

    def action_open_cv_uploads(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": "CV Uploads",
            "res_model": "job_pilot.cv.upload",
            "view_mode": "tree,form",
            "domain": [("profile_id", "=", self.id)],
            "context": {"default_profile_id": self.id},
        }

    @api.onchange("user_id")
    def _onchange_user_id(self):
        for profile in self:
            if profile.user_id and not profile.name:
                profile.name = profile.user_id.name
            if profile.user_id and not profile.email:
                profile.email = profile.user_id.email


class JobPilotProfileAttribute(models.Model):
    _name = "job_pilot.profile.attribute"
    _description = "Career Profile Attribute"
    _order = "sequence, id"

    profile_id = fields.Many2one("job_pilot.profile", required=True, ondelete="cascade", index=True)
    sequence = fields.Integer(default=10)
    name = fields.Char(required=True, string="Attribute")
    value = fields.Char(string="Value")


class JobPilotAdditionalInfo(models.Model):
    _name = "job_pilot.additional.info"
    _description = "Career Profile Additional Information"
    _order = "sequence, id"

    profile_id = fields.Many2one("job_pilot.profile", required=True, ondelete="cascade", index=True)
    sequence = fields.Integer(default=10)
    title = fields.Char(required=True)
    description = fields.Text()
