"""Read-only Work Order list, detail and deletion markers for one authorized site.

Selection always runs through ``frappe.get_list`` (role DocPerm plus this app's permission
hooks) with explicit site filters. Exact values are then read for the selected names with
``CAST(... AS CHAR)`` because Frappe's MariaDB driver converts DECIMAL columns to float.
Both reads run in the request's transaction; under MariaDB's default REPEATABLE READ
isolation they see one snapshot (Frappe does not override the isolation level).
"""

import json

import frappe

from neuradix_manufacturing_erpnext.integration import scope
from neuradix_manufacturing_erpnext.integration import serialization as ser
from neuradix_manufacturing_erpnext.integration.constants import (
    CONTRACT_VERSION,
    NOT_FOUND_MESSAGE,
    NOT_PERMITTED_MESSAGE,
    SCHEMA_WORK_ORDER_DELETION_PAGE,
    SCHEMA_WORK_ORDER_DETAIL,
    SCHEMA_WORK_ORDER_PAGE,
)

CURSOR_WORK_ORDERS = "work_orders"
CURSOR_DELETIONS = "work_order_deletions"
SELECT_FIELDS = ["name", "modified", "company", "docstatus", "fg_warehouse", "wip_warehouse"]

WORK_ORDER_COLUMNS = """
    name, modified, docstatus, status, company, production_item, item_name, bom_no, stock_uom,
    CAST(qty AS CHAR) AS qty,
    CAST(produced_qty AS CHAR) AS produced_qty,
    CAST(material_transferred_for_manufacturing AS CHAR) AS material_transferred,
    CAST(process_loss_qty AS CHAR) AS process_loss_qty,
    CAST(disassembled_qty AS CHAR) AS disassembled_qty,
    wip_warehouse, fg_warehouse, source_warehouse, scrap_warehouse,
    planned_start_date, planned_end_date, actual_start_date, actual_end_date,
    expected_delivery_date, amended_from, sales_order, production_plan, material_request, project,
    use_multi_level_bom, skip_transfer, transfer_material_against, has_serial_no, has_batch_no
"""


class ContractDataError(Exception):
    """Stored ERP data cannot be represented by the contract.

    Frappe returns HTTP 500. The page fails rather than silently skipping a record, so the
    consumer's watermark cannot advance past data it never received.
    """


def _invalid(exc):
    raise frappe.ValidationError(str(exc)) from exc


def _serialize(name, build):
    try:
        return build()
    except ser.ContractValueError as exc:
        raise ContractDataError(f"Work Order {name}: {exc}") from exc


def _require_role_read():
    """Every method requires the role's Work Order read DocPerm, including deletion markers."""
    if not frappe.has_permission("Work Order", "read"):
        raise frappe.PermissionError(NOT_PERMITTED_MESSAGE)


def _visible_amendment_sources(site, rows):
    """Names referenced by ``amended_from`` that are themselves in this site's scope.

    An amendment may point at a cancelled order in another site or Company; that name is not
    disclosed.
    """
    names = sorted({row.amended_from for row in rows if row.amended_from})
    if not names:
        return set()
    return set(
        frappe.get_all(
            "Work Order",
            filters=[*scope.list_filters(site), ["name", "in", names]],
            pluck="name",
        )
    )


def _context(site):
    zone_name = frappe.utils.get_system_timezone()
    try:
        zone = ser.system_zone(zone_name)
    except ser.ContractValueError as exc:
        _invalid(exc)
    return zone, {
        "source": {"system": "erpnext", "instance": frappe.local.site, "erp_time_zone": zone_name},
        "site": site.as_contract(),
        "generated_at": ser.erp_timestamp(frappe.utils.now_datetime(), zone),
    }


def _select(site, extra_filters=None, or_filters=None, limit=None):
    """Permission-checked selection of in-scope Work Order rows ordered by (modified, name)."""
    if not site.warehouses:
        return []
    rows = frappe.get_list(
        "Work Order",
        fields=SELECT_FIELDS,
        filters=scope.list_filters(site) + (extra_filters or []),
        or_filters=or_filters,
        order_by="modified asc, name asc",
        limit_page_length=limit,
    )
    return rows


