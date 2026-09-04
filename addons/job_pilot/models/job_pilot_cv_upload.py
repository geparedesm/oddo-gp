import base64
import io
import json
import os
import re
import urllib.error
import urllib.request
import zipfile
from xml.etree import ElementTree

from odoo import _, api, fields, models
from odoo.exceptions import UserError

EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
PHONE_RE = re.compile(r"(\+?\d[\d \-().]{7,}\d)")
DOCX_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"

SECTION_HEADINGS = {
    "skill": ("skills", "technical skills", "core competencies", "key skills"),
    "language": ("languages",),
    "professional": ("summary", "professional summary", "profile", "objective"),
}
ALL_SECTION_HEADINGS = {name for names in SECTION_HEADINGS.values() for name in names}


class JobPilotCvUpload(models.Model):
    _name = "job_pilot.cv.upload"
    _description = "CV Upload"
    _order = "create_date desc, id desc"
    _rec_name = "filename"

    profile_id = fields.Many2one(
        "job_pilot.profile",
        required=True,
        ondelete="cascade",
        index=True,
        default=lambda self: self.env["job_pilot.profile"].search(
            [("user_id", "=", self.env.uid)], limit=1
        ).id,
    )
    file = fields.Binary(string="CV File", required=True, attachment=True)
    filename = fields.Char(string="File Name")
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("extracted", "Text Extracted"),
            ("parsed", "Parsed"),
            ("reviewed", "Reviewed"),
            ("imported", "Imported"),
            ("error", "Error"),
        ],
        default="draft",
        required=True,
        copy=False,
    )
    extracted_text = fields.Text(copy=False)
    error_message = fields.Text(copy=False)

    review_line_ids = fields.One2many(
        "job_pilot.cv.import.line", "upload_id", string="Proposed Changes"
    )
    review_line_count = fields.Integer(compute="_compute_review_line_count")
    pending_review_count = fields.Integer(compute="_compute_review_line_count")
    unclassified_ids = fields.One2many(
        "job_pilot.cv.unclassified", "upload_id", string="Unclassified Information"
    )
    unclassified_count = fields.Integer(compute="_compute_unclassified_count")

    @api.depends("review_line_ids.decision")
    def _compute_review_line_count(self):
        for upload in self:
            upload.review_line_count = len(upload.review_line_ids)
            upload.pending_review_count = len(
                upload.review_line_ids.filtered(lambda l: l.decision == "pending")
            )

    @api.depends("unclassified_ids")
    def _compute_unclassified_count(self):
        for upload in self:
            upload.unclassified_count = len(upload.unclassified_ids)

    def action_extract_text(self):
        for upload in self:
            if not upload.file:
                raise UserError(_("Upload a CV file first."))
            extension = (upload.filename or "").lower().rsplit(".", 1)[-1] if "." in (upload.filename or "") else ""
            raw = base64.b64decode(upload.file)
            try:
                if extension == "pdf":
                    text = upload._extract_pdf_text(raw)
                elif extension == "docx":
                    text = upload._extract_docx_text(raw)
                else:
                    raise UserError(_("Unsupported file type. Upload a PDF or DOCX CV."))
            except UserError as exc:
                upload.write({"state": "error", "error_message": str(exc)})
                continue
            upload.write({"extracted_text": text, "state": "extracted", "error_message": False})

    def action_extract_with_codex(self):
        """Extract the document locally and obtain structured proposals from Codex."""
        for upload in self:
            if upload.state == "imported":
                raise UserError(_("An imported CV cannot be extracted again."))
            if upload.state != "draft":
                upload.action_reset_draft()
            upload.action_extract_text()
            if upload.state != "extracted":
                continue
            try:
                payload = upload._call_codex(upload.extracted_text)
                upload._create_codex_review_lines(payload)
            except UserError as exc:
                upload.write({"state": "error", "error_message": str(exc)})
                continue
            upload.write({"state": "parsed", "error_message": False})

    def _call_codex(self, text):
        parameters = self.env["ir.config_parameter"].sudo()
        endpoint = parameters.get_param("job_pilot.codex_endpoint") or os.environ.get(
            "JOB_PILOT_CODEX_ENDPOINT", "https://api.openai.com/v1/responses"
        )
        token = parameters.get_param("job_pilot.codex_api_key") or os.environ.get(
            "JOB_PILOT_CODEX_API_KEY"
        ) or os.environ.get("OPENAI_API_KEY")
        model = parameters.get_param("job_pilot.codex_model") or os.environ.get(
            "JOB_PILOT_CODEX_MODEL", "gpt-5.3-codex"
        )
        if not token:
            raise UserError(_("Codex is not configured. Set JOB_PILOT_CODEX_API_KEY or OPENAI_API_KEY."))
        if len(text or "") > 120000:
            raise UserError(_("The extracted CV text is too long for Codex."))
        schema = {
            "type": "object", "additionalProperties": False,
            "properties": {
                "personal": {"type": "object", "additionalProperties": False, "properties": {
                    "email": {"type": ["string", "null"]}, "phone": {"type": ["string", "null"]},
                    "mobile": {"type": ["string", "null"]}, "city": {"type": ["string", "null"]},
                    "street": {"type": ["string", "null"]}, "zip": {"type": ["string", "null"]},
                }, "required": ["email", "phone", "mobile", "city", "street", "zip"]},
                "professional": {"type": "object", "additionalProperties": False, "properties": {
                    "title": {"type": ["string", "null"]}, "summary": {"type": ["string", "null"]},
                }, "required": ["title", "summary"]},
                "skills": {"type": "array", "items": {"type": "object", "additionalProperties": False,
                    "properties": {"name": {"type": "string"}, "level": {"type": ["string", "null"]}},
                    "required": ["name", "level"]}},
                "languages": {"type": "array", "items": {"type": "object", "additionalProperties": False,
                    "properties": {"name": {"type": "string"}, "proficiency": {"type": ["string", "null"]}},
                    "required": ["name", "proficiency"]}},
                "experience": {"type": "array", "items": {"type": "object", "additionalProperties": False,
                    "properties": {"company_name": {"type": "string"}, "job_title": {"type": "string"},
                        "location": {"type": ["string", "null"]}, "start_date": {"type": ["string", "null"]},
                        "end_date": {"type": ["string", "null"]}, "currently_working": {"type": "boolean"},
                        "description": {"type": ["string", "null"]}},
                    "required": ["company_name", "job_title", "location", "start_date", "end_date", "currently_working", "description"]}},
            },
            "required": ["personal", "professional", "skills", "languages", "experience"],
        }
        instructions = (
            "Extract this CV into the supplied JSON schema. Do not infer missing values; use null or []. "
            "Use ISO dates only when the CV supports them. Return only structured facts from the CV."
        )
        body = json.dumps({
            "model": model,
            "input": [{"role": "system", "content": [{"type": "input_text", "text": instructions}]},
                      {"role": "user", "content": [{"type": "input_text", "text": text}]}],
            "text": {"format": {"type": "json_schema", "name": "cv_extraction", "strict": True, "schema": schema}},
            "reasoning": {"effort": "low"},
        }).encode("utf-8")
        request = urllib.request.Request(
            endpoint, data=body,
            headers={"Authorization": "Bearer %s" % token, "Content-Type": "application/json"}, method="POST"
        )
        try:
            with urllib.request.urlopen(request, timeout=120) as response:
                result = json.loads(response.read(2 * 1024 * 1024).decode("utf-8"))
            content = result.get("output_text")
            if not content:
                content = next(
                    item["content"][0]["text"] for item in result.get("output", [])
                    if item.get("type") == "message" and item.get("content")
                )
            payload = json.loads(content)
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, KeyError, IndexError, StopIteration, TypeError) as exc:
            raise UserError(_("Codex could not extract this CV: %s") % exc)
        if not isinstance(payload, dict):
            raise UserError(_("Codex returned an invalid CV structure."))
        return payload

    def _create_codex_review_lines(self, payload):
        self.ensure_one()
        self.review_line_ids.unlink()
        self.unclassified_ids.unlink()
        profile = self.profile_id
        lines = []
        for field_name, label, current in (
            ("email", "Email", profile.email), ("phone", "Phone", profile.phone),
            ("mobile", "Mobile", profile.mobile), ("city", "City", profile.city),
            ("street", "Street", profile.street), ("zip", "ZIP", profile.zip),
        ):
            value = (payload.get("personal") or {}).get(field_name)
            if isinstance(value, str) and value.strip():
                lines.append(self._build_field_line("personal", field_name, _(label), current, value))
        for field_name, label, target, current in (
            ("title", "Professional Title", "professional_title", profile.professional_title),
            ("summary", "Professional Summary", "professional_summary", profile.professional_summary),
        ):
            value = (payload.get("professional") or {}).get(field_name)
            if isinstance(value, str) and value.strip():
                lines.append(self._build_field_line("professional", target, _(label), current, value))
        existing_skills = self.env["job_pilot.skill"].search([("profile_id", "=", profile.id)])
        for item in payload.get("skills") or []:
            if isinstance(item, dict) and isinstance(item.get("name"), str) and item["name"].strip():
                lines.append(self._build_record_line("skill", _("Skill"), item["name"].strip(), existing_skills))
        existing_languages = self.env["job_pilot.language"].search([("profile_id", "=", profile.id)])
        for item in payload.get("languages") or []:
            if isinstance(item, dict) and isinstance(item.get("name"), str) and item["name"].strip():
                lines.append(self._build_record_line("language", _("Language"), item["name"].strip(), existing_languages))
        for item in payload.get("experience") or []:
            if (
                isinstance(item, dict)
                and item.get("company_name")
                and item.get("job_title")
                and item.get("start_date")
            ):
                lines.append({"section": "experience", "field_label": _("Experience: %s") % item["company_name"],
                              "current_value": False, "new_value": json.dumps(item), "is_duplicate": False, "decision": "apply"})
        self.env["job_pilot.cv.import.line"].create([dict(line, upload_id=self.id) for line in lines])

    @api.model
    def _extract_pdf_text(self, raw):
        try:
            from pypdf import PdfReader
        except ImportError:
            try:
                from PyPDF2 import PdfReader
            except ImportError:
                raise UserError(
                    _(
                        "PDF extraction requires the 'pypdf' or 'PyPDF2' Python "
                        "package to be installed on the server."
                    )
                )
        try:
            reader = PdfReader(io.BytesIO(raw))
            pages = [page.extract_text() or "" for page in reader.pages]
        except Exception:
            raise UserError(_("The PDF file could not be read. It may be corrupted."))
        text = "\n\n".join(pages).strip()
        if not text:
            raise UserError(
                _("No extractable text was found in the PDF. It may be a scanned image.")
            )
        return text

    @api.model
    def _extract_docx_text(self, raw):
        try:
            with zipfile.ZipFile(io.BytesIO(raw)) as archive:
                xml_content = archive.read("word/document.xml")
        except (zipfile.BadZipFile, KeyError):
            raise UserError(
                _("The DOCX file could not be read. It may be corrupted or not a valid Word document.")
            )
        tree = ElementTree.fromstring(xml_content)
        paragraphs = []
        for para in tree.iter("{%s}p" % DOCX_NS):
            texts = [node.text for node in para.iter("{%s}t" % DOCX_NS) if node.text]
            paragraphs.append("".join(texts))
        text = "\n\n".join(p for p in paragraphs if p.strip()).strip()
        if not text:
            raise UserError(_("No extractable text was found in the DOCX file."))
        return text

    def action_parse(self):
        ImportLine = self.env["job_pilot.cv.import.line"]
        Unclassified = self.env["job_pilot.cv.unclassified"]
        for upload in self:
            if upload.state != "extracted":
                raise UserError(_("Extract the CV text before parsing."))
            upload.review_line_ids.unlink()
            upload.unclassified_ids.unlink()
            review_vals, unclassified_vals = upload._parse_cv_text(upload.extracted_text)
            for vals in review_vals:
                vals["upload_id"] = upload.id
            for vals in unclassified_vals:
                vals["upload_id"] = upload.id
            if review_vals:
                ImportLine.create(review_vals)
            if unclassified_vals:
                Unclassified.create(unclassified_vals)
            upload.write({"state": "parsed"})

    def _build_field_line(self, section, target_field, label, current_value, new_value):
        current_value = current_value or False
        new_value = (new_value or "").strip()
        return {
            "section": section,
            "target_field": target_field,
            "field_label": label,
            "current_value": current_value,
            "new_value": new_value,
            "is_duplicate": bool(current_value),
            "decision": "keep" if current_value else "apply",
        }

    def _build_record_line(self, section, label_prefix, name, existing_recordset):
        match = existing_recordset.filtered(lambda r, n=name: r.name.lower() == n.lower())
        return {
            "section": section,
            "field_label": _("%s: %s") % (label_prefix, name),
            "current_value": match[:1].name if match else False,
            "new_value": name,
            "is_duplicate": bool(match),
            "matched_record_ref": "%s,%s" % (match[0]._name, match[0].id) if match else False,
            "decision": "keep" if match else "apply",
        }

    def _parse_cv_text(self, text):
        self.ensure_one()
        profile = self.profile_id
        review_vals = []
        blocks = [b.strip() for b in re.split(r"\n\s*\n", text or "") if b.strip()]
        consumed = set()

        email_match = EMAIL_RE.search(text or "")
        if email_match:
            review_vals.append(
                self._build_field_line("personal", "email", _("Email"), profile.email, email_match.group(0))
            )
        phone_match = PHONE_RE.search(text or "")
        if phone_match:
            review_vals.append(
                self._build_field_line(
                    "personal", "phone", _("Phone"), profile.phone, phone_match.group(0)
                )
            )

        idx = 0
        num_blocks = len(blocks)
        while idx < num_blocks:
            block = blocks[idx]
            heading, _sep, rest = block.partition("\n")
            heading_norm = heading.strip().lower().rstrip(":")
            rest = rest.strip()
            content_idx = idx
            if not rest and heading_norm in ALL_SECTION_HEADINGS and idx + 1 < num_blocks:
                # Standalone heading paragraph (e.g. a lone "Skills" line); the
                # actual content lives in the next paragraph/block.
                content_idx = idx + 1
                rest = blocks[content_idx].strip()
            if not rest:
                idx += 1
                continue
            if heading_norm in SECTION_HEADINGS["skill"]:
                consumed.add(idx)
                consumed.add(content_idx)
                for item in re.split(r"[,\n;•]+", rest):
                    name = item.strip(" -\t")
                    if name:
                        review_vals.append(self._build_record_line("skill", _("Skill"), name, profile.skill_ids))
            elif heading_norm in SECTION_HEADINGS["language"]:
                consumed.add(idx)
                consumed.add(content_idx)
                for item in re.split(r"[,\n;•]+", rest):
                    name = item.strip(" -\t")
                    if name:
                        review_vals.append(
                            self._build_record_line("language", _("Language"), name, profile.language_ids)
                        )
            elif heading_norm in SECTION_HEADINGS["professional"]:
                consumed.add(idx)
                consumed.add(content_idx)
                review_vals.append(
                    self._build_field_line(
                        "professional",
                        "professional_summary",
                        _("Professional Summary"),
                        profile.professional_summary,
                        rest,
                    )
                )
            idx = content_idx + 1

        unclassified_vals = []
        for idx, block in enumerate(blocks):
            if idx in consumed:
                continue
            if EMAIL_RE.fullmatch(block) or PHONE_RE.fullmatch(block):
                continue
            unclassified_vals.append({"sequence": idx * 10, "content": block})
        return review_vals, unclassified_vals

    def action_mark_reviewed(self):
        for upload in self:
            if upload.state != "parsed":
                raise UserError(_("Parse the CV before marking it as reviewed."))
            if upload.review_line_ids.filtered(lambda l: l.decision == "pending"):
                raise UserError(_("Resolve every proposed change before marking the CV as reviewed."))
            upload.state = "reviewed"

    def action_import(self):
        for upload in self:
            if upload.state != "reviewed":
                raise UserError(_("Only a reviewed CV can be imported."))
            profile = upload.profile_id
            for line in upload.review_line_ids.filtered(lambda l: l.decision == "apply"):
                if line.section in ("personal", "professional") and line.target_field:
                    profile.write({line.target_field: line.new_value})
                elif line.section == "skill" and not line.is_duplicate:
                    category = self.env["job_pilot.skill.category"].search(
                        [("name", "=", "Uncategorized")], limit=1
                    )
                    if not category:
                        category = self.env["job_pilot.skill.category"].create({"name": "Uncategorized"})
                    self.env["job_pilot.skill"].create(
                        {"profile_id": profile.id, "name": line.new_value, "category_id": category.id}
                    )
                elif line.section == "language" and not line.is_duplicate:
                    self.env["job_pilot.language"].create(
                        {"profile_id": profile.id, "name": line.new_value}
                    )
                elif line.section == "experience":
                    experience = json.loads(line.new_value)
                    self.env["job_pilot.work.experience"].create(
                        {key: experience[key] for key in (
                            "company_name", "job_title", "location", "start_date", "end_date",
                            "currently_working", "description",
                        ) if key in experience and experience[key] is not None}
                        | {"profile_id": profile.id}
                    )
            upload.state = "imported"

    def action_reset_draft(self):
        for upload in self:
            upload.review_line_ids.unlink()
            upload.unclassified_ids.unlink()
            upload.write({"state": "draft", "extracted_text": False, "error_message": False})


