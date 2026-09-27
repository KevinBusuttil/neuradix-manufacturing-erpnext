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

## First next increment: EN-01 scoped read API

1. Agree one named development ERPNext/Frappe pair and synthetic company/site fixtures.
2. Define a least-privilege integration role and enforce server-side company/site access. Bind scope
   to authenticated identity; payload fields cannot expand it. Include users who lack the role.
3. Define stable Work Order DTOs, units, quantities, modified/version cursor and pagination.
4. Implement authorized list/detail using ERPNext/Frappe permissions; include closed/cancelled and
   changed BOM references. Do not add stock or document mutation shortcuts in the read increment.
5. Add real Frappe site tests and matching Rust contract fixtures. Publish method/version changes.

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
