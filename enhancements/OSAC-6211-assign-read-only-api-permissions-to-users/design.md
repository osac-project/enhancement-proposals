---
title: assign-read-only-api-permissions-to-users
authors: Juan Hernandez
creation-date: 2026-10-20
last-updated: 2026-10-21
tracking-link: https://redhat.atlassian.net/browse/OSAC-6211
prd: prd.md
see-also: []
replaces: "N/A"
superseded-by: "N/A"
---

# Assign read-only API permissions to users

# 1. Overview

### Terminology

- **Reader role:** either `tenant-reader` or `cloud-provider-reader`. Each
  role grants reviewed read methods; it does not revoke other permissions.
- **Additive role grants:** a user's effective permissions are the union of
  grants from all assigned roles and the existing policy. Adding a role never
  removes an existing grant.
- **Read-only user:** a user whose combined grants allow no mutation methods.
  Having a reader role alone does not make a user read-only.
- **Reviewed read method:** an explicitly approved gRPC path whose method is
  exactly `Get`, `List`, or `Watch`, and whose handler keeps the existing
  tenant and object checks.
- **READY:** the RoleBinding controller has synchronized the role to Keycloak.
  It does not mean every active token has refreshed.

This design uses the existing Role and RoleBinding flow to add read access
through the Fulfillment Service gRPC authorization policy. The existing
`tenant-reader` and `cloud-provider-reader` roles grant reviewed methods named
exactly `Get`, `List`, or `Watch`. Permissions from other roles and the
existing client policy remain effective. For example, a user who already has
`Clusters/Create` access keeps it after `tenant-reader` is added. Assigning a
reader role therefore does not by itself make an ordinary client read-only.
Existing tenant and resource checks still decide which objects a user can
access, and cloud provider readers keep their existing provider scope. Role
changes appear in a user's token after refresh. The full behavior is in the
[PRD](prd.md).

# 2. Goals and Non-Goals

## 2.1 Goals

- Add the reviewed reader method grants in the gRPC authorization boundary.
- Keep role assignment on the existing RoleBinding API, controller, and UI.
- Preserve current tenant and resource visibility checks.
- Document what reader roles grant and how their permissions combine with
  existing grants.

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
currently use them to add reviewed read-method grants. The UI recognizes no
distinct reader session role. [Codebase:
fulfillment-service/internal/controllers/rolebinding/]

# 4. Design

## 4.1 Architecture

An administrator creates or updates a RoleBinding through the existing API or
UI. Fulfillment Service persists it, and the role-binding controller syncs the
assignment to Keycloak. After the user receives a token containing the reader
role, the gRPC authorization interceptor passes the method path and identity
claims to OPA. OPA combines the reader grants with all other matching policy
grants. A method is allowed when any grant allows it; it is denied before the
handler only when no grant allows it. Allowed calls continue to the existing
handlers, which retain their tenant and object checks.

~~~mermaid
flowchart LR
  Admin[Cloud Provider Admin or Tenant Admin] -->|RoleBinding API or UI| Fulfillment[Fulfillment Service]
  Fulfillment -->|persist binding| DB[(PostgreSQL)]
  DB --> Controller[RoleBinding controller]
  Controller -->|sync role| Keycloak
  Keycloak -->|reader role in token| Interceptor[gRPC auth interceptor]
  User[User with reader role] -->|gRPC method and token| Interceptor
  Interceptor --> OPA[OPA authorization policy]
  Existing[Other role and client grants] --> OPA
  OPA -->|allowed by any matching grant| Handler[Existing API handler]
  Handler --> Scope[Existing tenant and object checks]
  OPA -->|no matching grant: PERMISSION_DENIED| Denied[Request rejected]
~~~

The diagram shows administrators assigning a role through existing surfaces,
existing policy grants, and a later user request checked by OPA before it
reaches its handler. Keycloak synchronization supplies the reader role claim.
The reader role adds grants for reviewed read methods; existing handlers
continue to enforce visibility.

