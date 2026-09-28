"""Fast capability checks. They do not replace the real Frappe site tests."""

import unittest

from neuradix_manufacturing_erpnext.capabilities import describe_capabilities

WRITE_OPERATIONS = ("post_stock", "post_production", "maintenance_sync", "discover_command_outcome")


class CapabilityTests(unittest.TestCase):
    def test_only_scoped_reads_are_available(self):
        result = describe_capabilities()
        self.assertEqual(result["maturity"], "development")
        self.assertTrue(result["operations"]["read_work_orders"])
        self.assertEqual(set(result["operations"]), {"read_work_orders", *WRITE_OPERATIONS})
        self.assertFalse(any(result["operations"][name] for name in WRITE_OPERATIONS))

    def test_result_is_not_shared_mutable_state(self):
        result = describe_capabilities()
        result["operations"]["post_stock"] = True
        result["sync"]["order"].append("creation")
        fresh = describe_capabilities()
        self.assertFalse(fresh["operations"]["post_stock"])
        self.assertEqual(fresh["sync"]["order"], ["modified", "name"])

    def test_full_reconciliation_is_always_declared(self):
        sync = describe_capabilities()["sync"]
        self.assertTrue(sync["full_reconciliation_required"])
        self.assertGreaterEqual(sync["recommended_overlap_seconds"], 3600)


if __name__ == "__main__":
    unittest.main()
