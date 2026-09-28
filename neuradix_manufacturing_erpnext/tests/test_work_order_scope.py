"""Real Frappe/ERPNext tests: integration identity, site scope and Frappe permission paths.

These run against an actual site with ERPNext installed. Users are switched with
``frappe.set_user`` so Frappe's role, DocPerm and hook evaluation run for real.
"""

import frappe
import frappe.client

from neuradix_manufacturing_erpnext.api import v1
from neuradix_manufacturing_erpnext.integration import scope
from neuradix_manufacturing_erpnext.integration.constants import (
    INTEGRATION_ROLE,
    NOT_FOUND_MESSAGE,
    NOT_PERMITTED_MESSAGE,
    PRINCIPAL_DOCTYPE,
    SITE_DOCTYPE,
)
from neuradix_manufacturing_erpnext.setup.install import ensure_integration_access
from neuradix_manufacturing_erpnext.tests import fixtures as fx
from neuradix_manufacturing_erpnext.tests.base import RealSiteTestCase

BUSINESS_METHODS = (
    (v1.work_orders, {"site": fx.SITE_A1}),
    (v1.work_order, {"site": fx.SITE_A1, "name": "MFG-WO-DOES-NOT-EXIST"}),
    (v1.work_order_deletions, {"site": fx.SITE_A1}),
)


class TestIntegrationIdentity(RealSiteTestCase):
    def test_guest_is_denied_everywhere(self):
        for method, kwargs in (*BUSINESS_METHODS, (v1.capabilities, {})):
            with self.subTest(method=method.__name__):
                self.assert_denied("Guest", method, **kwargs)

    def test_authenticated_user_without_role_is_denied(self):
        for method, kwargs in (*BUSINESS_METHODS, (v1.capabilities, {})):
            with self.subTest(method=method.__name__):
                self.assert_denied(fx.USER_PLAIN, method, **kwargs)

    def test_erpnext_manufacturing_user_is_not_an_integration_principal(self):
        order = fx.make_work_order(fx.SITE_A1)
        with self.set_user(fx.USER_MFG):
            # ERPNext grants this user Work Order read, so the denial below is ours, not ERPNext's.
            self.assertTrue(frappe.has_permission("Work Order", "read", doc=order.name))
        for method, kwargs in BUSINESS_METHODS:
            with self.subTest(method=method.__name__):
                self.assert_denied(fx.USER_MFG, method, **kwargs)

    def test_role_without_principal_record_is_denied(self):
        for method, kwargs in BUSINESS_METHODS:
            self.assert_denied(fx.USER_NO_RECORD, method, **kwargs)

    def test_disabled_principal_is_denied(self):
        for method, kwargs in BUSINESS_METHODS:
            self.assert_denied(fx.USER_DISABLED, method, **kwargs)

    def test_disabled_user_is_denied(self):
        frappe.db.set_value("User", fx.USER_A1, "enabled", 0)
        self.assert_denied(fx.USER_A1, v1.work_orders, site=fx.SITE_A1)

    def test_principal_that_gains_another_role_is_denied(self):
        fx.ensure_user(fx.USER_A1, [INTEGRATION_ROLE, "Stock User"])
        self.assert_denied(fx.USER_A1, v1.work_orders, site=fx.SITE_A1)
        self.assert_denied(fx.USER_A1, v1.capabilities)

    def test_administrator_is_not_an_integration_principal(self):
        self.assert_denied("Administrator", v1.work_orders, site=fx.SITE_A1)
        self.assertIsNone(self.call_as("Administrator", v1.capabilities)["principal"])

    def test_unknown_unauthorized_and_missing_sites_are_indistinguishable(self):
        for site in (fx.SITE_B1, fx.SITE_A2, "NXT-UNKNOWN", "nxt-a1", "", None, ["NXT-A1"]):
            with self.subTest(site=site), self.set_user(fx.USER_A1):
                with self.assertRaises(frappe.PermissionError) as denied:
                    v1.work_orders(site=site)
                self.assertEqual(str(denied.exception), NOT_PERMITTED_MESSAGE)

    def test_disabled_site_is_denied(self):
        frappe.db.set_value(SITE_DOCTYPE, fx.SITE_A1, "enabled", 0)
        self.assert_denied(fx.USER_A1, v1.work_orders, site=fx.SITE_A1)

    def test_distinct_principals_have_distinct_scopes(self):
        a1 = fx.make_work_order(fx.SITE_A1)
        a2 = fx.make_work_order(fx.SITE_A2)
        b1 = fx.make_work_order(fx.SITE_B1)
        self.assertIn(a1.name, self.list_names(fx.USER_A1, fx.SITE_A1))
        multi_a2 = self.list_names(fx.USER_MULTI, fx.SITE_A2)
        multi_b1 = self.list_names(fx.USER_MULTI, fx.SITE_B1)
        self.assertIn(a2.name, multi_a2)
        self.assertIn(b1.name, multi_b1)
        self.assertNotIn(a1.name, multi_a2 + multi_b1)
        self.assertNotIn(b1.name, multi_a2)
        self.assert_denied(fx.USER_MULTI, v1.work_orders, site=fx.SITE_A1)

    def test_request_parameters_cannot_expand_scope(self):
        a1 = fx.make_work_order(fx.SITE_A1)
        b1 = fx.make_work_order(fx.SITE_B1)
        with self.set_user(fx.USER_A1):
            page = frappe.call(
                "neuradix_manufacturing_erpnext.api.v1.work_orders",
                site=fx.SITE_A1,
                page_size=200,
                company=fx.BETA.name,
                filters={"company": fx.BETA.name},
                user=fx.USER_MULTI,
                ignore_permissions=1,
            )
        names = [item["name"] for item in page["items"]]
        self.assertIn(a1.name, names)
        self.assertNotIn(b1.name, names)
        self.assertEqual({item["company"] for item in page["items"]}, {fx.ALPHA.name})


