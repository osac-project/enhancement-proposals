# Testplan — OSAC-2476

## Overview

- **Feature:** OSAC-2476 — Self-Subject Access Review API
- **Total test cases:** 15
- **Requirements covered:** 6 of 6 (3 user stories + 3 technical requirements)
- **Interface changes covered:** 1 of 1

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

1. Send `CreateSelfSubjectAccessReviewRequest` with `spec.resource_type="VirtualNetwork"`, `spec.verb="create"`, `spec.tenant="org-a"`
2. Observe response

##### Expected Results

- Response `status.allowed` is `true`
- No `status.reason` field present (permission granted)

#### TC-US1-02: Check permission to create VirtualNetwork in non-member tenant

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-1 | high | automated |

##### Preconditions

- Tenant admin user is authenticated with JWT token
- User is a member of tenant `org-a` with `tenant-admin` realm role
- User is NOT a member of tenant `org-b`

##### Steps

1. Send `CreateSelfSubjectAccessReviewRequest` with `spec.resource_type="VirtualNetwork"`, `spec.verb="create"`, `spec.tenant="org-b"`
2. Observe response

##### Expected Results

- Response `status.allowed` is `false`
- Response `status.reason` indicates user is not authorized for the specified tenant

#### TC-US1-03: Check permission to manage users via User resource operations

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-1 | high | automated |

##### Preconditions

- Tenant admin user is authenticated with JWT token
- User has `tenant-admin` realm role

##### Steps

1. Send `CreateSelfSubjectAccessReviewRequest` with `spec.resource_type="User"`, `spec.verb="create"`
2. Observe response

##### Expected Results

- Response `status.allowed` is `true` (tenant admins can manage users)
- No `status.reason` field present

### US-2: Tenant User Infrastructure Operations

**User Story:** As a tenant user, I want to check whether I have permission to create, update, or delete infrastructure resources (ComputeInstance, Subnet, SecurityGroup) in a specific tenant before starting the workflow, so that the UI and CLI can validate permissions upfront and warn me before I invest effort in changes I cannot save

#### TC-US2-01: Check permission to create ComputeInstance

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-1 | critical | automated |

##### Preconditions

- Tenant user is authenticated with JWT token
- User is a member of tenant `org-a` with `client` role

##### Steps

1. Send `CreateSelfSubjectAccessReviewRequest` with `spec.resource_type="ComputeInstance"`, `spec.verb="create"`, `spec.tenant="org-a"`
2. Observe response

##### Expected Results

- Response `status.allowed` is `true`
- No `status.reason` field present

#### TC-US2-02: Check permission to delete Subnet in own tenant

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-1 | high | automated |

##### Preconditions

- Tenant user is authenticated with JWT token
- User is a member of tenant `org-a`
- User has previously created a Subnet named `test-subnet` in `org-a`

##### Steps

1. Send `CreateSelfSubjectAccessReviewRequest` with `spec.resource_type="Subnet"`, `spec.verb="delete"`, `spec.tenant="org-a"`, `spec.resource_name="test-subnet"`
2. Observe response

##### Expected Results

- Response `status.allowed` is `true`
- No `status.reason` field present

#### TC-US2-03: Check permission to update SecurityGroup not owned by user

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-1 | high | automated |

##### Preconditions

- Tenant user is authenticated with JWT token
- User is a member of tenant `org-a`
- Another user in `org-a` has created a SecurityGroup named `other-sg`
- Current user does not own `other-sg`

##### Steps

1. Send `CreateSelfSubjectAccessReviewRequest` with `spec.resource_type="SecurityGroup"`, `spec.verb="update"`, `spec.tenant="org-a"`, `spec.resource_name="other-sg"`
2. Observe response

##### Expected Results

- Response `status.allowed` is `false`
- Response `status.reason` indicates user does not own the specified resource

### US-3: Tenant User Resource-Scoped Permissions

**User Story:** As a tenant user, I want to check resource-scoped permissions (update or delete operations on a specific resource by name) before enabling edit or delete actions, so that I know whether I can modify a particular resource before attempting the operation

