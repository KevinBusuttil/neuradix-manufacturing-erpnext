"""Fast capability and authorization checks; these do not replace a real Frappe site test."""

import importlib
import sys
import types
import unittest
from unittest.mock import patch

from neuradix_manufacturing_erpnext.capabilities import describe_capabilities


class CapabilityTests(unittest.TestCase):
    def test_every_business_operation_is_unavailable(self):
        result = describe_capabilities()
        self.assertEqual(result["maturity"], "scaffold")
        self.assertTrue(result["operations"])
        self.assertFalse(any(result["operations"].values()))

    def test_result_is_not_shared_mutable_state(self):
        result = describe_capabilities()
        result["operations"]["post_stock"] = True
        self.assertFalse(describe_capabilities()["operations"]["post_stock"])

    def test_endpoint_requires_identity_and_role(self):
        fake = types.ModuleType("frappe")
        fake.session = types.SimpleNamespace(user="Guest")
        fake.PermissionError = PermissionError
        fake.whitelist = lambda **kwargs: lambda fn: fn

        def throw(message, exception):
            raise exception(message)

        def only_for(role):
            self.assertEqual(role, "System Manager")
            if fake.session.user != "bootstrap-admin":
                raise PermissionError("Missing role")

        fake.throw = throw
        fake.only_for = only_for
        module = "neuradix_manufacturing_erpnext.api.v1"
        with patch.dict(sys.modules, {"frappe": fake}):
            sys.modules.pop(module, None)
            api = importlib.import_module(module)
            try:
                with self.assertRaises(PermissionError):
                    api.capabilities()
                fake.session.user = "ordinary-user"
                with self.assertRaises(PermissionError):
                    api.capabilities()
                fake.session.user = "bootstrap-admin"
                self.assertEqual(api.capabilities()["maturity"], "scaffold")
            finally:
                sys.modules.pop(module, None)
