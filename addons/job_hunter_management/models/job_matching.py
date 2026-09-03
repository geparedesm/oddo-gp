import base64
import hashlib
import logging
import re

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


_logger = logging.getLogger(__name__)


def _items(value, language_names=False):
    parts = re.split(r"[,;\n]+", value or "")
    if language_names:
        parts = [part.split(":", 1)[0] for part in parts]
    return {part.strip().casefold(): part.strip() for part in parts if part.strip()}


def _lines(values):
    return "\n".join(sorted(values, key=str.casefold))


class JobHunterProfile(models.Model):
    _name = "job.hunter.profile"
    _description = "Reusable Professional Profile"
    _order = "active desc, id desc"

    name = fields.Char(required=True)
    active = fields.Boolean(default=True)
    version = fields.Integer(required=True, default=1, readonly=True)
    skills = fields.Text(required=True)
    technologies = fields.Text()
    years_experience = fields.Float(string="Years of Experience")
    work_experience = fields.Text()
    education = fields.Text()
    certifications = fields.Text()
    languages = fields.Text(help="One language per line, optionally followed by its level.")
    target_roles = fields.Text()
    location = fields.Char()
    remote_ok = fields.Boolean(string="Remote", default=True)
    hybrid_ok = fields.Boolean(string="Hybrid", default=True)
    onsite_ok = fields.Boolean(string="Onsite", default=True)
    target_salary = fields.Float()
    salary_currency = fields.Char(default="AUD")
    primary_cv = fields.Binary(string="Primary CV", attachment=True)
    primary_cv_filename = fields.Char(string="CV Filename")
    cv_checksum = fields.Char(compute="_compute_cv_checksum", store=True, readonly=True)
    last_hermes_search_at = fields.Datetime(readonly=True, copy=False)

    @api.depends("primary_cv")
    def _compute_cv_checksum(self):
        for profile in self:
            try:
                content = base64.b64decode(profile.primary_cv or b"", validate=False)
            except (ValueError, TypeError):
                content = b""
            profile.cv_checksum = hashlib.sha256(content).hexdigest() if content else False

    def write(self, values):
        versioned = {
            "skills", "technologies", "years_experience", "work_experience", "education",
            "certifications", "languages", "target_roles", "location", "remote_ok", "hybrid_ok",
            "onsite_ok", "target_salary", "salary_currency", "primary_cv", "primary_cv_filename",
        }
        if versioned.intersection(values):
            for profile in self:
                super(JobHunterProfile, profile).write(dict(values, version=profile.version + 1))
            return True
        return super().write(values)

    def _hermes_search_config(self):
        self.ensure_one()
        config_model = self.env["job.hunter.search.config"]
        config = config_model.search([("profile_id", "=", self.id)], limit=1)
        if not config:
            config = config_model.create({
                "name": _("Hermes - %s") % self.name,
                "profile_id": self.id,
            })
        elif not config.active:
            config.active = True
        return config

    def run_hermes_search(self):
        self.ensure_one()
        return self.env["job.hunter.search.run"].run_config(
            self._hermes_search_config(), include_fixtures=False,
        )

    def action_run_hermes_search(self):
        self.run_hermes_search()
        return {"type": "ir.actions.client", "tag": "reload"}

    @api.model
    def action_run_all_hermes_searches(self):
        summary = self.run_all_hermes_searches()
        return {
            "type": "ir.actions.client", "tag": "display_notification",
            "params": {
                "title": _("Hermes search completed"),
                "message": _("%(profiles)s profiles processed, %(runs)s runs, %(errors)s errors.") % summary,
                "type": "warning" if summary["errors"] else "success", "sticky": False,
            },
        }

    @api.model
    def run_all_hermes_searches(self):
        profiles = self.search([("active", "=", True)])
        summary = {"runs": 0, "profiles_processed": 0, "errors": 0, "timestamp": False}
        for profile in profiles:
            summary["profiles_processed"] += 1
            try:
                with self.env.cr.savepoint():
                    profile.run_hermes_search()
                summary["runs"] += 1
            except Exception:
                _logger.exception("Controlled Hermes search failure for profile %s", profile.id)
                attempted_at = fields.Datetime.now()
                profile.write({"last_hermes_search_at": attempted_at})
                summary["errors"] += 1
        summary["timestamp"] = fields.Datetime.to_string(fields.Datetime.now())
        return summary

    @api.constrains("years_experience", "target_salary")
    def _check_non_negative_values(self):
        for profile in self:
            if profile.years_experience < 0 or profile.target_salary < 0:
                raise ValidationError(_("Experience and target salary cannot be negative."))