class TestFrappePermissionPaths(RealSiteTestCase):
    """The role's Work Order read is narrowed on Frappe's generic read paths too."""

    def setUp(self):
        super().setUp()
        self.a1 = fx.make_work_order(fx.SITE_A1)
        self.a2 = fx.make_work_order(fx.SITE_A2)
        self.b1 = fx.make_work_order(fx.SITE_B1)
        self.draft = fx.make_work_order(fx.SITE_A1, submit=False)
        self.span = fx.make_work_order(
            fx.SITE_A1, wip_warehouse=fx.site_warehouse(fx.SITE_A2, fx.WIP)
        )

    def test_get_list_and_count_are_confined_to_site_scope(self):
        with self.set_user(fx.USER_A1):
            names = set(frappe.get_list("Work Order", pluck="name", limit_page_length=0))
            count = frappe.client.get_count("Work Order")
        self.assertIn(self.a1.name, names)
        for hidden in (self.a2, self.b1, self.draft, self.span):
            self.assertNotIn(hidden.name, names)
        self.assertEqual(count, len(names))
        companies = set(
            frappe.get_all("Work Order", filters={"name": ["in", list(names)]}, pluck="company")
        )
        self.assertEqual(companies, {fx.ALPHA.name})

    def test_api_list_excludes_every_out_of_scope_order(self):
        names = self.list_names(fx.USER_A1, fx.SITE_A1)
        self.assertIn(self.a1.name, names)
        for hidden in (self.a2, self.b1, self.draft, self.span):
            with self.subTest(order=hidden.name):
                self.assertNotIn(hidden.name, names)

    def test_explicit_filters_match_the_membership_rule(self):
        """The API's own filters must agree with scope.contains without relying on hooks."""
        skip = fx.make_work_order(fx.SITE_A1, skip_transfer=True)
        orders = (self.a1, self.a2, self.b1, self.draft, self.span, skip)
        for site_id in (fx.SITE_A1, fx.SITE_A2, fx.SITE_B1):
            site = scope.load_site(site_id)
            for order in orders:
                with self.subTest(site=site_id, order=order.name):
                    matched = frappe.get_all(
                        "Work Order",
                        filters=[*scope.list_filters(site), ["name", "=", order.name]],
                        pluck="name",
                    )
                    row = frappe.db.get_value("Work Order", order.name, "*", as_dict=True)
                    self.assertEqual(bool(matched), scope.contains(site, row))
        self.assertTrue(scope.contains(scope.load_site(fx.SITE_A1), skip))
        self.assertFalse(scope.contains(scope.load_site(fx.SITE_A1), self.span))

    def test_child_table_lists_are_confined(self):
        for doctype in ("Work Order Item", "Work Order Operation"):
            with self.subTest(doctype=doctype), self.set_user(fx.USER_A1):
                parents = set(
                    frappe.get_list(
                        doctype,
                        parent_doctype="Work Order",
                        pluck="parent",
                        limit_page_length=0,
                    )
                )
                self.assertIn(self.a1.name, parents)
                for hidden in (self.a2, self.b1, self.draft, self.span):
                    self.assertNotIn(hidden.name, parents)

    def test_document_reads_outside_scope_are_denied(self):
        with self.set_user(fx.USER_A1):
            self.assertTrue(frappe.has_permission("Work Order", "read", doc=self.a1.name))
            for hidden in (self.a2, self.b1, self.draft, self.span):
                with self.subTest(order=hidden.name):
                    self.assertFalse(frappe.has_permission("Work Order", "read", doc=hidden.name))
                    with self.assertRaises(frappe.PermissionError):
                        frappe.client.get("Work Order", hidden.name)

    def test_role_grants_no_write_or_other_doctypes(self):
        with self.set_user(fx.USER_A1):
            for ptype in ("write", "create", "submit", "cancel", "delete", "amend", "export"):
                with self.subTest(ptype=ptype):
                    self.assertFalse(frappe.has_permission("Work Order", ptype, doc=self.a1.name))
            for doctype in ("BOM", "Item", "Warehouse", "Stock Entry", "Company", SITE_DOCTYPE):
                with self.subTest(doctype=doctype):
                    self.assertFalse(frappe.has_permission(doctype, "read"))
                    with self.assertRaises(frappe.PermissionError):
                        frappe.get_list(doctype, limit_page_length=1)

    def test_frappe_role_permission_is_required_by_the_api(self):
        frappe.db.delete("Custom DocPerm", {"parent": "Work Order", "role": INTEGRATION_ROLE})
        frappe.clear_cache(doctype="Work Order")
        self.assert_denied(fx.USER_A1, v1.work_orders, site=fx.SITE_A1)
        self.assert_denied(fx.USER_A1, v1.work_order, site=fx.SITE_A1, name=self.a1.name)
        self.assert_denied(fx.USER_A1, v1.work_order_deletions, site=fx.SITE_A1)
        with self.set_user(fx.USER_A1):
            self.assertFalse(frappe.has_permission("Work Order", "read", doc=self.a1.name))

    def test_principal_without_active_record_sees_no_generic_rows(self):
        frappe.db.set_value(PRINCIPAL_DOCTYPE, fx.USER_A1, "enabled", 0)
        with self.set_user(fx.USER_A1):
            self.assertEqual([], frappe.get_list("Work Order", pluck="name", limit_page_length=0))
            self.assertFalse(frappe.has_permission("Work Order", "read", doc=self.a1.name))

    def test_shared_document_does_not_escape_api_scope(self):
        frappe.share.add_docshare(
            "Work Order", self.b1.name, fx.USER_A1, read=1, flags={"ignore_share_permission": 1}
        )
        with self.set_user(fx.USER_A1):
            # Frappe sharing is an explicit administrative grant on generic routes ...
            self.assertTrue(frappe.has_permission("Work Order", "read", doc=self.b1.name))
            # ... but the integration API applies site filters and never returns it.
            with self.assertRaises(frappe.DoesNotExistError):
                v1.work_order(site=fx.SITE_A1, name=self.b1.name)
        self.assertNotIn(self.b1.name, self.list_names(fx.USER_A1, fx.SITE_A1))


