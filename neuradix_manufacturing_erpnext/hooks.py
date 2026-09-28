app_name = "neuradix_manufacturing_erpnext"
app_title = "Neuradix Manufacturing ERPNext"
app_publisher = "Busuttil Technologies Limited"
app_description = "ERPNext companion foundation for Neuradix Manufacturing"
# Distribution terms require a product decision before release; no licence grant is added here.
app_license = "Unspecified"
required_apps = ["erpnext"]

after_install = "neuradix_manufacturing_erpnext.setup.install.after_install"
after_migrate = "neuradix_manufacturing_erpnext.setup.install.after_migrate"
before_uninstall = "neuradix_manufacturing_erpnext.setup.install.before_uninstall"

# Confine integration principals to their Manufacturing site scope on every Frappe read path.
_permissions = "neuradix_manufacturing_erpnext.integration.permissions"
permission_query_conditions = {
    "Work Order": f"{_permissions}.work_order_query_conditions",
    "Work Order Item": f"{_permissions}.work_order_child_query_conditions",
    "Work Order Operation": f"{_permissions}.work_order_child_query_conditions",
}
has_permission = {"Work Order": f"{_permissions}.work_order_has_permission"}

# Over HTTP, integration principals may call only this app's v1 read methods.
auth_hooks = ["neuradix_manufacturing_erpnext.integration.auth.restrict_integration_principals"]

# Test runner only: run ERPNext's own test bootstrap before this app's real-site tests.
before_tests = "neuradix_manufacturing_erpnext.tests.bootstrap.before_tests"
