# Testplan — OSAC-3058

## Overview

- **Feature:** OSAC-3058 — Configurable Named Roles
- **Total test cases:** 69
- **Requirements covered:** 13 of 13
- **Interface changes covered:** 12 of 12

Unit and component-integration cases belong to [DEV]; deployed
cross-component journeys belong to [QE]. Cases describe planned coverage,
not executed tests.

Unless stated otherwise, subjects are already provisioned and hold only the
bindings named in the case. Grant mutations use an authorized administrator.
Use valid payloads and accessible projects so unrelated checks do not mask the
permission being tested. Method names without a package mean public API
methods; supply the target tenant explicitly.

Project-scoped named roles are deferred. Project cases preserve the existing
ProjectMembership and Keycloak-group behavior.

## Test Cases

### FR-1: Method catalog of full service-qualified gRPC methods

#### TC-FR1-01: Permission documentation supports role authoring

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-3 | high | manual |

**Tier:** manual documentation verification ([DEV])

##### Preconditions

- API references and role-management guides for the running build are available.
- Cloud Provider Admin credentials and the internal catalog test fixture are available.

##### Steps

1. Compare the documented full method references and wildcard forms with the
   internal registry-derived catalog for the running build.
2. Use documented public and private method references to create and read a
   role through the existing API and generic CLI verbs.

##### Expected Results

- Documentation identifies complete service-qualified references such as
  `osac.public.v1.Clusters/Create` and `osac.private.v1.Volumes/Create`, plus
  `*`, package wildcards, and service wildcards and their scope.
- Documented references are accepted and stored verbatim. Discovery guidance
  uses documentation and existing Role listings; no permission-discovery
  service, CLI resource, or catalog-driven composer is required.

#### TC-FR1-02: Internal catalog includes grantable methods from both API layers

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-3 | medium | automated |

**Tier:** unit ([DEV])

##### Preconditions

- Catalog builder and proto registry descriptors for both API layers are available.

##### Steps

1. Build the internal catalog from the registry.
2. Compare its concrete references with the registered methods in
   `osac.public.v1` and `osac.private.v1`.
3. Inspect the exclusions and the package/service prefixes used for wildcard
   validation.

##### Expected Results

- Every grantable public and private method appears as a complete
  service-qualified reference; `Clusters/Signal` belongs only to the private
  layer when that is where it is registered.
- Infrastructure methods (metadata, reflection, health) and `Capabilities`
  are excluded. Wildcard expressions are authoring syntax, not catalog entries.
- Known package and service prefixes match the registry and support role
  validation and wildcard expansion without an external discovery endpoint.

#### TC-FR1-03: Catalog is derived from the running build

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-3 | medium | automated |

**Tier:** unit ([DEV])

##### Preconditions

- Registry-scan unit test harness available.

##### Steps

1. Register a stub service descriptor in the test registry.
2. Rebuild the internal catalog and inspect its entries.

##### Expected Results

- The stub service's methods appear in the catalog without any migration or
  configuration change; removing the descriptor removes them on rebuild.

#### TC-FR1-04: Role creation rejects unknown permission references

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-1 | high | automated |

**Tier:** component-integration ([DEV])

##### Preconditions

- Authenticated as a Cloud Provider Admin.

##### Steps

1. Create a Role with `spec.permissions` containing
   `"osac.public.v1.Clusters/Create"` and `"osac.public.v1.Nope/Fake"`.

##### Expected Results

- The request fails with `INVALID_ARGUMENT`.
- The error message names `"osac.public.v1.Nope/Fake"` as the offending
  entry; no Role row is created.

#### TC-FR1-05: Role creation rejects malformed wildcard references

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-12 | high | automated |

**Tier:** component-integration ([DEV])

##### Preconditions

- Authenticated as a Cloud Provider Admin.

##### Steps

1. Create a Role with `spec.permissions` containing
   `"osac.public.v1.Clusters/*"`, `"osac.public.v1.Nope/*"`,
   `"osac.public.v1.Clusters/Crea*"`, and `"*/Get"`.

##### Expected Results

- The request fails with `INVALID_ARGUMENT`.
- The error names `"osac.public.v1.Nope/*"` (unknown prefix),
  `"osac.public.v1.Clusters/Crea*"` (malformed form), and `"*/Get"`
  (unsupported verb-suffix form) as offending entries; no Role row is
  created.

### FR-2: Named roles as method sets with two authoring surfaces

#### TC-FR2-01: Cloud Provider Admin creates a platform-scoped role

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-1 | critical | automated |

**Tier:** component-integration ([DEV])

##### Preconditions

- A subject holding the seeded `cloud-provider-admin` binding.

##### Steps

1. Create a Role with `metadata.tenant = "shared"`, a title, and
   `spec.permissions = ["osac.public.v1.Clusters/Get",
   "osac.public.v1.Clusters/List"]`.
2. Get the Role by id.

##### Expected Results

- Create and Get both succeed; the stored `spec.permissions` equals the
  request.

#### TC-FR2-02: Tenant Admin creates a tenant-scoped role

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-1 | critical | automated |

**Tier:** component-integration ([DEV])

##### Preconditions

- A Tenant Admin subject in tenant `t1` (holds the seeded `tenant-admin`
  role).

##### Steps

1. Create a Role with `metadata.tenant = "t1"` and permissions drawn from the
   Tenant Admin's own effective set.

##### Expected Results

- The Role is created in tenant `t1` with the requested permissions.

#### TC-FR2-03: Tenant Admin cannot create a role in the shared tenant

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-1 | high | automated |

**Tier:** component-integration ([DEV])

##### Preconditions

- Tenant Admin subject in tenant `t1`.

##### Steps

1. Create a Role with `metadata.tenant = "shared"`.

##### Expected Results

- The request fails with `PERMISSION_DENIED` — `shared` is not an assignable
  tenant for the subject.

#### TC-FR2-04: Tenant-scoped roles are invisible outside their tenant

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-1 | high | automated |

**Tier:** component-integration ([DEV])

##### Preconditions

- A role exists in tenant `t1`; a Tenant User of tenant `t2` exists.

##### Steps

1. As a Tenant User of `t2`, call `Roles/List`.

##### Expected Results

- The response contains roles from `t2` and `shared` only; the `t1` role is
  absent.

#### TC-FR2-05: Role creation accepts and stores wildcard entries verbatim

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-12 | high | automated |

