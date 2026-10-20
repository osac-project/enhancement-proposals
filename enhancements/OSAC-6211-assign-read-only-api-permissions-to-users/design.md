---
title: assign-read-only-api-permissions-to-users
authors: Juan Hernandez
creation-date: 2026-10-20
last-updated: 2026-10-20
tracking-link: https://redhat.atlassian.net/browse/OSAC-6211
prd: prd.md
see-also: []
replaces: "N/A"
superseded-by: "N/A"
---

# Assign read-only API permissions to users

# 1. Overview

### Terminology

- **Reader role:** either `tenant-reader` or `cloud-provider-reader`.
- **Reviewed read method:** an explicitly approved gRPC path whose method is
  exactly `Get`, `List`, or `Watch`, and whose handler keeps the existing
  tenant and object checks.
- **READY:** the RoleBinding controller has synchronized the role to Keycloak.
  It does not mean every active token has refreshed.

This design uses the existing Role and RoleBinding flow to assign read-only
access, then enforces it in Fulfillment Service's gRPC authorization policy.
Readers use the existing `tenant-reader` and `cloud-provider-reader` roles
through the RoleBindings API and UI. Only reviewed methods named exactly
`Get`, `List`, or `Watch` are allowed; every other gRPC method is denied
with `PERMISSION_DENIED`. Existing tenant and resource checks still decide
which objects a reader can access. Cloud provider readers keep their existing
provider scope. Role changes apply to a user's access after the token is
refreshed. The full behavior is in the [PRD](prd.md).

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
claims to OPA. OPA allows only reviewed paths whose final method name is exactly
Get, List, or Watch. Allowed calls continue to the existing handlers, which
retain their tenant and object checks. All other calls are denied before a
handler can change data.

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

When either reader role is present, its rule determines the final decision.
It overrides general client and admin grants and global metadata, reflection,
and health grants. A method is allowed only when its full path is in the
reviewed read-method list. Every listed method must end in exactly `Get`,
`List`, or `Watch`, be read-only, and keep its existing tenant and object
checks. Other methods, including future methods not yet reviewed, are denied.
This prevents an additive allow rule from giving a reader write access.

The policy can express this decision as:

~~~text
if identity_has_reader_role:
    decision = method_path in reviewed_reader_rpc_paths
else:
    decision = existing_policy_decision
~~~

For example, `GetByName` does not match `Get`. A reader remains restricted
even if another role or grant would otherwise allow a method.

## 4.2 Data Model / Schema Changes

No schema changes are required. Role and RoleBinding already store role names,
tenant-scoped user assignments, and synchronization status. The database seed
already includes `tenant-reader` and `cloud-provider-reader`; this design
uses those roles.

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

Each request adds a role-membership check and an exact method-path check to
the existing in-process OPA evaluation. It adds no database query or
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
under those paths use the same reviewed-path check. For example, Check and
ServerReflectionInfo are denied. A reviewed Get, List, or Watch method still
passes through the existing scope checks.

## 4.6 Failure Handling and Recovery

- A denied method returns PERMISSION_DENIED with the existing message
  permission denied. The request does not reach the handler.
- A failed role-binding reconciliation remains visible as FAILED through the
  existing status model. The user does not receive the intended role until
  Keycloak synchronization succeeds.
- The policy reads roles from the JWT. A token minted before a role change
  keeps its existing claims until it is refreshed or replaced. READY confirms
  Keycloak synchronization, not that every active session has refreshed.
  Users must refresh or re-authenticate before relying on the changed access.
  Existing tokens keep the access allowed by their current claims until they
  expire or are replaced.

## 4.7 RBAC / Tenancy

The `tenant-reader` role stays within its existing tenant scope.
`cloud-provider-reader` keeps the user's existing provider authorization
scope; assigning it does not add visibility to other tenants or resources.

The UI session mapper returns a reader category for either role. The UI hides
Create, Update, and Delete controls for reader sessions. Server-side
authorization remains the security boundary.

For either reader role, only reviewed methods named exactly `Get`, `List`,
or `Watch` are allowed. A method name does not bypass existing tenant or
object checks. The design does not change authorization for users who have no
reader role.

## 4.8 Extensibility / Future-Proofing

The policy uses an explicit list of reviewed read-method paths. New RPCs stay
denied to readers until they are reviewed, even when their method is named
`Get`, `List`, or `Watch`. Review confirms the method is read-only and that
its handler keeps the existing tenant and object checks.

# 5. Interface Changes

