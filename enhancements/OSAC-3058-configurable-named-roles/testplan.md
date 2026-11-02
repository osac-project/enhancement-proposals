# Testplan — OSAC-3058

## Overview

- **Feature:** OSAC-3058 — Configurable Named Roles with Separation of Duties
- **Total test cases:** 51
- **Requirements covered:** 13 of 13
- **Interface changes covered:** 12 of 12

Tier and owner conventions follow
[docs/INTEGRATION-TESTING.md](../../docs/INTEGRATION-TESTING.md): unit and
component-integration cases belong to the owning [DEV] work; deployed
cross-component journeys belong to [QE] work.

## Test Cases

### FR-1: Method catalog of full service-qualified gRPC methods

#### TC-FR1-01: Permissions/List returns complete service-qualified entries

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-3 | high | automated |

**Tier:** component-integration ([DEV])

##### Preconditions

- Fulfillment service deployed with the new `Permissions` service registered.

##### Steps

1. Authenticate as any seeded admin identity.
2. Call `osac.public.v1.Permissions/List` with no filter.

##### Expected Results

- The response contains entries for every public-layer service method (for
  example `osac.public.v1.Clusters/Create`) and every private-layer method
  (for example `osac.private.v1.Volumes/Create`).
- Each entry carries a single `name` field — a valid `spec.permissions`
  entry verbatim (for example `osac.private.v1.Volumes/Create`).
- Infrastructure methods (`/metadata.*`, `/grpc.reflection.*`,
  `/grpc.health.*`) and `Capabilities/Get` are absent.

#### TC-FR1-02: Permissions/List filters entries by name prefix

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-3 | medium | automated |

**Tier:** unit ([DEV])

##### Preconditions

- Catalog populated from the proto registry.

##### Steps

1. Call `Permissions/List` with the filter
   `this.name.startsWith("osac.public.v1.Clusters/")`.
2. Call `Permissions/List` with the filter
   `this.name.startsWith("osac.private.v1.")`.

##### Expected Results

- The first response contains only public `Clusters` methods (`Create`,
  `Delete`, `Get`, `List`, `Update`); `Signal` is private-layer only and
  does not match the public service prefix.
- The second response contains only private-layer references (for example
  `osac.private.v1.Volumes/Create`).

#### TC-FR1-03: Catalog is derived from the running build

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-3 | medium | automated |

**Tier:** unit ([DEV])

##### Preconditions

- Registry-scan unit test harness available.

##### Steps

1. Register a stub service descriptor in the test registry.
2. Rebuild the catalog and list entries.

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

- The subject is denied every method — the stale wildcard expands to
  nothing and grants nothing.
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

- Console deployed with regenerated types; CPA and TA test users.

##### Steps

1. As Tenant Admin, open the role authoring view, compose a role from the
   permission picker, and save.
2. As Tenant Admin, open the RoleBinding create form and assign the role to
   a user.
3. As Cloud Provider Admin, author a role in `shared`.

##### Expected Results

- The composer groups permissions by service, shows public-layer entries by
   default, and saves the role; the assignment form lists the new role; the
   CPA can select `shared` as the target tenant.

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

- Tenant Admin in `t1`; Tenant User `u1` in `t1` holding the default role;
  a tenant-scoped role `r1` with `Clusters/Create`.

##### Steps

1. As the Tenant Admin, create a RoleBinding granting `r1` to `u1`.
2. As `u1`, call `Clusters/Create` and a method only in the default role.

##### Expected Results

- The binding is created; `u1` can call both methods — the union of the
  default role and `r1`.

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

#### TC-FR5-04: Tenant assignments never cross tenant boundaries

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-2 | critical | automated |

**Tier:** component-integration ([DEV])

##### Preconditions

- Tenant Admin in `t1`; Tenant User `u2` in `t2`.

##### Steps

1. As the Tenant Admin of `t1`, attempt to create a RoleBinding in `t1`
   referencing `u2`.

