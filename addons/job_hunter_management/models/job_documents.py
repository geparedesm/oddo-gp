import hashlib
import re

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


GENERATOR_MODEL = "deterministic-structured-v1"
PROMPT_VERSION = "phase6-structured-template-v1"


def _ordered_items(value):
    return [item.strip() for item in re.split(r"[,;\n]+", value or "") if item.strip()]


class JobDocumentGenerationRule(models.Model):
    _name = "job.document.generation.rule"
    _description = "Job Document Generation Rule"
    _order = "active desc, id"

    name = fields.Char(required=True)
    active = fields.Boolean(default=True)
    minimum_priority_score = fields.Float(required=True, default=75)

    @api.constrains("minimum_priority_score")
    def _check_minimum_priority_score(self):
        for rule in self:
            if not 0 <= rule.minimum_priority_score <= 100:
                raise ValidationError(_("The document generation threshold must be between 0 and 100."))


class JobApplicationDocument(models.Model):
    _name = "job.application.document"
    _description = "Tailored Job Application Document Version"
    _order = "version desc, id desc"

    application_id = fields.Many2one("job.application", required=True, ondelete="cascade", index=True)
    profile_id = fields.Many2one("job.hunter.profile", required=True, ondelete="restrict", index=True)
    rule_id = fields.Many2one("job.document.generation.rule", required=True, ondelete="restrict")
    version = fields.Integer(required=True, readonly=True)
    state = fields.Selection(
        [("draft", "Draft"), ("reviewed", "Reviewed"), ("approved", "Approved")],
        required=True, default="draft", readonly=True, index=True,
    )
    tailored_cv = fields.Text(string="Tailored CV", required=True)
    cover_letter = fields.Text(required=True)
    generated_at = fields.Datetime(required=True, default=fields.Datetime.now, readonly=True)
    generated_by = fields.Many2one("res.users", required=True, default=lambda self: self.env.user, readonly=True)
    reviewed_at = fields.Datetime(readonly=True)
    reviewed_by = fields.Many2one("res.users", readonly=True)
    approved_at = fields.Datetime(readonly=True)
    approved_by = fields.Many2one("res.users", readonly=True)
    generator_origin = fields.Selection(
        [("structured_profile", "Structured professional profile")], required=True,
        default="structured_profile", readonly=True,
    )
    generator_model = fields.Char(required=True, readonly=True, default=GENERATOR_MODEL)
    prompt_version = fields.Char(required=True, readonly=True, default=PROMPT_VERSION)
    generation_metadata = fields.Json(required=True, readonly=True)
    source_snapshot = fields.Json(required=True, readonly=True)
    profile_version = fields.Integer(required=True, readonly=True)
    master_cv_checksum = fields.Char(readonly=True)
    master_cv_filename = fields.Char(readonly=True)
    change_summary = fields.Text(required=True, readonly=True)
    content_checksum = fields.Char(required=True, readonly=True)
    validation_state = fields.Selection(
        [("passed", "Passed"), ("blocked", "Blocked")], required=True, default="passed", readonly=True,
    )
    validation_message = fields.Text(readonly=True)

    _sql_constraints = [
        ("application_version_unique", "unique(application_id, version)",
         "Document versions must be unique per job application."),
    ]

    @api.model_create_multi
    def create(self, values_list):
        if not self.env.context.get("controlled_document_generation"):
            raise ValidationError(_("Document versions can only be created by the controlled generator."))
        return super().create(values_list)

    def write(self, values):
        workflow_fields = {
            "state", "reviewed_at", "reviewed_by", "approved_at", "approved_by",
            "validation_state", "validation_message",
        }
        immutable_fields = {
            "application_id", "profile_id", "rule_id", "version", "generated_at", "generated_by",
            "generator_origin", "generator_model", "prompt_version", "generation_metadata",
            "source_snapshot", "profile_version", "master_cv_checksum", "master_cv_filename",
            "change_summary", "content_checksum",
        }
        if immutable_fields.intersection(values):
            raise ValidationError(_("Document provenance and source metadata are immutable."))
        if workflow_fields.intersection(values) and not self.env.context.get("controlled_document_workflow"):
            raise ValidationError(_("Use the explicit Review and Approve actions to change document status."))
        if {"tailored_cv", "cover_letter"}.intersection(values) and any(
            document.state != "draft" for document in self
        ):
            raise ValidationError(_("Only Draft document text can be edited."))
        return super().write(values)

    @staticmethod
    def _checksum(cv_text, cover_text):
        return hashlib.sha256((cv_text + "\0" + cover_text).encode("utf-8")).hexdigest()

    def _validate_against_source(self):
        self.ensure_one()
        expected_cv, expected_cover, _summary = self.env["job.application"]._render_documents(
            self.source_snapshot,
        )
        return (
            self.tailored_cv == expected_cv
            and self.cover_letter == expected_cover
            and self.content_checksum == self._checksum(expected_cv, expected_cover)
        )

    def action_review(self):
        for document in self:
            if document.state != "draft":
                raise ValidationError(_("Only Draft documents can be reviewed."))
            if not document._validate_against_source():
                document.with_context(controlled_document_workflow=True).write({
                    "validation_state": "blocked",
                    "validation_message": _(
                        "Content differs from the approved source of truth; it remains Draft for correction."
                    ),
                })
                return False
            document.with_context(controlled_document_workflow=True).write({
                "state": "reviewed", "reviewed_at": fields.Datetime.now(),
                "reviewed_by": self.env.user.id, "validation_state": "passed",
                "validation_message": _("Validated against the frozen approved source snapshot."),
            })
        return True

    def action_approve(self):
        for document in self:
            if document.state != "reviewed":
                raise ValidationError(_("Only Reviewed documents can be approved."))
            if not document._validate_against_source():
                raise ValidationError(_("Approval blocked: content differs from the approved source of truth."))
            document.with_context(controlled_document_workflow=True).write({
                "state": "approved", "approved_at": fields.Datetime.now(),
                "approved_by": self.env.user.id,
            })
        return True


