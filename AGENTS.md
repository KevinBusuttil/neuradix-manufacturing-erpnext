# Working in the ERPNext companion

Read README.md, docs/status.md, docs/implementation-plan.md and docs/api-contract.md first.

- Preserve user changes and use a reviewable task branch.
- Keep ERP-specific transactional Python here; Flutter/Rust live in Manufacturing.
- ERPNext remains stock/accounting authority. Use validated document methods, not direct ledger SQL.
- No machinery/robot control, PLC credentials or independent maintenance recurrence engine here.
- Before business APIs, enforce server-side role/company/site scope and test negative access.
- Do not implement posting before durable command identity and outcome recovery.
- Preserve client ISNACK separately; do not copy customer settings, data or private commercial plans here.
- Keep docs/status.md and versioned contracts honest; list unexecuted integration checks explicitly.
- Run affected fast and disposable Bench checks from docs/development.md.
- Do not infer equipment readiness from ERP maintenance completion.
