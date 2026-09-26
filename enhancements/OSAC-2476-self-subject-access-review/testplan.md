# Testplan — OSAC-2476

## Overview

- **Feature:** OSAC-2476 — Self-Subject Access Review API
- **Total test cases:** 15
- **Requirements covered:** 6 of 6 (3 user stories + 3 technical requirements)
- **Interface changes covered:** 1 of 1

Permission review requests use `spec.service` and `spec.method`; optional tenant
scope and target resource name are supplied in the review object's top-level
`metadata.tenant` and `metadata.name` fields.

## Test Cases

### US-1: Tenant Admin Management Operations

**User Story:** As a tenant admin, I want to check whether I have permission to perform management operations (create VirtualNetwork, manage users via User resource operations, update Tenant quota settings) before attempting them via the UI, CLI, or API, so that interfaces can show or hide actions based on my actual permissions and prevent navigation to features I cannot use

#### TC-US1-01: Check permission to create VirtualNetwork

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-1 | high | automated |

##### Preconditions

- Tenant admin user is authenticated with JWT token
- User is a member of tenant `org-a` with `tenant-admin` realm role

##### Steps

1. Send `CreateSelfSubjectAccessReviewRequest` with `spec.service="osac.public.v1.VirtualNetworks"`, `spec.method="Create"`, `metadata.tenant="org-a"`
2. Observe response

##### Expected Results

- Response `status.allowed` is `true`
- `status.reason` is empty (v1 does not return denial reasons)

#### TC-US1-02: Check permission to create VirtualNetwork in non-member tenant

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-1 | high | automated |

##### Preconditions

- Tenant admin user is authenticated with JWT token
- User is a member of tenant `org-a` with `tenant-admin` realm role
- User is NOT a member of tenant `org-b`

##### Steps

1. Send `CreateSelfSubjectAccessReviewRequest` with `spec.service="osac.public.v1.VirtualNetworks"`, `spec.method="Create"`, `metadata.tenant="org-b"`
2. Observe response

##### Expected Results

- Response `status.allowed` is `false`
- `status.reason` is empty; the response does not describe the target tenant

#### TC-US1-03: Check permission to manage users via User resource operations

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-1 | high | automated |

##### Preconditions

- Tenant admin user is authenticated with JWT token
- User has `tenant-admin` realm role

##### Steps

1. Send `CreateSelfSubjectAccessReviewRequest` with `spec.service="osac.public.v1.Users"`, `spec.method="Create"`
2. Observe response

##### Expected Results

- Response `status.allowed` is `true` (tenant admins can manage users)
- `status.reason` is empty

### US-2: Tenant User Infrastructure Operations

**User Story:** As a tenant user, I want to check whether I have permission to create or delete infrastructure resources in a specific tenant, so that the UI and CLI can validate permissions upfront

#### TC-US2-01: Check permission to create ComputeInstance

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-1 | critical | automated |

##### Preconditions

- Tenant user is authenticated with JWT token
- User is a member of tenant `org-a` with `client` role

##### Steps

1. Send `CreateSelfSubjectAccessReviewRequest` with `spec.service="osac.public.v1.ComputeInstances"`, `spec.method="Create"`, `metadata.tenant="org-a"`
2. Observe response

##### Expected Results

- Response `status.allowed` is `true`
- `status.reason` is empty

#### TC-US2-02: Check permission to delete Subnet in own tenant

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-1 | high | automated |

##### Preconditions

- Tenant user is authenticated with JWT token
- User is a member of tenant `org-a`
- User has previously created READY NetworkACL `test-acl` in VirtualNetwork `prod-net` and Subnet `test-subnet` in `prod-net` with an explicit `network_acl` reference to `test-acl`

##### Steps

1. Send `CreateSelfSubjectAccessReviewRequest` with `spec.service="osac.public.v1.Subnets"`, `spec.method="Delete"`, `metadata.tenant="org-a"`, `metadata.name="test-subnet"`
2. Observe response

##### Expected Results

- Response `status.allowed` is `true`
- `status.reason` is empty

### US-3: Tenant User Resource-Scoped Permissions

**User Story:** As a tenant user, I want to check resource-scoped permissions for supported operations on a specific resource by name before enabling actions, so that I know which operations are available before attempting them

#### TC-US3-01: Check permission to delete specific VirtualNetwork owned by another user

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-1 | high | automated |

##### Preconditions