class JobHunterMatchRule(models.Model):
    _name = "job.hunter.match.rule"
    _description = "Job Match State Rule"
    _order = "active desc, id"

    name = fields.Char(required=True)
    active = fields.Boolean(default=True)
    high_score = fields.Float(required=True, default=75)
    medium_score = fields.Float(required=True, default=50)
    medium_state = fields.Selection([("found", "Found"), ("analysing", "Analysing")], default="analysing", required=True)
    low_state = fields.Selection([("keep", "Keep current state"), ("ignored", "Ignored")], default="keep", required=True)

    @api.constrains("high_score", "medium_score")
    def _check_thresholds(self):
        for rule in self:
            if not 0 <= rule.medium_score < rule.high_score <= 100:
                raise ValidationError(_("Thresholds must satisfy 0 <= medium < high <= 100."))


class JobMatchAnalysis(models.Model):
    _name = "job.match.analysis"
    _description = "Job Match Analysis Trace"
    _order = "analyzed_at desc, id desc"

    application_id = fields.Many2one("job.application", required=True, ondelete="cascade", index=True)
    profile_id = fields.Many2one("job.hunter.profile", required=True, ondelete="restrict")
    rule_id = fields.Many2one("job.hunter.match.rule", required=True, ondelete="restrict")
    score = fields.Float(required=True)
    criteria = fields.Json(required=True)
    explanation = fields.Text(required=True)
    profile_version = fields.Integer(required=True)
    cv_checksum = fields.Char()
    cv_filename = fields.Char()
    state_before = fields.Char(required=True)
    state_after = fields.Char(required=True)
    analyzed_at = fields.Datetime(required=True, default=fields.Datetime.now)
    analyzed_by = fields.Many2one("res.users", required=True, default=lambda self: self.env.user)