def _fetch(names):
    if not names:
        return {}
    rows = frappe.db.sql(
        f"select {WORK_ORDER_COLUMNS} from `tabWork Order` where name in %(names)s",
        {"names": tuple(names)},
        as_dict=True,
    )
    return {row.name: row for row in rows}


def _summary(row, zone, visible_sources):
    amended_from = row.amended_from if row.amended_from in visible_sources else None
    return {
        "name": row.name,
        "version": ser.erp_version(row.modified),
        "modified_at": ser.erp_timestamp(row.modified, zone),
        "lifecycle": ser.lifecycle(row.docstatus),
        "status": ser.work_order_status(row.status),
        "erp_status": row.status or "",
        "company": row.company,
        "production_item": {
            "item_code": row.production_item,
            "item_name": ser.optional_text(row.item_name),
        },
        "bom_no": row.bom_no,
        "stock_uom": ser.optional_text(row.stock_uom),
        "quantities": {
            "planned": ser.exact_decimal(row.qty),
            "produced": ser.exact_decimal(row.produced_qty),
            "material_transferred": ser.exact_decimal(row.material_transferred),
            "process_loss": ser.exact_decimal(row.process_loss_qty),
            "disassembled": ser.exact_decimal(row.disassembled_qty),
        },
        "warehouses": {
            "wip": ser.optional_text(row.wip_warehouse),
            "fg": row.fg_warehouse,
            "source": ser.optional_text(row.source_warehouse),
            "scrap": ser.optional_text(row.scrap_warehouse),
        },
        "planned_start_at": ser.erp_timestamp(row.planned_start_date, zone),
        "planned_end_at": ser.erp_timestamp(row.planned_end_date, zone),
        "actual_start_at": ser.erp_timestamp(row.actual_start_date, zone),
        "actual_end_at": ser.erp_timestamp(row.actual_end_date, zone),
        "expected_delivery_date": ser.erp_date(row.expected_delivery_date),
        "amended_from": ser.optional_text(amended_from),
        "references": {
            "sales_order": ser.optional_text(row.sales_order),
            "production_plan": ser.optional_text(row.production_plan),
            "material_request": ser.optional_text(row.material_request),
            "project": ser.optional_text(row.project),
        },
    }


def list_work_orders(site, cursor=None, modified_since=None, page_size=None):
    _require_role_read()
    try:
        size = ser.page_size(page_size)
        if cursor and modified_since:
            raise ser.ContractValueError("Use either cursor or modified_since, not both")
        zone, envelope = _context(site)
        extra, or_filters = [], None
        if cursor:
            position, name = ser.decode_cursor(cursor, CURSOR_WORK_ORDERS, site.site_id)
            # (modified, name) > (position, name) expressed as AND plus one OR group.
            extra.append(["modified", ">=", position])
            or_filters = [["modified", ">", position], ["name", ">", name]]
        elif modified_since:
            extra.append(["modified", ">=", ser.parse_since(modified_since, zone)])
    except ser.ContractValueError as exc:
        _invalid(exc)

    rows = _select(site, extra, or_filters, limit=size + 1)
    scanned = rows[:size]
    next_cursor = None
    if len(rows) > size:
        last = scanned[-1]
        next_cursor = ser.encode_cursor(
            CURSOR_WORK_ORDERS, site.site_id, ser.erp_version(last.modified), last.name
        )
    # Defence in depth: the filters already express membership; a shared record never escapes.
    names = [row.name for row in scanned if scope.contains(site, row)]
    data = _fetch(names)
    sources = _visible_amendment_sources(site, data.values())
    items = [
        _serialize(name, lambda row=data[name]: _summary(row, zone, sources))
        for name in names
        if name in data
    ]
    return {
        "schema": SCHEMA_WORK_ORDER_PAGE,
        "contract_version": CONTRACT_VERSION,
        **envelope,
        "page_size": size,
        "items": items,
        "next_cursor": next_cursor,
    }


