"""Run inside a disposable ERPNext v15 Bench site."""

import frappe
from frappe.tests.utils import FrappeTestCase

from neuradix_manufacturing_erpnext.api.v1 import capabilities


class TestCapabilities(FrappeTestCase):
    def test_administrator_reads_scaffold_metadata(self):
        previous = frappe.session.user
        try:
            frappe.set_user("Administrator")
            self.assertEqual(capabilities()["maturity"], "scaffold")
            self.assertFalse(any(capabilities()["operations"].values()))
        finally:
            frappe.set_user(previous)

    def test_guest_cannot_read_capabilities(self):
        previous = frappe.session.user
        try:
            frappe.set_user("Guest")
            self.assertRaises(frappe.PermissionError, capabilities)
        finally:
            frappe.set_user(previous)
