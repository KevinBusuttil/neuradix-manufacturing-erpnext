"""Versioned, read-only integration methods. No stock, production or equipment mutations exist.

Every method is GET-only and denies Guest. Business reads require an active integration
principal (a dedicated user holding only the Neuradix Integration Reader role, bound to
Manufacturing sites by a Neuradix Integration Principal record). Administrator and System
Manager may read bootstrap capability metadata but are not integration principals.
"""

import frappe

from neuradix_manufacturing_erpnext.capabilities import describe_capabilities
from neuradix_manufacturing_erpnext.integration import identity
from neuradix_manufacturing_erpnext.integration import work_orders as reads


def _authenticated_user():
    user = frappe.session.user
    if not user or user == "Guest":
        identity.deny()
    return user


@frappe.whitelist(methods=["GET"])
def capabilities():
    """Declared companion capabilities, plus the caller's scope when it is a principal."""
    user = _authenticated_user()
    if identity.is_bootstrap_administrator(user):
        principal = None
    else:
        principal = identity.resolve_principal(user).as_contract()
    return describe_capabilities(
        principal=principal,
        instance=frappe.local.site,
        erp_time_zone=frappe.utils.get_system_timezone(),
    )


@frappe.whitelist(methods=["GET"])
def work_orders(site=None, cursor=None, modified_since=None, page_size=None):
    """One page of submitted and cancelled Work Orders for an authorized site."""
    _authenticated_user()
    authorized = identity.resolve_principal().site(site)
    return reads.list_work_orders(
        authorized, cursor=cursor, modified_since=modified_since, page_size=page_size
    )


@frappe.whitelist(methods=["GET"])
def work_order(site=None, name=None):
    """One Work Order in an authorized site; out-of-scope and missing orders look identical."""
    _authenticated_user()
    authorized = identity.resolve_principal().site(site)
    return reads.get_work_order(authorized, name)


@frappe.whitelist(methods=["GET"])
def work_order_deletions(site=None, cursor=None, deleted_since=None, page_size=None):
    """Best-effort deletion markers for Work Orders previously in the site's scope."""
    _authenticated_user()
    authorized = identity.resolve_principal().site(site)
    return reads.list_deletions(
        authorized, cursor=cursor, deleted_since=deleted_since, page_size=page_size
    )
