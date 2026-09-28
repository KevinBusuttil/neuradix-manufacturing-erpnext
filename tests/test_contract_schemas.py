"""The published schemas are generated, valid, and accept the observed real-site examples."""

import copy
import json
import subprocess
import sys
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[1]
CONTRACTS = ROOT / "neuradix_manufacturing_erpnext" / "contracts"
EXAMPLES = {
    "capabilities.json": "neuradix.erpnext.capabilities.v1",
    "work_order_page.json": "neuradix.erpnext.work_order_page.v1",
    "work_order_detail.json": "neuradix.erpnext.work_order_detail.v1",
    "work_order_deletion_page.json": "neuradix.erpnext.work_order_deletion_page.v1",
}


def validator(schema_id):
    schema = json.loads((CONTRACTS / f"{schema_id}.schema.json").read_text())
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema, format_checker=FormatChecker())


def example(name):
    return json.loads((CONTRACTS / "examples" / name).read_text())


class ContractSchemaTests(unittest.TestCase):
    def test_committed_schemas_are_current(self):
        result = subprocess.run(
            [sys.executable, str(ROOT / "tools" / "build_contract_schemas.py"), "--check"],
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_observed_examples_are_valid(self):
        for name, schema_id in EXAMPLES.items():
            with self.subTest(example=name):
                errors = list(validator(schema_id).iter_errors(example(name)))
                self.assertEqual([], [error.message for error in errors])

    def test_contract_rejects_lossy_or_ambiguous_values(self):
        page_validator = validator("neuradix.erpnext.work_order_page.v1")
        base = example("work_order_page.json")
        self.assertTrue(base["items"], "example page must contain orders")

        def mutated(change):
            payload = copy.deepcopy(base)
            change(payload["items"][0])
            return payload

        cases = {
            "float quantity": lambda item: item["quantities"].__setitem__("planned", 12.5),
            "exponent": lambda item: item["quantities"].__setitem__("planned", "1E+2"),
            "trailing zero": lambda item: item["quantities"].__setitem__("planned", "12.50"),
            "negative": lambda item: item["quantities"].__setitem__("planned", "-1"),
            "naive time": lambda item: item.__setitem__("modified_at", "2026-09-28T12:00:00"),
            "draft": lambda item: item.__setitem__("lifecycle", "draft"),
            "extra field": lambda item: item.__setitem__("valuation", "10"),
            "missing fg": lambda item: item["warehouses"].__setitem__("fg", None),
        }
        for label, change in cases.items():
            with self.subTest(case=label):
                self.assertTrue(list(page_validator.iter_errors(mutated(change))))

    def test_capabilities_never_enable_writes(self):
        caps_validator = validator("neuradix.erpnext.capabilities.v1")
        payload = example("capabilities.json")
        for operation in ("post_stock", "post_production", "maintenance_sync"):
            with self.subTest(operation=operation):
                enabled = copy.deepcopy(payload)
                enabled["operations"][operation] = True
                self.assertTrue(list(caps_validator.iter_errors(enabled)))


if __name__ == "__main__":
    unittest.main()
