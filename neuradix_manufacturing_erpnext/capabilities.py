"""Capability description shared by the endpoint and dependency-free tests."""


def describe_capabilities():
    return {
        "contract_version": "0.1.0-draft",
        "maturity": "scaffold",
        "target_erpnext_major": 15,
        "operations": {
            "read_work_orders": False,
            "post_stock": False,
            "post_production": False,
            "maintenance_sync": False,
            "discover_command_outcome": False,
        },
    }