Authorization grants are additive. OPA allows a method when any matching
policy rule grants it. A reader role contributes only paths in the reviewed
read-method list. It does not override general-client, admin, metadata,
reflection, health, or other role grants. If another grant allows
`/osac.public.v1.Clusters/Create`, that method remains allowed after
`tenant-reader` is added. Every method in the reader list must end in exactly
`Get`, `List`, or `Watch`, be read-only, and retain its existing tenant and
object checks. A method outside that list is denied only when no other policy
rule grants it.

The policy can express this decision as:

~~~text
decision = existing_policy_decision
if identity_has_reader_role and method_path in reviewed_reader_rpc_paths:
    decision = allow
~~~

For example, `GetByName` does not match `Get`, so the reader role does not
grant it. Another policy rule may still allow it. The current client policy
classifies ordinary non-admin users as clients and grants many CRUD methods;
adding a reader role to one of those users does not remove those permissions.
A user is effectively read-only only when none of their grants allows a
mutation method.

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

The reader roles add permission for reviewed methods whose final name is
exactly Get, List, or Watch. A method outside that set returns gRPC
PERMISSION_DENIED with message permission denied only when no other matching
policy rule grants it. Existing role-binding methods and other API methods
keep their current grants. There is no new request validation or error code.
[Codebase: fulfillment-service/internal/auth/grpc_authz_interceptor.go]

## 4.4 Scalability and Performance

Each request adds a role-membership check and an exact method-path check to
the existing in-process OPA evaluation. It adds no database query or
network call to the request path. Keycloak traffic remains limited to the
existing asynchronous role-binding reconciliation. Storage and retention do
not change. [Codebase:
fulfillment-service/internal/auth/authorization_evaluator.go]

## 4.5 Security Considerations

The policy adds reviewed read-method grants for the reader roles and preserves
all existing grants. A mutation is denied before the handler only when no
matching policy rule allows it. The current general-client policy grants
Create, Update, and Delete to ordinary non-admin users, so assigning a reader
role to one of those users does not remove that access. [User]

The method rule does not grant access to every object. Existing tenant and
object-level checks remain in the handlers and data paths. Tests must cover
both an allowed read in the user's scope and a read outside that scope.
[PRD: In Scope]

The current policy also has global allows for metadata, reflection, and
health paths. They remain effective for users with reader roles. A reader
role does not add these paths, and it does not revoke the existing grants.
Reviewed Get, List, and Watch methods still pass through the existing scope
checks.

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

The UI session mapper returns a reader category when either role is present,
and the UI hides Create, Update, and Delete controls for reader sessions.
This is a presentation choice; it does not revoke API access granted by
another role or the general-client policy. Server-side authorization uses the
union of all matching grants.

Each reader role grants only reviewed methods named exactly `Get`, `List`, or
`Watch`. A method name does not bypass existing tenant or object checks. Users
without a reader role keep the existing authorization behavior.

## 4.8 Extensibility / Future-Proofing

The reader grants use an explicit list of reviewed read-method paths. New
RPCs receive no grant from a reader role until reviewed, even when their
method is named `Get`, `List`, or `Watch`. Another existing policy grant may
still allow a new method. Review confirms each reader path is read-only and
its handler keeps the existing tenant and object checks.

# 5. Interface Changes

The PRD has no FR or NFR identifiers. For this design and testplan only,
FR-1 refers to the first In Scope bullet and FR-2 to the second. These labels
are trace references, not new requirements.

## IC-1: Additive gRPC reader method grants

**Requirements:** FR-1

The reader roles add grants for reviewed Get, List, and Watch methods.
Authorization continues to combine grants from the user's other roles and
the existing client policy. A method returns PERMISSION_DENIED only when no
matching grant allows it. Existing tenant and object checks continue to
filter results. See §4.1, §4.3, and §4.7.

## IC-2: Assign a reader role through the existing RoleBindings API

**Requirements:** FR-2

Cloud Provider Admins and Tenant Admins use existing RoleBinding methods to
add the reader role. The existing controller syncs it to Keycloak and reports
its status. Existing permissions remain effective, and
`cloud-provider-reader` keeps the user's existing provider scope. See §4.1,
§4.3, and §4.7.