def get_work_order(site, name):
    _require_role_read()
    if not isinstance(name, str) or not name or len(name) > ser.MAX_NAME_LENGTH:
        raise frappe.DoesNotExistError(NOT_FOUND_MESSAGE)
    zone, envelope = _context(site)
    rows = _select(site, [["name", "=", name]], limit=1)
    if not rows or rows[0].name != name or not scope.contains(site, rows[0]):
        raise frappe.DoesNotExistError(NOT_FOUND_MESSAGE)
    # Document-level check through Frappe (role, controller hooks); sharing cannot widen it.
    if not frappe.has_permission("Work Order", "read", doc=name, ignore_share_permissions=True):
        raise frappe.DoesNotExistError(NOT_FOUND_MESSAGE)
    row = _fetch([name]).get(name)
    if row is None or not scope.contains(site, row):
        raise frappe.DoesNotExistError(NOT_FOUND_MESSAGE)
    sources = _visible_amendment_sources(site, [row])
    work_order = _serialize(name, lambda: _detail(row, name, zone, sources))
    return {
        "schema": SCHEMA_WORK_ORDER_DETAIL,
        "contract_version": CONTRACT_VERSION,
        **envelope,
        "work_order": work_order,
    }


def _detail(row, name, zone, sources):
    work_order = _summary(row, zone, sources)
    work_order.update(
        {
            "use_multi_level_bom": ser.flag(row.use_multi_level_bom),
            "skip_transfer": ser.flag(row.skip_transfer),
            "transfer_material_against": ser.transfer_against(row.transfer_material_against),
            "has_serial_no": ser.flag(row.has_serial_no),
            "has_batch_no": ser.flag(row.has_batch_no),
            "required_items": _required_items(name),
            "operations": _operations(name, zone),
        }
    )
    return work_order


def _required_items(name):
    rows = frappe.db.sql(
        """
        select idx, item_code, item_name, operation, source_warehouse, stock_uom,
            include_item_in_manufacturing, allow_alternative_item,
            CAST(required_qty AS CHAR) AS required_qty,
            CAST(transferred_qty AS CHAR) AS transferred_qty,
            CAST(consumed_qty AS CHAR) AS consumed_qty,
            CAST(returned_qty AS CHAR) AS returned_qty
        from `tabWork Order Item`
        where parent = %(name)s and parenttype = 'Work Order' and parentfield = 'required_items'
        order by idx asc
        """,
        {"name": name},
        as_dict=True,
    )
    return [
        {
            "row": int(row.idx),
            "item_code": row.item_code,
            "item_name": ser.optional_text(row.item_name),
            "operation": ser.optional_text(row.operation),
            "source_warehouse": ser.optional_text(row.source_warehouse),
            "stock_uom": ser.optional_text(row.stock_uom),
            "include_item_in_manufacturing": ser.flag(row.include_item_in_manufacturing),
            "allow_alternative_item": ser.flag(row.allow_alternative_item),
            "quantities": {
                "required": ser.exact_decimal(row.required_qty),
                "transferred": ser.exact_decimal(row.transferred_qty),
                "consumed": ser.exact_decimal(row.consumed_qty),
                "returned": ser.exact_decimal(row.returned_qty),
            },
        }
        for row in rows
    ]


def _operations(name, zone):
    rows = frappe.db.sql(
        """
        select idx, sequence_id, operation, workstation, workstation_type, bom, status,
            CAST(completed_qty AS CHAR) AS completed_qty,
            CAST(process_loss_qty AS CHAR) AS process_loss_qty,
            CAST(time_in_mins AS CHAR) AS time_in_mins,
            planned_start_time, planned_end_time, actual_start_time, actual_end_time
        from `tabWork Order Operation`
        where parent = %(name)s and parenttype = 'Work Order' and parentfield = 'operations'
        order by idx asc
        """,
        {"name": name},
        as_dict=True,
    )
    return [
        {
            "row": int(row.idx),
            "sequence_id": int(row.sequence_id) if row.sequence_id else None,
            "operation": row.operation,
            "workstation": ser.optional_text(row.workstation),
            "workstation_type": ser.optional_text(row.workstation_type),
            "bom": ser.optional_text(row.bom),
            "status": ser.operation_status(row.status),
            "erp_status": ser.optional_text(row.status),
            "quantities": {
                "completed": ser.exact_decimal(row.completed_qty),
                "process_loss": ser.exact_decimal(row.process_loss_qty),
            },
            "planned_minutes": ser.exact_decimal(row.time_in_mins),
            "planned_start_at": ser.erp_timestamp(row.planned_start_time, zone),
            "planned_end_at": ser.erp_timestamp(row.planned_end_time, zone),
            "actual_start_at": ser.erp_timestamp(row.actual_start_time, zone),
            "actual_end_at": ser.erp_timestamp(row.actual_end_time, zone),
        }
        for row in rows
    ]