class JobApplicationMatching(models.Model):
    _inherit = "job.application"

    mandatory_skills = fields.Text()
    desired_skills = fields.Text()
    required_technologies = fields.Text()
    required_years_experience = fields.Float()
    required_seniority = fields.Selection([("junior", "Junior"), ("mid", "Mid"), ("senior", "Senior"), ("lead", "Lead")])
    required_education = fields.Char()
    required_languages = fields.Text()
    target_role = fields.Char()
    match_strengths = fields.Text(readonly=True)
    match_gaps = fields.Text(readonly=True)
    missing_mandatory_requirements = fields.Text(readonly=True)
    matched_skills = fields.Text(readonly=True)
    missing_skills = fields.Text(readonly=True)
    match_explanation = fields.Text(readonly=True)
    match_profile_id = fields.Many2one("job.hunter.profile", readonly=True, ondelete="restrict")
    match_profile_version = fields.Integer(readonly=True)
    match_cv_checksum = fields.Char(readonly=True)
    match_cv_filename = fields.Char(readonly=True)
    last_match_at = fields.Datetime(readonly=True)
    manual_state_locked = fields.Boolean(readonly=True, copy=False)
    match_analysis_ids = fields.One2many("job.match.analysis", "application_id", readonly=True)

    def write(self, values):
        if "state" in values and not self.env.context.get("automated_matching_state"):
            values = dict(values, manual_state_locked=True)
        return super().write(values)

    @api.constrains("required_years_experience")
    def _check_required_experience(self):
        for application in self:
            if application.required_years_experience < 0:
                raise ValidationError(_("Required experience cannot be negative."))

    def _match_result(self, profile):
        profile_skills = _items(profile.skills)
        mandatory = _items(self.mandatory_skills)
        desired = _items(self.desired_skills)
        technologies = _items(self.required_technologies)
        profile_technologies = _items(profile.technologies)
        languages = _items(self.required_languages, language_names=True)
        profile_languages = _items(profile.languages, language_names=True)
        matched_mandatory = mandatory.keys() & profile_skills.keys()
        matched_desired = desired.keys() & profile_skills.keys()
        matched_technologies = technologies.keys() & profile_technologies.keys()
        missing_mandatory = mandatory.keys() - profile_skills.keys()
        missing_desired = desired.keys() - profile_skills.keys()
        missing_technologies = technologies.keys() - profile_technologies.keys()

        def ratio(found, required):
            return len(found) / len(required) if required else 1.0

        seniority_years = {"junior": 0, "mid": 3, "senior": 6, "lead": 10}
        experience_ratio = min(profile.years_experience / self.required_years_experience, 1.0) if self.required_years_experience else 1.0
        seniority_ok = not self.required_seniority or profile.years_experience >= seniority_years[self.required_seniority]
        education_ok = not self.required_education or self.required_education.casefold() in (profile.education or "").casefold()
        location_ok = not self.location or self.location.strip().casefold() == (profile.location or "").strip().casefold()
        mode_ok = not self.modalidad or bool(getattr(profile, "%s_ok" % self.modalidad))
        language_matches = languages.keys() & profile_languages.keys()
        roles = _items(profile.target_roles)
        role = (self.target_role or self.name or "").strip().casefold()
        role_ok = not role or role in roles
        criteria = {
            "mandatory_skills": {"weight": 25, "earned": round(25 * ratio(matched_mandatory, mandatory), 2)},
            "desired_skills": {"weight": 10, "earned": round(10 * ratio(matched_desired, desired), 2)},
            "experience": {"weight": 15, "earned": round(15 * experience_ratio, 2)},
            "seniority": {"weight": 10, "earned": 10 if seniority_ok else 0},
            "education": {"weight": 10, "earned": 10 if education_ok else 0},
            "technologies": {"weight": 10, "earned": round(10 * ratio(matched_technologies, technologies), 2)},
            "location": {"weight": 5, "earned": 5 if location_ok else 0},
            "modality": {"weight": 5, "earned": 5 if mode_ok else 0},
            "language": {"weight": 5, "earned": round(5 * ratio(language_matches, languages), 2)},
            "role": {"weight": 5, "earned": 5 if role_ok else 0},
        }
        score = round(sum(item["earned"] for item in criteria.values()), 2)
        strengths, gaps = [], []
        if matched_mandatory:
            strengths.append(_("Mandatory skills matched: %s") % ", ".join(sorted(mandatory[key] for key in matched_mandatory)))
        if matched_technologies:
            strengths.append(_("Technologies matched: %s") % ", ".join(sorted(technologies[key] for key in matched_technologies)))
        if experience_ratio >= 1:
            strengths.append(_("Required experience met"))
        if missing_mandatory:
            gaps.append(_("Missing mandatory skills: %s") % ", ".join(sorted(mandatory[key] for key in missing_mandatory)))
        if missing_technologies:
            gaps.append(_("Missing technologies: %s") % ", ".join(sorted(technologies[key] for key in missing_technologies)))
        if experience_ratio < 1:
            gaps.append(_("Experience below requirement"))
        if not education_ok:
            gaps.append(_("Education requirement not met"))
        if languages and ratio(language_matches, languages) < 1:
            gaps.append(_("Language requirement not met"))
        if not location_ok or not mode_ok:
            gaps.append(_("Location or work mode preference differs"))
        if not role_ok:
            gaps.append(_("Role is outside target roles"))
        matched = {**{key: mandatory[key] for key in matched_mandatory}, **{key: desired[key] for key in matched_desired}}
        missing = {**{key: mandatory[key] for key in missing_mandatory}, **{key: desired[key] for key in missing_desired}}
        explanation = _("Deterministic score %(score).2f/100 from 10 weighted criteria; mandatory skills %(mandatory).2f/25, experience %(experience).2f/15, and technologies %(technologies).2f/10.") % {
            "score": score, "mandatory": criteria["mandatory_skills"]["earned"],
            "experience": criteria["experience"]["earned"], "technologies": criteria["technologies"]["earned"],
        }
        return {"score": score, "criteria": criteria, "strengths": "\n".join(strengths), "gaps": "\n".join(gaps),
                "missing_mandatory": _lines([mandatory[key] for key in missing_mandatory]),
                "matched_skills": _lines(matched.values()), "missing_skills": _lines(missing.values()), "explanation": explanation}

    def action_analyze_match(self, profile=None, rule=None):
        profile = profile or self.env["job.hunter.profile"].search([("active", "=", True)], limit=1)
        rule = rule or self.env["job.hunter.match.rule"].search([("active", "=", True)], limit=1)
        if not profile or not rule:
            raise ValidationError(_("An active professional profile and matching rule are required."))
        for application in self:
            result = application._match_result(profile)
            state_before = application.state
            state_after = state_before
            automatic_states = {"found", "analysing", "good_match"}
            if not application.manual_state_locked and state_before in automatic_states:
                if result["score"] >= rule.high_score:
                    state_after = "good_match"
                elif result["score"] >= rule.medium_score:
                    state_after = rule.medium_state
                elif rule.low_state == "ignored":
                    state_after = "ignored"
            values = {
                "match_score": result["score"], "match_strengths": result["strengths"], "match_gaps": result["gaps"],
                "missing_mandatory_requirements": result["missing_mandatory"], "matched_skills": result["matched_skills"],
                "missing_skills": result["missing_skills"], "match_explanation": result["explanation"],
                "match_profile_id": profile.id, "match_profile_version": profile.version,
                "match_cv_checksum": profile.cv_checksum, "match_cv_filename": profile.primary_cv_filename,
                "last_match_at": fields.Datetime.now(),
            }
            if state_after != state_before:
                values["state"] = state_after
            application.with_context(automated_matching_state=True).write(values)
            # Audit rows are immutable to users; only this controlled engine creates them.
            self.env["job.match.analysis"].sudo().create({
                "application_id": application.id, "profile_id": profile.id, "rule_id": rule.id,
                "score": result["score"], "criteria": result["criteria"], "explanation": result["explanation"],
                "profile_version": profile.version, "cv_checksum": profile.cv_checksum,
                "cv_filename": profile.primary_cv_filename, "state_before": state_before, "state_after": application.state,
            })
        return True