## IC-3: Assign a reader role in the OSAC UI

**Requirements:** FR-1, FR-2

The Role Bindings page and form use the existing Roles and RoleBindings APIs
to show and assign the reader role to eligible users. The session mapper
returns the reader category for assigned users and hides Create, Update, and
Delete controls. This does not remove API grants from other roles. See §4.1
and §4.7.

## IC-4: Explain read-only permissions in user documentation

**Requirements:** FR-2

Update the tenant identity and access guide with the API and UI assignment
paths, the reader role's exact method grants, the additive behavior of
existing permissions, tenant and provider scope, hidden mutation controls,
and READY versus token refresh timing. See §4.3, §4.6, and §4.7.

# 6. Alternatives Considered

- **Add a new permission field or custom action set to Role.** This could
  describe more combinations, but the PRD excludes custom per-resource
  permissions, and the existing reader roles provide a role-based path.
- **Make the reader role override other grants.** This would prevent writes
  for a user with the reader role, but it would revoke permissions granted by
  other roles. The design keeps role grants additive.
- **Allow every method based on its name alone.** This avoids maintaining a
  path list, but a new method could be exposed before anyone checks its
  behavior. The design uses an explicit reviewed list and keeps new methods
  denied until review.
- **Revoke existing sessions immediately.** This would apply a role change
  sooner, but requires a new session invalidation path. This design uses the
  existing token refresh flow and documents the delay.
- **Show mutation controls in every reader session.** This would match other
  grants that may still permit writes, but could encourage actions outside the
  reader grant. The design hides those controls as a UI choice and explains
  that this does not revoke API permissions.

# 7. Observability and Monitoring

No new observability changes are proposed. Existing authorization logs and
RoleBinding synchronization status apply.

# 8. Impact and Compatibility

The gRPC and protobuf contracts remain unchanged. Existing RoleBinding
requests and stored resources remain compatible. Reader roles add the
reviewed read-method grants within the user's existing resource scope; all
other grants remain effective. A role change does not update an already-issued
token; users must refresh or re-authenticate after Keycloak reports READY. No
database migration is needed because the seeded reader roles are reused.

## 8.1 Risks and Mitigations

- **A reader assignment does not make a regular client read-only.** The
  current general-client policy already grants mutations to ordinary
  non-admin users. Adding a reader role preserves those grants; the design
  and user documentation must make that behavior clear.
- **A method could be added to the reader list without being safe.** New RPCs
  remain denied until review confirms the method is read-only and retains
  tenant and object checks.
- **An active token may keep old permissions.** READY reports Keycloak sync
  only. The guide and UI explain that users must refresh or sign in again;
  tests compare access before and after refresh.
- **Hidden UI controls could be mistaken for revoked API access.** The UI may
  hide mutation controls for reader sessions while another grant still allows
  direct API calls. The UI and documentation must explain that controls do
  not change effective authorization.

## 8.2 Drawbacks

- The reviewed method list needs updates when new read RPCs are added.
- A new read method stays unavailable to readers until that review is done.
- Role changes do not affect active tokens until refresh or expiry.
- The reader roles do not provide strict read-only access to users who keep
  grants for mutations. A separate policy change would be needed to remove
  those grants, and is outside this additive design.
- Hiding controls changes the UI only; API access still follows all grants.

---

## Provenance

Authored: draft @ design 0.11.5 - 4164796, workspace main @ 95fbc127c
Final: respond @ design 0.11.5 - d1824b1, workspace main @ 95fbc127c

> Context changed between draft and respond.

<!-- ai-workflow-provenance:{"schema_version":1,"provenance_kind":"session","workflow":"design","workflow_version":"0.11.5","ai_workflows":"d1824b1","source_repo":"95fbc127c","source_repo_branch":"main","commits_behind_main":0,"commits_ahead_main":0,"main_ref":"main","phases":["draft","respond","respond","respond","respond","respond","respond","respond"],"authoring_modes":["skill"],"context_changed":true,"origin_untracked":false} -->
