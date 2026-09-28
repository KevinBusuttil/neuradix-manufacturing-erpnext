"""Contract identifiers and fixed limits shared by the endpoints and dependency-free tests."""

CONTRACT_VERSION = "0.2.0-draft"

INTEGRATION_ROLE = "Neuradix Integration Reader"
# Roles Frappe assigns implicitly to a Website User. A principal may hold these plus
# INTEGRATION_ROLE, nothing else; "Desk User" (added for System Users) is deliberately excluded.
IMPLICIT_ROLES = frozenset({"All", "Guest"})
BOOTSTRAP_ROLE = "System Manager"

SITE_DOCTYPE = "Neuradix Manufacturing Site"
PRINCIPAL_DOCTYPE = "Neuradix Integration Principal"
PRINCIPAL_SITE_DOCTYPE = "Neuradix Integration Principal Site"

SCHEMA_CAPABILITIES = "neuradix.erpnext.capabilities.v1"
SCHEMA_WORK_ORDER_PAGE = "neuradix.erpnext.work_order_page.v1"
SCHEMA_WORK_ORDER_DETAIL = "neuradix.erpnext.work_order_detail.v1"
SCHEMA_WORK_ORDER_DELETION_PAGE = "neuradix.erpnext.work_order_deletion_page.v1"

PAGE_SIZE_DEFAULT = 50
PAGE_SIZE_MAX = 200

# Re-read window for incremental passes. It covers long-running ERP transactions that commit an
# older `modified` value late, and the repeated local hour when the ERP time zone leaves DST,
# because Frappe stores naive wall-clock timestamps.
RECOMMENDED_OVERLAP_SECONDS = 3900

# Submitted (docstatus 1) and cancelled (docstatus 2) orders only. Drafts are not released
# production intent and are never exposed to an integration principal.
EXPOSED_DOCSTATUS = (1, 2)

NOT_PERMITTED_MESSAGE = "Not permitted for Neuradix integration reads"
NOT_FOUND_MESSAGE = "Work Order not found in the authorized Manufacturing site"