class TestScopeDrift(RealSiteTestCase):
    def test_sites_overlapping_after_warehouse_reparenting_fail_closed(self):
        moved = frappe.get_doc("Warehouse", fx.ALPHA.warehouse("Plant A2"))
        moved.parent_warehouse = fx.ALPHA.warehouse("Plant A1")
        moved.save()
        self.assert_denied(fx.USER_A1, v1.work_orders, site=fx.SITE_A1)
        self.assert_denied(fx.USER_MULTI, v1.work_orders, site=fx.SITE_A2)
        # The unaffected Beta site keeps working for the same principal.
        self.call_as(fx.USER_MULTI, v1.work_orders, site=fx.SITE_B1)
        with self.set_user(fx.USER_A1):
            self.assertEqual([], frappe.get_list("Work Order", pluck="name", limit_page_length=0))

    def test_percent_signs_in_scope_names_still_match(self):
        company = fx.ALPHA
        root = fx.ensure_warehouse(company, "Plant 100% A3", company.warehouse("All Warehouses"), 1)
        wip = fx.ensure_warehouse(company, "Plant 100% A3 WIP", root)
        fg = fx.ensure_warehouse(company, "Plant 100% A3 FG", root)
        fx.ensure_site("NXT-A3", company, root)
        fx.ensure_principal(fx.USER_NO_RECORD, ["NXT-A3"])
        order = fx.make_work_order(fx.SITE_A1, wip_warehouse=wip, fg_warehouse=fg)
        with self.set_user(fx.USER_NO_RECORD):
            self.assertIn(
                order.name, frappe.get_list("Work Order", pluck="name", limit_page_length=0)
            )
            self.assertTrue(frappe.has_permission("Work Order", "read", doc=order.name))
        self.assertIn(order.name, self.list_names(fx.USER_NO_RECORD, "NXT-A3"))


