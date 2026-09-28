"""Server-side binding of a dedicated integration user to its Manufacturing sites."""

import frappe
from frappe import _
from frappe.model.document import Document

from neuradix_manufacturing_erpnext.integration.constants import INTEGRATION_ROLE
from neuradix_manufacturing_erpnext.integration.identity import disallowed_roles


class NeuradixIntegrationPrincipal(Document):
    def validate(self):
        if self.user in ("Administrator", "Guest"):
            frappe.throw(_("Administrator and Guest cannot be integration principals."))
        if INTEGRATION_ROLE not in frappe.get_roles(self.user):
            frappe.throw(_("User {0} must hold the {1} role.").format(self.user, INTEGRATION_ROLE))
        extra = disallowed_roles(self.user)
        if extra:
            frappe.throw(
                _("Integration principal {0} must not hold other roles: {1}").format(
                    self.user, ", ".join(extra)
                )
            )
        seen = set()
        for row in self.sites:
            if row.site in seen:
                frappe.throw(_("Manufacturing Site {0} is listed twice.").format(row.site))
            seen.add(row.site)
        if not seen:
            frappe.throw(_("At least one Manufacturing Site is required."))