class JobPilotCvImportLine(models.Model):
    _name = "job_pilot.cv.import.line"
    _description = "CV Import Proposed Change"
    _order = "section, id"

    upload_id = fields.Many2one("job_pilot.cv.upload", required=True, ondelete="cascade", index=True)
    profile_id = fields.Many2one(
        "job_pilot.profile", related="upload_id.profile_id", store=True, index=True
    )
    section = fields.Selection(
        [
            ("personal", "Personal Information"),
            ("professional", "Professional Summary"),
            ("skill", "Skill"),
            ("language", "Language"),
            ("experience", "Work Experience"),
            ("education", "Education"),
            ("certification", "Certification"),
            ("leadership", "Leadership & Volunteering"),
            ("reference", "Reference"),
        ],
        required=True,
    )
    target_field = fields.Char(string="Technical Field")
    field_label = fields.Char(required=True)
    current_value = fields.Char(string="Current Value")
    new_value = fields.Char(string="Proposed Value", required=True)
    is_duplicate = fields.Boolean(string="Conflicts With Existing Data")
    matched_record_ref = fields.Reference(
        selection=[
            ("job_pilot.skill", "Skill"),
            ("job_pilot.language", "Language"),
        ],
        string="Matching Record",
    )
    decision = fields.Selection(
        [
            ("pending", "Pending"),
            ("keep", "Keep Existing / Skip"),
            ("apply", "Apply / Add"),
        ],
        default="pending",
        required=True,
    )


class JobPilotCvUnclassified(models.Model):
    _name = "job_pilot.cv.unclassified"
    _description = "CV Unclassified Information"
    _order = "sequence, id"

    upload_id = fields.Many2one("job_pilot.cv.upload", required=True, ondelete="cascade", index=True)
    profile_id = fields.Many2one(
        "job_pilot.profile", related="upload_id.profile_id", store=True, index=True
    )
    sequence = fields.Integer(default=10)
    content = fields.Text(required=True)
    state = fields.Selection(
        [("open", "Open"), ("resolved", "Resolved"), ("ignored", "Ignored")],
        default="open",
        required=True,
    )

    def action_mark_resolved(self):
        self.write({"state": "resolved"})

    def action_mark_ignored(self):
        self.write({"state": "ignored"})
