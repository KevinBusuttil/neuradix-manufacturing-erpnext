"""Dependency-free value encoding for the read contract.

Kept free of Frappe imports so the exact-decimal, time and cursor rules have fast unit tests.
Callers translate ``ContractValueError`` into the appropriate Frappe exception.
"""

import base64
import binascii
import datetime as dt
import json
import re
from decimal import Decimal, InvalidOperation
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from neuradix_manufacturing_erpnext.integration.constants import PAGE_SIZE_DEFAULT, PAGE_SIZE_MAX


class ContractValueError(ValueError):
    """A request parameter or stored value cannot be represented by the contract."""


_DECIMAL_SOURCE = re.compile(r"-?[0-9]{1,12}(\.[0-9]{1,9})?")
_PAGE_SIZE = re.compile(r"[0-9]{1,4}")
_ERP_DATETIME = "%Y-%m-%d %H:%M:%S.%f"
CURSOR_VERSION = 1
MAX_CURSOR_LENGTH = 1024
MAX_NAME_LENGTH = 140

WORK_ORDER_STATUS = {
    "Submitted": "submitted",
    "Not Started": "not_started",
    "In Process": "in_process",
    "Completed": "completed",
    "Stopped": "stopped",
    "Closed": "closed",
    "Cancelled": "cancelled",
}
OPERATION_STATUS = {
    "Pending": "pending",
    "Work in Progress": "work_in_progress",
    "Completed": "completed",
}
TRANSFER_AGAINST = {"Work Order": "work_order", "Job Card": "job_card"}
LIFECYCLE = {1: "submitted", 2: "cancelled"}


def exact_decimal(value):
    """Canonical exact decimal string for a DECIMAL(21,9) value read as text.

    Accepts the ``CAST(column AS CHAR)`` text or a ``Decimal``. Floats are rejected because
    Frappe's driver conversion already lost exactness by then.
    """
    if isinstance(value, bool) or value is None or isinstance(value, float):
        raise ContractValueError("Quantity must be read as exact decimal text")
    text = str(value)
    if not _DECIMAL_SOURCE.fullmatch(text):
        raise ContractValueError(f"Unsupported decimal value: {text!r}")
    number = Decimal(text)
    if number < 0:
        raise ContractValueError("Negative quantities are not part of the read contract")
    if number == 0:
        return "0"
    rendered = format(number.normalize(), "f")
    return rendered


def system_zone(name):
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError) as exc:
        raise ContractValueError(f"Unknown ERP time zone: {name!r}") from exc


def erp_timestamp(value, zone):
    """Label a naive ERP wall-clock value with the ERP system zone offset.

    Frappe stores naive local timestamps. During a DST fall-back the local hour repeats and the
    first occurrence (fold=0) is chosen; consumers use ``version`` rather than this value for
    change detection.
    """
    if value is None:
        return None
    if isinstance(value, str):
        value = parse_erp_datetime(value)
    if not isinstance(value, dt.datetime):
        raise ContractValueError("Expected an ERP datetime")
    if value.tzinfo is not None:
        raise ContractValueError("ERP datetimes are stored without a zone")
    return value.replace(tzinfo=zone).isoformat(timespec="microseconds")


def erp_date(value):
    if value is None:
        return None
    if isinstance(value, dt.datetime):
        raise ContractValueError("Date-only field unexpectedly contains a time")
    if isinstance(value, str):
        value = dt.date.fromisoformat(value)
    return value.isoformat()


def erp_version(value):
    """Exact stored modification value, used as an opaque change token and cursor key."""
    if isinstance(value, str):
        value = parse_erp_datetime(value)
    if not isinstance(value, dt.datetime) or value.tzinfo is not None:
        raise ContractValueError("Expected a naive ERP datetime")
    return value.strftime(_ERP_DATETIME)


