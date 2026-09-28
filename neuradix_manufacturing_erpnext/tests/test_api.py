"""Run inside a disposable ERPNext v15 Bench site: capability metadata and its access rules."""

import frappe

from neuradix_manufacturing_erpnext.api.v1 import capabilities
from neuradix_manufacturing_erpnext.integration.constants import SCHEMA_CAPABILITIES
from neuradix_manufacturing_erpnext.tests import fixtures as fx
from neuradix_manufacturing_erpnext.tests.base import RealSiteTestCase

WRITE_OPERATIONS = ("post_stock", "post_production", "maintenance_sync", "discover_command_outcome")


class TestCapabilities(RealSiteTestCase):
    def test_administrator_reads_bootstrap_metadata_without_principal(self):
        result = self.call_as("Administrator", capabilities)
        self.assert_contract(result, SCHEMA_CAPABILITIES)
        self.assertEqual(result["maturity"], "development")
        self.assertTrue(result["operations"]["read_work_orders"])
        self.assertFalse(any(result["operations"][name] for name in WRITE_OPERATIONS))
        self.assertIsNone(result["principal"])

    def test_principal_sees_only_its_own_sites(self):
        result = self.call_as(fx.USER_MULTI, capabilities)
        self.assert_contract(result, SCHEMA_CAPABILITIES)
        self.assertEqual(result["principal"]["user"], fx.USER_MULTI)
        self.assertEqual(
            [site["site_id"] for site in result["principal"]["sites"]], [fx.SITE_A2, fx.SITE_B1]
        )

    def test_guest_cannot_read_capabilities(self):
        self.assert_denied("Guest", capabilities)

    def test_users_outside_bootstrap_and_integration_roles_are_denied(self):
        for user in (fx.USER_PLAIN, fx.USER_MFG, fx.USER_NO_RECORD, fx.USER_DISABLED):
            with self.subTest(user=user):
                self.assert_denied(user, capabilities)

    def test_system_manager_is_bootstrap_only(self):
        fx.ensure_user(fx.USER_PLAIN, ["System Manager"])
        result = self.call_as(fx.USER_PLAIN, capabilities)
        self.assertIsNone(result["principal"])
        frappe.set_user("Administrator")