**Tier:** component-integration ([DEV])

##### Preconditions

- Authenticated as a Cloud Provider Admin.

##### Steps

1. Create a Role in `shared` with `spec.permissions =
   ["osac.public.v1/*", "osac.public.v1.Clusters/Create"]`.
2. Get the Role by id.

##### Expected Results

- Create and Get both succeed; the stored `spec.permissions` equals the request
  verbatim — wildcard entries are stored as written, never expanded or
  rewritten by the server.

#### TC-FR2-06: Stale wildcard references fail closed

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-12 | medium | automated |

**Tier:** unit ([DEV])

##### Preconditions

- Unit harness with a catalog populated from the test registry; a role
  `r-stale` containing `osac.public.v1.Missing/*` (a service absent from
  the catalog); a subject holding only `r-stale`.

##### Steps

1. Resolve the subject's effective permissions.
2. Evaluate any catalog method for the subject.
3. Attempt to create a new role containing `osac.public.v1.Missing/*`.

##### Expected Results

- The subject is denied every role-controlled method — the stale wildcard
  expands to nothing. Always-allowed surfaces remain available.
- The create fails with `INVALID_ARGUMENT` — write-time validation rejects
  unknown prefixes on new writes.

### FR-3: Runtime role management across API, CLI, and console

#### TC-FR3-01: Role lifecycle through the API

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-1 | critical | automated |

**Tier:** component-integration ([DEV])

##### Preconditions

- Cloud Provider Admin subject.

##### Steps

1. Create a Role; Update its `spec.title` via update mask; List roles
   filtered by name; Delete the Role.

##### Expected Results

- Each step succeeds; the List result reflects the update; after Delete, Get
   returns `NOT_FOUND`.

#### TC-FR3-02: CLI manages roles and role bindings through generic verbs

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-8 | high | automated |

**Tier:** component-integration ([DEV], `it/` CLI harness)

##### Preconditions

- `osac` CLI built with regenerated types; admin credentials.

##### Steps

1. Run `osac get role`, `osac create role <file>`, `osac edit role <name>`,
   `osac delete role <name>`, and `osac get rolebinding`.

##### Expected Results

- All verbs resolve the resource types through reflection and complete; the
  created role appears in `osac get role` output.

#### TC-FR3-03: Console role authoring and assignment surfaces

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-9 | high | manual |

**Tier:** manual UI verification ([DEV] UI task)

##### Preconditions

- Console deployed with regenerated types; CPA and Tenant Admin sessions;
  tenant `t1` and an existing target user. Record the test role name.

##### Steps

1. Select `t1`, open role management, and enter the full permission strings
   `osac.public.v1.Clusters/Get` and `osac.public.v1.Clusters/List` directly.
2. Save, then edit the role to use `osac.public.v1.Clusters/*`; save again.
3. Attempt to save an unknown reference and a malformed wildcard.
4. Open RoleBindings, bind the target user to the role, and reopen both records.
5. As Cloud Provider Admin, author a role in `shared`.

##### Expected Results

- Forms provide guidance linking to permission documentation and accept
  exact references and supported wildcards; saved entries remain verbatim.
- Server validation errors appear on save; invalid edits leave the saved role
  unchanged. Existing Role listings supply the assignment picker.
- The assignment references the selected role in `t1`; the CPA can author in
  `shared`, and the Tenant Admin's authoring is limited to their own tenant.

### FR-4: Unrestricted Cloud Provider Admin composition

#### TC-FR4-01: CPA composes a role containing administrator-level methods

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-5 | high | automated |

**Tier:** component-integration ([DEV])

##### Preconditions

- Subject holding `cloud-provider-admin`.

##### Steps

1. Create a Role in `shared` whose permissions include `osac.public.v1.Users/Delete`
   and `osac.public.v1.Roles/Delete`.

##### Expected Results

- The Role is created; no method is rejected as administrator-only.

#### TC-FR4-02: CPA composes a role with private-layer methods

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-5 | high | automated |

**Tier:** component-integration ([DEV])

##### Preconditions

- Subject holding `cloud-provider-admin`.

##### Steps

1. Create a Role in `shared` containing a private-layer method (for
   example `osac.private.v1.Volumes/Create`).

##### Expected Results

- The Role is created; no method is rejected as administrator-only.

#### TC-FR4-03: Wildcard holders gain newly cataloged methods automatically

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-12 | critical | automated |

**Tier:** unit ([DEV])

##### Preconditions

- Registry-scan unit test harness (as TC-FR1-03); a subject holding a role
  with `permissions = ["*"]`; a subject holding an explicit role listing every
  pre-existing catalog permission.

##### Steps

1. Register a stub service descriptor in the test registry and rebuild the
   catalog.
2. Evaluate the stub service's method for both subjects.

##### Expected Results

- The wildcard holder is allowed the new method without any role edit or
  migration.
- The explicit-set holder is denied — enumerated roles do not grow with the
  catalog.

### FR-5: Assignment bounded by the assigner's permissions

#### TC-FR5-01: Tenant Admin assigns a role; the union of held roles applies

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-2 | critical | automated |

**Tier:** component-integration ([DEV])

##### Preconditions

- Tenant Admin in `t1`; user `u1` in `t1` holding only `Clusters/Get`;
  a tenant-scoped role `r1` with `Clusters/Delete`.

##### Steps

1. As the Tenant Admin, create a RoleBinding granting `r1` to `u1`.
2. As `u1`, Get and Delete a cluster in `t1`.

##### Expected Results

- The binding is created; both methods succeed through the combined grants
  in `t1`.

#### TC-FR5-02: Tenant Admin cannot assign a provider role with platform scope

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-5 | critical | automated |

**Tier:** component-integration ([DEV])

##### Preconditions

- Tenant Admin in `t1`; the seeded `cloud-provider-admin` role exists in
  `shared`.

##### Steps

1. As the Tenant Admin, create a RoleBinding in `t1` referencing
   `cloud-provider-admin`.

##### Expected Results

- The request fails with `PERMISSION_DENIED` — the role's permission set
  is not a subset of the assigner's effective permissions.

#### TC-FR5-03: Tenant Admin cannot author a role exceeding their permissions

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-5 | critical | automated |

**Tier:** component-integration ([DEV])

##### Preconditions

- Tenant Admin in `t1` whose effective set lacks `Users/Delete` (hold a
  narrowed tenant-admin variant if needed).

