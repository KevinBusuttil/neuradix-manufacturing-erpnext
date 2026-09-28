"""Real Frappe/ERPNext tests of the Work Order read contract: DTOs, pagination and changes."""

import datetime as dt
from decimal import Decimal
from zoneinfo import ZoneInfo

import frappe
from frappe.utils import get_system_timezone

from neuradix_manufacturing_erpnext.api import v1
from neuradix_manufacturing_erpnext.integration.constants import (
    SCHEMA_WORK_ORDER_DELETION_PAGE,
    SCHEMA_WORK_ORDER_DETAIL,
    SCHEMA_WORK_ORDER_PAGE,
)
from neuradix_manufacturing_erpnext.integration.work_orders import ContractDataError
from neuradix_manufacturing_erpnext.tests import fixtures as fx
from neuradix_manufacturing_erpnext.tests.base import RealSiteTestCase

FUTURE = dt.datetime(2099, 1, 1, 0, 0, 0)


def erp_instant(naive):
    """RFC 3339 string for a naive ERP wall-clock value in the site's system time zone."""
    return naive.replace(tzinfo=ZoneInfo(get_system_timezone())).isoformat()


def db_decimal(doctype, name, column):
    """Stored DECIMAL text, normalized independently of the serializer under test."""
    text = frappe.db.sql(
        f"select CAST(`{column}` AS CHAR) from `tab{doctype}` where name = %s", name
    )[0][0]
    value = Decimal(text)
    return "0" if value == 0 else format(value.normalize(), "f")


