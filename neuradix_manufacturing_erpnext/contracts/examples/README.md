# Observed contract examples

These are `message` bodies returned over HTTP by a real Frappe v15.98.0 / ERPNext v15.87.2 site
(MariaDB 10.6, time zone America/New_York) to the synthetic principal `nx-int-a1@example.test`,
captured by `neuradix_manufacturing_erpnext/tests/test_http_api.py` with
`NEURADIX_CONTRACT_CAPTURE_DIR` set. `errors.json` keeps only the HTTP status and Frappe `exc_type`
of each error case; Frappe error bodies are not part of this contract.

All companies, users, items and documents are synthetic test fixtures. `test.localhost` is the
disposable site name. The fast test `tests/test_contract_schemas.py` validates every example
against its schema; Manufacturing vendors these files verbatim with a SHA-256 manifest.
