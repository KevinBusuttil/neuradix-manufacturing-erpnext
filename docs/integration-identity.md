# Integration identity runbook

How a System Manager provisions, rotates and revokes the read-only principal used by a
Neuradix Manufacturing backend. Use synthetic data on development sites; never reuse test
credentials at a customer.

## Provision

1. Install or migrate the app. `after_install`/`after_migrate` create the `Neuradix Integration Reader`
   role (desk access off) and exactly one Work Order Custom DocPerm for it granting `read` only.
   Adding that first Custom DocPerm copies Work Order's standard permissions into Custom DocPerm, as
   Frappe's Role Permission Manager does; review ERPNext upgrades that change standard Work Order
   permissions on such sites. Uninstall restores the standard permissions if nobody edited the
   copies.
2. Create one `Neuradix Manufacturing Site` per physical site: a stable uppercase `site_id`, its
   Company and the root warehouse of that site's warehouse subtree. Subtrees of one Company must not
   overlap. Company and root warehouse cannot be changed afterwards. Re-parenting warehouses so
   that two sites overlap makes both unavailable until the tree or sites are corrected.
3. Create a dedicated user per Manufacturing deployment. Give it **only** the
   `Neuradix Integration Reader` role; any other role makes every call fail.
4. Create a `Neuradix Integration Principal` for that user and list only the sites it serves.
5. Generate the user's API key and secret from the User record and store them only in the
   Manufacturing backend's secret store (MF-02). Never place them in Flutter, device configuration
   or source control.
6. Call `capabilities` with the new credentials and check `principal.sites`.

The principal can call only the four GET read methods. Every other route, including
`/api/resource`, `frappe.client`, desk pages and private files, returns 403 for it.

## Rotate and revoke

- Rotate by generating a new secret, updating the backend, then confirming the old secret returns 401.
- Revoke immediately by disabling the user (token authentication then fails with 401) or the
  principal record (authenticated calls then fail with 403).
- Remove a site from the principal to narrow scope; disable a site record to withdraw it for everyone.

## Verify

The real-site test suite (`bench --site <site> run-tests --app neuradix_manufacturing_erpnext`) covers
Guest, role-less users, ERPNext Manufacturing Users, principals without records, disabled users,
disabled principals, principals that gain another role, unauthorized and unknown sites, direct
identifier probing, Frappe's generic list/count/document routes and token authentication over HTTP.