class TestRouteRestriction(RealSiteTestCase):
    """The auth hook on routes whose HTML error pages need built assets (absent on test benches).

    JSON API routes are exercised end to end in test_http_api.py.
    """

    def run_hook(self, user, path, method="GET", query=""):
        from werkzeug.test import EnvironBuilder
        from werkzeug.wrappers import Request

        from neuradix_manufacturing_erpnext.integration.auth import restrict_integration_principals

        request = Request(
            EnvironBuilder(path=path, method=method, query_string=query).get_environ()
        )
        frappe.local.request = request
        frappe.local.form_dict = frappe._dict(request.args)
        try:
            with self.set_user(user):
                restrict_integration_principals()
        finally:
            del frappe.local.request
            frappe.local.form_dict = frappe._dict()

    def test_principal_is_refused_outside_the_read_methods(self):
        for path in ("/app/work-order", "/private/files/report.pdf", "/me", "/api/resource/Item"):
            with self.subTest(path=path), self.assertRaises(frappe.PermissionError):
                self.run_hook(fx.USER_A1, path)
        self.run_hook(fx.USER_A1, "/api/method/neuradix_manufacturing_erpnext.api.v1.work_orders")

    def test_other_users_are_not_restricted(self):
        for user in ("Guest", "Administrator", fx.USER_MFG, fx.USER_PLAIN):
            with self.subTest(user=user):
                self.run_hook(user, "/app/work-order")


