import base64
import json
from unittest.mock import patch

from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase, tagged


def _build_docx(paragraphs):
    """Build a minimal valid .docx (OOXML) file from a list of paragraph strings."""
    import io
    import zipfile

    body = "".join("<w:p><w:r><w:t>%s</w:t></w:r></w:p>" % p for p in paragraphs)
    document_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        "<w:body>%s</w:body></w:document>" % body
    )
    content_types = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/word/document.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
        "</Types>"
    )
    rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" '
        'Target="word/document.xml"/></Relationships>'
    )
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("[Content_Types].xml", content_types)
        archive.writestr("_rels/.rels", rels)
        archive.writestr("word/document.xml", document_xml)
    return buffer.getvalue()


@tagged("post_install", "-at_install")
class TestJobPilotCvUpload(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user = cls.env["res.users"].create(
            {"name": "CV User", "login": "cv_user", "email": "cv.user@example.com"}
        )
        cls.profile = cls.env["job_pilot.profile"].create(
            {"name": "CV User", "user_id": cls.user.id, "email": "old.email@example.com"}
        )
        cls.env["job_pilot.skill"].create(
            {
                "profile_id": cls.profile.id,
                "name": "Python",
                "category_id": cls.env.ref("job_pilot.skill_category_technical").id,
            }
        )

    def _create_upload(self, paragraphs):
        raw = _build_docx(paragraphs)
        return self.env["job_pilot.cv.upload"].create(
            {
                "profile_id": self.profile.id,
                "filename": "cv.docx",
                "file": base64.b64encode(raw),
            }
        )

    def test_full_workflow_extract_parse_review_import(self):
        upload = self._create_upload(
            [
                "John Doe",
                "new.email@example.com",
                "Skills",
                "Python, Go, Communication",
                "Random unmapped paragraph about hobbies.",
            ]
        )
        upload.action_extract_text()
        self.assertEqual(upload.state, "extracted")
        self.assertIn("new.email@example.com", upload.extracted_text)

        upload.action_parse()
        self.assertEqual(upload.state, "parsed")
        self.assertTrue(upload.unclassified_ids)

        email_line = upload.review_line_ids.filtered(lambda l: l.target_field == "email")
        self.assertTrue(email_line)
        self.assertEqual(email_line.decision, "keep")

        python_line = upload.review_line_ids.filtered(
            lambda l: l.section == "skill" and l.new_value == "Python"
        )
        self.assertTrue(python_line)
        self.assertTrue(python_line.is_duplicate)
        self.assertEqual(python_line.decision, "keep")

        go_line = upload.review_line_ids.filtered(lambda l: l.section == "skill" and l.new_value == "Go")
        self.assertFalse(go_line.is_duplicate)
        self.assertEqual(go_line.decision, "apply")

        email_line.decision = "apply"
        upload.action_mark_reviewed()
        self.assertEqual(upload.state, "reviewed")

        upload.action_import()
        self.assertEqual(upload.state, "imported")
        self.assertEqual(self.profile.email, "new.email@example.com")
        self.assertIn("Go", self.profile.skill_ids.mapped("name"))
        self.assertEqual(len(self.profile.skill_ids.filtered(lambda s: s.name == "Python")), 1)

    def test_extract_rejects_unsupported_extension(self):
        upload = self.env["job_pilot.cv.upload"].create(
            {
                "profile_id": self.profile.id,
                "filename": "cv.txt",
                "file": base64.b64encode(b"plain text resume"),
            }
        )
        upload.action_extract_text()
        self.assertEqual(upload.state, "error")
        self.assertTrue(upload.error_message)

    def test_codex_extract_creates_review_proposals(self):
        upload = self._create_upload(["Jane Doe", "jane@example.com", "Skills", "Python, Go"])
        result = {
            "output_text": json.dumps({
                "personal": {"email": "jane@example.com", "phone": None, "mobile": None,
                              "city": None, "street": None, "zip": None},
                "professional": {"title": "Engineer", "summary": "Backend engineer"},
                "skills": [{"name": "Python", "level": None}],
                "languages": [],
                "experience": [],
            })
        }

        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def read(self, _limit):
                return json.dumps(result).encode("utf-8")

        with patch.dict("os.environ", {"JOB_PILOT_CODEX_API_KEY": "test-key"}), patch(
            "urllib.request.urlopen", return_value=FakeResponse()
        ) as urlopen:
            upload.action_extract_with_codex()

        self.assertEqual(upload.state, "parsed")
        self.assertTrue(upload.review_line_ids.filtered(lambda line: line.new_value == "Engineer"))
        self.assertTrue(upload.review_line_ids.filtered(lambda line: line.new_value == "Python"))
        urlopen.assert_called_once()

    def test_codex_uses_odoo_configuration_parameter(self):
        upload = self._create_upload(["Jane Doe", "jane@example.com"])
        parameters = self.env["ir.config_parameter"].sudo()
        parameters.set_param("job_pilot.codex_api_key", "odoo-test-key")
        parameters.set_param("job_pilot.codex_endpoint", "http://codex.test/v1/responses")
        parameters.set_param("job_pilot.codex_model", "test-codex-model")

        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def read(self, _limit):
                return json.dumps({"output_text": json.dumps({
                    "personal": {"email": "jane@example.com", "phone": None, "mobile": None,
                                  "city": None, "street": None, "zip": None},
                    "professional": {"title": None, "summary": None}, "skills": [],
                    "languages": [], "experience": [],
                })}).encode("utf-8")

        with patch("urllib.request.urlopen", return_value=FakeResponse()) as urlopen:
            upload.action_extract_with_codex()

        request = urlopen.call_args.args[0]
        self.assertEqual(request.full_url, "http://codex.test/v1/responses")
        self.assertIn(b"test-codex-model", request.data)

    def test_codex_restarts_non_imported_upload_from_any_review_state(self):
        upload = self._create_upload(["Jane Doe", "jane@example.com"])
        upload.action_extract_text()
        upload.action_parse()
        self.assertEqual(upload.state, "parsed")

        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def read(self, _limit):
                return json.dumps({"output_text": json.dumps({
                    "personal": {"email": "jane@example.com", "phone": None, "mobile": None,
                                  "city": None, "street": None, "zip": None},
                    "professional": {"title": None, "summary": None}, "skills": [],
                    "languages": [], "experience": [],
                })}).encode("utf-8")

        with patch.dict("os.environ", {"JOB_PILOT_CODEX_API_KEY": "test-key"}), patch(
            "urllib.request.urlopen", return_value=FakeResponse()
        ):
            upload.action_extract_with_codex()

        self.assertEqual(upload.state, "parsed")

    def test_reset_draft_clears_review_data(self):
        upload = self._create_upload(["Skills", "Rust"])
        upload.action_extract_text()
        upload.action_parse()
        self.assertTrue(upload.review_line_ids)
        upload.action_reset_draft()
        self.assertEqual(upload.state, "draft")
        self.assertFalse(upload.review_line_ids)
        self.assertFalse(upload.unclassified_ids)
