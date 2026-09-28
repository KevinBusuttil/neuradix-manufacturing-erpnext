"""Real HTTP tests through Frappe's WSGI application with API-key token authentication.

Requests run in a separate thread and database connection (``frappe.tests.test_api``), so the
data they read is committed. Set ``NEURADIX_CONTRACT_CAPTURE_DIR`` to also write the observed
response bodies; Manufacturing's contract fixtures are normalized from such a capture.
"""

import json
import os
from pathlib import Path
from urllib.parse import quote

import frappe
from frappe.app import application
from frappe.tests.test_api import make_request
from frappe.utils import add_to_date, now_datetime
from werkzeug.test import Client

from neuradix_manufacturing_erpnext.integration.constants import (
    SCHEMA_CAPABILITIES,
    SCHEMA_WORK_ORDER_DELETION_PAGE,
    SCHEMA_WORK_ORDER_DETAIL,
    SCHEMA_WORK_ORDER_PAGE,
)
from neuradix_manufacturing_erpnext.tests import fixtures as fx
from neuradix_manufacturing_erpnext.tests.base import RealSiteTestCase

API = "/api/method/neuradix_manufacturing_erpnext.api.v1."
CLIENT = Client(application, use_cookies=False)


def erp_rfc3339(naive):
    from zoneinfo import ZoneInfo

    return naive.replace(tzinfo=ZoneInfo(frappe.utils.get_system_timezone())).isoformat()