- Tenant user is authenticated with JWT token
- User is a member of tenant `org-a`
- Another user in `org-a` has created a VirtualNetwork named `other-net`
- Current user does not own `other-net`

##### Steps

1. Send `CreateSelfSubjectAccessReviewRequest` with `spec.service="osac.public.v1.VirtualNetworks"`, `spec.method="Delete"`, `metadata.tenant="org-a"`, `metadata.name="other-net"`
2. Observe response

##### Expected Results

- Response `status.allowed` is `false`
- `status.reason` is empty; the response does not describe the resource

### TR-1: Comprehensive Resource Coverage

**Technical Requirement:** Support permission checks for all OSAC resource types and standard verbs

#### TC-TR1-01: Check permissions for all resource types

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-1 | critical | automated |

##### Preconditions

- Admin user is authenticated with JWT token

##### Steps

1. For each OSAC service (`osac.public.v1.Clusters`, `osac.public.v1.ComputeInstances`, `osac.public.v1.DiskImages`, `osac.public.v1.ExternalIPs`, `osac.public.v1.ExternalIPAttachments`, `osac.public.v1.ExternalIPPools`, `osac.public.v1.NATGateways`, `osac.public.v1.NetworkACLs`, `osac.public.v1.Subnets`, `osac.public.v1.Tenants`, `osac.public.v1.Users`, `osac.public.v1.VirtualNetworks`):
   - Send `CreateSelfSubjectAccessReviewRequest` with `spec.service=<service>` and a method supported by that service; use `spec.method="List"` for `osac.public.v1.ExternalIPPools` and `spec.method="Create"` for the other listed services
   - Verify response `status.allowed` is `true` (admin has all permissions)
2. Observe all responses

##### Expected Results

- All permission checks return `status.allowed=true`
- No errors for any resource type

#### TC-TR1-02: Check permissions for all verbs

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-1 | high | automated |

##### Preconditions

- Admin user is authenticated with JWT token

##### Steps

1. For each method (`Create`, `Get`, `List`, `Update`, `Delete`):
   - Send `CreateSelfSubjectAccessReviewRequest` with `spec.service="osac.public.v1.Clusters"`, `spec.method=<method>`
   - Verify response is returned without error
2. Observe all responses

##### Expected Results

- All permission checks return valid responses
- No `InvalidArgument` errors for any method

#### TC-TR1-03: Reject unknown services, unsupported methods, and recursive reviews

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-1 | high | automated |

##### Preconditions

- Tenant user is authenticated with JWT token

##### Steps

1. Request a review for an unknown service.
2. Request a review for a known service with an unsupported method, including `Create` on `osac.public.v1.ExternalIPPools` and `Update` on `osac.public.v1.NetworkACLs` and `osac.public.v1.Subnets`.
3. Request a review for `osac.public.v1.SelfSubjectAccessReviews` with method `Create`.

##### Expected Results

- Each request returns `InvalidArgument` and no authorization evaluation is performed.
- The review service cannot recursively evaluate itself.

#### TC-TR1-04: Require authentication for permission reviews

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-1 | high | automated |

##### Steps

1. Call `SelfSubjectAccessReviews.Create` without an authentication token.
2. Call it again with an expired token.

##### Expected Results

- Both requests return `Unauthenticated`.
- No permission result is returned.

### TR-2: Authorization Consistency

**Technical Requirement:** Permission check results must match actual authorization outcomes for the same user attempting the same operation across different roles and resource types

#### TC-TR2-01: Permission check matches actual operation for allowed case

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-1 | critical | automated |

##### Preconditions

- Tenant admin user is authenticated with JWT token
- User is a member of tenant `org-a` with `tenant-admin` realm role

##### Steps

1. Send `CreateSelfSubjectAccessReviewRequest` with `spec.service="osac.public.v1.VirtualNetworks"`, `spec.method="Create"`, `metadata.tenant="org-a"`
2. Observe permission check response `status.allowed` value
3. Attempt actual `VirtualNetworks.Create()` call for tenant `org-a`
4. Observe actual operation result

##### Expected Results

- Permission check returns `status.allowed=true`
- Actual create operation succeeds (returns success status, not `PermissionDenied`)

#### TC-TR2-02: Permission check matches actual operation for denied case

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-1 | critical | automated |

##### Preconditions

- Client user is authenticated with JWT token
- User has `client` role (not tenant-admin)

##### Steps

