"""Generate the published JSON Schemas for the companion read contract.

The schemas are committed under ``neuradix_manufacturing_erpnext/contracts`` and copied
verbatim into the Manufacturing repository. Run this script after changing a definition;
``tests/test_contract_schemas.py`` fails when the committed files are stale.

    python tools/build_contract_schemas.py          # rewrite the committed files
    python tools/build_contract_schemas.py --check  # exit 1 if they differ
"""

import argparse
import json
import sys
from pathlib import Path

CONTRACT_VERSION = "0.2.0-draft"
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "neuradix_manufacturing_erpnext" / "contracts"
BASE_ID = "https://github.com/KevinBusuttil/neuradix-manufacturing-erpnext/contracts/"

# Frappe stores Float fields as DECIMAL(21,9): at most 12 integer and 9 fraction digits.
# Values are serialized exactly, without exponent, sign on zero or trailing fraction zeros.
NON_NEGATIVE_DECIMAL = r"^(0|[1-9][0-9]{0,11})(\.[0-9]{0,8}[1-9])?$"
ERP_TIMESTAMP = (
    r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}\.[0-9]{6}[+-][0-9]{2}:[0-9]{2}$"
)
ERP_DATE = r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$"
VERSION = r"^[0-9]{4}-[0-9]{2}-[0-9]{2} [0-9]{2}:[0-9]{2}:[0-9]{2}\.[0-9]{6}$"
SITE_ID = r"^[A-Z0-9][A-Z0-9_-]{0,63}$"


def nullable(schema):
    return {"anyOf": [schema, {"type": "null"}]}


def obj(properties, required=None):
    return {
        "type": "object",
        "additionalProperties": False,
        "required": sorted(required if required is not None else properties),
        "properties": properties,
    }


