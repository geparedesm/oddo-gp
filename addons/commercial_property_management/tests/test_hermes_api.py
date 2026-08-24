import json
import uuid
from types import SimpleNamespace
from unittest.mock import patch

from odoo import fields
from odoo.exceptions import ValidationError
from odoo.tests import tagged
from odoo.tests.common import HttpCase, TransactionCase

from ..controllers import hermes_api


class TestHermesPublicData(TransactionCase):
    def setUp(self):
        super().setUp()
        self.manager = self.env["res.users"].create(
            {
                "name": "Hermes Identity Manager %s" % self._testMethodName,
                "login": "hermes.identity.manager.%s" % self._testMethodName,
                "groups_id": [(6, 0, [self.env.ref("commercial_property_management.group_property_manager").id])],
            }
        )
        self.property_user = self.env["res.users"].create(
            {
                "name": "Hermes Identity User %s" % self._testMethodName,
                "login": "hermes.identity.user.%s" % self._testMethodName,
                "groups_id": [(6, 0, [self.env.ref("commercial_property_management.group_property_user").id])],
            }
        )
        self.feature_name = "Meeting room %s" % self._testMethodName
        feature = self.env["commercial.property.feature"].create({"name": self.feature_name})
        self.public_property = self.env["commercial.property"].create(
            {
                "name": "Internal Tower Name",
                "area": 120,
                "monthly_rent": 2200,
                "notes": "Private operating note",
                "public_name": "Central Tower Office",
                "public_description": "Light-filled office close to public transport.",
                "public_monthly_rent": 2400,
                "public_feature_ids": [(6, 0, feature.ids)],
                "is_published": True,
            }
        )
        self.hidden_property = self.env["commercial.property"].create(
            {
                "name": "Private Warehouse",
                "area": 500,
                "monthly_rent": 5000,
                "public_name": "Hidden Warehouse",
                "public_description": "This must not be returned.",
                "public_monthly_rent": 5000,
            }
        )

    def test_search_returns_only_public_available_properties(self):
        properties = self.env["commercial.property"].search_public_properties(min_area=100, max_rent=2500)

        self.assertIn(self.public_property, properties)
        self.assertNotIn(self.hidden_property, properties)
        self.assertEqual(
            self.env["commercial.property"].search_public_properties(code=self.public_property.code),
            self.public_property,
        )

    def test_equal_bearer_and_mcp_credentials_fail_closed(self):
        shared_token = "shared-controller-test-token"
        parameter_model = self.env["ir.config_parameter"].sudo()
        parameter_model.set_param(
            hermes_api.HermesPropertyController._TOKEN_PARAMETER,
            shared_token,
        )
        parameter_model.set_param(
            hermes_api.HermesPropertyController._MCP_TOKEN_PARAMETER,
            shared_token,
        )
        fake_request = SimpleNamespace(
            env=self.env,
            httprequest=SimpleNamespace(
                headers={
                    "X-Hermes-Channel": "mcp",
                    "X-Hermes-MCP-Token": shared_token,
                }
            ),
        )

        with patch.object(hermes_api, "request", fake_request):
            self.assertFalse(
                hermes_api.HermesPropertyController()._is_mcp_request()
            )

    def test_public_serializer_excludes_private_fields(self):
        public_data = self.public_property.get_public_data()

        self.assertEqual(public_data["features"], [self.feature_name])
        self.assertNotIn("notes", public_data)
        self.assertNotIn("tenant_id", public_data)
        self.assertNotIn("lease_ids", public_data)
        self.assertEqual(public_data["monthly_rent"], self.public_property.public_monthly_rent)
        self.assertNotEqual(public_data["monthly_rent"], self.public_property.monthly_rent)
        self.assertNotIn(self.hidden_property.code, [property_record.code for property_record in self.env["commercial.property"].search_public_properties()])

    def test_authenticated_whatsapp_sender_populates_and_persists_phone(self):
        lead = self.env["commercial.property.lead"].create(
            {
                "name": "WhatsApp Prospect",
                "whatsapp_sender": "+593 (999) 000-111",
                "unit_id": self.public_property.default_unit_id.id,
                "consent_at": fields.Datetime.now(),
                "source": "whatsapp",
            }
        )

        self.assertEqual(lead.phone, "+593999000111")
        self.assertEqual(lead.whatsapp_sender, "+593999000111")

    def test_authenticated_whatsapp_sender_overrides_caller_phone(self):
        lead = self.env["commercial.property.lead"].create(
            {
                "name": "WhatsApp Prospect",
                "phone": "+12025550199",
                "whatsapp_sender": "+593 (999) 000-111",
                "unit_id": self.public_property.default_unit_id.id,
                "consent_at": fields.Datetime.now(),
                "source": "whatsapp",
            }
        )

        self.assertEqual(lead.phone, "+593999000111")
        self.assertEqual(lead.whatsapp_sender, "+593999000111")

    def test_invalid_whatsapp_sender_is_rejected_before_persistence(self):
        lead_count = self.env["commercial.property.lead"].search_count([])

        with self.assertRaises(ValidationError):
            self.env["commercial.property.lead"].create(
                {
                    "name": "Invalid WhatsApp Prospect",
                    "whatsapp_sender": "not-a-phone",
                    "unit_id": self.public_property.default_unit_id.id,
                    "consent_at": fields.Datetime.now(),
                    "source": "whatsapp",
                }
            )

        self.assertEqual(self.env["commercial.property.lead"].search_count([]), lead_count)

    def test_sender_audit_field_is_restricted_to_whatsapp_source(self):
        with self.assertRaises(ValidationError):
            self.env["commercial.property.lead"].create(
                {
                    "name": "Manual Prospect",
                    "phone": "+12025550199",
                    "whatsapp_sender": "+593999000111",
                    "unit_id": self.public_property.default_unit_id.id,
                    "consent_at": fields.Datetime.now(),
                    "source": "manual",
                }
            )

    def test_sender_audit_field_prevents_changing_source_to_manual(self):
        lead = self.env["commercial.property.lead"].create(
            {
                "name": "WhatsApp Prospect",
                "whatsapp_sender": "+593999000111",
                "unit_id": self.public_property.default_unit_id.id,
                "consent_at": fields.Datetime.now(),
                "source": "whatsapp",
            }
        )

        with self.assertRaises(ValidationError):
            lead.write({"source": "manual"})

        self.assertEqual(lead.source, "whatsapp")

    def test_sender_audit_field_is_visible_only_to_property_managers(self):
        manager_fields = self.env["commercial.property.lead"].with_user(
            self.manager
        ).fields_get(["whatsapp_sender"])
        user_fields = self.env["commercial.property.lead"].with_user(
            self.property_user
        ).fields_get(["whatsapp_sender"])

        self.assertIn("whatsapp_sender", manager_fields)
        self.assertNotIn("whatsapp_sender", user_fields)

    def test_sender_audit_field_cannot_be_changed_or_rpc_erased(self):
        lead = self.env["commercial.property.lead"].create(
            {
                "name": "WhatsApp Prospect",
                "whatsapp_sender": "+593999000111",
                "unit_id": self.public_property.default_unit_id.id,
                "consent_at": fields.Datetime.now(),
                "source": "whatsapp",
            }
        )

        with self.assertRaises(ValidationError):
            lead.write({"whatsapp_sender": "+593999000222"})
        with self.assertRaises(ValidationError):
            lead.with_context(_whatsapp_sender_erasure=True).write(
                {"whatsapp_sender": False}
            )

        self.assertEqual(lead.whatsapp_sender, "+593999000111")

    def test_anonymization_erases_whatsapp_sender(self):
        lead = self.env["commercial.property.lead"].create(
            {
                "name": "WhatsApp Prospect",
                "whatsapp_sender": "+593999000111",
                "unit_id": self.public_property.default_unit_id.id,
                "consent_at": fields.Datetime.now(),
                "source": "whatsapp",
            }
        )
        lead.write({"retention_deadline": fields.Datetime.subtract(fields.Datetime.now(), days=1)})

        self.env["commercial.property.lead"]._cron_anonymize_expired_personal_data()

        self.assertFalse(lead.phone)
        self.assertFalse(lead.whatsapp_sender)


