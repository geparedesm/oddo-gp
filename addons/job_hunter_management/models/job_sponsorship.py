import re

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class JobSponsorshipRule(models.Model):
    _name = "job.sponsorship.rule"
    _description = "Sponsorship Priority Rule"
    _order = "active desc, id"

    name = fields.Char(required=True)
    active = fields.Boolean(default=True)
    yes_adjustment = fields.Float(required=True, default=20)
    unknown_adjustment = fields.Float(required=True, default=0)
    no_adjustment = fields.Float(required=True, default=-50)

    @api.constrains("yes_adjustment", "unknown_adjustment", "no_adjustment")
    def _check_adjustments(self):
        for rule in self:
            adjustments = (rule.yes_adjustment, rule.unknown_adjustment, rule.no_adjustment)
            if any(value < -100 or value > 100 for value in adjustments):
                raise ValidationError(_("Priority adjustments must be between -100 and 100."))
            if not rule.yes_adjustment > rule.unknown_adjustment > rule.no_adjustment:
                raise ValidationError(_("Priority adjustments must order Yes above Unknown above No."))


class JobSponsorshipAnalysis(models.Model):
    _name = "job.sponsorship.analysis"
    _description = "Sponsorship Analysis Trace"
    _order = "analyzed_at desc, id desc"

    application_id = fields.Many2one("job.application", required=True, ondelete="cascade", index=True)
    rule_id = fields.Many2one("job.sponsorship.rule", required=True, ondelete="restrict")
    status = fields.Selection([("yes", "Yes"), ("no", "No"), ("unknown", "Unknown")], required=True)
    confidence = fields.Float(required=True)
    evidence = fields.Text()
    evidence_source = fields.Selection([("job_description", "Job Description")], required=True)
    reason = fields.Text(required=True)
    priority_score = fields.Float(required=True)
    match_score_snapshot = fields.Float(required=True)
    analyzed_at = fields.Datetime(required=True, default=fields.Datetime.now)
    analyzed_by = fields.Many2one("res.users", required=True, default=lambda self: self.env.user)

    @api.constrains("confidence", "priority_score", "match_score_snapshot")
    def _check_percentages(self):
        for analysis in self:
            if not 0 <= analysis.confidence <= 100:
                raise ValidationError(_("Sponsorship confidence must be between 0 and 100."))
            if not 0 <= analysis.priority_score <= 100:
                raise ValidationError(_("Priority score must be between 0 and 100."))
            if not 0 <= analysis.match_score_snapshot <= 100:
                raise ValidationError(_("Match score snapshot must be between 0 and 100."))


