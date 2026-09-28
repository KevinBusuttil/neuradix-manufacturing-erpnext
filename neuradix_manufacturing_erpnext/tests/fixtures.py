"""Synthetic, idempotent ERPNext fixtures for real-site EN-01 tests.

Two companies and three Manufacturing sites with distinct scopes. All names are fictitious test
data; nothing here is customer configuration. Base fixtures are committed because HTTP tests run
in a separate request thread and database connection that cannot see uncommitted rows.
"""

from dataclasses import dataclass

import frappe
from frappe.utils import add_to_date, flt, now_datetime

from neuradix_manufacturing_erpnext.integration.constants import (
    INTEGRATION_ROLE,
    PRINCIPAL_DOCTYPE,
    SITE_DOCTYPE,
)

UOM = "Kg"
FG_ITEM = "NX-TEST-FG-01"
RM_ITEM = "NX-TEST-RM-01"
RM_ITEM_2 = "NX-TEST-RM-02"
OPERATION = "NX Test Blending"
WORKSTATION = "NX Test Blender"


@dataclass(frozen=True)
class CompanyFixture:
    name: str
    abbr: str

    def warehouse(self, label):
        return f"{label} - {self.abbr}"


ALPHA = CompanyFixture("NX Test Alpha Manufacturing Ltd", "NXA")
BETA = CompanyFixture("NX Test Beta Manufacturing Ltd", "NXB")

SITE_A1 = "NXT-A1"
SITE_A2 = "NXT-A2"
SITE_B1 = "NXT-B1"
SITES = {
    SITE_A1: (ALPHA, "Plant A1"),
    SITE_A2: (ALPHA, "Plant A2"),
    SITE_B1: (BETA, "Plant B1"),
}

USER_A1 = "nx-int-a1@example.test"  # principal for NXT-A1 only
USER_MULTI = "nx-int-multi@example.test"  # principal for NXT-A2 and NXT-B1
USER_NO_RECORD = "nx-int-norecord@example.test"  # role but no principal record
USER_DISABLED = "nx-int-disabled@example.test"  # role and a disabled principal
USER_PLAIN = "nx-plain@example.test"  # authenticated, no roles
USER_MFG = "nx-mfg-user@example.test"  # ERPNext Manufacturing User, not an integration principal
FIXTURE_USERS = (USER_A1, USER_MULTI, USER_NO_RECORD, USER_DISABLED, USER_PLAIN, USER_MFG)

WIP = "WIP"
FG = "FG"


def site_warehouse(site_id, kind):
    company, plant = SITES[site_id]
    return company.warehouse(f"{plant} {kind}")


def ensure_base_fixtures():
    """Create (or reuse) every shared fixture and commit. Safe to call from any test class."""
    ensure_uom(UOM)
    # Committed HTTP-test orders keep open Job Cards; without this, ERPNext capacity planning
    # eventually refuses new orders on a reused disposable site (CapacityError).
    frappe.db.set_single_value("Manufacturing Settings", "disable_capacity_planning", 1)
    for company in (ALPHA, BETA):
        ensure_company(company)
    for site_id, (company, plant) in SITES.items():
        root = ensure_warehouse(company, plant, company.warehouse("All Warehouses"), is_group=1)
        ensure_warehouse(company, f"{plant} {WIP}", root)
        ensure_warehouse(company, f"{plant} {FG}", root)
        ensure_site(site_id, company, root)
    ensure_item(FG_ITEM, "NX Test Finished Blend")
    ensure_item(RM_ITEM, "NX Test Base Powder")
    ensure_item(RM_ITEM_2, "NX Test Additive")
    ensure_operation()
    ensure_bom(ALPHA, [(RM_ITEM, "2.25")], with_operation=True)
    ensure_bom(ALPHA, [(RM_ITEM, "2.25"), (RM_ITEM_2, "0.125")], index=2, default=False)
    ensure_bom(BETA, [(RM_ITEM, "3")])
    ensure_user(USER_A1, [INTEGRATION_ROLE])
    ensure_user(USER_MULTI, [INTEGRATION_ROLE])
    ensure_user(USER_NO_RECORD, [INTEGRATION_ROLE])
    ensure_user(USER_DISABLED, [INTEGRATION_ROLE])
    ensure_user(USER_PLAIN, [])
    ensure_user(USER_MFG, ["Manufacturing User"])
    ensure_principal(USER_A1, [SITE_A1])
    ensure_principal(USER_MULTI, [SITE_A2, SITE_B1])
    ensure_principal(USER_DISABLED, [SITE_A1], enabled=0)
    frappe.db.commit()
    for user in FIXTURE_USERS:
        frappe.clear_cache(user=user)


def ensure_uom(name):
    if not frappe.db.exists("UOM", name):
        frappe.get_doc({"doctype": "UOM", "uom_name": name, "must_be_whole_number": 0}).insert()
    else:
        frappe.db.set_value("UOM", name, "must_be_whole_number", 0)


def ensure_company(company):
    if frappe.db.exists("Company", company.name):
        return
    frappe.get_doc(
        {
            "doctype": "Company",
            "company_name": company.name,
            "abbr": company.abbr,
            "default_currency": "USD",
            "country": "United States",
            "create_chart_of_accounts_based_on": "Standard Template",
            "chart_of_accounts": "Standard",
        }
    ).insert()


def ensure_warehouse(company, label, parent, is_group=0):
    name = company.warehouse(label)
    if not frappe.db.exists("Warehouse", name):
        frappe.get_doc(
            {
                "doctype": "Warehouse",
                "warehouse_name": label,
                "company": company.name,
                "parent_warehouse": parent,
                "is_group": is_group,
            }
        ).insert()
    return name


