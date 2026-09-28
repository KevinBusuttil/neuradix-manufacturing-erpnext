"""Capability description shared by the endpoint and dependency-free tests."""

from neuradix_manufacturing_erpnext.integration.constants import (
    CONTRACT_VERSION,
    PAGE_SIZE_DEFAULT,
    PAGE_SIZE_MAX,
    RECOMMENDED_OVERLAP_SECONDS,
    SCHEMA_CAPABILITIES,
    SCHEMA_WORK_ORDER_DELETION_PAGE,
    SCHEMA_WORK_ORDER_DETAIL,
    SCHEMA_WORK_ORDER_PAGE,
)


def describe_capabilities(principal=None, instance="", erp_time_zone=""):
    """Only scoped Work Order reads exist. Every write, posting and outcome operation is off."""
    return {
        "schema": SCHEMA_CAPABILITIES,
        "contract_version": CONTRACT_VERSION,
        "maturity": "development",
        "target_erpnext_major": 15,
        "operations": {
            "read_work_orders": True,
            "post_stock": False,
            "post_production": False,
            "maintenance_sync": False,
            "discover_command_outcome": False,
        },
        "read_contracts": {
            "work_order_page": SCHEMA_WORK_ORDER_PAGE,
            "work_order_detail": SCHEMA_WORK_ORDER_DETAIL,
            "work_order_deletion_page": SCHEMA_WORK_ORDER_DELETION_PAGE,
        },
        "limits": {"page_size_default": PAGE_SIZE_DEFAULT, "page_size_max": PAGE_SIZE_MAX},
        "sync": {
            "order": ["modified", "name"],
            "lifecycles": ["submitted", "cancelled"],
            "recommended_overlap_seconds": RECOMMENDED_OVERLAP_SECONDS,
            "full_reconciliation_required": True,
        },
        "principal": principal,
        "source": {"system": "erpnext", "instance": instance, "erp_time_zone": erp_time_zone},
    }
