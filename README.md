# Neuradix Manufacturing ERPNext

Installable Frappe companion foundation for Neuradix Manufacturing.
ERPNext remains authoritative for inventory, valuation and accounting.

**Status: EN-00 scaffold.** Provides app packaging, ERPNext dependency metadata and an
authenticated System Manager capability endpoint. All business operations are declared unavailable.
No Work Order synchronization, stock posting, maintenance synchronization or machine control is implemented.

## Documentation

- [Implementation plan and M0–M8 mapping](docs/implementation-plan.md)
- [API boundary and planned transaction contract](docs/api-contract.md)
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
bench --site dev.localhost run-tests --app neuradix_manufacturing_erpnext
```

While the foundation PR is open, add `--branch scaffold/initial-foundation` to `bench get-app`.
The initial qualification target is Frappe v15.98.0 / ERPNext v15.87.2. This is a test target,
not a claim that every v15 installation or v16 is supported. See the current validation record.

System Managers can call authenticated GET
`/api/method/neuradix_manufacturing_erpnext.api.v1.capabilities`.
Frappe wraps the return value in `message`. No guest access is enabled.
Production integration identity and company/site scope are EN-01 work; do not deploy with an
administrator token as the product's integration account.

No ISNACK code is copied in EN-00. No distribution licence is selected by this scaffold;
resolve release licensing and notices before distribution.
