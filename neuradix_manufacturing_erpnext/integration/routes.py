"""HTTP routes an integration principal may use. Dependency-free for fast tests."""

READ_METHODS = ("capabilities", "work_orders", "work_order", "work_order_deletions")
METHOD_MODULE = "neuradix_manufacturing_erpnext.api.v1."
ROUTE_PREFIXES = ("/api/method/", "/api/v1/method/")
ALLOWED_PATHS = frozenset(
    prefix + METHOD_MODULE + method for prefix in ROUTE_PREFIXES for method in READ_METHODS
)


def is_allowed_request(method, path, form_dict):
    # Frappe dispatches a `cmd` form value before path routing, so it must be absent.
    return method == "GET" and path in ALLOWED_PATHS and not (form_dict or {}).get("cmd")