The PRD has no FR or NFR identifiers. For this design and testplan only,
FR-1 refers to the first In Scope bullet and FR-2 to the second. These labels
are trace references, not new requirements.

## IC-1: Read-only gRPC method authorization

**Requirements:** FR-1

The Fulfillment gRPC authorization result changes for a user with a reader
role. Reviewed Get, List, and Watch methods continue to the existing handler;
all other methods return PERMISSION_DENIED before the handler runs. Existing
tenant and object checks continue to filter results. See §4.1,
§4.3, and §4.7.

## IC-2: Assign a reader role through the existing RoleBindings API

**Requirements:** FR-2

Cloud Provider Admins and Tenant Admins use existing RoleBinding methods to
assign read-only access. The existing controller syncs the role to Keycloak
and reports its status. The seeded role names are reused, and
`cloud-provider-reader` keeps the user's existing provider scope. See §4.1,
§4.3, and §4.7.

## IC-3: Assign a reader role in the OSAC UI

**Requirements:** FR-1, FR-2

The Role Bindings page and form use the existing Roles and RoleBindings APIs
to show and assign the reader role to eligible users. The session mapper
returns the reader category for assigned users and hides Create, Update, and
Delete controls. See §4.1 and §4.7.

## IC-4: Explain read-only permissions in user documentation

**Requirements:** FR-2

Update the tenant identity and access guide with the API and UI assignment
paths, the exact allowed method names, denied calls, existing tenant and
provider scope, hidden mutation controls, and READY versus token refresh
timing. See §4.3, §4.6, and §4.7.

# 6. Alternatives Considered

- **Add a new permission field or custom action set to Role.** This could
  describe more combinations, but the PRD excludes custom per-resource
  permissions, and the existing reader roles provide a role-based path.
- **Add reader allows to the current additive OPA rules.** This is smaller,
  but existing client grants would still permit writes. The design instead
  checks the reader restriction before broader grants.
- **Allow every method based on its name alone.** This avoids maintaining a
  path list, but a new method could be exposed before anyone checks its
  behavior. The design uses an explicit reviewed list and keeps new methods
  denied until review.
- **Revoke existing sessions immediately.** This would apply a role change
  sooner, but requires a new session invalidation path. This design uses the
  existing token refresh flow and documents the delay.
- **Leave mutation controls visible.** Server denials would still protect
  data, but the UI would appear editable. The design hides those controls for
  reader sessions.

# 7. Observability and Monitoring

No new observability changes are proposed. Existing authorization logs and
RoleBinding synchronization status apply.

# 8. Impact and Compatibility

The gRPC and protobuf contracts remain unchanged. Existing RoleBinding
requests and stored resources remain compatible. Reader access is limited to
the reviewed method list and the user's existing resource scope. A role change
does not update an already-issued token; users must refresh or re-authenticate
after Keycloak reports READY. No database migration is needed because the
seeded reader roles are reused.

## 8.1 Risks and Mitigations

- **A broader OPA grant could allow a write.** When a reader role is present,
  the reader rule determines the final decision. Tests cover a reader with an
  additional grant that would otherwise allow a write.
- **A method could be added to the reader list without being safe.** New RPCs
  remain denied until review confirms the method is read-only and retains
  tenant and object checks.
- **An active token may keep old permissions.** READY reports Keycloak sync
  only. The guide and UI explain that users must refresh or sign in again;
  tests compare access before and after refresh.
- **UI controls could be mistaken for server enforcement.** The UI hides
  mutation controls for readers, while the gRPC policy remains authoritative.

## 8.2 Drawbacks

- The reviewed method list needs updates when new read RPCs are added.
- A new read method stays unavailable to readers until that review is done.
- Role changes do not affect active tokens until refresh or expiry.
- Hiding controls improves the UI experience, but server checks must still
  reject direct requests.

---

## Provenance

Committed: commit @ design 0.11.5 - 4164796, workspace design/OSAC-6211 @ 55da833 (dirty)

> Authoring phases not recorded this session (commit-time snapshot only).

<!-- ai-workflow-provenance:{"schema_version":1,"provenance_kind":"commit_only","workflow":"design","workflow_version":"0.11.5","ai_workflows":"4164796","source_repo":"55da833 (dirty)","source_repo_branch":"design/OSAC-6211","commits_behind_main":0,"commits_ahead_main":3,"main_ref":"main","phases":["commit"],"authoring_modes":["skill"],"context_changed":false,"origin_untracked":false} -->