##### Steps

1. Create a Role in `t1` containing `osac.public.v1.Users/Delete`.

##### Expected Results

- The request fails with `PERMISSION_DENIED` by the authoring subset rule.

#### TC-FR5-04: Tenant administration cannot place grants in another tenant

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-2, IC-5 | critical | automated |

**Tier:** component-integration ([DEV])

##### Preconditions

- Tenant Admin bound only in `t1`; an existing user in `t2`.

##### Steps

1. As that admin, create a RoleBinding in `t2` for the `t2` user.

##### Expected Results

- The request fails with `PERMISSION_DENIED`; no binding is created.

#### TC-FR5-05: A narrowed subject cannot assign beyond its own grants

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-5 | high | automated |

**Tier:** component-integration ([DEV])

##### Preconditions

- Subject `n1` in `t1` holds only a custom role containing
   `RoleBindings/Create` and `Clusters/Get` — nothing broader.

##### Steps

1. As `n1`, attempt to bind another subject to the seeded `tenant-admin`
   role.

##### Expected Results

- The request fails with `PERMISSION_DENIED`; the target role's set is not a
  subset of `n1`'s effective permissions.

#### TC-FR5-06: Tenant super-admin cannot author or assign beyond the public layer

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-5 | high | automated |

**Tier:** component-integration ([DEV])

##### Preconditions

- Tenant Admin in `t1` holding the seeded `tenant-admin` role
  (`osac.public.v1/*`).

##### Steps

1. As the Tenant Admin, create a Role in `t1` with `spec.permissions = ["*"]`.
2. As the Tenant Admin, create a Role in `t1` containing a private-layer
   method (for example `osac.private.v1.Volumes/Create`).

##### Expected Results

- Both requests fail with `PERMISSION_DENIED` — under the
  expanded-subset rule, the written role's expansion (private-layer
  methods) is not a subset of the Tenant Admin's effective permissions.

#### TC-FR5-07: Tenant super-admin delegates any public method within the tenant

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-5 | critical | automated |

**Tier:** component-integration ([DEV])

##### Preconditions

- Tenant Admin in `t1` holding the seeded `tenant-admin` role; Tenant User
  `u1` in `t1`.

##### Steps

1. As the Tenant Admin, create a Role in `t1` containing a public-layer
   method the pre-change tenant-admin surface did not include, plus a
   second public method.
2. Bind the new role to `u1`.
3. As `u1`, call both methods.

##### Expected Results

- The role is created and assigned — the written set is a subset of the
  Tenant Admin's expanded effective set; `u1` can call both methods within
  `t1`.

#### TC-FR5-08: Platform staffing lets a CPA bind in a tenant without reach

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-5 | high | automated |

**Tier:** component-integration ([DEV])

##### Preconditions

- A CPA holding `cloud-provider-admin` only through the seeded
  `system`-placed binding (no binding in tenant `t1`); Tenant User `u1` in
  `t1`; Tenant Admin of `t1`.

##### Steps

1. As the CPA, create a RoleBinding in `t1` granting the seeded
   `tenant-admin` role to `u1`.
2. As the Tenant Admin of `t1`, attempt to create a RoleBinding in `t2`.

##### Expected Results

- Step 1 succeeds — the CPA's Roles/RoleBindings write methods come from a
  `system`-placed binding, which carries any-tenant placement (platform
  staffing), bounded by the subset ceiling.
- Step 2 fails with `PERMISSION_DENIED` — the Tenant Admin's
  Roles/RoleBindings grant is tenant-placed and does not cross tenant
  boundaries.

#### TC-FR5-09: Role edits check every tenant with an assignment

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-1, IC-5 | critical | automated |

**Tier:** component-integration ([DEV])

##### Preconditions

- A shared role `r1` grants `Clusters/Get` and is assigned in `t1` and `t2`.
- The editor holds shared `Roles/Update`, `Clusters/Get`, and
  `Clusters/Delete`; holds `Clusters/Get` in both ordinary tenants; and
  holds `Clusters/Delete` only in `t1`. No `system` binding exists.

##### Steps

1. Update only `r1.spec.permissions` to add `Clusters/Delete`.
2. Grant the editor `Clusters/Delete` in `t2` and retry.

##### Expected Results

- Step 1 returns `PERMISSION_DENIED`; the stored role and both grants stay
  unchanged. Step 2 succeeds once the editor also holds the permission in
  the role's defining tenant and every assigned tenant.

#### TC-FR5-10: Public and private mutations enforce the same invariants

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-1, IC-2, IC-5 | critical | automated |

**Tier:** component-integration ([DEV])

##### Preconditions

- An actor holds explicit public and private Roles/RoleBindings CRUD
  permissions in `t1`, plus `Clusters/Get`; no staffing authority.
- An administrator has prepared a narrow role and a role containing
  `Clusters/Delete`, which the actor does not hold.
- Tenant `t1` selects the narrow role through `spec.default_role`.
  Another unbound role is referenced only by a Tenant default-role selection.

##### Steps

1. Through each API, Create and masked Update a role with an unknown
   permission, then with the unheld `Clusters/Delete` permission.
2. Through each API, Create and masked Update a binding to the broader role.
3. Repeat with a valid `Clusters/Get` role and binding.
4. Through each API, try to delete the bound role and the role referenced
   only by a Tenant's `spec.default_role`.

##### Expected Results

- Unknown permissions return `INVALID_ARGUMENT`; ceiling violations return
  `PERMISSION_DENIED`. Rejected updates leave stored objects unchanged.
- Valid narrow writes succeed through both APIs.
- Both APIs reject deletion of either referenced role with
  `FAILED_PRECONDITION`. Private permission does not bypass validation.

#### TC-FR5-11: Explicit permissions cannot delegate wildcard authority

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-5, IC-12 | critical | automated |

**Tier:** component-integration ([DEV])

##### Preconditions

- An actor holds every current catalog permission through explicit entries
  in `t1`, with no wildcard grants. An admin has prepared wildcard roles.

##### Steps

1. Attempt to Create a role, Update a role, and assign a role using each
   of `*`, `osac.public.v1/*`, and `osac.public.v1.Clusters/*`.
2. Repeat using explicit permission entries instead.

##### Expected Results

- Every wildcard write returns `PERMISSION_DENIED`, even though its current
  expansion is a subset of the actor's permissions.
