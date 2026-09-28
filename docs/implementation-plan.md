# ERPNext companion implementation plan

Technical baseline aligned to Neuradix Manufacturing specification v0.3 and commercial plan v0.2,
27 September 2026. This public document intentionally contains the technical work and acceptance
criteria needed here; private customer information and commercial budgeting remain in Manufacturing.

## Scope and ownership

This app implements scoped, transactional ERPNext methods and outcome discovery. Rust invokes
those methods; it does not write stock/accounting tables or reconstruct ERPNext submit/cancel rules.
ERPNext controls its inventory ledger and Asset Maintenance schedule. Manufacturing controls factory
workflow and equipment-release decisions. Robotics Platform controls qualified equipment execution.

| ID | Gate | Work | Dependencies | Exit evidence |
|---|---|---|---|---|
| EN-00 | Foundation | App package, metadata endpoint, tests, CI and documentation | None | Installable scaffold; all business capabilities false |
| EN-01 | M0–M2 | Pin ERP configuration, integration role/user scope, company/site mapping and Work Order read API | MF-01/02 decisions | Cross-company denial, pagination, status/cancellation fixtures, no guest read |
| EN-02 | M2–M3 | Persistent command receipt, key/payload conflict detection and outcome lookup | EN-01; agreed ERP-neutral commands | Commit/rollback tests; duplicate callers; lost-response discovery |
| EN-03 | M3 | Staging, issue, consumption, output, scrap, return and reversal through ERPNext methods | EN-02; MF-04; selected manufacturing settings | Quantities reconcile; actual/backflush policy; serial/batch mapping; duplicate protection |
| EN-04 | M4 | Quality holds, inspection mappings, maintenance occurrences, spares and verification mapping | MF-05; selected authority matrix | Alternate posting paths respect holds; zero vs missing; completion distinct from release |
| EN-05 | M5 | Connector certification, reconciliation, upgrade/restore and permission review | EN-01–04; exact ERP versions/settings | Selected acceptance scenarios pass on real ERPNext site |
| EN-06 | M6–M8 | Pilot support, second-site install, migrations, supported release | Qualified integration | Repeatable install, support runbook and compatibility matrix |

## Commercial milestone context

M0 is discovery and scope; M1 freezes reviewed contracts/prototype and hardware feasibility; M2 supplies
foundations; M3 is a connected demonstration on an actual machine and robot; M4 integrates all hubs;
M5 qualifies the production profile; M6 is first paid pilot; M7 proves a second site; M8 is commercial
release. These gates are shared with Manufacturing, not additional elapsed phases.

EN-00 does not close M0, M1 or M2. Product work can proceed while Robotics Platform develops its
required subset. Physical integration must pass M3/M5; mock ERP or robot fixtures do not qualify it.

## EN-01 scoped read API (implemented, development maturity)

1. Development pair: Frappe v15.98.0 / ERPNext v15.87.2; synthetic fixtures with two Companies and
   three Manufacturing sites. A Manufacturing site maps to one Company and one warehouse subtree and
   is distinct from the Frappe site (ERP instance).
2. Least-privilege `Neuradix Integration Reader` role (Work Order read only) plus a server-side
   principal record; scope is bound to the authenticated user, and permission hooks confine the role
   on Frappe's generic routes. Users who lack the role, extra roles and disabled records are refused.
3. Versioned DTOs (contract 0.2.0-draft, JSON Schemas and observed examples), exact decimal strings,
   ERP-zone timestamps, opaque versions and keyset cursors; see [API contract](api-contract.md).
4. Authorized list/detail and deletion markers; closed, stopped, cancelled and amended orders and BOM
   changes are covered. No stock or document mutation exists.
5. Real Frappe site tests including HTTP token authentication; Manufacturing vendors the schemas and
   observed examples and decodes them in its Rust consumer tests.

Remaining for EN-01 acceptance: review of the site mapping and DTO by Manufacturing (MF-01/02),
named customer ERP configuration inventory (M0), and CI evidence on the merged revision. The
next companion increment is EN-02 (durable command receipt and outcome discovery), which depends on
agreed ERP-neutral commands from Manufacturing.

## Posting and maintenance rules for later increments

A command receipt and the resulting ERP operation must share an appropriate transaction boundary.
A repeated key with different content fails. A timeout means outcome unknown until discovered;
never infer that the ledger write failed. Record command/site/company/principal and document references.
Do not manually commit half a command or swallow a failed submission. Qualify concurrent requests.

Separate material request, draft issue and submitted consumption. Preserve chosen v15 serial/batch
handling, actual vs backflush policy, WIP, corrections and cancellation. Do not mutate historical
ledger entries merely to populate Manufacturing.

Asset Maintenance / Asset Maintenance Log remain recurrence authority in ERPNext-led mode. Distinguish
work physically complete, supervisor verified and equipment released; the last decision is not
inferred from a completed ERP schedule entry. Only one scheduler creates each maintenance occurrence.

## Definition of done

Each increment updates docs/status.md with executed evidence, fixtures, compatibility and known limits.
Keep v16 disabled until separately qualified. No stock-posting or hardware claim follows from a
successful app installation. Align release tags with Manufacturing and the Robotics device profile.
