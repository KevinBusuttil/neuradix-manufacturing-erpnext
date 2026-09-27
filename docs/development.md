# Development and validation

## Fast checks without a Bench

Python 3.10+ package, tested by the initial CI on Python 3.12:

```bash
python -m pip install -e . build ruff==0.12.12
python -m ruff check .
python -m ruff format --check .
python -m unittest discover -s tests -v
python -m build
```

These tests verify honest capability metadata and the endpoint's explicit permission calls using
a Frappe test double. They do not prove real Frappe authentication, installation or ERP transactions.

## Disposable ERPNext integration site

Initial pinned target: Frappe v15.98.0, ERPNext v15.87.2, Python 3.11, Node 18, MariaDB 10.6 and Redis 6.
The CI integration job pins setuptools 80.9.0 inside the Bench environment because this Frappe
release still imports `pkg_resources` through Dropbox. It creates a fresh development site,
installs ERPNext and this app, and runs:

```bash
bench --site test.localhost run-tests --app neuradix_manufacturing_erpnext
```

The tests use Administrator only to exercise bootstrap metadata, and explicitly deny Guest.
Business integration identity, cross-company permission and posting tests are future EN work.
Credentials in the ephemeral CI service configuration are test-only; never reuse them at a customer.

The application declares `required_apps = ["erpnext"]` and Frappe/ERPNext v15 dependencies in
`pyproject.toml`. The namespace and module files are included in its wheel. Installation creates
no custom business DocTypes, scheduled jobs, stock documents or equipment integration.

Sources: [Frappe app structure](https://docs.frappe.io/framework/user/en/basics/apps),
[required-app hook](https://docs.frappe.io/framework/user/en/python-api/hooks), and
[REST API](https://docs.frappe.io/framework/user/en/guides/integration/rest_api).