##### Expected Results

- The request fails — the subject belongs to another tenant and is not
   assignable within `t1` (existing tenancy enforcement).

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

### FR-6: Propagation without re-login or redeployment

#### TC-FR6-01: A new grant takes effect without token refresh

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-4 | critical | automated |

**Tier:** component-integration ([DEV])

##### Preconditions

- Tenant User `u1` holding only the default role; Tenant Admin authenticated
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

- Role `r1` with bindings (from TC-FR7-01).

##### Steps

1. Delete all bindings referencing `r1`.
2. Call `Roles/Delete` for `r1`.

##### Expected Results

- The delete succeeds; Get returns `NOT_FOUND`.

#### TC-FR7-03: System roles cannot be deleted

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-1 | high | automated |

**Tier:** component-integration ([DEV])

##### Preconditions

- Seeded `system` roles present (for example `tenant-user`).

##### Steps

1. As a Cloud Provider Admin, call `Roles/Delete` for a system role.

##### Expected Results

- The request fails with `FAILED_PRECONDITION` regardless of bindings.

### FR-8: Multiple roles; union semantics; no exclusions

#### TC-FR8-01: A user holds multiple roles with union access

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-4 | high | automated |

**Tier:** component-integration ([DEV])

##### Preconditions

- `u1` holds role `rA` (`Clusters/Get`) and role `rB` (`Subnets/Create`).

##### Steps

1. As `u1`, call `Clusters/Get` and `Subnets/Create`.

##### Expected Results

- Both calls succeed — access is the union of held roles.

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

- The assignment succeeds; no exclusivity check runs; the user holds the
  union.

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

- Console deployed; Tenant Admin session.

##### Steps

1. Open the RoleBinding create form and expand the role picker.

##### Expected Results

- Seeded and shared roles appear grouped and searchable ahead of custom
  tenant roles.

### FR-10: Default role at onboarding

#### TC-FR10-01: A new user's first request succeeds and assigns the default

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-6 | critical | automated |

**Tier:** component-integration ([DEV])

##### Preconditions

- Tenant `t1` with no default override; a brand-new Keycloak user in `t1`'s
  organization with a fresh token.

##### Steps

1. As the new user, call any default-role method (for example
   `Clusters/List`).

##### Expected Results

- The call succeeds; a User row exists for the user; a RoleBinding in `t1`
  references the platform default role and the new user.

#### TC-FR10-02: Tenant default override applies to new users

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-6 | high | automated |

**Tier:** component-integration ([DEV])

##### Preconditions

- Tenant Admin in `t1` has flagged a tenant role `r-override` with
  `spec.is_default = true`.

##### Steps

1. As a brand-new user of `t1`, make a first request.

##### Expected Results

- The auto-created binding references `r-override`, not the platform
  default.

#### TC-FR10-03: Removing the override falls back to the platform default

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-6 | high | automated |

**Tier:** component-integration ([DEV])

##### Preconditions

- `r-override` no longer flagged `is_default`.

##### Steps

1. As a brand-new user of `t1`, make a first request.

##### Expected Results

- The auto-created binding references the platform default role.

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

#### TC-FR10-05: The last default role cannot be unflagged

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-6 | medium | automated |

**Tier:** component-integration ([DEV])

##### Preconditions

- Only one `is_default` role exists in a tenant.

##### Steps

1. Update that role with `is_default = false`.

##### Expected Results

- The update fails with `FAILED_PRECONDITION`.

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

### FR-11: Tenant Users see held roles and what they permit

#### TC-FR11-01: SelfSubjectRulesReviews returns held roles and methods

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-7 | high | automated |

**Tier:** component-integration ([DEV])

##### Preconditions

- `u1` holds two roles with known permission sets.

##### Steps

1. As `u1`, call `SelfSubjectRulesReviews/Create`.

##### Expected Results

- The response lists both roles by name with their permission sets, the
  tenants where the caller holds bindings, and an effective-permission
  union equal to the union of both sets.

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

