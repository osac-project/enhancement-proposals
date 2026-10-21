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
  role grants reviewed read methods. An identity with a reader role does not
  receive the implicit general-client fallback.
- **Additive role grants:** grants from explicitly assigned roles combine.
  Adding a reader role does not remove a permission granted by another role.
- **Reader-only user:** a user with a reader role and no other assigned role
  or admin grant that allows methods outside the reviewed read list.
- **Reviewed read method:** an explicitly approved gRPC path whose method is
  exactly `Get`, `List`, or `Watch`, and whose handler keeps the existing
  tenant and object checks.
- **READY:** the RoleBinding controller has synchronized the role to Keycloak.
  It does not mean every active token has refreshed.

This design uses the existing Role and RoleBinding flow to give auditors
read-only access through the Fulfillment Service gRPC authorization policy.
The existing `tenant-reader` and `cloud-provider-reader` roles grant reviewed
methods named exactly `Get`, `List`, or `Watch`; a reader role also opts the
identity out of the implicit general-client fallback. Grants from other
explicitly assigned roles or an admin identity still apply. For example, a
user with a role that allows `Clusters/Create` keeps that access when
`tenant-reader` is added.
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
some writes. A reader allow rule alone would not take away those default grants,
so this design skips the defaults for reader identities while preserving
permissions granted by other assigned roles. [Codebase:
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
claims to OPA. For an identity with a reader role, OPA combines the reviewed
reader grants with explicit grants from other assigned roles or an admin
identity. It skips the implicit general-client fallback and default
metadata, reflection, and health grants. Without a reader role, the current
policy behavior remains in place. Allowed calls continue to the existing
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
  Existing[Other explicit role or admin grants] --> OPA
  Default[Default client and global allow rules] -->|when no reader role| OPA
  OPA -->|reader role: reviewed reads plus explicit grants| Handler[Existing API handler]
  OPA -->|no reader role: existing policy| Handler
  Handler --> Scope[Existing tenant and object checks]
  OPA -->|no matching grant: PERMISSION_DENIED| Denied[Request rejected]
~~~

The diagram shows administrators assigning a role through existing surfaces,
other assigned-role grants, and default policy grants. A reader role skips the
default grants, including general-client, metadata, reflection, and health
allows. Grants from other assigned roles or admin identities still combine
with the reader grants. For example, if another role allows
`/osac.public.v1.Clusters/Create`, that method remains allowed after
`tenant-reader` is added. Without such another role grant, the reader identity
can call only explicitly reviewed paths ending in exactly `Get`, `List`, or
`Watch`, and those handlers keep their existing tenant and object checks.

The policy can express this decision as:

~~~text
if identity_has_reader_role:
    decision = grants_from_assigned_roles_and_admin_identity(
        reviewed_reader_rpc_paths,
        other_explicit_grants,
    )
else:
    decision = existing_policy_decision
~~~

For example, `GetByName` does not match `Get`, so the reader role does not
grant it. An explicit role or admin grant may still allow it. The
general-client fallback is implicit policy behavior, not an assigned role,
and does not apply when a reader role is present. A reader-only user is
therefore limited to reviewed read methods. A separate role that grants
writes still allows those writes.

The policy should exclude reader identities from the ordinary `is_client`
fallback. It should keep client-level grants inherited from explicit roles
such as `tenant-admin`; those assigned-role grants remain additive.

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
PERMISSION_DENIED with message permission denied for a reader-only user.
Explicit grants from another role or admin identity still apply, while the
implicit general-client fallback and global default allows do not apply to
identities with a reader role. Existing role-binding APIs and other users keep
their current behavior. There is no new request validation or error code.
[Codebase: fulfillment-service/internal/auth/grpc_authz_interceptor.go]

## 4.4 Scalability and Performance

Each request adds a role-membership check and an exact method-path check to
the existing in-process OPA evaluation. It adds no database query or
network call to the request path. Keycloak traffic remains limited to the
existing asynchronous role-binding reconciliation. Storage and retention do
not change. [Codebase:
fulfillment-service/internal/auth/authorization_evaluator.go]

## 4.5 Security Considerations

The policy gives reader identities the reviewed read-method grants and skips
the implicit general-client fallback. This makes a reader-only account
read-only even when it would otherwise be classified as a general client.
Grants from other explicitly assigned roles remain additive, so an account
with a separate write-capable role or admin privilege can still make the
changes it allows. Administrators should not give those privileges to an
auditor account.
[User]

The method rule does not grant access to every object. Existing tenant and
object-level checks remain in the handlers and data paths. Tests must cover
both an allowed read in the user's scope and a read outside that scope.
[PRD: In Scope]

The current policy also has global allows for metadata, reflection, and
health paths. Those default allows do not apply to an identity with a reader
role, consistent with the rule that a reader-only account can call only
reviewed Get, List, and Watch methods. Explicit role and admin grants still
apply. Reviewed read methods continue through the existing scope checks.

## 4.6 Failure Handling and Recovery

- A denied method returns PERMISSION_DENIED with the existing message
  permission denied. The request does not reach the handler.
- A failed role-binding reconciliation remains visible as FAILED through the
  existing status model. The user does not receive the intended role until
  Keycloak synchronization succeeds.
- The policy reads roles from the JWT. A token minted before a role change
  keeps its existing claims until it is refreshed or replaced. READY confirms
  Keycloak synchronization, not that every active session has refreshed.
  Users must refresh their token before relying on the changed access.
  Existing tokens keep the access allowed by their current claims until they
  expire or are replaced.

## 4.7 RBAC / Tenancy

The `tenant-reader` role stays within its existing tenant scope.
`cloud-provider-reader` keeps the user's existing provider authorization
scope; assigning it does not add visibility to other tenants or resources.

The UI session mapper returns a reader category when either role is present,
and the UI hides Create, Update, and Delete controls for reader sessions.
This is a presentation choice; it does not revoke API access granted by
another explicitly assigned role or admin identity. Server-side authorization
combines the reader grants with those explicit grants, while skipping the
implicit general-client fallback for identities with a reader role.

Each reader role grants only reviewed methods named exactly `Get`, `List`, or
`Watch`. A method name does not bypass existing tenant or object checks. Users
without a reader role keep the existing authorization behavior, including
general-client fallback grants.

## 4.8 Extensibility / Future-Proofing

The reader grants use an explicit list of reviewed read-method paths. New
RPCs receive no grant from a reader role until reviewed, even when their
method is named `Get`, `List`, or `Watch`. Another explicitly assigned role
may still allow a new method. Review confirms each reader path is read-only
and its handler keeps the existing tenant and object checks.

# 5. Interface Changes

The PRD has no FR or NFR identifiers. For this design and testplan only,
FR-1 refers to the first In Scope bullet and FR-2 to the second. These labels
are trace references, not new requirements.

## IC-1: Reader method grants with additive explicit roles

**Requirements:** FR-1

The reader roles add reviewed Get, List, and Watch grants. They skip the
implicit general-client fallback, so a reader-only identity is denied every
other method. Explicit grants from another role or an admin identity still
apply; for example, a tenant-admin role may grant Create, Update, or Delete
through its existing client permissions. Existing tenant and object checks
continue to filter results. See §4.1, §4.3, and §4.7.

## IC-2: Assign a reader role through the existing RoleBindings API

**Requirements:** FR-2

Cloud Provider Admins and Tenant Admins use existing RoleBinding methods to
add the reader role. The existing controller syncs it to Keycloak and reports
its status. Grants from other assigned roles or admin identities remain
effective, and `cloud-provider-reader` keeps the user's existing provider
scope. See §4.1, §4.3, and §4.7.

## IC-3: Assign a reader role in the OSAC UI

**Requirements:** FR-1, FR-2

The Role Bindings page and form use the existing Roles and RoleBindings APIs
to show and assign the reader role to eligible users. The session mapper
returns the reader category for assigned users and hides Create, Update, and
Delete controls. This does not remove API grants from other assigned roles or
admin identities. See §4.1 and §4.7.

## IC-4: Explain read-only permissions in user documentation

**Requirements:** FR-2

Update the tenant identity and access guide with the API and UI assignment
paths, the reader role's exact method grants, the additive behavior of
explicit role grants, the general-client fallback exception, tenant and
provider scope, hidden mutation controls, and READY versus token refresh
timing. See §4.3, §4.6, and §4.7.

# 6. Alternatives Considered

- **Add a new permission field or custom action set to Role.** This could
  describe more combinations, but the PRD excludes custom per-resource
  permissions, and the existing reader roles provide a role-based path.
- **Keep the general-client fallback for reader identities.** This would
  leave ordinary client users able to write after receiving a reader role,
  which would not meet the auditor use case. The design skips that implicit
  fallback while keeping grants from other assigned roles additive.
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
requests and stored resources remain compatible. Reader roles grant reviewed
read methods within the user's existing resource scope and skip the implicit
general-client fallback. Grants from other explicitly assigned roles remain
effective. A role change does not update an already-issued token; users must
refresh their token after Keycloak reports READY. No database migration is
needed because the seeded reader roles are reused.

## 8.1 Risks and Mitigations

- **A reader assignment removes default client access.** An ordinary client
  with a reader role loses the implicit general-client fallback. The UI and
  user documentation should make clear that users needing writes require
  another explicitly assigned role that grants them.
- **A method could be added to the reader list without being safe.** New RPCs
  remain denied until review confirms the method is read-only and retains
  tenant and object checks.
- **An active token may keep old permissions.** READY reports Keycloak sync
  only. The guide and UI explain that users must refresh their token; tests
  compare access before and after refresh.
- **Hidden UI controls could be mistaken for revoked API access.** The UI may
  hide mutation controls for reader sessions while another assigned role
  still allows direct API calls. The UI and documentation must explain that
  controls do not change those role grants.

## 8.2 Drawbacks

- The reviewed method list needs updates when new read RPCs are added.
- A new read method stays unavailable to readers until that review is done.
- Role changes do not affect active tokens until refresh or expiry.
- Another assigned role or admin grant can still allow mutations for a reader
  identity. Administrators must keep those grants off auditor accounts.
- Hiding controls changes the UI only; API access still follows all grants.

---

## Provenance

Authored: draft @ design 0.11.5 - 4164796, workspace main @ 95fbc127c
Final: respond @ design 0.11.5 - d1824b1, workspace main @ 95fbc127c

> Context changed between draft and respond.

<!-- ai-workflow-provenance:{"schema_version":1,"provenance_kind":"session","workflow":"design","workflow_version":"0.11.5","ai_workflows":"d1824b1","source_repo":"95fbc127c","source_repo_branch":"main","commits_behind_main":0,"commits_ahead_main":0,"main_ref":"main","phases":["draft","respond","respond","respond","respond","respond","respond","respond","respond"],"authoring_modes":["skill"],"context_changed":true,"origin_untracked":false} -->