class TestWorkOrderDtos(RealSiteTestCase):
    def test_list_page_matches_contract_and_scope(self):
        before = frappe.utils.now_datetime() - dt.timedelta(seconds=1)
        a1 = fx.make_work_order(fx.SITE_A1)
        skip = fx.make_work_order(fx.SITE_A1, skip_transfer=True)
        a2 = fx.make_work_order(fx.SITE_A2)
        with self.set_user(fx.USER_A1):
            page = v1.work_orders(site=fx.SITE_A1, modified_since=erp_instant(before))
        self.assert_contract(page, SCHEMA_WORK_ORDER_PAGE)
        names = [item["name"] for item in page["items"]]
        self.assertIn(a1.name, names)
        self.assertIn(skip.name, names, "an empty WIP warehouse stays in scope")
        self.assertNotIn(a2.name, names)
        self.assertEqual(page["site"]["site_id"], fx.SITE_A1)
        self.assertEqual(page["site"]["company"], fx.ALPHA.name)
        self.assertEqual(page["source"]["erp_time_zone"], get_system_timezone())
        self.assertEqual(page["source"]["instance"], frappe.local.site)
        item = next(item for item in page["items"] if item["name"] == skip.name)
        self.assertIsNone(item["warehouses"]["wip"])

    def test_detail_values_are_exact_and_labelled_as_erp_time(self):
        order = fx.make_work_order(fx.SITE_A1, qty="12.5")
        with self.set_user(fx.USER_A1):
            payload = v1.work_order(site=fx.SITE_A1, name=order.name)
        self.assert_contract(payload, SCHEMA_WORK_ORDER_DETAIL)
        wo = payload["work_order"]
        order.reload()
        self.assertEqual(wo["lifecycle"], "submitted")
        self.assertEqual(wo["status"], "not_started")
        self.assertEqual(wo["erp_status"], "Not Started")
        self.assertEqual(wo["quantities"]["planned"], "12.5")
        self.assertEqual(wo["quantities"]["produced"], "0")
        self.assertEqual(wo["stock_uom"], fx.UOM)
        self.assertEqual(wo["bom_no"], order.bom_no)
        self.assertEqual(wo["production_item"]["item_code"], fx.FG_ITEM)
        self.assertEqual(wo["warehouses"]["source"], fx.ALPHA.warehouse("Stores"))
        self.assertEqual(wo["version"], order.modified.strftime("%Y-%m-%d %H:%M:%S.%f"))
        zone = ZoneInfo(get_system_timezone())
        expected_start = order.planned_start_date.replace(tzinfo=zone)
        self.assertEqual(dt.datetime.fromisoformat(wo["planned_start_at"]), expected_start)
        self.assertEqual(wo["planned_start_at"][-6:], expected_start.isoformat()[-6:])
        [material] = wo["required_items"]
        self.assertEqual(material["item_code"], fx.RM_ITEM)
        self.assertEqual(material["quantities"]["required"], "28.125")
        stored = db_decimal("Work Order Item", order.required_items[0].name, "required_qty")
        self.assertEqual(material["quantities"]["required"], stored)
        [operation] = wo["operations"]
        self.assertEqual(operation["operation"], fx.OPERATION)
        self.assertEqual(operation["status"], "pending")
        stored = db_decimal("Work Order Operation", order.operations[0].name, "time_in_mins")
        self.assertEqual(operation["planned_minutes"], stored)

    def test_decimal_values_keep_every_stored_digit(self):
        order = fx.make_work_order(fx.SITE_A1, qty="12.5")
        frappe.db.sql(
            "update `tabWork Order` set qty = %s where name = %s",
            ("123456789012.123456789", order.name),
        )
        with self.set_user(fx.USER_A1):
            wo = v1.work_order(site=fx.SITE_A1, name=order.name)["work_order"]
        # A float round-trip would print 123456789012.12346.
        self.assertEqual(wo["quantities"]["planned"], "123456789012.123456789")

    def test_stored_values_outside_the_contract_fail_the_request(self):
        order = fx.make_work_order(fx.SITE_A1)
        frappe.db.sql("update `tabWork Order` set qty = -1 where name = %s", order.name)
        with self.set_user(fx.USER_A1):
            with self.assertRaises(ContractDataError) as failed:
                v1.work_order(site=fx.SITE_A1, name=order.name)
            self.assertIn(order.name, str(failed.exception))
            with self.assertRaises(ContractDataError):
                self.list_names(fx.USER_A1, fx.SITE_A1)

    def test_amendment_source_outside_the_site_is_not_disclosed(self):
        original = fx.make_work_order(fx.SITE_A2)
        original.cancel()
        amended = frappe.copy_doc(original)
        amended.docstatus = 0
        amended.amended_from = original.name
        amended.wip_warehouse = fx.site_warehouse(fx.SITE_A1, fx.WIP)
        amended.fg_warehouse = fx.site_warehouse(fx.SITE_A1, fx.FG)
        amended.insert()
        amended.submit()
        with self.set_user(fx.USER_A1):
            detail = v1.work_order(site=fx.SITE_A1, name=amended.name)["work_order"]
        self.assertIsNone(detail["amended_from"])
        with self.set_user(fx.USER_MULTI):
            source = v1.work_order(site=fx.SITE_A2, name=original.name)["work_order"]
        self.assertEqual(source["lifecycle"], "cancelled")

    def test_bom_change_through_amendment_is_visible(self):
        original = fx.make_work_order(fx.SITE_A1)
        original.cancel()
        amended = frappe.copy_doc(original)
        amended.docstatus = 0
        amended.amended_from = original.name
        amended.bom_no = fx.boms(fx.ALPHA)[1]
        amended.get_items_and_operations_from_bom()
        for row in amended.required_items:
            row.source_warehouse = fx.ALPHA.warehouse("Stores")
        amended.insert()
        amended.submit()
        with self.set_user(fx.USER_A1):
            old = v1.work_order(site=fx.SITE_A1, name=original.name)["work_order"]
            new = v1.work_order(site=fx.SITE_A1, name=amended.name)["work_order"]
        self.assertEqual(old["lifecycle"], "cancelled")
        self.assertEqual(old["status"], "cancelled")
        self.assertEqual(new["amended_from"], original.name)
        self.assertNotEqual(new["bom_no"], old["bom_no"])
        self.assertEqual(
            {row["item_code"] for row in new["required_items"]}, {fx.RM_ITEM, fx.RM_ITEM_2}
        )