- Equivalent explicit grants succeed; no rejected write changes stored grants.

#### TC-FR5-12: Wildcard delegation requires matching or broader authority

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-5, IC-12 | critical | automated |

**Tier:** component-integration ([DEV])

##### Preconditions

- Actors in `t1` hold, respectively, `*`, `osac.public.v1/*`, or
  `osac.public.v1.Clusters/*`, plus explicit role/binding write permissions.
- For rejected wildcard attempts, also grant explicit permissions covering
  the requested expansion, without adding a covering wildcard.

##### Steps

1. For each actor, author and assign roles containing the same wildcard.
2. Delegate `osac.public.v1.Clusters/*` from the package-wildcard actor,
   and package/service wildcards from the `*` actor.
3. Try a broader wildcard and an unrelated service wildcard from the
   Clusters-wildcard actor; try `*` and a private wildcard from the
   public-package actor.

##### Expected Results

- Matching and narrower wildcard grants succeed.
- Broader and unrelated wildcard grants return `PERMISSION_DENIED`, even
  when the actor has explicit permissions covering their current expansion.

#### TC-FR5-13: Delegation cannot borrow permissions from another tenant

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-5, IC-12 | critical | automated |

**Tier:** component-integration ([DEV])

##### Preconditions

- An actor holds role/binding write permissions in `t1` and `t2`,
  `Clusters/Get` in `t1`, and `osac.public.v1.Clusters/*` only in `t2`;
  no staffing authority.

##### Steps

1. In `t1`, attempt to author and assign roles granting `Clusters/Delete`
   and `osac.public.v1.Clusters/*`.
2. Repeat in `t2`.

##### Expected Results

- Both grants fail with `PERMISSION_DENIED` in `t1` and succeed in `t2`.
- Neither explicit permissions nor wildcard authority transfers across tenants.

#### TC-FR5-14: Role edits include default-role selections in the assignment ceiling

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-1, IC-5, IC-6 | critical | automated |

**Tier:** component-integration ([DEV])

##### Preconditions

- A shared role `r-default` grants `Clusters/Get` and is selected by
  `t1.spec.default_role` and `t2.spec.default_role`, with no RoleBindings yet.
- The editor holds public and private Roles/Update in `shared`, and Get in
  `shared`, `t1`, and `t2`, but Delete only in `shared` and `t1`; no staffing
  authority.

##### Steps

1. Through public and private APIs, attempt a masked role edit adding
   `Clusters/Delete`.
2. Grant Delete in `t2` and retry.
3. Repeat with a service wildcard, first without and then with a covering
   wildcard held in every affected tenant.

##### Expected Results

- Missing explicit or wildcard delegation authority in any default-using
  tenant returns `PERMISSION_DENIED`; rejected writes leave the role unchanged.
- Writes succeed only when the authoring and delegation ceilings are met in
  the defining tenant and every tenant selecting the default, even before
  users onboard.

### FR-6: Propagation without re-login or redeployment

#### TC-FR6-01: A new grant takes effect without token refresh

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-4 | critical | automated |

**Tier:** component-integration ([DEV])

##### Preconditions

- Existing user `u1` in `t1` with no bindings; Tenant Admin authenticated
  separately.

##### Steps

1. As `u1`, call `Clusters/Create` — denied.
2. As the Tenant Admin, grant `u1` a role containing `Clusters/Create`.
3. As `u1`, call `Clusters/Create` again with the same bearer token.

##### Expected Results

- Step 1 returns `PERMISSION_DENIED`; step 3 succeeds without `u1`
  re-authenticating.

#### TC-FR6-02: Revocation denies subsequent requests

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-4 | critical | automated |

**Tier:** component-integration ([DEV])

##### Preconditions

- `u1` holds a binding granting `Clusters/Create`.

##### Steps

1. Delete the RoleBinding.
2. As `u1`, call `Clusters/Create` with the same token.

##### Expected Results

- The call returns `PERMISSION_DENIED`.

#### TC-FR6-03: Role edits apply to all holders

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-4 | critical | automated |

**Tier:** component-integration ([DEV])

##### Preconditions

- Two users hold role `r1` containing `Clusters/Get` and `Clusters/List`.

##### Steps

1. Update `r1` to remove `Clusters/List`.
2. As each holder, call `Clusters/List` and `Clusters/Get` with unchanged
   tokens.

##### Expected Results

- `Clusters/List` returns `PERMISSION_DENIED` for both holders;
  `Clusters/Get` still succeeds for both.

#### TC-FR6-04: Missing roles and resolver errors fail closed

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-4 | high | automated |

**Tier:** unit ([DEV])

##### Preconditions

- A resolver fixture contains a dangling role reference and a separate
  valid binding granting `Clusters/Get`.

##### Steps

1. Resolve and evaluate permissions with the dangling reference present.
2. Inject a database lookup failure and repeat a role-controlled request.

##### Expected Results

- The missing role grants nothing; the valid binding still applies.
- The database failure returns `INTERNAL`; no cached or partial allow is used.

### FR-7: Guarded deletion

#### TC-FR7-01: Deleting a role with active bindings is rejected

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-1 | high | automated |

**Tier:** component-integration ([DEV])

##### Preconditions

- Role `r1` referenced by an active RoleBinding.

##### Steps

1. Call `Roles/Delete` for `r1`.

##### Expected Results

- The request fails with `FAILED_PRECONDITION`; the message names the
  referencing binding; the Role still exists.

#### TC-FR7-02: Deletion succeeds once assignments are removed

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-1 | medium | automated |

**Tier:** component-integration ([DEV])

##### Preconditions

- Role `r1` with bindings (from TC-FR7-01), with no Tenant default-role references.

##### Steps

1. Delete all bindings referencing `r1`.
2. Call `Roles/Delete` for `r1`.

##### Expected Results

- The delete succeeds; Get returns `NOT_FOUND`.

#### TC-FR7-03: Deleting a seeded role with active bindings is rejected

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-1 | high | automated |

**Tier:** component-integration ([DEV])

##### Preconditions

- Migration 135 applied (the emergency binding in the `system` tenant
  references `system-emergency-admin`).

##### Steps

1. As a Cloud Provider Admin, call `Roles/Delete` for
   `system-emergency-admin`.

##### Expected Results

- The request fails with `FAILED_PRECONDITION`, naming the referencing
  binding — seeded roles use the same reference guards as custom roles.

