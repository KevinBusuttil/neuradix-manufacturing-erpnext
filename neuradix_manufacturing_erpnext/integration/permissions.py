"""Frappe permission hooks that confine integration principals everywhere, not only in our API.

The Neuradix Integration Reader role grants read on Work Order through a Custom DocPerm. These
hooks narrow that grant for users holding the role, so generic routes (``/api/resource``,
``frappe.client``, report view, counts, link search and attachments) expose only submitted or
cancelled Work Orders of the principal's enabled sites. Controller hooks can only deny.

Frappe document sharing can still re-grant a shared document; the companion endpoints apply
explicit site filters and never return a shared record outside the site scope.
"""

import frappe

from neuradix_manufacturing_erpnext.integration import identity, scope

READ_PTYPES = ("read", "select")


def work_order_query_conditions(user=None, doctype=None):
    user = user or frappe.session.user
    if not identity.holds_integration_role(user):
        return ""
    try:
        principal = identity.resolve_principal(user)
    except frappe.PermissionError:
        return "(1 = 0)"
    return scope.sql_condition(principal.sites.values())


def work_order_has_permission(doc, ptype=None, user=None, debug=False):
    user = user or frappe.session.user
    if not identity.holds_integration_role(user):
        return None
    if ptype not in READ_PTYPES:
        return False
    try:
        principal = identity.resolve_principal(user)
    except frappe.PermissionError:
        return False
    if any(scope.contains(site, doc) for site in principal.sites.values()):
        return None  # no objection; role DocPerms still decide (hooks can only deny)
    return False


def work_order_child_query_conditions(user=None, doctype=None):
    """Required-item and operation rows are visible only under an in-scope Work Order."""
    user = user or frappe.session.user
    if not identity.holds_integration_role(user) or doctype is None:
        return ""
    try:
        principal = identity.resolve_principal(user)
    except frappe.PermissionError:
        return "(1 = 0)"
    table = f"`tab{doctype}`"
    return (
        f"({table}.`parenttype` = 'Work Order' and {table}.`parent` in "
        f"(select `tabWork Order`.`name` from `tabWork Order` where "
        f"{scope.sql_condition(principal.sites.values())}))"
    )