class TestPagination(RealSiteTestCase):
    def make_tied_orders(self):
        orders = [fx.make_work_order(fx.SITE_A1, qty=str(index + 1)) for index in range(5)]
        names = [order.name for order in orders]
        tie = FUTURE
        later = FUTURE + dt.timedelta(microseconds=1)
        fx.set_modified(names[:3], tie)
        fx.set_modified(names[3:], later)
        expected = sorted(names[:3]) + sorted(names[3:])
        return expected

    def test_keyset_pages_are_ordered_bounded_and_gapless_across_ties(self):
        expected = self.make_tied_orders()
        since = erp_instant(FUTURE - dt.timedelta(seconds=1))
        seen, cursor, sizes = [], None, []
        while True:
            params = {"site": fx.SITE_A1, "page_size": "2"}
            params.update({"cursor": cursor} if cursor else {"modified_since": since})
            with self.set_user(fx.USER_A1):
                page = v1.work_orders(**params)
            self.assert_contract(page, "neuradix.erpnext.work_order_page.v1")
            sizes.append(len(page["items"]))
            seen.extend(item["name"] for item in page["items"])
            cursor = page["next_cursor"]
            if not cursor:
                break
        self.assertEqual(seen, expected)
        self.assertEqual(sizes, [2, 2, 1])

    def test_page_size_default_and_bounds(self):
        with self.set_user(fx.USER_A1):
            self.assertEqual(v1.work_orders(site=fx.SITE_A1)["page_size"], 50)
            self.assertEqual(v1.work_orders(site=fx.SITE_A1, page_size="200")["page_size"], 200)
            for bad in (0, "0", 201, "201", "-1", "abc", "1.5", True, 1.5, "٣"):
                with self.subTest(page_size=bad), self.assertRaises(frappe.ValidationError):
                    v1.work_orders(site=fx.SITE_A1, page_size=bad)

    def test_cursor_and_since_validation(self):
        self.make_tied_orders()
        since = erp_instant(FUTURE - dt.timedelta(seconds=1))
        with self.set_user(fx.USER_A1):
            cursor = v1.work_orders(site=fx.SITE_A1, page_size=1, modified_since=since)[
                "next_cursor"
            ]
            deletion_cursor = cursor  # same token shape, but bound to a different method below
        self.assertTrue(cursor)
        invalid = {
            "garbage": {"cursor": "not-a-cursor"},
            "cursor plus since": {"cursor": cursor, "modified_since": since},
            "naive since": {"modified_since": "2099-01-01T00:00:00"},
            "date only": {"modified_since": "2099-01-01"},
        }
        for label, params in invalid.items():
            with self.subTest(case=label), self.set_user(fx.USER_A1):
                with self.assertRaises(frappe.ValidationError):
                    v1.work_orders(site=fx.SITE_A1, **params)
        with self.set_user(fx.USER_A1), self.assertRaises(frappe.ValidationError):
            v1.work_order_deletions(site=fx.SITE_A1, cursor=deletion_cursor)

    def test_cursor_is_bound_to_its_site(self):
        fx.make_work_order(fx.SITE_A2)
        fx.make_work_order(fx.SITE_A2)
        with self.set_user(fx.USER_MULTI):
            cursor = v1.work_orders(site=fx.SITE_A2, page_size=1)["next_cursor"]
            self.assertTrue(cursor)
            with self.assertRaises(frappe.ValidationError):
                v1.work_orders(site=fx.SITE_B1, cursor=cursor)