@tagged("post_install", "-at_install")
class TestHermesEnquiryIdentity(HttpCase):
    _PARAMETER_KEYS = (
        "commercial_property_management.hermes_api_token",
        "commercial_property_management.hermes_mcp_channel_token",
        "commercial_property_management.whatsapp_intake_enabled",
    )

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.token = "hermes-identity-test-token"
        cls.mcp_channel_token = "hermes-identity-test-mcp-channel-token"
        cls._property_id = False
        cls._unit_ids = []
        cls._test_state_restored = False
        cls._setup_complete = False
        cls._executed_http_cases = set()
        parameter_model = cls.env["ir.config_parameter"].sudo()
        previous_records = parameter_model.search([("key", "in", cls._PARAMETER_KEYS)])
        cls._previous_parameters = {
            key: {
                "exists": key in previous_records.mapped("key"),
                "value": previous_records.filtered(lambda record: record.key == key).value,
            }
            for key in cls._PARAMETER_KEYS
        }
        cls.addClassCleanup(cls._restore_test_state)
        try:
            parameter_model.set_param(cls._PARAMETER_KEYS[0], cls.token)
            parameter_model.set_param(cls._PARAMETER_KEYS[1], cls.mcp_channel_token)
            parameter_model.set_param(cls._PARAMETER_KEYS[2], "True")
            property_record = cls.env["commercial.property"].create(
                {
                    "name": "Identity Test Property",
                    "area": 100,
                    "monthly_rent": 1000,
                    "public_name": "Identity Test Property",
                    "public_description": "Identity test listing",
                    "public_monthly_rent": 1000,
                    "is_published": True,
                }
            )
            cls._property_id = property_record.id
            cls._unit_ids = property_record.unit_ids.ids
            cls.unit = property_record.default_unit_id
            cls.env.cr.commit()
            cls._signal_http_worker_cache_invalidation()
            cls._setup_complete = True
        except Exception:
            cls.env.cr.rollback()
            cls._restore_test_state()
            raise

    @classmethod
    def _signal_http_worker_cache_invalidation(cls):
        """Make committed fixture parameters visible to the live HTTP worker."""
        cls.env.cr.execute("SELECT nextval('base_cache_signaling')")
        cls.env.cr.fetchone()

    @classmethod
    def _restore_test_state(cls):
        if cls._test_state_restored:
            return
        cls.env.cr.rollback()
        errors = []

        def attempt(operation):
            try:
                with cls.env.cr.savepoint():
                    operation()
            except Exception as error:  # Keep restoring independent state.
                errors.append(error)

        if cls._setup_complete and cls._executed_http_cases:
            attempt(cls._validate_persisted_http_results)

        if cls._unit_ids:
            attempt(
                lambda: cls.env["commercial.property.lead"].sudo().search(
                    [("unit_id", "in", cls._unit_ids)]
                ).unlink()
            )
        if cls._property_id:
            def remove_property_fixture():
                property_record = cls.env["commercial.property"].sudo().browse(
                    cls._property_id
                ).exists()
                if property_record:
                    property_record.write({"default_unit_id": False})
                    property_record.unit_ids.unlink()
                    property_record.unlink()

            attempt(remove_property_fixture)

        parameter_model = cls.env["ir.config_parameter"].sudo()
        for key, previous in cls._previous_parameters.items():
            def restore_parameter(key=key, previous=previous):
                current = parameter_model.search([("key", "=", key)], limit=1)
                if previous["exists"]:
                    if current:
                        current.write({"value": previous["value"]})
                    else:
                        parameter_model.create(
                            {"key": key, "value": previous["value"]}
                        )
                else:
                    current.unlink()

            attempt(restore_parameter)

        attempt(cls._validate_restored_parameters)
        try:
            cls.env.cr.commit()
            cls._signal_http_worker_cache_invalidation()
        except Exception as error:
            cls.env.cr.rollback()
            errors.append(error)
        cls._test_state_restored = not errors
        if errors:
            raise errors[0]

    @classmethod
    def _validate_restored_parameters(cls):
        parameter_model = cls.env["ir.config_parameter"].sudo()
        for key, previous in cls._previous_parameters.items():
            records = parameter_model.search([("key", "=", key)])
            if previous["exists"]:
                if len(records) != 1 or records.value != previous["value"]:
                    raise AssertionError("Failed to restore test parameter %s." % key)
            elif records:
                raise AssertionError("Failed to remove test parameter %s." % key)

    @classmethod
    def _validate_persisted_http_results(cls):
        lead_model = cls.env["commercial.property.lead"].sudo()
        expectations = {
            "test_explicit_phone_fallback_still_creates_lead": {
                "name": "Explicit Phone Prospect",
                "phone": "+12025550199",
                "whatsapp_sender": False,
            },
            "test_mcp_sender_creates_lead_with_normalized_persisted_identity": {
                "name": "New WhatsApp Prospect",
                "phone": "+593999000222",
                "whatsapp_sender": "+593999000222",
            },
            "test_mcp_sender_overrides_mismatched_payload_phone": {
                "name": "Mismatched Phone Prospect",
                "phone": "+593999000444",
                "whatsapp_sender": "+593999000444",
            },
        }
        absent_names = {
            "test_mcp_header_without_channel_secret_cannot_spoof_sender": (
                "Untrusted MCP Prospect"
            ),
            "test_non_mcp_request_cannot_spoof_sender_without_phone": (
                "Spoofed Prospect"
            ),
        }
        for test_name in cls._executed_http_cases:
            if test_name in expectations:
                expected = expectations[test_name]
                leads = lead_model.search(
                    [
                        ("unit_id", "in", cls._unit_ids),
                        ("name", "=", expected["name"]),
                    ]
                )
                if len(leads) != 1:
                    raise AssertionError(
                        "Expected one committed lead for %s, found %s."
                        % (test_name, len(leads))
                    )
                if leads.phone != expected["phone"]:
                    raise AssertionError(
                        "Unexpected committed phone for %s." % test_name
                    )
                if leads.whatsapp_sender != expected["whatsapp_sender"]:
                    raise AssertionError(
                        "Unexpected committed WhatsApp sender for %s." % test_name
                    )
            elif test_name in absent_names:
                leads = lead_model.search(
                    [
                        ("unit_id", "in", cls._unit_ids),
                        ("name", "=", absent_names[test_name]),
                    ]
                )
                if leads:
                    raise AssertionError(
                        "Unexpected committed lead for %s." % test_name
                    )

    @classmethod
    def tearDownClass(cls):
        cleanup_error = None
        try:
            cls._restore_test_state()
        except Exception as error:
            cleanup_error = error
        finally:
            super().tearDownClass()
        if cleanup_error:
            raise cleanup_error

    def _post_enquiry(self, payload, *, mcp=True, mcp_secret=True):
        headers = {
            "Authorization": "Bearer %s" % self.token,
            "Content-Type": "application/json",
            "Idempotency-Key": str(uuid.uuid4()),
        }
        if mcp:
            headers["X-Hermes-Channel"] = "mcp"
        if mcp and mcp_secret:
            headers["X-Hermes-MCP-Token"] = self.mcp_channel_token
        return self.url_open(
            "/api/hermes/properties/%s/enquiries" % self.unit.code,
            data=json.dumps(payload).encode(),
            headers=headers,
        )


    def test_mcp_sender_creates_lead_with_normalized_persisted_identity(self):
        response = self._post_enquiry(
            {
                "name": "New WhatsApp Prospect",
                "whatsapp_sender": "+593 (999) 000-222",
                "consent": True,
            }
        )

        self.assertEqual(response.status_code, 201)
        self.__class__._executed_http_cases.add(self._testMethodName)

    def test_mcp_sender_overrides_mismatched_payload_phone(self):
        response = self._post_enquiry(
            {
                "name": "Mismatched Phone Prospect",
                "phone": "+12025550199",
                "whatsapp_sender": "+593 (999) 000-444",
                "consent": True,
            }
        )

        self.assertEqual(response.status_code, 201)
        self.__class__._executed_http_cases.add(self._testMethodName)

    def test_mcp_header_without_channel_secret_cannot_spoof_sender(self):
        response = self._post_enquiry(
            {
                "name": "Untrusted MCP Prospect",
                "whatsapp_sender": "+593999000555",
                "consent": True,
            },
            mcp_secret=False,
        )

        self.assertEqual(response.status_code, 400)
        self.__class__._executed_http_cases.add(self._testMethodName)

    def test_non_mcp_request_cannot_spoof_sender_without_phone(self):
        response = self._post_enquiry(
            {
                "name": "Spoofed Prospect",
                "whatsapp_sender": "+593999000333",
                "consent": True,
            },
            mcp=False,
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("a verified contact number", response.text)
        self.__class__._executed_http_cases.add(self._testMethodName)

    def test_explicit_phone_fallback_still_creates_lead(self):
        response = self._post_enquiry(
            {
                "name": "Explicit Phone Prospect",
                "phone": "+12025550199",
                "consent": True,
            },
            mcp=False,
        )

        self.assertEqual(response.status_code, 201)
        self.__class__._executed_http_cases.add(self._testMethodName)
