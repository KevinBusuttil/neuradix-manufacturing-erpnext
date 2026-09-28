"""Fast checks of exact decimals, ERP time labelling, cursors and parameter bounds."""

import datetime as dt
import unittest
from decimal import Decimal
from zoneinfo import ZoneInfo

from neuradix_manufacturing_erpnext.integration import serialization as ser

NEW_YORK = ZoneInfo("America/New_York")


class DecimalTests(unittest.TestCase):
    def test_canonical_exact_strings(self):
        cases = {
            "0.000000000": "0",
            "12.500000000": "12.5",
            "100.000000000": "100",
            "0.000000001": "0.000000001",
            "123456789012.123456789": "123456789012.123456789",
            Decimal("28.125000000"): "28.125",
        }
        for raw, expected in cases.items():
            with self.subTest(raw=raw):
                self.assertEqual(ser.exact_decimal(raw), expected)

    def test_inexact_or_unsupported_values_are_rejected(self):
        for raw in (
            12.5,
            None,
            True,
            "1e3",
            "NaN",
            "-1.000000000",
            "1234567890123",
            "1.0000000001",
            "",
        ):
            with self.subTest(raw=raw), self.assertRaises(ser.ContractValueError):
                ser.exact_decimal(raw)


class TimeTests(unittest.TestCase):
    def test_erp_timestamp_carries_zone_offset_and_microseconds(self):
        summer = dt.datetime(2026, 9, 28, 12, 0, 0)
        winter = dt.datetime(2026, 12, 1, 12, 0, 0, 5)
        self.assertEqual(ser.erp_timestamp(summer, NEW_YORK), "2026-09-28T12:00:00.000000-04:00")
        self.assertEqual(ser.erp_timestamp(winter, NEW_YORK), "2026-12-01T12:00:00.000005-05:00")
        self.assertIsNone(ser.erp_timestamp(None, NEW_YORK))

    def test_repeated_fall_back_hour_uses_first_occurrence(self):
        ambiguous = dt.datetime(2026, 11, 1, 1, 30)
        self.assertEqual(ser.erp_timestamp(ambiguous, NEW_YORK), "2026-11-01T01:30:00.000000-04:00")

    def test_since_requires_offset_and_converts_to_erp_wall_clock(self):
        self.assertEqual(
            ser.parse_since("2026-09-28T16:00:00Z", NEW_YORK), dt.datetime(2026, 9, 28, 12, 0)
        )
        self.assertEqual(
            ser.parse_since("2026-09-28T18:00:00.000001+02:00", NEW_YORK),
            dt.datetime(2026, 9, 28, 12, 0, 0, 1),
        )
        for bad in ("2026-09-28T12:00:00", "2026-09-28", "yesterday", 5, "x" * 65):
            with self.subTest(value=bad), self.assertRaises(ser.ContractValueError):
                ser.parse_since(bad, NEW_YORK)

    def test_dates_stay_dates(self):
        self.assertEqual(ser.erp_date(dt.date(2026, 9, 30)), "2026-09-30")
        with self.assertRaises(ser.ContractValueError):
            ser.erp_date(dt.datetime(2026, 9, 30, 1, 0))

    def test_version_is_exact_stored_value(self):
        self.assertEqual(
            ser.erp_version(dt.datetime(2026, 9, 28, 12, 0, 0, 7)), "2026-09-28 12:00:00.000007"
        )


class CursorAndPageTests(unittest.TestCase):
    def test_cursor_round_trip_is_bound_to_method_and_site(self):
        token = ser.encode_cursor("work_orders", "NXT-A1", "2026-09-28 12:00:00.000007", "WO-1")
        position, name = ser.decode_cursor(token, "work_orders", "NXT-A1")
        self.assertEqual(position, dt.datetime(2026, 9, 28, 12, 0, 0, 7))
        self.assertEqual(name, "WO-1")
        for kind, site in (("work_order_deletions", "NXT-A1"), ("work_orders", "NXT-B1")):
            with self.subTest(kind=kind, site=site), self.assertRaises(ser.ContractValueError):
                ser.decode_cursor(token, kind, site)

    def test_malformed_cursors_are_rejected(self):
        for token in ("", "!!!", "e30", "a" * 1025, None, 7):
            with self.subTest(token=token), self.assertRaises(ser.ContractValueError):
                ser.decode_cursor(token, "work_orders", "NXT-A1")

    def test_page_size_bounds(self):
        self.assertEqual(ser.page_size(None), 50)
        self.assertEqual(ser.page_size("200"), 200)
        self.assertEqual(ser.page_size(1), 1)
        for bad in (0, 201, "0", "-1", "1.5", "abc", True, 2.0, "٣"):
            with self.subTest(value=bad), self.assertRaises(ser.ContractValueError):
                ser.page_size(bad)


class StatusTests(unittest.TestCase):
    def test_status_mapping_keeps_unknown_values_explicit(self):
        self.assertEqual(ser.work_order_status("In Process"), "in_process")
        self.assertEqual(ser.work_order_status("Something New"), "unknown")
        self.assertEqual(ser.operation_status("Work in Progress"), "work_in_progress")
        self.assertEqual(ser.lifecycle(2), "cancelled")
        with self.assertRaises(ser.ContractValueError):
            ser.lifecycle(0)


class AuthAllowlistTests(unittest.TestCase):
    def test_only_plain_gets_to_the_read_methods_are_allowed(self):
        from neuradix_manufacturing_erpnext.integration.routes import is_allowed_request

        ok = "/api/method/neuradix_manufacturing_erpnext.api.v1.work_orders"
        self.assertTrue(is_allowed_request("GET", ok, {}))
        self.assertTrue(is_allowed_request("GET", ok.replace("/api/", "/api/v1/"), {}))
        refused = [
            ("POST", ok, {}),
            ("HEAD", ok, {}),
            ("GET", ok, {"cmd": "frappe.client.get_list"}),
            ("GET", ok + "/", {}),
            ("GET", "/api/v2/method/neuradix_manufacturing_erpnext.api.v1.work_orders", {}),
            ("GET", "/api/resource/Work Order", {}),
            ("GET", "/api/method/frappe.client.validate_link", {}),
            ("GET", "/api/method/neuradix_manufacturing_erpnext.api.v1.describe", {}),
        ]
        for method, path, form in refused:
            with self.subTest(method=method, path=path, form=form):
                self.assertFalse(is_allowed_request(method, path, form))


if __name__ == "__main__":
    unittest.main()