class JobApplicationDocuments(models.Model):
    _inherit = "job.application"

    document_ids = fields.One2many("job.application.document", "application_id", readonly=True)
    document_count = fields.Integer(compute="_compute_document_count")

    @api.depends("document_ids")
    def _compute_document_count(self):
        for application in self:
            application.document_count = len(application.document_ids)

    @staticmethod
    def _source_snapshot(application, profile):
        profile_skills = _ordered_items(profile.skills)
        profile_technologies = _ordered_items(profile.technologies)
        vacancy_keywords = (
            _ordered_items(application.mandatory_skills)
            + _ordered_items(application.desired_skills)
            + _ordered_items(application.required_technologies)
        )
        legitimate = []
        approved = {item.casefold(): item for item in profile_skills + profile_technologies}
        for keyword in vacancy_keywords:
            if keyword.casefold() in approved and approved[keyword.casefold()] not in legitimate:
                legitimate.append(approved[keyword.casefold()])
        remaining = [item for item in profile_skills + profile_technologies if item not in legitimate]
        return {
            "job": {"position": application.name, "company": application.company_name},
            "profile": {
                "name": profile.name,
                "years_experience": profile.years_experience,
                "work_experience": profile.work_experience or "",
                "education": profile.education or "",
                "certifications": profile.certifications or "",
                "languages": profile.languages or "",
                "target_roles": profile.target_roles or "",
                "skills": profile_skills,
                "technologies": profile_technologies,
                "location": profile.location or "",
            },
            "legitimate_keywords": legitimate,
            "remaining_capabilities": remaining,
        }

    @api.model
    def _render_documents(self, snapshot):
        job = snapshot["job"]
        profile = snapshot["profile"]
        keywords = snapshot["legitimate_keywords"]
        capabilities = keywords + snapshot["remaining_capabilities"]
        sections = [
            profile["name"],
            "PROFESSIONAL SUMMARY",
            "Professional targeting %s roles with %s years of experience." % (
                job["position"], "%g" % profile["years_experience"],
            ),
            "CORE SKILLS",
            ", ".join(capabilities),
            "WORK EXPERIENCE",
            profile["work_experience"],
            "EDUCATION",
            profile["education"],
            "CERTIFICATIONS",
            profile["certifications"],
            "LANGUAGES",
            profile["languages"],
        ]
        cv_text = "\n\n".join(section for section in sections if section)
        fit = ", ".join(keywords) if keywords else "the approved professional background"
        cover_text = (
            "Dear Hiring Team at %(company)s,\n\n"
            "I am applying for the %(position)s position. My approved professional profile "
            "shows relevant experience with %(fit)s.\n\n"
            "My documented experience is: %(experience)s\n\n"
            "Thank you for considering my application.\n\nSincerely,\n%(name)s"
        ) % {
            "company": job["company"], "position": job["position"], "fit": fit,
            "experience": profile["work_experience"], "name": profile["name"],
        }
        summary = _("Adjusted the professional summary for %(position)s at %(company)s; prioritized approved matching keywords (%(keywords)s); retained all approved experience, education, certifications, languages, and dates unchanged.") % {
            "position": job["position"], "company": job["company"],
            "keywords": ", ".join(keywords) or _("none"),
        }
        return cv_text, cover_text, summary

    def action_generate_documents(self, profile=None, rule=None):
        profile = profile or self.env["job.hunter.profile"].search([("active", "=", True)], limit=1)
        rule = rule or self.env["job.document.generation.rule"].search([("active", "=", True)], limit=1)
        if not profile or not rule:
            raise UserError(_("An active professional profile and document generation rule are required."))
        for application in self:
            if application.priority_score < rule.minimum_priority_score:
                raise UserError(_("This vacancy priority (%(actual).2f) is below the configured document threshold (%(minimum).2f).") % {
                    "actual": application.priority_score, "minimum": rule.minimum_priority_score,
                })
            snapshot = self._source_snapshot(application, profile)
            cv_text, cover_text, summary = self._render_documents(snapshot)
            latest = self.env["job.application.document"].search(
                [("application_id", "=", application.id)], order="version desc", limit=1,
            )
            self.env["job.application.document"].with_context(controlled_document_generation=True).create({
                "application_id": application.id, "profile_id": profile.id, "rule_id": rule.id,
                "version": (latest.version or 0) + 1, "tailored_cv": cv_text,
                "cover_letter": cover_text, "source_snapshot": snapshot,
                "profile_version": profile.version, "master_cv_checksum": profile.cv_checksum,
                "master_cv_filename": profile.primary_cv_filename, "change_summary": summary,
                "content_checksum": JobApplicationDocument._checksum(cv_text, cover_text),
                "generation_metadata": {
                    "model": GENERATOR_MODEL, "prompt_version": PROMPT_VERSION,
                    "method": "structured deterministic template", "external_provider": False,
                },
                "validation_state": "passed",
                "validation_message": _("Generated exclusively from the frozen approved source snapshot."),
            })
        return True
