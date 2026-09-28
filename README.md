# Neuradix Manufacturing ERPNext

Installable Frappe companion foundation for Neuradix Manufacturing.
ERPNext remains authoritative for inventory, valuation and accounting.

**Status: EN-01 development.** Provides a least-privilege integration identity bound to
Manufacturing sites and a read-only, scoped Work Order API (list, detail, deletion markers) with
versioned JSON Schemas. Stock posting, production posting, maintenance synchronization and
command outcome discovery are declared unavailable. No machine control is implemented.

## Documentation

- [Implementation plan and M0–M8 mapping](docs/implementation-plan.md)
- [API contract: identity, scope, Work Order reads and planned transactions](docs/api-contract.md)
- [Integration identity runbook](docs/integration-identity.md)
- [Installation and validation](docs/development.md)
- [Current status and compatibility](docs/status.md)

[Manufacturing](https://github.com/KevinBusuttil/neuradix-manufacturing) contains the Flutter/Rust
product and full specification/commercial baseline (private access required).
[Robotics integration plan](https://github.com/KevinBusuttil/neuradix-robotics-platform/blob/main/docs/integrations/Neuradix-Manufacturing.md)
explains the mandatory machinery boundary independently of that private repository.
The local documentation is self-contained for companion development.

## Install on a disposable development site

Use an existing supported Frappe/ERPNext v15 Bench, with ERPNext installed first:

```bash
bench get-app https://github.com/KevinBusuttil/neuradix-manufacturing-erpnext.git
bench --site dev.localhost install-app neuradix_manufacturing_erpnext
bench setup requirements --python --dev neuradix_manufacturing_erpnext
bench --site dev.localhost set-config allow_tests true
CI=1 bench --site dev.localhost run-tests --app neuradix_manufacturing_erpnext
```

The tests create synthetic companies, users and Work Orders and commit shared fixtures, so run
them only on a disposable site. See [development](docs/development.md).

The initial qualification target is Frappe v15.98.0 / ERPNext v15.87.2. This is a test target,
not a claim that every v15 installation or v16 is supported. See the current validation record.

Integration principals call authenticated GET methods under
`/api/method/neuradix_manufacturing_erpnext.api.v1.` (`capabilities`, `work_orders`, `work_order`,
`work_order_deletions`); Frappe wraps results in `message`. No guest access is enabled. Provision a
dedicated user holding only the `Neuradix Integration Reader` role and a principal record as
described in the [runbook](docs/integration-identity.md); never use an administrator token as the
product's integration account.

No ISNACK code is copied in EN-00 or EN-01. No distribution licence is selected by this scaffold;
resolve release licensing and notices before distribution.