class TestHttpApi(RealSiteTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        started = add_to_date(now_datetime(), seconds=-1)
        cls.since = erp_rfc3339(started)
        cls.a1 = fx.make_work_order(fx.SITE_A1, qty="7.25").name
        cls.a1_second = fx.make_work_order(fx.SITE_A1, qty="3", skip_transfer=True).name
        stopped = fx.make_work_order(fx.SITE_A1, qty="40")
        fx.stop(stopped.name)
        cancelled = fx.make_work_order(fx.SITE_A1, qty="1.5")
        cancelled.cancel()
        cls.b1 = fx.make_work_order(fx.SITE_B1).name
        deleted = fx.make_work_order(fx.SITE_A1)
        deleted.cancel()
        cls.deleted = deleted.name
        frappe.delete_doc("Work Order", deleted.name)
        frappe.db.commit()
        cls.keys = {
            user: fx.issue_api_keys(user)
            for user in (fx.USER_A1, fx.USER_MULTI, fx.USER_PLAIN, fx.USER_NO_RECORD, fx.USER_MFG)
        }
        cls.captured = {}

    @classmethod
    def tearDownClass(cls):
        target = os.environ.get("NEURADIX_CONTRACT_CAPTURE_DIR")
        if target and cls.captured:
            path = Path(target)
            path.mkdir(parents=True, exist_ok=True)
            for name, body in cls.captured.items():
                (path / f"{name}.json").write_text(
                    json.dumps(body, indent=2, sort_keys=True) + "\n"
                )
        super().tearDownClass()

    def request(self, method, params=None, user=None, secret=None, http="GET", path=None):
        headers = {}
        if user:
            key, real_secret = self.keys[user]
            headers["Authorization"] = f"token {key}:{secret or real_secret}"
        target = CLIENT.get if http == "GET" else CLIENT.post
        return make_request(
            target=target,
            args=(path or API + method,),
            kwargs={"query_string": params or {}, "headers": headers},
        )

    def capture(self, name, response):
        self.captured[name] = {"status": response.status_code, "body": response.json}

    def test_principal_reads_scoped_list_detail_and_deletions(self):
        caps = self.request("capabilities", user=fx.USER_A1)
        self.assertEqual(caps.status_code, 200, caps.json)
        self.assert_contract(caps.json["message"], SCHEMA_CAPABILITIES)
        self.capture("capabilities", caps)

        page = self.request(
            "work_orders",
            {"site": fx.SITE_A1, "modified_since": self.since, "page_size": "200"},
            user=fx.USER_A1,
        )
        self.assertEqual(page.status_code, 200, page.json)
        body = page.json["message"]
        self.assert_contract(body, SCHEMA_WORK_ORDER_PAGE)
        names = [item["name"] for item in body["items"]]
        self.assertIn(self.a1, names)
        self.assertNotIn(self.b1, names)
        self.capture("work_order_page", page)

        detail = self.request("work_order", {"site": fx.SITE_A1, "name": self.a1}, user=fx.USER_A1)
        self.assertEqual(detail.status_code, 200, detail.json)
        self.assert_contract(detail.json["message"], SCHEMA_WORK_ORDER_DETAIL)
        self.assertEqual(detail.json["message"]["work_order"]["quantities"]["planned"], "7.25")
        self.capture("work_order_detail", detail)

        deletions = self.request(
            "work_order_deletions",
            {"site": fx.SITE_A1, "deleted_since": self.since},
            user=fx.USER_A1,
        )
        self.assertEqual(deletions.status_code, 200, deletions.json)
        self.assert_contract(deletions.json["message"], SCHEMA_WORK_ORDER_DELETION_PAGE)
        self.assertIn(self.deleted, [item["name"] for item in deletions.json["message"]["items"]])
        self.capture("work_order_deletion_page", deletions)

    def test_cursor_round_trip_over_http(self):
        first = self.request(
            "work_orders",
            {"site": fx.SITE_A1, "modified_since": self.since, "page_size": "1"},
            user=fx.USER_A1,
        )
        self.assertEqual(first.status_code, 200, first.json)
        cursor = first.json["message"]["next_cursor"]
        self.assertIsNotNone(cursor, "two committed orders exist since class start")
        second = self.request(
            "work_orders", {"site": fx.SITE_A1, "cursor": cursor, "page_size": "1"}, user=fx.USER_A1
        )
        self.assertEqual(second.status_code, 200, second.json)
        self.assertNotEqual(
            first.json["message"]["items"][0]["name"], second.json["message"]["items"][0]["name"]
        )

    def test_guest_requests_are_forbidden(self):
        for method, params in (
            ("capabilities", {}),
            ("work_orders", {"site": fx.SITE_A1}),
            ("work_order", {"site": fx.SITE_A1, "name": self.a1}),
            ("work_order_deletions", {"site": fx.SITE_A1}),
        ):
            with self.subTest(method=method):
                response = self.request(method, params)
                self.assertEqual(response.status_code, 403)
                self.assertNotIn("message", response.json)
        self.capture("error_guest_forbidden", self.request("work_orders", {"site": fx.SITE_A1}))

    def test_bad_secret_is_unauthorized(self):
        response = self.request(
            "work_orders", {"site": fx.SITE_A1}, user=fx.USER_A1, secret="incorrect-secret"
        )
        self.assertEqual(response.status_code, 401)
        self.capture("error_bad_credentials", response)

    def test_users_without_role_or_principal_are_forbidden(self):
        for user in (fx.USER_PLAIN, fx.USER_NO_RECORD):
            with self.subTest(user=user):
                response = self.request("work_orders", {"site": fx.SITE_A1}, user=user)
                self.assertEqual(response.status_code, 403)
                self.assertEqual(response.json["exc_type"], "PermissionError")

    def test_unauthorized_site_is_forbidden_and_foreign_order_is_not_found(self):
        site = self.request("work_orders", {"site": fx.SITE_B1}, user=fx.USER_A1)
        self.assertEqual(site.status_code, 403)
        self.capture("error_site_forbidden", site)
        foreign = self.request("work_order", {"site": fx.SITE_A1, "name": self.b1}, user=fx.USER_A1)
        missing = self.request(
            "work_order", {"site": fx.SITE_A1, "name": "MFG-WO-NOPE"}, user=fx.USER_A1
        )
        self.assertEqual(foreign.status_code, 404)
        self.assertEqual(missing.status_code, 404)
        self.assertEqual(foreign.json.get("exc_type"), missing.json.get("exc_type"))
        self.capture("error_order_not_found", foreign)

    def test_multi_site_principal_reads_its_other_company(self):
        detail = self.request(
            "work_order", {"site": fx.SITE_B1, "name": self.b1}, user=fx.USER_MULTI
        )
        self.assertEqual(detail.status_code, 200, detail.json)
        self.assertEqual(detail.json["message"]["work_order"]["company"], fx.BETA.name)

    def test_post_is_rejected(self):
        response = self.request("work_orders", {"site": fx.SITE_A1}, user=fx.USER_A1, http="POST")
        self.assertEqual(response.status_code, 403)
        self.capture("error_method_not_allowed", response)

    def test_invalid_page_size_is_a_validation_error(self):
        response = self.request(
            "work_orders", {"site": fx.SITE_A1, "page_size": "201"}, user=fx.USER_A1
        )
        self.assertEqual(response.status_code, 417)
        self.capture("error_invalid_page_size", response)

    def test_http_parameters_cannot_expand_scope(self):
        response = self.request(
            "work_orders",
            {
                "site": fx.SITE_A1,
                "modified_since": self.since,
                "page_size": "200",
                "company": fx.BETA.name,
                "filters": json.dumps({"company": fx.BETA.name}),
                "user": fx.USER_MULTI,
            },
            user=fx.USER_A1,
        )
        self.assertEqual(response.status_code, 200, response.json)
        companies = {item["company"] for item in response.json["message"]["items"]}
        self.assertEqual(companies, {fx.ALPHA.name})

    def test_generic_routes_are_closed_to_principals(self):
        """Only the four v1 read methods are reachable; oracles and other routes return 403."""
        work_order = "/api/resource/Work%20Order/"
        cases = {
            "resource list": ("/api/resource/Work%20Order", {"limit_page_length": "0"}),
            "in-scope resource document": (work_order + quote(self.a1), {}),
            "foreign resource document": (work_order + quote(self.b1), {}),
            "count": ("/api/method/frappe.client.get_count", {"doctype": "Work Order"}),
            "validate_link oracle": (
                "/api/method/frappe.client.validate_link",
                {"doctype": "Work Order", "docname": self.b1},
            ),
            "get by filters oracle": (
                "/api/method/frappe.client.get",
                {"doctype": "Work Order", "filters": json.dumps({"company": fx.BETA.name})},
            ),
            "child table list": (
                "/api/method/frappe.client.get_list",
                {"doctype": "Work Order Item", "parent": "Work Order"},
            ),
            "v2 route": (
                "/api/v2/method/neuradix_manufacturing_erpnext.api.v1.work_orders",
                {"site": fx.SITE_A1},
            ),
            "cmd smuggling": (
                API + "work_orders",
                {"site": fx.SITE_A1, "cmd": "frappe.client.get_list"},
            ),
            "bom": ("/api/resource/BOM", {}),
        }
        for label, (path, params) in cases.items():
            with self.subTest(route=label):
                response = self.request(None, params, user=fx.USER_A1, path=path)
                self.assertEqual(response.status_code, 403, (label, response.status_code))
        self.capture(
            "error_generic_route_forbidden",
            self.request(None, {}, user=fx.USER_A1, path=work_order + quote(self.a1)),
        )

    def test_other_users_keep_their_generic_routes(self):
        response = self.request(
            None,
            {"limit_page_length": "0"},
            user=fx.USER_MFG,
            path="/api/resource/Work%20Order",
        )
        self.assertEqual(response.status_code, 200, response.json)
        names = [row["name"] for row in response.json["data"]]
        self.assertIn(self.a1, names)
        self.assertIn(self.b1, names)
