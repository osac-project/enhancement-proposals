# Assign read-only API permissions to users

| Field     | Value |
|-----------|-------|
| Author(s) | Juan Hernandez |
| Jira      | [OSAC-6211](https://redhat.atlassian.net/browse/OSAC-6211) |
| PRD       | [prd.md](prd.md) |
| Date      | 2026-10-20 |

# 1. Overview

This design uses the existing Role and RoleBinding flow to assign read-only
access, then enforces it in Fulfillment Service's gRPC authorization policy.
For a user assigned a reader role, only methods named exactly Get, List, or
Watch are allowed. Every other method is denied with gRPC
PERMISSION_DENIED. Existing tenant and resource checks still decide which
objects those methods can return. The full behavior is in the [PRD](prd.md).
[User]

The design proposes using the existing tenant-reader and cloud-provider-reader
roles, the existing RoleBindings API and UI, and Keycloak role synchronization.
It adds no resource lifecycle methods or schema fields. Role names, assignment
scope, and session update timing remain open for review.
[Codebase: fulfillment-service/internal/auth/policies/authz.rego]

# 2. Goals and Non-Goals

## 2.1 Goals

- Enforce the reader method rule in the gRPC authorization boundary.
- Keep role assignment on the existing RoleBinding API, controller, and UI.
- Preserve current tenant and resource visibility checks.
- Document how administrators assign read-only access and what it permits.

## 2.2 Non-Goals

- Add custom per-resource permission combinations.
- Change public resource lifecycle methods or protobuf contracts.
- Change provisioning behavior in operators or providers.

# 3. Motivation / Background

Fulfillment Service already evaluates gRPC methods in an OPA policy from the
authentication interceptor. The policy has explicit method grants, global
metadata, reflection, and health grants, and general client grants that include
some writes. Its rules are additive, so adding a reader allow rule alone would
not take away those existing grants. [Codebase:
fulfillment-service/internal/auth/policies/authz.rego]

Role and RoleBinding resources already represent named roles, user assignments,
tenant scope, and Keycloak synchronization status. The database seeds
tenant-reader and cloud-provider-reader, but the authorization policy does not
currently treat them as read-only roles. The UI recognizes no distinct reader
session role. [Codebase:
fulfillment-service/internal/controllers/rolebinding/]

# 4. Design

## 4.1 Architecture

An administrator creates or updates a RoleBinding through the existing API or
UI. Fulfillment Service persists it, and the role-binding controller syncs the
assignment to Keycloak. After the user receives a token containing the reader
role, the gRPC authorization interceptor passes the method path and identity
claims to OPA. OPA allows only methods whose final path segment is exactly Get,
List, or Watch. Allowed calls continue to the existing handlers, which retain
their tenant and object checks. All other calls are denied before a handler can
change data.

~~~mermaid
flowchart LR
  Admin[Cloud Provider Admin or Tenant Admin] -->|RoleBinding API or UI| Fulfillment[Fulfillment Service]
  Fulfillment -->|persist binding| DB[(PostgreSQL)]
  DB --> Controller[RoleBinding controller]
  Controller -->|sync role| Keycloak
  Keycloak -->|reader role in token| Interceptor[gRPC auth interceptor]
  User[Read-only user] -->|gRPC method and token| Interceptor
  Interceptor --> OPA[OPA authorization policy]
  OPA -->|Get, List, Watch| Handler[Existing API handler]
  Handler --> Scope[Existing tenant and object checks]
  OPA -->|all other methods: PERMISSION_DENIED| Denied[Request rejected]
~~~

The diagram shows two paths: administrators assign a role through existing
surfaces, and a later user request is checked by OPA before reaching its
handler. Keycloak synchronization supplies the reader role claim; OPA limits
the method set; existing handlers continue to enforce visibility.

The reader check must take precedence over all current grants, including
general client and admin grants and global metadata, reflection, and health
grants. Otherwise a reader could still call methods outside the required set.
Methods are matched by the exact final path segment, not by prefix; for
example, GetByName is denied. A reader with a tenant-reader or
cloud-provider-reader role is restricted even if another grant would otherwise
allow the method. [User]

## 4.2 Data Model / Schema Changes

No schema changes are required. Role and RoleBinding already store role names,
tenant-scoped user assignments, and synchronization status. The database seed
already includes tenant-reader and cloud-provider-reader. Whether these exact
role names are used is an open question in §9.1. [Codebase:
fulfillment-service/internal/database/migrations/33_create_roles_tables.up.sql]

## 4.3 API Changes

No gRPC methods, request fields, response fields, or REST routes are added or
changed. Administrators use the existing RoleBindings List, Get, Create,
Update, and Delete methods to manage assignments. The RoleBinding controller
continues to apply the corresponding Keycloak realm role and report PENDING,
READY, or FAILED. [Codebase:
proto/private/osac/private/v1/role_bindings_service.proto]

For a user assigned a reader role, the existing authorization interceptor
returns gRPC PERMISSION_DENIED with message permission denied for methods
outside the exact Get, List, and Watch set. Existing role-binding methods and
other API methods are governed by the same rule when invoked by a reader.
There is no new request validation or error code. [Codebase:
fulfillment-service/internal/auth/grpc_authz_interceptor.go]

## 4.4 Scalability and Performance

Each request adds a role-membership check and an exact method-name comparison
to the existing in-process OPA evaluation. It adds no database query or
network call to the request path. Keycloak traffic remains limited to the
existing asynchronous role-binding reconciliation. Storage and retention do
not change. [Codebase:
fulfillment-service/internal/auth/authorization_evaluator.go]

## 4.5 Security Considerations

The authorization policy must apply the reader restriction before any broader
allow rule. This prevents the current additive client grants from allowing a
reader to create, update, delete, or invoke another non-reader method. Denials
happen in the interceptor before the handler runs, and denied requests cannot
change stored resources. [User]

The method rule does not grant access to every object. Existing tenant and
object-level checks remain in the handlers and data paths. Tests must cover
both an allowed read in the user's scope and a read outside that scope.
[PRD: In Scope]

The current policy also has global allows for metadata, reflection, and
health paths. Those rules are not blanket exceptions for readers: methods
under those paths use the same exact-name check. For example, Check and
ServerReflectionInfo are denied; a method named exactly Get, List, or Watch
continues through the existing scope checks.

## 4.6 Failure Handling and Recovery

- A denied method returns PERMISSION_DENIED with the existing message
  permission denied. The request does not reach the handler.
- A failed role-binding reconciliation remains visible as FAILED through the
  existing status model. The user does not receive the intended role until
  Keycloak synchronization succeeds.
- The policy reads roles from the JWT. A token minted before a role change
  keeps its existing claims until it is refreshed or replaced. READY confirms
  Keycloak synchronization, not that every active session has refreshed.
  Whether role changes must take effect for existing sessions immediately is
  an open question in §9.4. [Codebase:
  fulfillment-service/internal/auth/policies/authz.rego]

## 4.7 RBAC / Tenancy

The design proposes that tenant-reader and cloud-provider-reader identify
read-only users. A tenant-reader assignment remains tenant-scoped through the
existing RoleBinding metadata and user organization claims. The exact scope
for cloud-provider-reader assignments is open in §9.2. [Codebase:
fulfillment-service/internal/database/migrations/33_create_roles_tables.up.sql]

The UI UserRole type adds a reader category. The session mapper returns reader
for either configured reader role instead of falling back to tenant-user. This
lets the UI apply reader-specific controls; whether those controls are hidden
or disabled is open in §9.3. [Codebase:
osac-ui/apps/app-frontend/src/hooks/oidc-login.tsx]

For either reader role, only methods named exactly Get, List, or Watch are
allowed. A method name does not bypass the existing tenant or object checks.
When a reader role is present, no other identity or role grant broadens the
allowed method set. The design does not change the authorization of users who
have no reader role. [User]

## 4.8 Extensibility / Future-Proofing

The exact method-name check applies consistently as services add methods:
new Get, List, or Watch methods enter the reader path, while other new methods
remain denied. Each new read method must still enforce tenant and object scope;
the method name alone is not an object-level grant.

# 5. Interface Changes

The PRD has no FR or NFR identifiers. For this design and testplan only,
FR-1 refers to the first In Scope bullet and FR-2 to the second. These labels
are trace references, not new requirements.

## IC-1: Read-only gRPC method authorization

**Requirements:** FR-1

The Fulfillment gRPC authorization result changes for a user with a reader
role. Exact method names Get, List, and Watch continue to the existing
handler; all other methods return PERMISSION_DENIED before the handler runs.
Existing tenant and object checks continue to filter results. See §4.1,
§4.3, and §4.7.

## IC-2: Assign a reader role through the existing RoleBindings API

**Requirements:** FR-2

Cloud Provider Admins and Tenant Admins use existing RoleBinding methods to
assign read-only access. The existing controller syncs the role to Keycloak
and reports its status. The role names and provider assignment scope need
review. See §4.1 and §4.3.

## IC-3: Assign a reader role in the OSAC UI

**Requirements:** FR-1, FR-2

The Role Bindings page and form use the existing Roles and RoleBindings APIs
to show and assign the reader role to eligible users. The session mapper
returns the reader category for assigned users; mutation controls use that
category. Whether controls are hidden or disabled is open for review. See
§4.1 and §4.7.

## IC-4: Explain read-only permissions in user documentation

**Requirements:** FR-2

Update the tenant identity and access guide with the API and UI assignment
paths, the exact allowed method names, denied calls, tenant scope, and role
sync status. See §4.3 and §4.6.

# 6. Alternatives Considered

- **Add a new permission field or custom action set to Role.** This could
  describe more combinations, but the PRD excludes custom per-resource
  permissions and the current reader roles already provide a role-based path.
  Reusing the existing reader roles is the proposed approach; confirm the
  exact role names in §9.1.
- **Add reader allows to the current additive OPA rules.** This is smaller,
  but existing client grants would still permit writes. The design instead
  checks the reader restriction before broader grants.
- **List every allowed RPC path individually.** This gives an explicit
  inventory, but it would not apply the PRD rule uniformly to all methods
  named Get, List, or Watch. The design matches the exact final method name
  and keeps object scope in each existing handler.
- **Scope provider-reader bindings per tenant or across all tenants.** A
  per-tenant binding reuses the current RoleBinding boundary; a provider-wide
  binding follows the provider's existing visibility scope. The PRD does not
  choose between them; resolve this in §9.2.
- **Wait for token refresh or revoke existing sessions after assignment.**
  Refresh uses the existing JWT role claims; immediate revocation needs an
  additional session invalidation path. Resolve the required timing in §9.4.
- **Leave UI mutation controls visible and rely on server denials.** This
  preserves current UI behavior but makes a read-only session appear editable.
  The proposed UI behavior is to recognize reader sessions and hide
  mutation controls; confirm whether hiding or disabling is preferred in §9.3.

# 7. Observability and Monitoring

No new observability changes are proposed. Existing authorization logs and
RoleBinding synchronization status apply.

# 8. Impact and Compatibility

The gRPC and protobuf contracts remain unchanged. Existing role-binding
requests and stored resources remain compatible. A reader token receives a
narrower method set, and its existing session claims may delay the visible
effect of a role change until token refresh. No database migration is needed
if the seeded reader role names are reused. Changes to those names or their
assignment scope could require role seed or UI updates.

# 9. Open Questions

## 9.1 Should the feature use the existing tenant-reader and cloud-provider-reader role names?

- **Owner:** OSAC Core team
- **Impact:** §4.1, §4.2, §4.7, and IC-2/IC-3; determines the role claims
  and whether role seed data needs an update.

## 9.2 Should cloud-provider-reader assignments be tenant-scoped or grant the cloud-provider user's existing cross-tenant scope?

- **Owner:** OSAC Core team
- **Impact:** §4.1 and §4.7; determines RoleBinding scope, assignment behavior,
  and which resources a cloud-provider reader can see.

## 9.3 Should the UI hide or disable mutation controls for reader sessions?

- **Owner:** OSAC Core and OSAC UI teams
- **Impact:** §4.7 and IC-3; changes the reader experience, but does not change
  server-side denial behavior.

## 9.4 Must a role change restrict an already-issued token immediately, or is access updated after token refresh?

- **Owner:** OSAC Core team
- **Impact:** §4.6 and §8; determines the assignment completion contract,
  session behavior, and timing tests.

---

## Provenance

Authored: draft @ design 0.11.5 - 4164796, workspace main @ 95fbc127c

<!-- ai-workflow-provenance:{"schema_version":1,"provenance_kind":"session","workflow":"design","workflow_version":"0.11.5","ai_workflows":"4164796","source_repo":"95fbc127c","source_repo_branch":"main","commits_behind_main":0,"commits_ahead_main":0,"main_ref":"main","phases":["draft"],"authoring_modes":["skill"],"context_changed":false,"origin_untracked":false} -->
