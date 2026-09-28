"""Resolve the authenticated integration principal and its Manufacturing site scope.

Scope comes only from server-side records bound to ``frappe.session.user``. Request parameters
can select one of the principal's sites but can never add a site, Company or warehouse.

Role checks deliberately avoid ``frappe.only_for``: in Frappe v15 it returns early for
Administrator and whenever ``frappe.flags.in_test`` is set, so tests would not exercise it.
"""

from dataclasses import dataclass, field

import frappe

from neuradix_manufacturing_erpnext.integration import scope
from neuradix_manufacturing_erpnext.integration.constants import (
    BOOTSTRAP_ROLE,
    IMPLICIT_ROLES,
    INTEGRATION_ROLE,
    NOT_PERMITTED_MESSAGE,
    PRINCIPAL_DOCTYPE,
    PRINCIPAL_SITE_DOCTYPE,
)


@dataclass(frozen=True)
class Principal:
    user: str
    sites: dict = field(default_factory=dict)

    def site(self, site_id):
        """Return an authorized site. Unknown, disabled and unauthorized sites look identical."""
        if not isinstance(site_id, str) or site_id not in self.sites:
            deny()
        return self.sites[site_id]

    def as_contract(self):
        return {
            "user": self.user,
            "sites": [self.sites[key].as_contract() for key in sorted(self.sites)],
        }


def deny():
    # Raised without frappe.throw so no message is queued when a permission hook catches it.
    raise frappe.PermissionError(NOT_PERMITTED_MESSAGE)


def holds_integration_role(user):
    if user in (None, "", "Guest", "Administrator"):
        return False
    return INTEGRATION_ROLE in frappe.get_roles(user)


def disallowed_roles(user):
    """Roles beyond the integration role; any of them disqualifies a principal."""
    return sorted(set(frappe.get_roles(user)) - IMPLICIT_ROLES - {INTEGRATION_ROLE})


def is_bootstrap_administrator(user):
    return user == "Administrator" or (user != "Guest" and BOOTSTRAP_ROLE in frappe.get_roles(user))


def resolve_principal(user=None):
    """Return the active principal for ``user`` or raise ``frappe.PermissionError``."""
    user = user or frappe.session.user
    if not holds_integration_role(user):
        deny()
    if disallowed_roles(user):
        deny()
    if not frappe.db.get_value("User", user, "enabled"):
        deny()
    record = frappe.db.get_value(
        PRINCIPAL_DOCTYPE, {"user": user}, ["name", "enabled"], as_dict=True
    )
    if not record or not record.enabled:
        deny()
    site_ids = frappe.get_all(
        PRINCIPAL_SITE_DOCTYPE,
        filters={"parent": record.name, "parenttype": PRINCIPAL_DOCTYPE, "parentfield": "sites"},
        pluck="site",
        order_by="idx asc",
    )
    sites = {}
    for site_id in site_ids:
        site = scope.load_site(site_id)
        if site is not None:
            sites[site.site_id] = site
    return Principal(user=user, sites=sites)


def require_principal():
    if frappe.session.user == "Guest":
        deny()
    return resolve_principal(frappe.session.user)