#### TC-FR7-04: Seeded roles are deletable once unreferenced

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-1 | medium | automated |

**Tier:** component-integration ([DEV])

##### Preconditions

- Migration 135 applied; a seeded role referenced by neither bindings nor
  Tenant default-role selections (for example an unused viewer role).

##### Steps

1. As a Cloud Provider Admin, call `Roles/Delete` for the unreferenced
   seeded role.

##### Expected Results

- The delete succeeds; Get returns `NOT_FOUND` — there is no
  deletion-protected role class; recovery is re-creating the role (§4.3).

#### TC-FR7-05: Tenant default-role references guard deletion

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-1, IC-6 | high | automated |

**Tier:** component-integration ([DEV])

##### Preconditions

- A shared role is selected as the platform default and as the override in
  two ordinary tenants; no RoleBindings reference it. CPA credentials exist.

##### Steps

1. Through public and private APIs, attempt to delete the role.
2. Replace the platform default and one tenant's selection, then retry Delete.
3. Clear the remaining tenant override and retry Delete.

##### Expected Results

- Deletion returns `FAILED_PRECONDITION` while any default-role reference
  remains; the error names the referencing Tenants.
- Once all references are replaced or cleared, deletion succeeds. No seeded
  or custom role has a separate deletion-protected status.

### FR-8: Multiple roles; union semantics; no exclusions

#### TC-FR8-01: A user holds multiple roles with union access

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-4 | high | automated |

**Tier:** component-integration ([DEV])

##### Preconditions

- `u1` holds role `rA` (`Clusters/Get`) and role `rB` (`Subnets/Create`),
  both bound in `t1`.

##### Steps

1. As `u1`, call `Clusters/Get` and `Subnets/Create`.

##### Expected Results

- Both calls succeed in `t1` — access combines roles within that tenant.

#### TC-FR8-02: Roles combine freely with no conflict rules

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-4 | medium | automated |

**Tier:** component-integration ([DEV])

##### Preconditions

- Two roles whose personas would conflict under a separation-of-duties
  regime (for example a writer role and an auditor-style reader role).

##### Steps

1. Grant both roles to one user.

##### Expected Results

- The assignment succeeds; no exclusivity check runs. Permissions combine
  within each binding tenant.

#### TC-FR8-03: Permissions remain attached to their binding tenants

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-4 | critical | automated |

**Tier:** component-integration ([DEV])

##### Preconditions

- `u1` holds `Clusters/Get` only in `t1` and `Clusters/Delete` only in `t2`.
- Both tenants contain clusters; `u1` has no other grants.

##### Steps

1. Get a cluster in each tenant.
2. Delete a cluster in each tenant.
3. Give `u1` an organization claim naming an additional tenant with no binding
   and attempt a resource read there, retaining the already-provisioned User.

##### Expected Results

- Get succeeds only in `t1`; Delete succeeds only in `t2`.
- Other attempts fail without returning or changing the target object.
- Organization membership alone does not grant resource access.

#### TC-FR8-04: List filters by the specific permission before pagination

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-4 | critical | automated |

**Tier:** component-integration ([DEV])

##### Preconditions

- `u1` holds `Clusters/List` in `t1`, `Clusters/Get` in `t2`, and
  `Subnets/List` in `t3`; no staffing authority.
- Each tenant has multiple clusters and subnets in accessible projects.

##### Steps

1. List clusters across all pages, with a small page size and a client filter
   matching objects across tenants. Check totals if the API returns them.
2. List subnets with the same setup.

##### Expected Results

- Cluster results and totals include only eligible `t1` objects; subnet
  results and totals include only eligible `t3` objects.
- Get permission and another resource's List permission do not widen results.
- Unauthorized rows neither consume page slots nor affect totals.

#### TC-FR8-05: Mutations check placement and every stored target

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-4 | high | automated |

**Tier:** component-integration ([DEV])

##### Preconditions

- A subject holds the tested resource's Create/Update permissions in `t1`
  only. A second subject holds Create in both `t1` and `t2`.
- Valid resources exist in both tenants.

##### Steps

1. Create with an explicit authorized tenant, then an unauthorized tenant.
2. Omit the tenant for each subject; repeat with a subject whose only Create
   grant is in `shared` or `system`.
3. Update a `t1` object to change its tenant; try updating a `t2` object while
   claiming `t1` in the payload.
4. For any supported multi-object mutation, include an unauthorized target.

##### Expected Results

- Explicit placement succeeds only where authorized. An omitted tenant
  selects the sole eligible ordinary tenant; ambiguous or absent ordinary
  placement returns `INVALID_ARGUMENT`, never defaulting to `shared`/`system`.
- Tenant changes return `INVALID_ARGUMENT`; spoofing payload metadata cannot
  authorize a stored target. Rejected mutations leave objects unchanged.
- Multi-object operations check all targets before writing.

### FR-9: Predefined capability roles

#### TC-FR9-01: Seeded capability roles exist and are assignable

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-10 | high | automated |

**Tier:** component-integration ([DEV])

##### Preconditions

- Migration 135 applied.

##### Steps

1. List roles in `shared`.
2. As a Tenant Admin, bind `cluster-creator` to a tenant user.
3. As that user, call `Clusters/Create`.

##### Expected Results

- `cluster-creator` and `vm-viewer` appear in the listing; the bound user
  can create clusters.

#### TC-FR9-02: Binding picker presents predefined roles

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-9 | medium | manual |

**Tier:** manual UI verification ([DEV] UI task)

##### Preconditions

- Console deployed; Tenant Admin session in `t1`; seeded shared roles
  and one custom role in `t1`.

##### Steps

1. From `t1`'s RoleBindings page, create a binding and expand the role picker.
2. Search for `cluster-creator`, then the custom role; select and save each
   in separate bindings and reopen them to verify the selected role.
3. In `t1`'s settings, select a local role, replace it with a shared role,
   then select inherit-platform-default. Reopen settings after each save.
4. As a CPA, select the platform default in the `shared` Tenant's settings.

##### Expected Results

- Seeded shared and tenant-local roles are searchable and assignable.
  Roles from unrelated tenants are absent; saved bindings reference the
  selected roles. Grouping and ordering follow the console's agreed layout.
- Tenant settings persist the selected `spec.default_role`; inheritance clears
  the override. CPA settings update the shared Tenant's platform selection.