def parse_erp_datetime(text):
    if not isinstance(text, str):
        raise ContractValueError("Expected an ERP datetime string")
    for pattern in (_ERP_DATETIME, "%Y-%m-%d %H:%M:%S"):
        try:
            return dt.datetime.strptime(text, pattern)
        except ValueError:
            continue
    raise ContractValueError(f"Invalid ERP datetime: {text!r}")


def parse_since(value, zone):
    """Convert an RFC 3339 instant with an explicit offset to naive ERP wall-clock time."""
    if value is None or value == "":
        return None
    if not isinstance(value, str) or len(value) > 64:
        raise ContractValueError("Timestamp must be an RFC 3339 string")
    text = value.strip()
    if text.endswith(("Z", "z")):
        text = text[:-1] + "+00:00"
    if "T" not in text and "t" not in text:
        raise ContractValueError("Timestamp must include a date and time")
    try:
        instant = dt.datetime.fromisoformat(text)
    except ValueError as exc:
        raise ContractValueError("Timestamp must be an RFC 3339 string") from exc
    if instant.tzinfo is None or instant.utcoffset() is None:
        raise ContractValueError("Timestamp must include a UTC offset")
    return instant.astimezone(zone).replace(tzinfo=None)


def page_size(value):
    if value is None or value == "":
        return PAGE_SIZE_DEFAULT
    if isinstance(value, bool):
        raise ContractValueError("page_size must be an integer")
    if isinstance(value, int):
        size = value
    elif isinstance(value, str) and _PAGE_SIZE.fullmatch(value):
        size = int(value)
    else:
        raise ContractValueError("page_size must be an integer")
    if not 1 <= size <= PAGE_SIZE_MAX:
        raise ContractValueError(f"page_size must be between 1 and {PAGE_SIZE_MAX}")
    return size


def encode_cursor(kind, site_id, position, name):
    """Opaque continuation token. It carries position only; scope is re-checked on every call."""
    payload = {"v": CURSOR_VERSION, "k": kind, "s": site_id, "m": position, "n": name}
    raw = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def decode_cursor(token, kind, site_id):
    if not isinstance(token, str) or not token or len(token) > MAX_CURSOR_LENGTH:
        raise ContractValueError("Invalid cursor")
    try:
        raw = base64.urlsafe_b64decode(token + "=" * (-len(token) % 4))
        payload = json.loads(raw)
    except (binascii.Error, ValueError, UnicodeDecodeError) as exc:
        raise ContractValueError("Invalid cursor") from exc
    if not isinstance(payload, dict) or set(payload) != {"v", "k", "s", "m", "n"}:
        raise ContractValueError("Invalid cursor")
    if payload["v"] != CURSOR_VERSION or payload["k"] != kind:
        raise ContractValueError("Cursor does not belong to this method or contract version")
    if payload["s"] != site_id:
        raise ContractValueError("Cursor does not belong to this site")
    name = payload["n"]
    if not isinstance(name, str) or not name or len(name) > MAX_NAME_LENGTH:
        raise ContractValueError("Invalid cursor")
    position = parse_erp_datetime(payload["m"])
    return position, name


def work_order_status(raw):
    return WORK_ORDER_STATUS.get(raw or "", "unknown")


def operation_status(raw):
    return OPERATION_STATUS.get(raw or "", "unknown")


def transfer_against(raw):
    if raw in (None, ""):
        return None
    try:
        return TRANSFER_AGAINST[raw]
    except KeyError as exc:
        raise ContractValueError(f"Unsupported transfer_material_against: {raw!r}") from exc


def lifecycle(docstatus):
    try:
        return LIFECYCLE[int(docstatus)]
    except (KeyError, TypeError, ValueError) as exc:
        raise ContractValueError("Draft or unknown document status is not exposed") from exc


def optional_text(value):
    return value if value not in (None, "") else None


def flag(value):
    try:
        return bool(int(value or 0))
    except (TypeError, ValueError, InvalidOperation) as exc:
        raise ContractValueError("Invalid check value") from exc