def ensure_site(site_id, company, root):
    if frappe.db.exists(SITE_DOCTYPE, site_id):
        return
    frappe.get_doc(
        {
            "doctype": SITE_DOCTYPE,
            "site_id": site_id,
            "site_name": f"Synthetic {site_id}",
            "company": company.name,
            "root_warehouse": root,
        }
    ).insert()


def ensure_item(code, item_name):
    if frappe.db.exists("Item", code):
        return
    group = "Products" if frappe.db.exists("Item Group", "Products") else "All Item Groups"
    frappe.get_doc(
        {
            "doctype": "Item",
            "item_code": code,
            "item_name": item_name,
            "item_group": group,
            "stock_uom": UOM,
            "is_stock_item": 1,
            "include_item_in_manufacturing": 1,
            "valuation_rate": 10,
        }
    ).insert()


def ensure_operation():
    if not frappe.db.exists("Workstation", WORKSTATION):
        frappe.get_doc(
            {"doctype": "Workstation", "workstation_name": WORKSTATION, "production_capacity": 1}
        ).insert()
    if not frappe.db.exists("Operation", OPERATION):
        frappe.get_doc(
            {"doctype": "Operation", "name": OPERATION, "workstation": WORKSTATION}
        ).insert()


def boms(company):
    return frappe.get_all(
        "BOM",
        filters={"item": FG_ITEM, "company": company.name, "docstatus": 1},
        pluck="name",
        order_by="creation asc",
    )


def ensure_bom(company, materials, index=1, default=True, with_operation=False):
    existing = boms(company)
    if len(existing) >= index:
        return existing[index - 1]
    bom = frappe.get_doc(
        {
            "doctype": "BOM",
            "item": FG_ITEM,
            "company": company.name,
            "currency": "USD",
            "quantity": 1,
            "is_active": 1,
            "is_default": int(default),
            "with_operations": int(with_operation),
            "rm_cost_as_per": "Valuation Rate",
        }
    )
    for item_code, qty in materials:
        bom.append("items", {"item_code": item_code, "qty": flt(qty), "uom": UOM, "rate": 10})
    if with_operation:
        bom.append(
            "operations",
            {"operation": OPERATION, "workstation": WORKSTATION, "time_in_mins": 37.5},
        )
    bom.insert()
    bom.submit()
    return bom.name


def ensure_user(email, roles):
    if not frappe.db.exists("User", email):
        frappe.get_doc(
            {
                "doctype": "User",
                "email": email,
                "first_name": email.split("@", 1)[0],
                "send_welcome_email": 0,
                "enabled": 1,
            }
        ).insert(ignore_permissions=True)
    user = frappe.get_doc("User", email)
    wanted = set(roles)
    current = {row.role for row in user.roles}
    if current != wanted:
        user.set("roles", [])
        for role in sorted(wanted):
            user.append("roles", {"role": role})
        user.save(ignore_permissions=True)
    frappe.clear_cache(user=email)
    return user


def ensure_principal(user, sites, enabled=1):
    if frappe.db.exists(PRINCIPAL_DOCTYPE, user):
        doc = frappe.get_doc(PRINCIPAL_DOCTYPE, user)
    else:
        doc = frappe.new_doc(PRINCIPAL_DOCTYPE)
        doc.user = user
    doc.enabled = enabled
    doc.set("sites", [{"site": site} for site in sites])
    doc.save()
    return doc


def make_work_order(site_id, qty="12.5", bom_index=1, submit=True, skip_transfer=False, **extra):
    """Create an order whose WIP and Target warehouses lie inside ``site_id``'s subtree."""
    company, _plant = SITES[site_id]
    wo = frappe.new_doc("Work Order")
    wo.update(
        {
            "production_item": FG_ITEM,
            "bom_no": boms(company)[bom_index - 1],
            "company": company.name,
            "qty": flt(qty),
            # ERPNext's own test helper sets this too; the desk client normally fetches it.
            "stock_uom": frappe.db.get_value("Item", FG_ITEM, "stock_uom"),
            "fg_warehouse": site_warehouse(site_id, FG),
            "wip_warehouse": None if skip_transfer else site_warehouse(site_id, WIP),
            "skip_transfer": int(skip_transfer),
            "source_warehouse": company.warehouse("Stores"),
            "planned_start_date": now_datetime(),
            "planned_end_date": add_to_date(now_datetime(), hours=6),
            "transfer_material_against": "Work Order",
        }
    )
    wo.update(extra)
    wo.get_items_and_operations_from_bom()
    for row in wo.required_items:
        row.source_warehouse = company.warehouse("Stores")
    wo.insert()
    if submit:
        wo.submit()
    return wo


def stop(work_order_name):
    from erpnext.manufacturing.doctype.work_order.work_order import stop_unstop

    stop_unstop(work_order_name, "Stopped")


def close(work_order_name):
    from erpnext.manufacturing.doctype.work_order.work_order import close_work_order

    close_work_order(work_order_name, "Closed")


def set_modified(names, value):
    """Force identical or ordered modification stamps to exercise keyset ties."""
    frappe.db.sql(
        "update `tabWork Order` set modified = %(value)s where name in %(names)s",
        {"value": value, "names": tuple(names)},
    )


def issue_api_keys(user):
    """Return (api_key, api_secret) for token authentication; commits for HTTP tests."""
    doc = frappe.get_doc("User", user)
    doc.api_key = doc.api_key or frappe.generate_hash(length=15)
    secret = frappe.generate_hash(length=15)
    doc.api_secret = secret
    doc.save(ignore_permissions=True)
    frappe.db.commit()
    return doc.api_key, secret