### FR-10: Default role at onboarding

#### TC-FR10-01: A new user's first request succeeds and assigns the default

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-6 | critical | automated |

**Tier:** component-integration ([DEV])

##### Preconditions

- Migration 135 applied; `shared.spec.default_role` references the seeded
  `tenant-user` role, which grants `Clusters/List`.
- Tenant `t1` has no default override; a brand-new Keycloak user in `t1`'s
  organization has a fresh token.

##### Steps

1. As the new user, call any default-role method (for example
   `Clusters/List`).

##### Expected Results

- The call succeeds; a User row exists for the user; a RoleBinding in `t1`
  references the platform default role and the new user.

#### TC-FR10-02: Tenant default selection and replacement affect future onboarding only

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-6, IC-8 | high | automated |

**Tier:** component-integration ([DEV], `it/` CLI harness)

##### Preconditions

- Migration 135 applied; `shared.spec.default_role` selects `tenant-user`.
- Tenant Admin in `t1` can manage the Tenant and assign the test roles.
- Existing roles `r-override` and `r-next` in `t1` grant `Clusters/Get`.

##### Steps

1. Using generic CLI verbs, update `t1.spec.default_role` to reference
   `r-override` and read the Tenant back.
2. As a brand-new user of `t1`, make a first `Clusters/Get` request.
3. Replace `t1.spec.default_role` with `r-next`; onboard another new user.
4. Inspect both users' bindings and the stored Tenant selection.

##### Expected Results

- The Tenant stores one RoleReference; replacing it selects the new role
  without a duplicate-default conflict or a uniqueness index.
- The first user receives `r-override` and keeps that binding after replacement;
  the second receives `r-next`. Each request succeeds using its selected role.

#### TC-FR10-03: Clearing the override inherits the platform default

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-6 | high | automated |

**Tier:** component-integration ([DEV])

##### Preconditions

- Migration 135 applied; `shared.spec.default_role` references `tenant-user`.
- `t1.spec.default_role` selects `r-override`; an existing user holds its
  onboarding binding. The Tenant Admin can update `t1`.

##### Steps

1. Clear `t1.spec.default_role` using a Tenant update mask.
2. As a brand-new user of `t1`, make a first `Clusters/List` request.
3. Inspect the new user's binding and the existing user's binding.

##### Expected Results

- The new user's binding references the platform default and the request
  succeeds. Clearing the override means inheritance, not disabled onboarding.
- The existing user's binding is unchanged.

#### TC-FR10-04: A user with no assignment is denied everything

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-6 | critical | automated |

**Tier:** component-integration ([DEV])

##### Preconditions

- Existing user whose every binding has been deleted.

##### Steps

1. As that user, call a default-role method and a metadata-exempt method
   (`Capabilities/Get`).

##### Expected Results

- The default-role method returns `PERMISSION_DENIED`; `Capabilities/Get`
  still succeeds (always-allowed surface).

#### TC-FR10-05: CPA replaces the platform default through the shared Tenant

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-6 | medium | automated |

**Tier:** component-integration ([DEV])

##### Preconditions

- Migration 135 applied; `shared.spec.default_role` references `tenant-user`.
- Another shared role grants `Clusters/Get`; `t1` inherits the platform
  default and `t2` selects its own override. CPA and Tenant Admin sessions exist.

##### Steps

1. As the Tenant Admin, attempt to change `shared.spec.default_role`.
2. As the CPA, replace it with the other shared role.
3. Onboard new users in `t1` and `t2` and inspect their bindings.

##### Expected Results

- The Tenant Admin receives `PERMISSION_DENIED`; the CPA update succeeds.
- New `t1` users receive the newly selected shared role; `t2` users keep the
  tenant override. Existing users' assignments are unchanged.

#### TC-FR10-06: A revoked default is not resurrected

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-6 | critical | automated |

**Tier:** component-integration ([DEV])

##### Preconditions

- An existing, provisioned user whose default binding was revoked (from
  TC-FR10-04 state).

##### Steps

1. Make further requests as that user.

##### Expected Results

- Requests to role-gated methods remain `PERMISSION_DENIED`; the JIT
  provisioner does not recreate the default binding because the User row
  already exists.

#### TC-FR10-07: Tenant default-role references validate through both APIs

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-6 | high | automated |

**Tier:** component-integration ([DEV])

##### Preconditions

- CPA credentials; tenant-local and shared roles, including same-named roles;
  a role defined only in an unrelated tenant; an existing `t1` selection.
- Use isolated fixtures for each API and Create/Update path, including roles
  and permissions prepared for the tenant being created.

##### Steps

1. Through public and private Tenant Create/Update paths, select roles by ID
   and by name, testing tenant-local lookup and fallback to `shared`.
2. Try a malformed reference, an unrelated tenant's role by ID, and a
   nonexistent role. On `shared`, try selecting an ordinary tenant's role.
3. Test masked Updates where an invalid default is outside the mask, then
   where that field is included.

##### Expected Results

- Valid local/shared references succeed; tenant-local names take precedence
  over shared names. The shared Tenant accepts only roles defined in `shared`.
- Malformed or out-of-scope references return `INVALID_ARGUMENT`; missing
  roles return `FAILED_PRECONDITION`. Rejected writes leave no partial changes.
- Validation uses the final Tenant after the mask is applied; fields outside
  the mask do not replace the stored selection.

#### TC-FR10-08: Selecting a default enforces assignment and wildcard ceilings

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-5, IC-6 | critical | automated |

**Tier:** component-integration ([DEV])

##### Preconditions

- An actor can manage `t1` but initially lacks RoleBindings write permission.
- Shared/local roles grant Get, Delete, or a Clusters service wildcard.
  The actor holds Get in `t1`, Delete only in `t2`, and no staffing authority.
- Use isolated fixtures for each API and Create/Update path; Create fixtures
  pre-grant the actor the tested permissions in the prospective tenant.

##### Steps

1. Through public and private Tenant Create/Update paths, attempt to select
   the Get role without RoleBindings write permission; grant it and retry.
2. Attempt to select the Delete role in `t1`.
3. Grant explicit coverage of every Clusters method and select the wildcard
   role, then grant a covering wildcard and retry.
4. Repeat without permission to manage the target Tenant.

##### Expected Results

- Selecting a default requires both Tenant management and RoleBinding write
  permission plus every selected permission in the target tenant.
