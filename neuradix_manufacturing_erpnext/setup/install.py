"""Install-time configuration for the least-privilege integration role.

Frappe cannot add a standard DocPerm to ERPNext's Work Order from another app, so the role's
read right is a Custom DocPerm. Adding the first Custom DocPerm copies Work Order's standard
permissions into Custom DocPerm (Frappe's normal Role Permission Manager behaviour); later
standard permission changes from ERPNext upgrades then need review on this site.
"""

import frappe
import frappe.permissions
from frappe.permissions import add_permission, rights

from neuradix_manufacturing_erpnext.integration.constants import INTEGRATION_ROLE

WORK_ORDER = "Work Order"
GRANTED_RIGHTS = frozenset({"read"})


def after_install():
    ensure_integration_access()


def after_migrate():
    ensure_integration_access()


def before_uninstall():
    remove_integration_access()


def ensure_integration_access():
    ensure_role()
    ensure_work_order_read()


def ensure_role():
    if frappe.db.exists("Role", INTEGRATION_ROLE):
        role = frappe.get_doc("Role", INTEGRATION_ROLE)
        changed = False
        for fieldname, value in (("desk_access", 0), ("disabled", 0)):
            if role.get(fieldname) != value:
                role.set(fieldname, value)
                changed = True
        if changed:
            role.save(ignore_permissions=True)
        return
    frappe.get_doc(
        {
            "doctype": "Role",
            "role_name": INTEGRATION_ROLE,
            "desk_access": 0,
            "description": "Neuradix Manufacturing read-only integration principal. "
            "Grants Work Order read only; scope is limited by Neuradix Integration Principal.",
        }
    ).insert(ignore_permissions=True)


def ensure_work_order_read():
    """Exactly one Custom DocPerm row at permlevel 0 granting read and nothing else."""
    rows = frappe.get_all(
        "Custom DocPerm",
        filters={"parent": WORK_ORDER, "role": INTEGRATION_ROLE},
        pluck="name",
    )
    if not rows:
        add_permission(WORK_ORDER, INTEGRATION_ROLE, 0)
        rows = frappe.get_all(
            "Custom DocPerm",
            filters={"parent": WORK_ORDER, "role": INTEGRATION_ROLE},
            pluck="name",
        )
    keep, extra = rows[0], rows[1:]
    for name in extra:
        frappe.delete_doc("Custom DocPerm", name, ignore_permissions=True, force=True)
    values = {right: int(right in GRANTED_RIGHTS) for right in rights}
    values.update(permlevel=0, if_owner=0)
    frappe.db.set_value("Custom DocPerm", keep, values)
    frappe.clear_cache(doctype=WORK_ORDER)


def remove_integration_access():
    for name in frappe.get_all(
        "Custom DocPerm", filters={"parent": WORK_ORDER, "role": INTEGRATION_ROLE}, pluck="name"
    ):
        frappe.delete_doc("Custom DocPerm", name, ignore_permissions=True, force=True)
    if only_standard_copies_remain():
        # Installing copied Work Order's standard rows into Custom DocPerm; nobody changed them
        # since, so return the doctype to its standard permissions.
        frappe.permissions.reset_perms(WORK_ORDER)
    if frappe.db.exists("Role", INTEGRATION_ROLE):
        # Keep the role record for audit history and existing assignments, but make it inert.
        frappe.db.set_value("Role", INTEGRATION_ROLE, "disabled", 1)
    frappe.clear_cache(doctype=WORK_ORDER)


def _permission_rows(doctype_table):
    fields = ["role", "permlevel", "if_owner", *rights]
    rows = frappe.get_all(doctype_table, filters={"parent": WORK_ORDER}, fields=fields)
    return sorted(tuple(int(row[f]) if f != "role" else row[f] for f in fields) for row in rows)


def only_standard_copies_remain():
    custom = _permission_rows("Custom DocPerm")
    return bool(custom) and custom == _permission_rows("DocPerm")
