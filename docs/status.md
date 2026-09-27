# Current status and compatibility

Updated: 27 September 2026. EN-00 foundation only.

| Area | Status |
|---|---|
| Installable Python/Frappe app metadata | Implemented scaffold |
| System Manager capability metadata endpoint | Implemented; Guest denied |
| Work Order reads | Planned EN-01 |
| Scoped production integration identity | Planned EN-01 |
| Durable transactional command receipts | Planned EN-02 |
| ERPNext stock/production posting | Planned EN-03 |
| Quality and maintenance synchronization | Planned EN-04 |
| Supported production connector | Pending EN-05 and physical integration qualification |
| Machinery control | Owned by Robotics Platform; never implemented here |

Initial integration test target is Frappe v15.98.0 / ERPNext v15.87.2, with the exact source tags
pinned in CI. All other combinations, including v16, require separate acceptance. The broad v15
package dependency range permits development installation; it is not a certification matrix.

The foundation PR and CI runs record executed validation and remaining environmental limits.
Commercial milestones remain open. Update this file after each implementation increment.
