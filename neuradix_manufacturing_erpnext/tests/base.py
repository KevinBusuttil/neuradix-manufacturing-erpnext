"""Shared helpers for real-site tests. Not a test module (no ``test_`` prefix)."""

import json
from pathlib import Path

import frappe
from frappe.tests.utils import FrappeTestCase

from neuradix_manufacturing_erpnext.tests import fixtures

CONTRACTS = Path(__file__).resolve().parents[1] / "contracts"


def load_schema(schema_id):
    return json.loads((CONTRACTS / f"{schema_id}.schema.json").read_text())


def contract_validator(schema_id):
    try:
        from jsonschema import Draft202012Validator, FormatChecker
    except ImportError as exc:  # pragma: no cover - environment failure must be loud
        raise AssertionError(
            "jsonschema is required for contract validation; install the app's dev "
            "dependencies (bench setup requirements --python --dev neuradix_manufacturing_erpnext)"
        ) from exc
    schema = load_schema(schema_id)
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema, format_checker=FormatChecker())


class RealSiteTestCase(FrappeTestCase):
    """Commits shared synthetic fixtures once; rolls back each test's own changes."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        frappe.set_user("Administrator")
        fixtures.ensure_base_fixtures()

    def setUp(self):
        frappe.set_user("Administrator")

    def tearDown(self):
        frappe.set_user("Administrator")
        frappe.db.rollback()
        # Role and permission caches live in Redis and are not rolled back with the database.
        for user in fixtures.FIXTURE_USERS:
            frappe.clear_cache(user=user)
        frappe.clear_cache(doctype="Work Order")

    def assert_contract(self, payload, schema_id):
        errors = sorted(
            contract_validator(schema_id).iter_errors(payload), key=lambda e: list(e.path)
        )
        self.assertEqual([], [f"{list(e.path)}: {e.message}" for e in errors])

    def call_as(self, user, method, **kwargs):
        with self.set_user(user):
            return method(**kwargs)

    def assert_denied(self, user, method, **kwargs):
        with self.set_user(user):
            with self.assertRaises(frappe.PermissionError):
                method(**kwargs)

    def list_names(self, user, site, **kwargs):
        from neuradix_manufacturing_erpnext.api import v1

        names, cursor, pages = [], None, 0
        while True:
            params = dict(kwargs, site=site, page_size=kwargs.get("page_size", 200))
            if cursor:
                params.pop("modified_since", None)
                params["cursor"] = cursor
            page = self.call_as(user, v1.work_orders, **params)
            names.extend(item["name"] for item in page["items"])
            cursor = page["next_cursor"]
            pages += 1
            if not cursor:
                return names
            self.assertLess(pages, 1000, "pagination did not terminate")