1. Send `CreateSelfSubjectAccessReviewRequest` with `spec.service="osac.public.v1.Tenants"`, `spec.method="Update"`, `metadata.name="org-a"`
2. Observe permission check response `status.allowed` value
3. Attempt actual `Tenants.Update()` call
4. Observe actual operation result

##### Expected Results

- Permission check returns `status.allowed=false`
- Actual update operation fails with `PermissionDenied` gRPC error

#### TC-TR2-03: Do not expose evaluator failures

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-1 | high | automated |

##### Preconditions

- The handler is configured with a fake authorization evaluator that returns an error containing internal policy details.

##### Steps

1. Send a valid `CreateSelfSubjectAccessReviewRequest`.
2. Observe the gRPC response and server logs.

##### Expected Results

- The request returns `Internal` with a generic error message.
- The response does not include evaluator, policy, tenant, or resource details.
- Server-side diagnostics record a sanitized evaluator failure without the raw error or user-provided tenant/resource values.

#### TC-TR2-04: Cross-tenant denials do not disclose resource information

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-1 | critical | automated |

##### Preconditions

- Tenant user is authenticated in `org-a` and is not a member of `org-b`.
- A VirtualNetwork named `private-net` exists in `org-b`.

##### Steps

1. Request a review for `osac.public.v1.VirtualNetworks`, method `Get`, with `metadata.tenant="org-b"` and `metadata.name="private-net"`.
2. Repeat with a name that does not exist in `org-b`.
3. Observe both responses.

##### Expected Results

- Both responses have `status.allowed=false` and empty `status.reason`.
- Neither response reveals whether the target resource exists or repeats the tenant/resource name.

### TR-3: Advisory Results

**Technical Requirement:** Validation that permission check results reflect authorization state at check time, but actual operations must independently re-evaluate authorization

#### TC-TR3-01: Authorization state change between check and operation

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-1 | high | manual |

##### Preconditions

- Tenant user is authenticated with JWT token
- User initially has permission to create Clusters

##### Steps

1. Send `CreateSelfSubjectAccessReviewRequest` with `spec.service="osac.public.v1.Clusters"`, `spec.method="Create"`
2. Observe permission check returns `status.allowed=true`
3. Administrator revokes user's cluster creation permission via Keycloak (remove from appropriate group or revoke role)
4. User attempts actual `Clusters.Create()` call
5. Observe actual operation result

##### Expected Results

- Initial permission check returns `status.allowed=true`
- After permission revocation, actual create operation fails with `PermissionDenied` error
- This demonstrates that permission checks are advisory snapshots, not authoritative guarantees

## Test Execution and Implementation

- Add the end-to-end gRPC suite at `tests/e2e/iam/test_self_subject_access_review.py` in the OSAC source repository. Use the shared `GRPCClient` from `tests/e2e/core/grpc_client.py` and the `grpc`, `jwt_grpc_tenant1_admin`, `jwt_grpc_tenant1`, and `jwt_grpc_tenant2` fixtures from `tests/e2e/conftest.py`; follow the IAM reference pattern in `tests/e2e/references/test_iam_references.py`.
- Test evaluator errors in fulfillment-service unit tests with a fake `AuthorizationEvaluator`; the E2E suite should cover API-visible status and authentication behavior.
- The external test-infrastructure repository provisions dependencies; test suites belong in the OSAC source repository.

## Gaps

### Requirement Coverage Gaps

All PRD requirements have test cases.

### Interface Change Coverage Gaps

All interface changes are exercised by test cases.

## Summary

| Metric | Count |
|--------|-------|
| Total test cases | 15 |
| Critical | 5 |
| High | 10 |
| Medium | 0 |
| Low | 0 |
| Manual | 1 |
| Automated | 14 |
| Requirements with test cases | 6 / 6 |
| Interface changes with test cases | 1 / 1 |

---

## Provenance

Authored: revise @ design 0.11.3 - cc0daa6, workspace main @ 06d340f90 (43 behind origin/main)

> This document's phase history does not include an initial /draft — structure was not verified against the template from origin.

<!-- ai-workflow-provenance:{"schema_version":1,"provenance_kind":"session","workflow":"design","workflow_version":"0.11.3","ai_workflows":"cc0daa6","source_repo":"06d340f90","source_repo_branch":"main","commits_behind_main":43,"commits_ahead_main":0,"main_ref":"main","phases":["revise"],"authoring_modes":["skill"],"context_changed":false,"origin_untracked":true} -->