def list_deletions(site, cursor=None, deleted_since=None, page_size=None):
    """Deletion markers for Work Orders that were in this site's scope when deleted.

    Frappe records ``delete_doc`` deletions in Deleted Document unless deleted permanently;
    bulk SQL deletion (for example company transaction deletion) is not recorded and old rows can
    be purged, so consumers still run periodic full reconciliation. Restored deletions are still
    reported: Frappe restores a cancelled order as a draft, which is no longer exposed. Frappe can
    reuse a deleted order's name, so a marker applies only to a stored record whose version is not
    newer than ``last_version``. The scan is limited to the site's scope in SQL, so a cursor
    never refers to another Company's or site's deletion.
    """
    _require_role_read()
    try:
        size = ser.page_size(page_size)
        if cursor and deleted_since:
            raise ser.ContractValueError("Use either cursor or deleted_since, not both")
        zone, envelope = _context(site)
        warehouses = tuple(sorted(site.warehouses)) or ("",)
        params = {
            "limit": size + 1,
            "company": site.company,
            "warehouses": warehouses,
            "wip_values": (*warehouses, ""),
        }
        condition = ""
        if cursor:
            position, name = ser.decode_cursor(cursor, CURSOR_DELETIONS, site.site_id)
            params.update(position=position, name=name)
            condition = (
                "and (creation > %(position)s or (creation = %(position)s and name > %(name)s))"
            )
        elif deleted_since:
            params["position"] = ser.parse_since(deleted_since, zone)
            condition = "and creation >= %(position)s"
    except ser.ContractValueError as exc:
        _invalid(exc)

    rows = frappe.db.sql(
        f"""
        select name, creation, deleted_name, data
        from `tabDeleted Document`
        where deleted_doctype = 'Work Order'
            and JSON_VALUE(data, '$.company') = %(company)s
            and JSON_VALUE(data, '$.docstatus') in ('1', '2')
            and JSON_VALUE(data, '$.fg_warehouse') in %(warehouses)s
            and ifnull(JSON_VALUE(data, '$.wip_warehouse'), '') in %(wip_values)s
            {condition}
        order by creation asc, name asc
        limit %(limit)s
        """,
        params,
        as_dict=True,
    )
    scanned = rows[:size]
    next_cursor = None
    if len(rows) > size:
        last = scanned[-1]
        next_cursor = ser.encode_cursor(
            CURSOR_DELETIONS, site.site_id, ser.erp_version(last.creation), last.name
        )
    items = []
    for row in scanned:
        try:
            snapshot = json.loads(row.data or "{}")
        except ValueError:
            continue
        if not isinstance(snapshot, dict) or not scope.contains(site, snapshot):
            continue
        last_version = snapshot.get("modified")
        items.append(
            _serialize(
                row.deleted_name,
                lambda row=row, snapshot=snapshot, last_version=last_version: {
                    "name": row.deleted_name,
                    "deleted_at": ser.erp_timestamp(row.creation, zone),
                    "last_version": ser.erp_version(last_version),
                    "last_lifecycle": ser.lifecycle(snapshot.get("docstatus")),
                },
            )
        )
    return {
        "schema": SCHEMA_WORK_ORDER_DELETION_PAGE,
        "contract_version": CONTRACT_VERSION,
        **envelope,
        "page_size": size,
        "items": items,
        "next_cursor": next_cursor,
    }
