"""Test-runner bootstrap.

``bench run-tests --app neuradix_manufacturing_erpnext`` runs only this app's ``before_tests``
hook, so ERPNext's own test bootstrap (setup wizard, fiscal year, test defaults) is invoked
explicitly. It only runs under the Frappe test runner on a disposable site.
"""


def before_tests():
    from erpnext.setup.utils import before_tests as erpnext_before_tests

    erpnext_before_tests()