DEFS = {
    "decimal": {
        "type": "string",
        "pattern": NON_NEGATIVE_DECIMAL,
        "description": "Exact non-negative decimal from a DECIMAL(21,9) column, as a string.",
    },
    "erp_timestamp": {
        "type": "string",
        "format": "date-time",
        "pattern": ERP_TIMESTAMP,
        "description": "ERP wall-clock time with the ERP system time zone offset (not site time).",
    },
    "erp_date": {"type": "string", "format": "date", "pattern": ERP_DATE},
    "doc_name": {"type": "string", "minLength": 1, "maxLength": 140},
    "version": {
        "type": "string",
        "pattern": VERSION,
        "description": "Change token: the exact stored ERP modification value. Fixed width, so "
        "string order equals stored order; compare for equality and ordering only.",
    },
    "cursor": {"type": "string", "minLength": 1, "maxLength": 1024},
    "source": obj(
        {
            "system": {"const": "erpnext"},
            "instance": {"type": "string", "minLength": 1, "maxLength": 255},
            "erp_time_zone": {"type": "string", "minLength": 1, "maxLength": 64},
        }
    ),
    "site": obj(
        {
            "site_id": {"type": "string", "pattern": SITE_ID},
            "company": {"$ref": "#/$defs/doc_name"},
            "root_warehouse": {"$ref": "#/$defs/doc_name"},
        }
    ),
    "work_order_quantities": obj(
        {
            key: {"$ref": "#/$defs/decimal"}
            for key in (
                "planned",
                "produced",
                "material_transferred",
                "process_loss",
                "disassembled",
            )
        }
    ),
    "work_order_summary": obj(
        {
            "name": {"$ref": "#/$defs/doc_name"},
            "version": {"$ref": "#/$defs/version"},
            "modified_at": {"$ref": "#/$defs/erp_timestamp"},
            "lifecycle": {"enum": ["submitted", "cancelled"]},
            "status": {
                "enum": [
                    "submitted",
                    "not_started",
                    "in_process",
                    "completed",
                    "stopped",
                    "closed",
                    "cancelled",
                    "unknown",
                ]
            },
            "erp_status": {"type": "string", "maxLength": 140},
            "company": {"$ref": "#/$defs/doc_name"},
            "production_item": obj(
                {
                    "item_code": {"$ref": "#/$defs/doc_name"},
                    "item_name": nullable({"type": "string"}),
                }
            ),
            "bom_no": {"$ref": "#/$defs/doc_name"},
            "stock_uom": nullable({"$ref": "#/$defs/doc_name"}),
            "quantities": {"$ref": "#/$defs/work_order_quantities"},
            "warehouses": obj(
                {
                    "wip": nullable({"$ref": "#/$defs/doc_name"}),
                    "fg": {"$ref": "#/$defs/doc_name"},
                    "source": nullable({"$ref": "#/$defs/doc_name"}),
                    "scrap": nullable({"$ref": "#/$defs/doc_name"}),
                }
            ),
            "planned_start_at": {"$ref": "#/$defs/erp_timestamp"},
            "planned_end_at": nullable({"$ref": "#/$defs/erp_timestamp"}),
            "actual_start_at": nullable({"$ref": "#/$defs/erp_timestamp"}),
            "actual_end_at": nullable({"$ref": "#/$defs/erp_timestamp"}),
            "expected_delivery_date": nullable({"$ref": "#/$defs/erp_date"}),
            "amended_from": nullable({"$ref": "#/$defs/doc_name"}),
            "references": obj(
                {
                    key: nullable({"$ref": "#/$defs/doc_name"})
                    for key in ("sales_order", "production_plan", "material_request", "project")
                }
            ),
        }
    ),
    "work_order_required_item": obj(
        {
            "row": {"type": "integer", "minimum": 1},
            "item_code": {"$ref": "#/$defs/doc_name"},
            "item_name": nullable({"type": "string"}),
            "operation": nullable({"$ref": "#/$defs/doc_name"}),
            "source_warehouse": nullable({"$ref": "#/$defs/doc_name"}),
            "stock_uom": nullable({"$ref": "#/$defs/doc_name"}),
            "include_item_in_manufacturing": {"type": "boolean"},
            "allow_alternative_item": {"type": "boolean"},
            "quantities": obj(
                {
                    key: {"$ref": "#/$defs/decimal"}
                    for key in ("required", "transferred", "consumed", "returned")
                }
            ),
        }
    ),
    "work_order_operation": obj(
        {
            "row": {"type": "integer", "minimum": 1},
            "sequence_id": nullable({"type": "integer"}),
            "operation": {"$ref": "#/$defs/doc_name"},
            "workstation": nullable({"$ref": "#/$defs/doc_name"}),
            "workstation_type": nullable({"$ref": "#/$defs/doc_name"}),
            "bom": nullable({"$ref": "#/$defs/doc_name"}),
            "status": {"enum": ["pending", "work_in_progress", "completed", "unknown"]},
            "erp_status": nullable({"type": "string", "maxLength": 140}),
            "quantities": obj(
                {key: {"$ref": "#/$defs/decimal"} for key in ("completed", "process_loss")}
            ),
            "planned_minutes": {"$ref": "#/$defs/decimal"},
            "planned_start_at": nullable({"$ref": "#/$defs/erp_timestamp"}),
            "planned_end_at": nullable({"$ref": "#/$defs/erp_timestamp"}),
            "actual_start_at": nullable({"$ref": "#/$defs/erp_timestamp"}),
            "actual_end_at": nullable({"$ref": "#/$defs/erp_timestamp"}),
        }
    ),
    "work_order_detail_extension": obj(
        {
            "use_multi_level_bom": {"type": "boolean"},
            "skip_transfer": {"type": "boolean"},
            "transfer_material_against": nullable({"enum": ["work_order", "job_card"]}),
            "has_serial_no": {"type": "boolean"},
            "has_batch_no": {"type": "boolean"},
            "required_items": {
                "type": "array",
                "items": {"$ref": "#/$defs/work_order_required_item"},
            },
            "operations": {"type": "array", "items": {"$ref": "#/$defs/work_order_operation"}},
        }
    ),
    "work_order_deletion": obj(
        {
            "name": {"$ref": "#/$defs/doc_name"},
            "deleted_at": {"$ref": "#/$defs/erp_timestamp"},
            "last_version": {"$ref": "#/$defs/version"},
            "last_lifecycle": {"enum": ["submitted", "cancelled"]},
        }
    ),
}


def envelope(schema_id, extra):
    properties = {
        "schema": {"const": schema_id},
        "contract_version": {"const": CONTRACT_VERSION},
        "source": {"$ref": "#/$defs/source"},
        "site": {"$ref": "#/$defs/site"},
        "generated_at": {"$ref": "#/$defs/erp_timestamp"},
        **extra,
    }
    return properties


def page(schema_id, item_ref):
    return envelope(
        schema_id,
        {
            "page_size": {"type": "integer", "minimum": 1, "maximum": 200},
            "items": {"type": "array", "maxItems": 200, "items": {"$ref": item_ref}},
            "next_cursor": nullable({"$ref": "#/$defs/cursor"}),
        },
    )