#### TC-US3-01: Check permission to update specific VirtualNetwork by name

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-1 | high | automated |

##### Preconditions

- Tenant user is authenticated with JWT token
- User is a member of tenant `org-a`
- User has created a VirtualNetwork named `prod-net` in `org-a`

##### Steps

1. Send `CreateSelfSubjectAccessReviewRequest` with `spec.resource_type="VirtualNetwork"`, `spec.verb="update"`, `spec.tenant="org-a"`, `spec.resource_name="prod-net"`
2. Observe response

##### Expected Results

- Response `status.allowed` is `true`
- No `status.reason` field present

#### TC-US3-02: Check permission to delete specific VirtualNetwork owned by another user

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-1 | high | automated |

##### Preconditions

- Tenant user is authenticated with JWT token
- User is a member of tenant `org-a`
- Another user in `org-a` has created a VirtualNetwork named `other-net`
- Current user does not own `other-net`

##### Steps

1. Send `CreateSelfSubjectAccessReviewRequest` with `spec.resource_type="VirtualNetwork"`, `spec.verb="delete"`, `spec.tenant="org-a"`, `spec.resource_name="other-net"`
2. Observe response

##### Expected Results

- Response `status.allowed` is `false`
- Response `status.reason` indicates user does not own the specified resource

### TR-1: Comprehensive Resource Coverage

**Technical Requirement:** Support permission checks for all OSAC resource types and standard verbs

#### TC-TR1-01: Check permissions for all resource types

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-1 | critical | automated |

##### Preconditions

- Admin user is authenticated with JWT token

##### Steps

1. For each OSAC resource type (`Cluster`, `ComputeInstance`, `DiskImage`, `ExternalIP`, `ExternalIPAttachment`, `ExternalIPPool`, `NATGateway`, `SecurityGroup`, `Subnet`, `Tenant`, `VirtualNetwork`):
   - Send `CreateSelfSubjectAccessReviewRequest` with `spec.resource_type=<type>`, `spec.verb="create"`
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

1. For each verb (`create`, `get`, `list`, `update`, `delete`):
   - Send `CreateSelfSubjectAccessReviewRequest` with `spec.resource_type="Cluster"`, `spec.verb=<verb>`
   - Verify response is returned without error
2. Observe all responses

##### Expected Results

- All permission checks return valid responses
- No `InvalidArgument` errors for any verb

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

1. Send `CreateSelfSubjectAccessReviewRequest` with `spec.resource_type="VirtualNetwork"`, `spec.verb="create"`, `spec.tenant="org-a"`
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

1. Send `CreateSelfSubjectAccessReviewRequest` with `spec.resource_type="Tenant"`, `spec.verb="update"`
2. Observe permission check response `status.allowed` value
3. Attempt actual `Tenants.Update()` call
4. Observe actual operation result

##### Expected Results

- Permission check returns `status.allowed=false`
- Actual update operation fails with `PermissionDenied` gRPC error

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

1. Send `CreateSelfSubjectAccessReviewRequest` with `spec.resource_type="Cluster"`, `spec.verb="create"`
2. Observe permission check returns `status.allowed=true`
3. Administrator revokes user's cluster creation permission via Keycloak (remove from appropriate group or revoke role)
4. User attempts actual `Clusters.Create()` call
5. Observe actual operation result

##### Expected Results

- Initial permission check returns `status.allowed=true`
- After permission revocation, actual create operation fails with `PermissionDenied` error
- This demonstrates that permission checks are advisory snapshots, not authoritative guarantees

## Gaps

### Requirement Coverage Gaps

All PRD requirements have test cases.

### Interface Change Coverage Gaps

All interface changes are exercised by test cases.

## Summary

| Metric | Count |
|--------|-------|
| Total test cases | 15 |
| Critical | 3 |
| High | 11 |
| Medium | 0 |
| Low | 0 |
| Manual | 1 |
| Automated | 14 |
| Requirements with test cases | 6 / 6 |
| Interface changes with test cases | 1 / 1 |
