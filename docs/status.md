# Current status and compatibility

Updated: 28 September 2026. EN-01 scoped identity and read-only Work Order API, **development**
maturity. Not connector certification (EN-05) and not an M2 acceptance claim.

| Area | Status |
|---|---|
| Installable Python/Frappe app metadata | Implemented |
| Capability metadata endpoint | Implemented; contract 0.2.0-draft; Guest and non-principals denied |
| Scoped integration identity | Implemented: `Neuradix Integration Reader` role (Work Order read only), principal and Manufacturing Site records, server-side scope |
| Work Order list/detail and deletion markers | Implemented read-only; submitted and cancelled orders; keyset pagination; exact decimals |
| Least-privilege enforcement | Route allowlist for principals (`auth_hooks`), scope hooks on Work Order and its child rows, explicit filters in every method |
| Durable transactional command receipts | Planned EN-02 |
| ERPNext stock/production posting | Planned EN-03; disabled (`post_stock`/`post_production` false) |
| Quality and maintenance synchronization | Planned EN-04 |
| Supported production connector | Pending EN-05 and physical integration qualification |
| Machinery control | Owned by Robotics Platform; never implemented here |

## EN-01 evidence

Executed on 28 September 2026 on disposable sites of the pinned pair (Frappe v15.98.0, ERPNext
v15.87.2, MariaDB 10.6, Redis 6, Python 3.11, Node 18):

- Real-site suite, 65 tests, passing on an upgraded site (`bench migrate`) and on a freshly created
  site (`after_install`); `uninstall-app` then left no Work Order Custom DocPerm, disabled the role
  and removed the DocTypes. Includes real HTTP token-authentication tests through Frappe's WSGI
  application.
  Covered: Guest denial, authenticated user without role, ERPNext Manufacturing User, role without
  principal, disabled principal and user, principal gaining another role, Administrator,
  unauthorized/unknown/disabled sites, identical not-found for foreign/draft/missing identifiers,
  403 for principals on `/api/resource`, `frappe.client` count/get/validate_link/child lists, `/api/v2`,
  `cmd` dispatch and non-API paths while other users keep their routes; in-process confinement of
  `get_list`, counts, child-table lists and document checks; role DocPerm required; no
  BOM/Item/Warehouse access; sharing does not escape the API; request parameters cannot widen scope; exact decimals beyond float precision, ERP time zone labelling,
  gapless keyset pagination across identical `modified` values, page-size and cursor validation,
  stopped/closed/cancelled/amended orders, BOM change through amendment, site-scoped deletion
  markers whose cursor never scans other scopes, restored and reused-name deletion markers,
  hidden cross-site amendment sources, `%` in scope names, sites refused after warehouse
  re-parenting makes them overlap, the role DocPerm required by all three read methods, and loud
  failure on out-of-contract stored values. Uninstall disables the role and restores standard Work
  Order permissions unless the copied rows were customized.
- Mutation checks: disabling the route allowlist, the query-condition hook, the child-row
  conditions, the document hook, the extra-role check, the explicit WIP filter, `%`-safe
  escaping, the overlap re-check, amendment-source scoping or the deletion DocPerm check each
  made the suite fail. Removing only the Company filter of the deletion scan did not, because its warehouse
  filters already imply the Company (a redundant layer).
- Fast checks: ruff, schema generation check, 19 unit tests, wheel build.
- A multi-agent review of the EN-01 diffs found 21 issues across the coordinated repositories;
  the companion ones (escaping, name reuse after deletion, restored markers, overlap drift,
  disclosure through `amended_from`, DocPerm on deletions, test and doc gaps) are fixed and
  covered by the tests above.
- Non-API paths (desk, private files) are refused by the route hook; on the asset-less test bench
  Frappe cannot render its HTML 403 page, so those paths are tested by invoking the hook with real
  werkzeug requests rather than through the WSGI application.

CI on the pull request is the authoritative record for the committed revision.

### Local environment deviations (not code changes)

The cloud workspace that produced the evidence above blocks `codeload.github.com` and
`api.github.com`. Frappe's `air-datepicker` JS dependency was therefore built from the same Git
commit into a yarn offline mirror, and `install-app` was run through a wrapper that answers Frappe's
required-app GitHub lookup locally (`erpnext` → `frappe/erpnext`). CI performs the standard steps.

## Compatibility

Qualified test target: Frappe v15.98.0 / ERPNext v15.87.2 only, with exact tags pinned in CI.
All other combinations, including v16, require separate acceptance. The broad v15 package
dependency range permits development installation; it is not a certification matrix.

Contract 0.2.0-draft replaces 0.1.0-draft: `maturity` is `development`, `read_work_orders` is
true, and `schema`, `read_contracts`, `limits`, `sync`, `principal` and `source` were added.
The capability endpoint now also answers integration principals. Manufacturing consumes the
contract from its vendored copy; update both repositories together.

## Known limits

- One Company and one warehouse subtree per Manufacturing site; orders spanning sites are excluded.
- Some ERPNext paths change required-item quantities or renamed references without a new
  `modified`; full reconciliation and detail refresh are required (see the API contract).
- Deletion markers come from Frappe's Deleted Document log and miss bulk company deletion.
- ERP timestamps inherit Frappe's naive local storage; the recommended overlap covers DST fall-back.
- The integration role's Custom DocPerm freezes Work Order's copied standard permissions on that
  site until reviewed (Frappe behaviour for any custom permission).
- No audit log of reads is written; access is recorded only by Frappe's request logging.
- Public File attachments are readable by anyone by Frappe design; attach nothing sensitive
  publicly to Work Orders.

Commercial milestones remain open. Update this file after each implementation increment.