- Permissions held only in `t2` cannot authorize a `t1` default; explicit
  coverage cannot authorize wildcard delegation. Violations return
  `PERMISSION_DENIED` without changing the selection or creating the Tenant.
- Valid selections succeed once all assignment and wildcard ceilings are met.

#### TC-FR10-09: Onboarding is atomic and handles absent or unresolved defaults

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-6 | critical | automated |

**Tier:** component-integration ([DEV])

##### Preconditions

- JIT provisioning harness with database fault injection and fresh human users.
- A valid default role, a fixture with neither tenant nor platform selection,
  and fixtures with configured but unresolved tenant/platform references.

##### Steps

1. With a valid default selected, inject failure into each of the User and
   RoleBinding writes; retry the request after removing the fault.
2. With neither default selected, make a role-controlled first request.
3. With an unresolved configured reference, attempt first requests, including
   a missing tenant override while a valid platform default exists.

##### Expected Results

- A write failure returns `INTERNAL` and rolls back both rows. Retry creates
  one User and one binding, idempotent by their natural keys, before authorization.
- No configured default creates the User without a binding and continues to
  authorization; the role-controlled request is denied without a grant.
- A configured unresolved reference returns `INTERNAL` and rolls back
  provisioning; it does not silently fall back to a different role.

### FR-11: Tenant Users see held roles and what they permit

#### TC-FR11-01: Rules review preserves role identity and per-tenant grants

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-7 | high | automated |

**Tier:** component-integration ([DEV])

##### Preconditions

- `u1` has bindings in `t1` and `t2` to distinct roles with the same name:
  one grants `Clusters/Get`, the other `Clusters/Delete`.

##### Steps

1. As `u1`, call `SelfSubjectRulesReviews/Create`.

##### Expected Results

- `bindings` identifies each binding ID/tenant and role ID/name/defining
  tenant, with authored permissions.
- `tenant_rules` grants Get only in `t1` and Delete only in `t2`; no global
  union implies either permission in the other tenant.

#### TC-FR11-02: `osac whoami` renders roles from the rules review

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-8 | high | automated |

**Tier:** component-integration ([DEV], `it/` CLI harness)

##### Preconditions

- `u1` holds known roles; `whoami` built on the new surface.

##### Steps

1. Run `osac whoami`.

##### Expected Results

- Output groups grants by binding tenant and distinguishes same-named roles.
- Revoke a binding and rerun with the same token: the grant disappears.
  Grant output comes from the rules review rather than `realm_access.roles`.

#### TC-FR11-03: Rules review shows authored wildcards and scoped expansion

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-7 | high | automated |

**Tier:** component-integration ([DEV])

##### Preconditions

- `u1` holds a role with `permissions = ["osac.public.v1.Clusters/*"]`
  bound only in `t1`.

##### Steps

1. As `u1`, call `SelfSubjectRulesReviews/Create`.

##### Expected Results

- The held-role entry lists the permission set verbatim
  (`["osac.public.v1.Clusters/*"]`).
- `tenant_rules` for `t1` contains every expanded public `Clusters` method.
  No other tenant acquires those permissions. Clients need no pattern matching.

#### TC-FR11-04: Rules review separates staffing and shared reads

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-7 | high | automated |

**Tier:** component-integration ([DEV])

##### Preconditions

- A CPA holds `*` only through a `system` binding; a tenant user holds
  `Roles/Get` and `Roles/List` only in `t1`; a third existing user has no grants.

##### Steps

1. Call `SelfSubjectRulesReviews/Create` as each subject.

##### Expected Results

- The CPA has `system` rules and separate `staffing_permissions`; no ordinary
  tenant-resource grants are implied.
- The tenant user's `shared_read_permissions` includes shared Roles reads,
  without shared write authority.
- The unassigned user can inspect their own empty grants. Responses contain
  only the caller's bindings.

#### TC-FR11-05: Console capabilities follow the selected tenant

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-9 | high | manual |

**Tier:** manual UI verification ([DEV] UI task)

##### Preconditions

- Console deployed; `u1` can read clusters in `t1` and manage clusters in
  `t2`. A CPA has only a `system` binding.

##### Steps

1. Sign in as `u1`; select `t1`, then `t2`, and inspect cluster actions.
2. Sign in as the CPA and inspect tenant role administration and resource actions.

##### Expected Results

- Cluster actions follow the selected tenant's permissions.
- CPA staffing enables role administration without implying tenant-resource
  permissions; shared reads are shown separately.

### FR-12: Existing service accounts keep their access

#### TC-FR12-01: Seeded controller binding preserves full admin access

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-10 | critical | automated |

**Tier:** component-integration ([DEV], `it/`)

##### Preconditions

- Service deployed with the controller credentials from the chart defaults.

##### Steps

1. Authenticate as `service-account-osac-controller` via client credentials.
2. Call an admin-surface method (for example `Roles/Create`) and a
   tenant-scoped resource method in a provisioned tenant.

##### Expected Results

- Both calls succeed — the platform-level method through the seeded
  `system`-placed binding (with platform staffing for placements), the
  tenant resource method through the per-tenant seeded binding.

#### TC-FR12-02: CSI driver identity is scoped to private Volume methods

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-10 | critical | automated |

**Tier:** component-integration ([DEV])

##### Preconditions

- CSI driver service account bound to `osac-csi-driver` only in `t1`.

##### Steps

1. Authenticate as the CSI driver service account.
2. Call `osac.private.v1.Volumes/Create`.
3. Call `osac.public.v1.Clusters/Create` in `t1`.
4. Call the same private Volume method in `t2`.

##### Expected Results

- Step 2 succeeds in `t1`; steps 3 and 4 return `PERMISSION_DENIED`.

#### TC-FR12-03: Shared visibility does not grant shared write authority

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-4, IC-5 | high | automated |

**Tier:** component-integration ([DEV])

##### Preconditions

- A Tenant Admin is bound only in `t1`. Shared and tenant-local Roles exist.
- A CPA holds `*` only in `system`.

##### Steps

1. As the Tenant Admin, Get/List shared roles; try to Update/Delete an
   unreferenced shared role and Create a role in `shared`.
2. As the CPA, Create/Update/Delete an unreferenced shared test role through
   staffing. Repeat with public and private APIs.

##### Expected Results

