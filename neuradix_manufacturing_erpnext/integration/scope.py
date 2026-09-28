"""Manufacturing site scope for Work Orders.

A Manufacturing site is one physical production location served by a Neuradix Manufacturing
deployment. It is not a Frappe site (the ERP instance/database). In this contract version a
site maps to exactly one ERPNext Company and one warehouse subtree rooted at ``root_warehouse``.

A Work Order belongs to a site when all of these hold:

* its ``company`` is the site's Company;
* it is submitted or cancelled (drafts are never exposed);
* its Target Warehouse (``fg_warehouse``) is in the site's subtree; and
* its Work-In-Progress Warehouse is empty or also in the subtree.

Default source and scrap warehouses may be shared stores and do not decide membership. An order
whose warehouses span two sites belongs to neither (fail closed).
"""

from dataclasses import dataclass

import frappe

from neuradix_manufacturing_erpnext.integration.constants import EXPOSED_DOCSTATUS


@dataclass(frozen=True)
class Site:
    site_id: str
    company: str
    root_warehouse: str
    warehouses: frozenset

    def as_contract(self):
        return {
            "site_id": self.site_id,
            "company": self.company,
            "root_warehouse": self.root_warehouse,
        }


def load_site(site_id):
    """Return the enabled site with its current warehouse subtree, or None.

    Non-overlap is validated when a site is saved, but warehouses can be re-parented later.
    A site whose subtree now nests in or contains another site's subtree of the same Company is
    treated as unavailable (fail closed) until the mapping is repaired.
    """
    row = frappe.db.get_value(
        "Neuradix Manufacturing Site",
        site_id,
        ["name", "site_id", "company", "root_warehouse", "enabled"],
        as_dict=True,
    )
    if not row or not row.enabled or overlaps_another_site(row):
        return None
    return Site(
        site_id=row.site_id,
        company=row.company,
        root_warehouse=row.root_warehouse,
        warehouses=frozenset(warehouse_subtree(row.root_warehouse, row.company)),
    )


def overlaps_another_site(row):
    bounds = frappe.db.get_value("Warehouse", row.root_warehouse, ["lft", "rgt"], as_dict=True)
    if not bounds:
        return True
    others = frappe.get_all(
        "Neuradix Manufacturing Site",
        filters={"company": row.company, "name": ["!=", row.name]},
        pluck="root_warehouse",
    )
    for other in others:
        other_bounds = frappe.db.get_value("Warehouse", other, ["lft", "rgt"], as_dict=True)
        if other_bounds and nested(bounds, other_bounds):
            return True
    return False


def nested(a, b):
    """True when one nested-set interval contains the other."""
    return (a.lft <= b.lft and b.rgt <= a.rgt) or (b.lft <= a.lft and a.rgt <= b.rgt)


def warehouse_subtree(root_warehouse, company):
    bounds = frappe.db.get_value(
        "Warehouse", root_warehouse, ["lft", "rgt", "company"], as_dict=True
    )
    if not bounds or bounds.company != company:
        return []
    return frappe.get_all(
        "Warehouse",
        filters={"lft": [">=", bounds.lft], "rgt": ["<=", bounds.rgt], "company": company},
        pluck="name",
    )


def contains(site, work_order):
    """Membership test on a Work Order document or row (attribute or key access)."""

    def field(name):
        if isinstance(work_order, dict):
            return work_order.get(name)
        return getattr(work_order, name, None)

    try:
        docstatus = int(field("docstatus") or 0)
    except (TypeError, ValueError):
        return False
    wip = field("wip_warehouse")
    return (
        bool(site.warehouses)
        and field("company") == site.company
        and docstatus in EXPOSED_DOCSTATUS
        and field("fg_warehouse") in site.warehouses
        and (not wip or wip in site.warehouses)
    )


def list_filters(site):
    """Frappe filters equivalent to :func:`contains`; ``''`` lets Frappe coalesce empty WIP."""
    warehouses = sorted(site.warehouses)
    return [
        ["company", "=", site.company],
        ["docstatus", "in", list(EXPOSED_DOCSTATUS)],
        ["fg_warehouse", "in", warehouses],
        ["wip_warehouse", "in", [*warehouses, ""]],
    ]


def sql_condition(sites):
    """SQL predicate on `tabWork Order` for permission_query_conditions (fail closed)."""
    clauses = []
    for site in sorted(sites, key=lambda item: item.site_id):
        if not site.warehouses:
            continue
        # DatabaseQuery runs this SQL without bind values, so '%' must not be doubled.
        values = ", ".join(
            frappe.db.escape(name, percent=False) for name in sorted(site.warehouses)
        )
        docstatus = ", ".join(str(value) for value in EXPOSED_DOCSTATUS)
        clauses.append(
            "(`tabWork Order`.`company` = {company}"
            " and `tabWork Order`.`docstatus` in ({docstatus})"
            " and `tabWork Order`.`fg_warehouse` in ({values})"
            " and (ifnull(`tabWork Order`.`wip_warehouse`, '') = ''"
            " or `tabWork Order`.`wip_warehouse` in ({values})))".format(
                company=frappe.db.escape(site.company, percent=False),
                docstatus=docstatus,
                values=values,
            )
        )
    if not clauses:
        return "(1 = 0)"
    return "(" + " or ".join(clauses) + ")"
