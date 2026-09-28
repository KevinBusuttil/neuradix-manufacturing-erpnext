"""A physical Manufacturing site mapped to one Company and one warehouse subtree."""

import re

import frappe
from frappe import _
from frappe.model.document import Document

from neuradix_manufacturing_erpnext.integration.scope import nested

SITE_ID_PATTERN = re.compile(r"[A-Z0-9][A-Z0-9_-]{0,63}")


class NeuradixManufacturingSite(Document):
    def validate(self):
        if not SITE_ID_PATTERN.fullmatch(self.site_id or ""):
            frappe.throw(
                _("Site ID must be 1-64 uppercase letters, digits, hyphens or underscores."),
                frappe.ValidationError,
            )
        root = frappe.db.get_value(
            "Warehouse", self.root_warehouse, ["company", "lft", "rgt"], as_dict=True
        )
        if not root:
            frappe.throw(_("Root Warehouse {0} does not exist.").format(self.root_warehouse))
        if root.company != self.company:
            frappe.throw(
                _("Root Warehouse {0} belongs to {1}, not {2}.").format(
                    self.root_warehouse, root.company, self.company
                )
            )
        self.validate_no_overlap(root)

    def validate_no_overlap(self, root):
        """Two sites of one Company may not share warehouses, so membership stays unambiguous."""
        others = frappe.get_all(
            "Neuradix Manufacturing Site",
            filters={"company": self.company, "name": ["!=", self.name or ""]},
            fields=["name", "root_warehouse"],
        )
        for other in others:
            bounds = frappe.db.get_value(
                "Warehouse", other.root_warehouse, ["lft", "rgt"], as_dict=True
            )
            if not bounds:
                continue
            if nested(root, bounds):
                frappe.throw(
                    _("Warehouse subtree overlaps Manufacturing Site {0}.").format(other.name)
                )