- Shared reads succeed for the Tenant Admin; shared writes return
  `PERMISSION_DENIED` despite visibility of the target.
- CPA staffing permits the tested operations through both APIs, subject to
  the same mutation invariants.

#### TC-FR12-04: Access reviews and can-i report tenant-specific method eligibility

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-4, IC-8 | high | automated |

**Tier:** component-integration ([DEV])

##### Preconditions

- `u1` holds `Clusters/Get` only in `t1` and `Clusters/Delete` only in `t2`.
- Valid clusters are in accessible projects; another `t1` cluster is in an
  inaccessible project.

##### Steps

1. Review Get and Delete with `metadata.tenant` set to each tenant, then
   with no tenant. Repeat using `osac can-i`.
2. Make the corresponding resource requests.
3. Review Get in `t1`, then Get the cluster in the inaccessible project.
4. Revoke Delete in `t2` and repeat using the same token.

##### Expected Results

- Get is allowed only in `t1`, Delete only in `t2`; tenant-unspecified
  reviews report each as allowed somewhere.
- Valid accessible requests agree with the scoped method reviews.
- The method review may allow Get while the project check blocks the actual
  object request. Reviews do not guarantee object or payload authorization.
- Revoked permissions disappear from reviews and requests without token refresh.

#### TC-FR12-05: Project membership flows and resource filtering are preserved

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-4 | high | automated |

**Tier:** deployed cross-component ([QE])

##### Preconditions

- A project manager and viewer with the role permissions needed for the
  tested operations; projects A and B in `t1` and a project in `t2`.
- A deployed Keycloak environment and project reconcilers.

##### Steps

1. Use OSAC ProjectMembership to add a user as Viewer in A. Wait for sync
   and obtain a token containing the project group.
2. As the viewer, Get and Update project A; as the manager, repeat and
   manage A's memberships.
3. With resource Get/List permissions in `t1` only, read resources in A,
   an unassigned project B, and `t2`; list resources.
4. Check database-membership visibility before token refresh and descendant
   project visibility using the existing behavior.

##### Expected Results

- OSAC membership changes sync to Keycloak's project groups.
- Project viewers can Get the project; only managers can Update it and
  manage memberships under the existing project rules.
- Resource queries respect existing project visibility, including database
  memberships and descendants. Project membership cannot grant another tenant.
- Viewer/Manager is not a new per-project method-permission set; project-scoped
  named roles remain deferred.

#### TC-FR12-06: Seeded admin roles carry wildcard permission sets

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-10 | high | automated |

**Tier:** component-integration ([DEV])

##### Preconditions

- Migration 135 applied.

##### Steps

1. Get the seeded roles `cloud-provider-admin`, `system-emergency-admin`,
   and `tenant-admin`.

##### Expected Results

- `cloud-provider-admin` and `system-emergency-admin` carry
  `permissions = ["*"]`.
- `tenant-admin` carries `permissions = ["osac.public.v1/*"]` — admin
  access is release-independent rather than a migration-time snapshot.
- The seeded bindings for the admin/controller and emergency service
  accounts are placed in the `system` tenant.

### FR-13: Break-glass during tenant IdP outage

#### TC-FR13-01: Break-glass role management during IdP outage

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-10 | high | automated |

**Tier:** deployed cross-component ([QE])

##### Preconditions

- Deployed environment with Keycloak; a tenant with its break-glass account
  holding the seeded `tenant-idp-manager` binding.

##### Steps

1. Disable the tenant's upstream IdP federation (simulate outage).
2. Authenticate as the tenant's break-glass account (local Keycloak
   credentials).
3. Create a tenant RoleBinding granting an explicit `Clusters/Get` role,
   which is within the break-glass account's own permissions.

##### Expected Results

- The break-glass account authenticates and the role-binding operation
  succeeds — authorization depends only on the fulfillment database.

#### TC-FR13-02: Emergency staffing can create explicit resource access

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-10, IC-11 | critical | automated |

**Tier:** component-integration ([DEV])

##### Preconditions

- Emergency Kubernetes account configured by the authentication flag and
  seeded with `system-emergency-admin` in `system`; no binding in `t1`.
- A second authenticated service account has no bindings.

##### Steps

1. As the emergency account, List clusters in `t1`.
2. Use staffing to create a `t1` binding granting `Clusters/List` to itself.
3. Repeat the List using the same credential; delete the binding and repeat.
4. As the unassigned account, attempt role administration and a resource read.

##### Expected Results

- Step 1 is denied. Step 2 succeeds; Step 3 succeeds only while the explicit
  tenant binding exists. Staffing alone is not a standing resource grant.
- The unassigned account is denied. Authentication trust does not create a grant.

## Gaps

### Requirement Coverage Gaps

All PRD requirements have planned cases. Default selection, replacement,
reference guards, and transactional onboarding follow the updated design.
Project-scoped named roles are out of scope. Project-filter bypass for tenant
administrators needs alignment with the removal of Keycloak realm-role
authorization.

### Interface Change Coverage Gaps

All interface changes have planned coverage. OSAC-6554 is an in-flight
prerequisite for service-account subject lists in TC-FR12-01 and TC-FR12-02;
this plan exercises their grants through seeded bindings and the evaluator's
resolution. Permission discovery is documented; the catalog remains internal.

## Summary

| Metric | Count |
|--------|-------|
| Total test cases | 69 |
| Critical | 28 |
| High | 33 |
| Medium | 8 |
| Low | 0 |
| Automated | 65 |
| Manual | 4 |
| Requirements with test cases | 13 / 13 |
| Interface changes with test cases | 12 / 12 |

---

## Provenance

Authored: revise @ design 0.11.5 - e2b0d87, workspace main @ 3e4bfdb7b
Phases: draft, manual-edit, revise, manual-edit, revise, revise, revise, revise, revise, manual-edit, revise, revise, revise, revise, revise

<!-- ai-workflow-provenance:{"schema_version":1,"provenance_kind":"session","workflow":"design","workflow_version":"0.11.5","ai_workflows":"e2b0d87","source_repo":"3e4bfdb7b","source_repo_branch":"main","commits_behind_main":0,"commits_ahead_main":0,"main_ref":"main","phases":["draft","manual-edit","revise","manual-edit","revise","revise","revise","revise","revise","manual-edit","revise","revise","revise","revise","revise"],"authoring_modes":["manual","skill"],"context_changed":false,"origin_untracked":false} -->