class JobApplicationSponsorship(models.Model):
    _inherit = "job.application"

    sponsorship_confidence = fields.Float(readonly=True, copy=False)
    sponsorship_evidence = fields.Text(readonly=True, copy=False)
    sponsorship_evidence_source = fields.Selection(
        [("job_description", "Job Description")], readonly=True, copy=False,
    )
    sponsorship_reason = fields.Text(readonly=True, copy=False)
    sponsorship_analyzed_at = fields.Datetime(readonly=True, copy=False)
    sponsorship_rule_id = fields.Many2one("job.sponsorship.rule", readonly=True, copy=False, ondelete="restrict")
    sponsorship_priority_adjustment = fields.Float(readonly=True, copy=False)
    sponsorship_rank = fields.Integer(compute="_compute_sponsorship_priority", store=True, index=True)
    priority_score = fields.Float(
        compute="_compute_sponsorship_priority", store=True, index=True,
        help="Application priority after sponsorship adjustment; match score is not changed.",
    )
    sponsorship_analysis_ids = fields.One2many(
        "job.sponsorship.analysis", "application_id", readonly=True,
    )

    _POSITIVE_PATTERNS = (
        r"\bvisa sponsorship (?:is )?available\b",
        r"\b482 sponsorship\b",
        r"\bemployer sponsored\b",
    )
    _NEGATIVE_PATTERNS = (
        r"\bno (?:visa )?sponsorship (?:is )?available\b",
        r"\b(?:australian )?citizens? (?:or|and) permanent residents? only\b",
        r"\bcitizen\s*/\s*pr only\b",
    )
    _WORK_RIGHTS_PATTERNS = (
        r"\bmust have (?:full|current|valid) (?:australian )?work(?:ing)? rights\b",
        r"\bfull (?:australian )?work(?:ing)? rights (?:are )?required\b",
        r"\bright to work in australia\b",
    )

    @api.depends("match_score", "sponsorship_status", "sponsorship_priority_adjustment")
    def _compute_sponsorship_priority(self):
        ranks = {"yes": 3, "unknown": 2, "no": 1}
        for application in self:
            application.sponsorship_rank = ranks.get(application.sponsorship_status, 2)
            application.priority_score = min(
                100, max(0, application.match_score + application.sponsorship_priority_adjustment),
            )

    @api.constrains("sponsorship_confidence")
    def _check_sponsorship_confidence(self):
        for application in self:
            if not 0 <= application.sponsorship_confidence <= 100:
                raise ValidationError(_("Sponsorship confidence must be between 0 and 100."))

    @staticmethod
    def _pattern_matches(text, patterns):
        matches = []
        for pattern in patterns:
            matches.extend(match.group(0).strip() for match in re.finditer(pattern, text, re.I))
        return list(dict.fromkeys(matches))

    def _sponsorship_result(self):
        self.ensure_one()
        text = self.job_description or ""
        positives = self._pattern_matches(text, self._POSITIVE_PATTERNS)
        negatives = self._pattern_matches(text, self._NEGATIVE_PATTERNS)
        work_rights = self._pattern_matches(text, self._WORK_RIGHTS_PATTERNS)
        if negatives:
            status, confidence, evidence = "no", 100 if len(negatives) > 1 else 95, negatives
            reason = _("Explicit negative sponsorship evidence takes precedence over positive signals.")
        elif positives:
            status, confidence, evidence = "yes", 95 if len(positives) > 1 else 90, positives
            reason = _("Explicit employer or visa sponsorship evidence was found.")
        elif work_rights:
            status, confidence, evidence = "unknown", 70, []
            reason = _("Current work rights are requested, but that does not establish whether sponsorship is available.")
        else:
            status, confidence, evidence = "unknown", 0, []
            reason = _("No explicit sponsorship evidence was found; absence of evidence remains Unknown.")
        return {
            "status": status, "confidence": confidence, "evidence": "; ".join(evidence),
            "evidence_source": "job_description", "reason": reason,
        }

    def action_analyze_sponsorship(self, rule=None):
        rule = rule or self.env["job.sponsorship.rule"].search([("active", "=", True)], limit=1)
        if not rule:
            raise ValidationError(_("An active sponsorship priority rule is required."))
        adjustments = {"yes": rule.yes_adjustment, "unknown": rule.unknown_adjustment, "no": rule.no_adjustment}
        for application in self:
            result = application._sponsorship_result()
            analyzed_at = fields.Datetime.now()
            application.write({
                "sponsorship_status": result["status"],
                "sponsorship_confidence": result["confidence"],
                "sponsorship_evidence": result["evidence"],
                "sponsorship_evidence_source": result["evidence_source"],
                "sponsorship_reason": result["reason"],
                "sponsorship_analyzed_at": analyzed_at,
                "sponsorship_rule_id": rule.id,
                "sponsorship_priority_adjustment": adjustments[result["status"]],
            })
            self.env["job.sponsorship.analysis"].sudo().create({
                "application_id": application.id, "rule_id": rule.id,
                "status": result["status"], "confidence": result["confidence"],
                "evidence": result["evidence"], "evidence_source": result["evidence_source"],
                "reason": result["reason"], "priority_score": application.priority_score,
                "match_score_snapshot": application.match_score, "analyzed_at": analyzed_at,
            })
        return True