def detail_object():
    # A detail is the summary plus the extension; unevaluatedProperties closes the union.
    summary = DEFS["work_order_summary"]
    extension = DEFS["work_order_detail_extension"]
    return {
        "type": "object",
        "required": sorted(summary["required"] + extension["required"]),
        "properties": {**summary["properties"], **extension["properties"]},
        "additionalProperties": False,
    }


DEFS["work_order_detail"] = detail_object()


def capabilities():
    return {
        "schema": {"const": "neuradix.erpnext.capabilities.v1"},
        "contract_version": {"const": CONTRACT_VERSION},
        "maturity": {"enum": ["development"]},
        "target_erpnext_major": {"const": 15},
        "operations": obj(
            {
                "read_work_orders": {"const": True},
                "post_stock": {"const": False},
                "post_production": {"const": False},
                "maintenance_sync": {"const": False},
                "discover_command_outcome": {"const": False},
            }
        ),
        "read_contracts": obj(
            {
                "work_order_page": {"const": "neuradix.erpnext.work_order_page.v1"},
                "work_order_detail": {"const": "neuradix.erpnext.work_order_detail.v1"},
                "work_order_deletion_page": {
                    "const": "neuradix.erpnext.work_order_deletion_page.v1"
                },
            }
        ),
        "limits": obj(
            {
                "page_size_default": {"const": 50},
                "page_size_max": {"const": 200},
            }
        ),
        "sync": obj(
            {
                "order": {"const": ["modified", "name"]},
                "lifecycles": {"const": ["submitted", "cancelled"]},
                "recommended_overlap_seconds": {"type": "integer", "minimum": 0},
                "full_reconciliation_required": {"const": True},
            }
        ),
        "principal": nullable(
            obj(
                {
                    "user": {"type": "string", "minLength": 1},
                    "sites": {"type": "array", "items": {"$ref": "#/$defs/site"}},
                }
            )
        ),
        "source": {"$ref": "#/$defs/source"},
    }


def used_defs(root):
    """Return only the $defs reachable from ``root`` so each file stays self-contained."""
    seen = set()

    def walk(node):
        if isinstance(node, dict):
            ref = node.get("$ref")
            if isinstance(ref, str) and ref.startswith("#/$defs/"):
                key = ref.rsplit("/", 1)[1]
                if key not in seen:
                    seen.add(key)
                    walk(DEFS[key])
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)

    walk(root)
    return {key: DEFS[key] for key in sorted(seen)}


def document(schema_id, title, properties, description):
    body = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": BASE_ID + schema_id + ".schema.json",
        "title": title,
        "description": description,
        "type": "object",
        "additionalProperties": False,
        "required": sorted(properties),
        "properties": properties,
    }
    body["$defs"] = used_defs(body)
    return body


def build():
    page_id = "neuradix.erpnext.work_order_page.v1"
    detail_id = "neuradix.erpnext.work_order_detail.v1"
    deletion_id = "neuradix.erpnext.work_order_deletion_page.v1"
    detail_props = envelope(detail_id, {"work_order": {"$ref": "#/$defs/work_order_detail"}})
    documents = {
        page_id: document(
            page_id,
            "Scoped ERPNext Work Order page",
            page(page_id, "#/$defs/work_order_summary"),
            "Submitted and cancelled Work Orders of one Manufacturing site, ordered by "
            "(modified, name). Returned inside Frappe's `message` wrapper.",
        ),
        detail_id: document(
            detail_id,
            "Scoped ERPNext Work Order detail",
            detail_props,
            "One Work Order with its own required-item and operation rows. Linked BOM, Item "
            "and Warehouse records are referenced by name only.",
        ),
        deletion_id: document(
            deletion_id,
            "Scoped ERPNext Work Order deletion markers",
            page(deletion_id, "#/$defs/work_order_deletion"),
            "Best-effort deletion markers from Frappe's Deleted Document log. Periodic full "
            "reconciliation remains required.",
        ),
        "neuradix.erpnext.capabilities.v1": document(
            "neuradix.erpnext.capabilities.v1",
            "Companion capability profile",
            capabilities(),
            "Declared companion operations and read-contract identifiers.",
        ),
    }
    return {f"{key}.schema.json": value for key, value in documents.items()}


def render(value):
    return json.dumps(value, indent=2, sort_keys=False) + "\n"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    stale = []
    for filename, value in build().items():
        path = OUT / filename
        text = render(value)
        if args.check:
            if not path.exists() or path.read_text() != text:
                stale.append(filename)
        else:
            path.write_text(text)
    if stale:
        print("Stale contract schemas: " + ", ".join(stale), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
