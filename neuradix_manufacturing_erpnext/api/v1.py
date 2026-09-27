"""Initial metadata endpoint. No stock, production or equipment mutations exist."""

import frappe

from neuradix_manufacturing_erpnext.capabilities import describe_capabilities


@frappe.whitelist(methods=["GET"])
def capabilities():
    """Return declared maturity only to authenticated administrators during bootstrap.

    A dedicated scoped integration principal is introduced in EN-01 before any data API.
    Do not use an administrator token for the eventual production connector.
    """
    if frappe.session.user == "Guest":
        frappe.throw("Authentication required", frappe.PermissionError)
    frappe.only_for("System Manager")
    return describe_capabilities()