class TestChangesAndLifecycle(RealSiteTestCase):
    def pass_items(self, since):
        with self.set_user(fx.USER_A1):
            page = v1.work_orders(site=fx.SITE_A1, modified_since=since, page_size=200)
        self.assertIsNone(page["next_cursor"])
        return {item["name"]: item for item in page["items"]}

    def test_stopped_order_reappears_with_a_new_version(self):
        before = erp_instant(frappe.utils.now_datetime() - dt.timedelta(seconds=1))
        order = fx.make_work_order(fx.SITE_A1)
        unchanged = fx.make_work_order(fx.SITE_A1)
        first = self.pass_items(before)
        watermark = max(item["modified_at"] for item in first.values())
        fx.set_modified([unchanged.name], FUTURE - dt.timedelta(days=36500))
        fx.stop(order.name)
        second = self.pass_items(watermark)
        self.assertIn(order.name, second)
        self.assertNotIn(unchanged.name, second)
        self.assertEqual(second[order.name]["status"], "stopped")
        self.assertEqual(second[order.name]["lifecycle"], "submitted")
        self.assertNotEqual(second[order.name]["version"], first[order.name]["version"])

    def test_closed_and_cancelled_orders_are_listed(self):
        before = erp_instant(frappe.utils.now_datetime() - dt.timedelta(seconds=1))
        closed = fx.make_work_order(fx.SITE_A1)
        cancelled = fx.make_work_order(fx.SITE_A1)
        fx.close(closed.name)
        frappe.get_doc("Work Order", cancelled.name).cancel()
        items = self.pass_items(before)
        self.assertEqual(items[closed.name]["status"], "closed")
        self.assertEqual(items[closed.name]["lifecycle"], "submitted")
        self.assertEqual(items[cancelled.name]["status"], "cancelled")
        self.assertEqual(items[cancelled.name]["lifecycle"], "cancelled")

    def test_deletion_markers_are_site_scoped(self):
        before = erp_instant(frappe.utils.now_datetime() - dt.timedelta(seconds=1))
        a1 = fx.make_work_order(fx.SITE_A1)
        b1 = fx.make_work_order(fx.SITE_B1)
        draft = fx.make_work_order(fx.SITE_A1, submit=False)
        versions = {}
        for order in (a1, b1):
            doc = frappe.get_doc("Work Order", order.name)
            doc.cancel()
            versions[order.name] = frappe.db.get_value("Work Order", order.name, "modified")
            frappe.delete_doc("Work Order", order.name)
        frappe.delete_doc("Work Order", draft.name)
        with self.set_user(fx.USER_A1):
            page = v1.work_order_deletions(site=fx.SITE_A1, deleted_since=before)
        self.assert_contract(page, SCHEMA_WORK_ORDER_DELETION_PAGE)
        names = {item["name"]: item for item in page["items"]}
        self.assertIn(a1.name, names)
        self.assertNotIn(b1.name, names)
        self.assertNotIn(draft.name, names)
        self.assertEqual(names[a1.name]["last_lifecycle"], "cancelled")
        self.assertEqual(
            names[a1.name]["last_version"], versions[a1.name].strftime("%Y-%m-%d %H:%M:%S.%f")
        )
        with self.set_user(fx.USER_MULTI):
            beta = v1.work_order_deletions(site=fx.SITE_B1, deleted_since=before)
        self.assertEqual([item["name"] for item in beta["items"]], [b1.name])

    def test_restored_and_reused_names_keep_markers_version_safe(self):
        from frappe.core.doctype.deleted_document.deleted_document import restore

        before = erp_instant(frappe.utils.now_datetime() - dt.timedelta(seconds=1))
        reused = fx.make_work_order(fx.SITE_A1)
        reused.cancel()
        deleted_version = frappe.db.get_value("Work Order", reused.name, "modified")
        frappe.delete_doc("Work Order", reused.name)
        replacement = fx.make_work_order(fx.SITE_A1)
        self.assertEqual(replacement.name, reused.name, "naming series reverted and reused")

        restored = fx.make_work_order(fx.SITE_A1)
        restored.cancel()
        frappe.delete_doc("Work Order", restored.name)
        restore(
            frappe.db.get_value("Deleted Document", {"deleted_name": restored.name}), alert=False
        )
        # Frappe restores a cancelled order as a draft, which the API no longer exposes.
        self.assertEqual(frappe.db.get_value("Work Order", restored.name, "docstatus"), 0)

        with self.set_user(fx.USER_A1):
            markers = {
                item["name"]: item
                for item in v1.work_order_deletions(site=fx.SITE_A1, deleted_since=before)["items"]
            }
            live = v1.work_order(site=fx.SITE_A1, name=replacement.name)["work_order"]
        self.assertIn(restored.name, markers)
        marker = markers[reused.name]
        self.assertEqual(marker["last_version"], deleted_version.strftime("%Y-%m-%d %H:%M:%S.%f"))
        # A consumer applies a marker only to a stored version not newer than last_version.
        self.assertGreater(live["version"], marker["last_version"])

    def test_deletion_cursor_never_scans_other_scopes(self):
        before = erp_instant(frappe.utils.now_datetime() - dt.timedelta(seconds=1))
        a1 = fx.make_work_order(fx.SITE_A1)
        others = [fx.make_work_order(site) for site in (fx.SITE_B1, fx.SITE_A2, fx.SITE_B1)]
        for order in (a1, *others):
            frappe.get_doc("Work Order", order.name).cancel()
            frappe.delete_doc("Work Order", order.name)
        with self.set_user(fx.USER_A1):
            page = v1.work_order_deletions(site=fx.SITE_A1, deleted_since=before, page_size=1)
        self.assertEqual([item["name"] for item in page["items"]], [a1.name])
        self.assertIsNone(page["next_cursor"], "later out-of-scope deletions must not be scanned")
