# Companion API contract

## Implemented bootstrap endpoint

Authenticated GET `/api/method/neuradix_manufacturing_erpnext.api.v1.capabilities`.
Frappe returns the object below inside `message`; errors use Frappe's normal HTTP error handling.
Guest and non-System-Manager callers are denied. This endpoint returns no company or work records.

```json
{"contract_version":"0.1.0-draft","maturity":"scaffold","target_erpnext_major":15,
 "operations":{"read_work_orders":false,"post_stock":false,"post_production":false,
 "maintenance_sync":false,"discover_command_outcome":false}}
```

Bootstrap administrative access is temporary and metadata-only. EN-01 must add the scoped service
principal before business data is exposed; do not give a production Rust connector Administrator access.
Frappe authentication and transport use the site's supported mechanisms; secrets stay server-side.

## Planned business command envelope (not an implemented endpoint)

Agree version, stable command ID, idempotency key, authenticated principal binding, company/site,
operation, exact-decimal quantity/unit, expected source version, production/lot references and payload.
Scope and permission come from server-side identity, not a trusted-looking JSON field. Use
capability discovery to disable unsupported operations in Manufacturing.

Planned outcomes: pending, confirmed, rejected and unknown; ERP document references accompany
confirmed outcomes. A duplicate key with a different payload is a conflict. Every uncertain outcome
needs lookup/reconciliation. Exact methods and status codes are EN-01/02 decisions; this document
does not advertise unimplemented endpoints.

No PLC or robot credentials, control methods or direct actuator calls belong in this app.
Machine tasks always pass from Manufacturing through Neuradix Robotics Platform.
