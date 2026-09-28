"""Limit integration principals to the certified read methods over HTTP (Frappe ``auth_hooks``).

Frappe runs ``auth_hooks`` after it authenticates a request (API key, session or OAuth) and before
routing. For a user holding the integration role, every request other than a plain GET to one of
this app's v1 read methods is refused with 403. That closes generic routes which would otherwise
act as existence or count oracles for a role that holds a Work Order DocPerm, such as
``/api/resource``, ``frappe.client.validate_link``, ``frappe.client.get(filters=...)``, child-table
lists, report view, search, desk pages and private files. Other users are unaffected.
"""

import frappe

from neuradix_manufacturing_erpnext.integration import identity
from neuradix_manufacturing_erpnext.integration.constants import NOT_PERMITTED_MESSAGE
from neuradix_manufacturing_erpnext.integration.routes import is_allowed_request


def restrict_integration_principals():
    request = getattr(frappe.local, "request", None)
    if request is None or not identity.holds_integration_role(frappe.session.user):
        return
    if not is_allowed_request(request.method, request.path, frappe.local.form_dict):
        raise frappe.PermissionError(NOT_PERMITTED_MESSAGE)