class TestInstallAndConfiguration(RealSiteTestCase):
    def test_role_is_least_privilege(self):
        role = frappe.get_doc("Role", INTEGRATION_ROLE)
        self.assertEqual(role.desk_access, 0)
        self.assertEqual(role.disabled, 0)
        rows = frappe.get_all("Custom DocPerm", filters={"role": INTEGRATION_ROLE}, fields=["*"])
        self.assertEqual([row.parent for row in rows], ["Work Order"])
        granted = {right for right in frappe.permissions.rights if rows[0].get(right)}
        self.assertEqual(granted, {"read"})
        self.assertEqual(rows[0].permlevel, 0)
        self.assertEqual(rows[0].if_owner, 0)
        self.assertFalse(frappe.get_all("DocPerm", filters={"role": INTEGRATION_ROLE}))
        # Adding the custom rule preserved ERPNext's standard Work Order roles.
        roles = set(
            frappe.get_all("Custom DocPerm", filters={"parent": "Work Order"}, pluck="role")
        )
        self.assertTrue({"Manufacturing User", "Stock User"} <= roles)

    def test_uninstall_restores_standard_work_order_permissions(self):
        from neuradix_manufacturing_erpnext.setup.install import remove_integration_access

        remove_integration_access()
        self.assertFalse(frappe.get_all("Custom DocPerm", filters={"parent": "Work Order"}))
        self.assertEqual(frappe.db.get_value("Role", INTEGRATION_ROLE, "disabled"), 1)

    def test_uninstall_keeps_customized_work_order_permissions(self):
        from neuradix_manufacturing_erpnext.setup.install import remove_integration_access

        name = frappe.get_all(
            "Custom DocPerm",
            filters={"parent": "Work Order", "role": "Stock User"},
            pluck="name",
        )[0]
        frappe.db.set_value("Custom DocPerm", name, "export", 1)
        remove_integration_access()
        roles = set(
            frappe.get_all("Custom DocPerm", filters={"parent": "Work Order"}, pluck="role")
        )
        self.assertEqual(roles, {"Manufacturing User", "Stock User"})

    def test_after_migrate_repairs_escalated_rights_idempotently(self):
        name = frappe.get_all(
            "Custom DocPerm",
            filters={"parent": "Work Order", "role": INTEGRATION_ROLE},
            pluck="name",
        )[0]
        frappe.db.set_value("Custom DocPerm", name, {"write": 1, "export": 1})
        ensure_integration_access()
        ensure_integration_access()
        rows = frappe.get_all(
            "Custom DocPerm",
            filters={"parent": "Work Order", "role": INTEGRATION_ROLE},
            fields=["*"],
        )
        self.assertEqual(len(rows), 1)
        self.assertEqual(
            {right for right in frappe.permissions.rights if rows[0].get(right)}, {"read"}
        )

    def test_site_mapping_validation(self):
        root = fx.ALPHA.warehouse("Plant A1")
        cases = {
            "overlap": {"site_id": "NXT-A1-DUP", "company": fx.ALPHA.name, "root_warehouse": root},
            "nested": {
                "site_id": "NXT-A1-WIP",
                "company": fx.ALPHA.name,
                "root_warehouse": fx.site_warehouse(fx.SITE_A1, fx.WIP),
            },
            "wrong company": {"site_id": "NXT-X", "company": fx.BETA.name, "root_warehouse": root},
            "bad id": {"site_id": "nxt a1", "company": fx.ALPHA.name, "root_warehouse": root},
        }
        for label, values in cases.items():
            with self.subTest(case=label):
                doc = frappe.get_doc({"doctype": SITE_DOCTYPE, "site_name": label, **values})
                with self.assertRaises(frappe.ValidationError):
                    doc.insert()

    def test_principal_validation(self):
        cases = {
            "administrator": ("Administrator", [fx.SITE_A1], "cannot be integration principals"),
            "no role": (fx.USER_PLAIN, [fx.SITE_A1], "must hold the"),
            "duplicate site": (fx.USER_NO_RECORD, [fx.SITE_A1, fx.SITE_A1], "listed twice"),
        }
        for label, (user, sites, message) in cases.items():
            with self.subTest(case=label):
                self.assert_principal_rejected(user, sites, message)

    def test_principal_with_an_extra_role_cannot_be_saved(self):
        fx.ensure_user(fx.USER_NO_RECORD, [INTEGRATION_ROLE, "Stock User"])
        self.assert_principal_rejected(fx.USER_NO_RECORD, [fx.SITE_A1], "must not hold other roles")

    def assert_principal_rejected(self, user, sites, message):
        doc = frappe.new_doc(PRINCIPAL_DOCTYPE)
        doc.user = user
        doc.set("sites", [{"site": site} for site in sites])
        with self.assertRaises(frappe.ValidationError) as rejected:
            doc.insert()
        self.assertIn(message, str(rejected.exception))


class TestNotFoundIsUniform(RealSiteTestCase):
    def test_out_of_scope_and_missing_identifiers_are_not_found(self):
        a2 = fx.make_work_order(fx.SITE_A2)
        b1 = fx.make_work_order(fx.SITE_B1)
        draft = fx.make_work_order(fx.SITE_A1, submit=False)
        for name in (a2.name, b1.name, draft.name, "MFG-WO-DOES-NOT-EXIST", "", None, "x" * 141):
            with self.subTest(name=name), self.set_user(fx.USER_A1):
                with self.assertRaises(frappe.DoesNotExistError) as missing:
                    v1.work_order(site=fx.SITE_A1, name=name)
                self.assertEqual(str(missing.exception), NOT_FOUND_MESSAGE)
