# Development and validation

## Fast checks without a Bench

Python 3.10+ package, tested by CI on Python 3.12:

```bash
python -m pip install -e . build ruff==0.12.12 jsonschema==4.25.1
python -m ruff check .
python -m ruff format --check .
python tools/build_contract_schemas.py --check
python -m unittest discover -s tests -v
python -m build
```

These cover the contract schemas, the observed examples, exact-decimal/time/cursor encoding and
capability flags. They import no Frappe code and prove nothing about authentication, permissions,
installation or ERP data. The real-site suite below is the required evidence for those.

## Disposable ERPNext integration site

Pinned target: Frappe v15.98.0, ERPNext v15.87.2, Python 3.11, Node 18, MariaDB 10.6 and Redis 6.
The CI integration job pins setuptools 80.9.0 inside the Bench environment because this Frappe
release still imports `pkg_resources` through Dropbox. It creates a fresh development site,
installs ERPNext and this app, installs the app's test-only dev dependency and runs:

```bash
bench setup requirements --python --dev neuradix_manufacturing_erpnext   # jsonschema for tests
bench --site test.localhost set-config allow_tests true
CI=1 bench --site test.localhost run-tests --app neuradix_manufacturing_erpnext
```

`CI` makes `bench run-tests` exit non-zero on failure (GitHub Actions sets it). The app's
`before_tests` hook runs ERPNext's own test bootstrap (setup wizard, fiscal year, test defaults,
time zone America/New_York), because `--app` runs only this app's hook.

The suite (`neuradix_manufacturing_erpnext/tests/`) uses real users, roles, DocPerms and Frappe's
permission engine on synthetic fixtures: two Companies (`NX Test Alpha/Beta Manufacturing Ltd`),
three Manufacturing sites (`NXT-A1`, `NXT-A2` in Alpha; `NXT-B1` in Beta) with separate warehouse
subtrees, one finished item and two raw materials with three submitted BOMs (one with an
operation), and principals with distinct scopes. Shared
fixtures are committed because `test_http_api.py` sends real HTTP requests through Frappe's WSGI
application in another thread and database connection with API-key token authentication. That
class also commits its own Work Orders, Job Cards, API keys and Deleted Document rows, which
persist; every other test's changes are rolled back. The fixtures disable Manufacturing Settings
capacity planning so accumulated Job Cards cannot block later runs. Use a disposable site only.

Set `NEURADIX_CONTRACT_CAPTURE_DIR=<dir>` to write the HTTP responses observed by `test_http_api.py`.
CI uploads them as the `companion-contract-capture` artifact. The committed examples in
`neuradix_manufacturing_erpnext/contracts/examples/` are normalized `message` bodies from such a
capture (see that directory's README); refresh them and Manufacturing's vendored copy together.

Credentials in the ephemeral CI service configuration are test-only; never reuse them at a customer.
The application declares `required_apps = ["erpnext"]` and Frappe/ERPNext v15 dependencies in
`pyproject.toml`. Installation adds three configuration DocTypes, one Role and one read-only Custom
DocPerm for it. Frappe copies Work Order's standard permissions into Custom DocPerm when that first
custom rule is added. Uninstall removes the role's rule, disables the role, and resets Work Order to
its standard permissions only when the remaining custom rows are unmodified copies. It creates no
stock documents, scheduled jobs or equipment integration.

Sources: [Frappe app structure](https://docs.frappe.io/framework/user/en/basics/apps),
[hooks](https://docs.frappe.io/framework/user/en/python-api/hooks),
[REST API and token authentication](https://docs.frappe.io/framework/user/en/guides/integration/rest_api)
and the pinned Frappe/ERPNext source.