- Output lists the held role names; it does not read or print
  `realm_access.roles` (verifiable by revoking a role and re-running
  `whoami` with the same token — the revoked role is absent).

#### TC-FR11-03: Rules review renders wildcard entries and the expanded union

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-7 | high | automated |

**Tier:** component-integration ([DEV])

##### Preconditions

- `u1` holds a role with `permissions = ["osac.public.v1.Clusters/*"]`.

##### Steps

1. As `u1`, call `SelfSubjectRulesReviews/Create`.

##### Expected Results

- The held-role entry lists the permission set verbatim
  (`["osac.public.v1.Clusters/*"]`).
- The effective-permission union contains the expanded set — every cataloged
  `Clusters` permission — so capability gating needs no client-side pattern
  logic.

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

- CSI driver service account bound to `osac-csi-driver`.

##### Steps

1. Authenticate as the CSI driver service account.
2. Call `osac.private.v1.Volumes/Create`.
3. Call `osac.public.v1.Clusters/Create`.

##### Expected Results

- Step 2 succeeds; step 3 returns `PERMISSION_DENIED`.

#### TC-FR12-04: SelfSubjectAccessReview agrees with real requests

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-4 | high | automated |

**Tier:** component-integration ([DEV])

##### Preconditions

- `u1` with a known role; a role change pending.

##### Steps

1. Call `SelfSubjectAccessReviews/Create` for a method, then call the actual
   method.
2. Change the role's methods; repeat both calls.

##### Expected Results

- In both states, the review's allowed/denied answer equals the actual
   request outcome.

#### TC-FR12-05: Project group authorization is unchanged

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-4 | high | automated |

**Tier:** component-integration ([DEV])

##### Preconditions

- A project with `system:viewers` and `system:managers` organization groups
  and members of each.

##### Steps

1. As the viewer, call `Projects/Get` and `Projects/Update`.
2. As the manager, call `Projects/Get` and `Projects/Update`.

##### Expected Results

- Viewer: Get succeeds, Update returns `PERMISSION_DENIED`. Manager: both
  succeed — identical to the pre-change policy.

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
3. Manage role assignments for the tenant (create a RoleBinding).

##### Expected Results

- The break-glass account authenticates and the role-binding operation
  succeeds — authorization depends only on the fulfillment database.

#### TC-FR13-02: Emergency service account manages grants without implicit access

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-11 | critical | automated |

**Tier:** component-integration ([DEV])

##### Preconditions

- Service configured with `--grpc-authz-emergency-service-accounts=admin`;
  migration 135 applied (seeds the emergency binding).

##### Steps

1. Authenticate as `system:serviceaccount:<ns>:admin` with a Kubernetes
   service account token.
2. Create a RoleBinding in a tenant the account holds no reach into.
3. Call a tenant-resource read (for example `Clusters/List`) in that
   tenant.

##### Expected Results

- Step 2 succeeds — the seeded `system`-placed binding grants the methods
  and platform staffing authorizes the placement; role management depends
  only on the fulfillment database (FR-13).
- Step 3 is denied — break-glass covers role management, not
  tenant-resource reach.
- A service account not present in the flag holds no grant and is denied.

## Gaps

### Requirement Coverage Gaps

All PRD requirements have test cases.

### Interface Change Coverage Gaps

All interface changes are exercised by test cases. Service-account
subject-list matching semantics are delivered and tested with OSAC-6554;
this plan exercises service-account grants through the seeded bindings
(TC-FR12-01, TC-FR12-02) and the evaluator's resolution.

## Summary

| Metric | Count |
|--------|-------|
| Total test cases | 51 |
| Critical | 18 |
| High | 26 |
| Medium | 7 |
| Low | 0 |
| Automated | 49 |
| Manual | 2 |
| Requirements with test cases | 13 / 13 |
| Interface changes with test cases | 12 / 12 |
