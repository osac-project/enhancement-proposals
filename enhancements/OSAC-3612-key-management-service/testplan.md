# Testplan — OSAC-3612

## Overview

- **Feature:** OSAC-3612 — Key Management Service: Key Lifecycle Management
- **Total test cases:** 30
- **Requirements covered:** 9 of 9 derived PRD requirement anchors
- **Interface changes covered:** 9 of 9

The PRD has no FR/NFR identifiers. The FR-1 through FR-9 headings below are the traceability-only anchors defined in §1 of the design and preserve the PRD requirement text without adding requirements.

## Test Cases

### FR-1: Create and view tenant-owned and provider-owned logical keys through API and CLI

#### TC-FR1-01: Tenant Admin creates and reads a tenant-owned key through the API

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-1 | critical | automated |

##### Preconditions

- OpenBao Transit is ready and the caller is a Tenant Admin in tenant `tenant-a`.

##### Steps

1. Create a ManagedKey named `data-key` without specifying ownership.
2. Poll Get until the key leaves `PROVISIONING`.
3. List ManagedKeys in `tenant-a`.

##### Expected Results

- Create returns a stable ManagedKey ID, ownership `TENANT`, desired state `ACTIVE`, and no key material.
- Get reaches state `ACTIVE` with active version `1`.
- List contains `data-key` only in `tenant-a`.

#### TC-FR1-02: Cloud Provider Admin creates a provider-owned key

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-1 | critical | automated |

##### Preconditions

- OpenBao Transit is ready and the caller has existing Cloud Provider Admin access.

##### Steps

1. Create a ManagedKey with ownership `PROVIDER`.
2. Poll Get until reconciliation reaches a terminal state.
3. Read the private persisted object as the controller service.

##### Expected Results

- The public resource reaches state `ACTIVE` with active version `1`.
- The persisted key is attributed to the reserved `system` tenant.
- Public responses contain neither provider coordinates nor key bytes.

#### TC-FR1-03: CLI creates, lists, and describes a key

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-3 | critical | automated |

##### Preconditions

- The CLI is authenticated as a Tenant Admin and the Transit backend is ready.

##### Steps

1. Run `osac create key --name cli-key`.
2. Run `osac list keys`.
3. Run `osac describe key cli-key` after reconciliation.

##### Expected Results

- Create prints the key ID and its accepted lifecycle state.
- List includes `cli-key`.
- Describe prints tenant ownership, `ACTIVE`, active version `1`, capabilities, and conditions without backend paths or key material.

### FR-2: Expose lifecycle state, active version, retained versions, and meaningful interim states

#### TC-FR2-01: API reports interim and final provisioning state

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-2 | high | automated |

##### Preconditions

- The Transit test provider can pause key creation after desired state is persisted.

##### Steps

1. Create a ManagedKey while the provider is paused.
2. Get the key before releasing the provider.
3. Release the provider and get the key after reconciliation.

##### Expected Results

- The first Get reports `PROVISIONING`, a pending/applying operation, and a Progressing condition.
- The final Get reports `ACTIVE`, active version `1`, version `1` marked active, and a Ready condition.

#### TC-FR2-02: Resource events carry backend-neutral lifecycle status

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-2 | high | automated |

##### Preconditions

- An Events watch is active for a Tenant Admin's visible resources.

##### Steps

1. Create and rotate a ManagedKey.
2. Collect ManagedKey events until rotation reaches `ACTIVE`.
3. Inspect every public event payload.

##### Expected Results

- Events include the progressing and resulting lifecycle states.
- The final payload reports active version `2` and version `1` as retained.
- No event includes a Transit mount, backend object ID, credential, or key material.

### FR-3: Rotate a logical key while preserving its identity and retained material versions

#### TC-FR3-01: Rotation promotes one new generation without changing associations

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-1 | critical | automated |

##### Preconditions

- An active key at version `1` has one private consumer association.

##### Steps

1. Update `spec.rotation_trigger` with request ID `rotation-1`.
2. Poll until the operation reaches a terminal state.
3. Read the key and its private association.

##### Expected Results

- The ManagedKey ID and association key reference are unchanged.
- State returns to `ACTIVE`, active version is `2`, version `1` is retained, and version `2` is active.
- `status.observed_rotation_trigger` equals `rotation-1`.

#### TC-FR3-02: Reusing a rotation request ID is idempotent

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-1 | critical | automated |

##### Preconditions

- Rotation request `rotation-1` has completed at version `2`.

##### Steps

1. Submit an Update containing the same rotation trigger and current metadata version.
2. Reconcile the key twice.
3. Read Transit and ManagedKey status.

##### Expected Results

- Transit latest version remains `2`.
- ManagedKey active version remains `2` and no new operation is created.

#### TC-FR3-03: Ambiguous rotation timeout is resolved by observation

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-2 | critical | automated |

##### Preconditions

- The provider test double applies rotation and then returns a timeout before the controller receives a response.

##### Steps

1. Request rotation from version `1`.
2. Allow the controller to retry reconciliation.
3. Read the final ManagedKey and provider state.

##### Expected Results

- The controller observes provider version `2` and records the operation as succeeded.
- Provider version `3` is not created.
- The public status never reports `DESTROYED` or an unknown active version.

#### TC-FR3-04: CLI rotation exposes request identity and completion

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-4 | high | automated |

##### Preconditions

- `cli-key` is active at version `1`.

##### Steps

1. Run `osac rotate key cli-key --request-id cli-rotation-1 --wait`.
2. Run `osac describe key cli-key`.

##### Expected Results

- The command prints `cli-rotation-1` and exits zero only after the operation reaches `SUCCEEDED`.
- Describe reports active version `2` and retained version `1`.

### FR-4: Revoke all versions, block normal use and new associations, and permit explicit authorized recovery

#### TC-FR4-01: Revocation blocks all Transit cryptographic use and new associations

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-5 | critical | automated |

##### Preconditions

- A key has two material versions and is active.

##### Steps

1. Update desired state to `REVOKED` and wait for observed state `REVOKED`.
2. Attempt Transit encrypt and decrypt operations through the test integration.
3. Attempt to create a new ManagedKeyAssociation.

##### Expected Results

- OpenBao rejects encryption and decryption for the softly deleted key across retained versions.
- Association creation returns `FailedPrecondition` with reason `KeyNotActive`.
- ManagedKey status remains `REVOKED` and retains both version metadata records.

#### TC-FR4-02: Authorized recovery restores normal key use

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-1 | critical | automated |

##### Preconditions

- A tenant-owned key is `REVOKED` and the caller is its Tenant Admin.

##### Steps

1. Update desired state from `REVOKED` to `ACTIVE`.
2. Wait for reconciliation.
3. Perform a Transit encrypt/decrypt round trip through the integration fixture.

##### Expected Results

- The key passes through `RECOVERING` and reaches `ACTIVE` without changing its ID or active version.
- The round trip returns the original plaintext to the fixture.
- Existing version metadata remains present.

#### TC-FR4-03: CLI revoke and recover show interim and terminal outcomes

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-4 | high | automated |

##### Preconditions

- The CLI is authenticated with lifecycle authority over an active key.

##### Steps

1. Run `osac revoke key cli-key --wait`.
2. Run `osac recover key cli-key --wait`.

##### Expected Results

- Revoke exits zero with terminal state `REVOKED`.
- Recover exits zero with terminal state `ACTIVE`.
- Both commands print the operation ID and resulting state.

### FR-5: Maintain consumer-neutral associations and reject destruction while a consumer remains attached

#### TC-FR5-01: Private service creates a same-tenant association

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-5 | critical | automated |

##### Preconditions

- An active tenant-owned key and an authorized downstream service identity exist in `tenant-a`.

##### Steps

1. Create an association using a ManagedKey local reference and structured consumer reference.
2. Repeat the same create request.

##### Expected Results

- The first request stores one association referencing the stable ManagedKey ID.
- The second returns `AlreadyExists`; the table still contains one row.

#### TC-FR5-02: Association validation enforces tenant and lifecycle state

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-5 | critical | automated |

##### Preconditions

- One active key exists in `tenant-a` and one revoked key exists in `tenant-b`.

##### Steps

1. Try to associate a `tenant-b` consumer with the `tenant-a` key.
2. Try to associate a `tenant-b` consumer with the revoked `tenant-b` key.

##### Expected Results

- The cross-tenant request returns `InvalidArgument` with reason `TenantMismatch`.
- The revoked-key request returns `FailedPrecondition` with reason `KeyNotActive`.
- Neither request inserts an association row.

#### TC-FR5-03: Destruction is rejected while a consumer remains associated

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-1 | critical | automated |

##### Preconditions

- An active key has one association.

##### Steps

1. Update desired state to `DESTROYED`.
2. Read the ManagedKey and Transit key.

##### Expected Results

- Update returns `FailedPrecondition` with reason `KeyInUse` and no consumer identity.
- Desired and observed state remain `ACTIVE`.
- Transit key material remains present.

#### TC-FR5-04: Association creation and destruction admission are race-safe

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-5 | critical | automated |

##### Preconditions

- An active key has no associations and the test can synchronize concurrent database transactions.

##### Steps

1. Concurrently submit association creation and desired state `DESTROYED`.
2. Allow both transactions to finish.
3. Inspect key state and association rows.

##### Expected Results

- Exactly one transaction wins the key-row lock first.
- If association creation commits, destruction returns `KeyInUse`; if destruction commits, association creation returns `KeyNotActive`.
- No committed association refers to a key whose destruction was admitted.

#### TC-FR5-05: Unassociated key is destroyed permanently before metadata deletion

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-4 | critical | automated |

##### Preconditions

- A key has no associations and is active or revoked.

##### Steps

1. Run `osac destroy key <key> --wait`.
2. Verify the provider key is absent.
3. Call ManagedKeys Delete for the destroyed key.

##### Expected Results

- The key passes through `DESTROYING` and reaches `DESTROYED` only after Transit returns not found.
- Delete then removes the OSAC metadata.
- Calling Delete before provider-confirmed destruction returns `FailedPrecondition`.

### FR-6: Enforce Tenant Admin, Cloud Provider Admin, Tenant User, and Cloud Infrastructure Admin boundaries

#### TC-FR6-01: Tenant Admin cannot access another tenant's keys

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-9 | critical | automated |

##### Preconditions

- Tenant-owned keys exist in `tenant-a` and `tenant-b`; caller administers only `tenant-a`.

##### Steps

1. List ManagedKeys.
2. Get and update the `tenant-b` key by ID.

##### Expected Results

- List contains only `tenant-a` keys.
- Get and Update for the `tenant-b` key return `NotFound` without disclosing its existence.

#### TC-FR6-02: Tenant User has no direct key-management authority

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-9 | high | automated |

##### Preconditions

- The caller is an authenticated Tenant User without the Tenant Admin role.

##### Steps

1. Invoke each ManagedKeys CRUD method.
2. Invoke KMSBackends Get and List.

##### Expected Results

- Every request returns `PermissionDenied`.
- No key or backend-health data is returned.

#### TC-FR6-03: Existing Cloud Provider Admin access remains broad

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-9 | critical | automated |

##### Preconditions

- Tenant-owned keys exist in two tenants and a provider-owned key exists in `system`.

##### Steps

1. Authenticate as an existing administrator.
2. List, get, and update each key within valid lifecycle transitions.

##### Expected Results

- The administrator can access all three keys under existing universal tenancy behavior.
- Provider-owned and tenant-owned ownership values remain unchanged.

#### TC-FR6-04: Cloud Infrastructure Admin can read only backend health

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-9 | critical | automated |

##### Preconditions

- The caller has only the `cloud-infrastructure-admin` realm role.

##### Steps

1. List and get KMSBackend status.
2. Invoke every ManagedKeys method.
3. Invoke KMSBackends Create, Update, and Delete.

##### Expected Results

- KMSBackends Get and List return normalized health data.
- ManagedKeys requests return `PermissionDenied`.
- Backend mutations return `PermissionDenied` for this role.

### FR-7: Let Cloud Provider Admins configure transparent platform backends and policies without tenant selection

#### TC-FR7-01: Valid OpenBao Transit configuration becomes ready

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-6 | high | automated |

##### Preconditions

- Helm values define an `openbao-transit` backend, tenant/provider default policies, and valid Vault connection data.

##### Steps

1. Deploy the service and controller with the configuration.
2. Wait for backend conformance checks.
3. Create one tenant-owned and one provider-owned key.

##### Expected Results

- Backend state becomes `READY` and reports rotate, revoke, recover, and destroy capabilities.
- Each key privately records the configured immutable backend and corresponding default policy.
- Tenant-facing requests contain no backend or policy selector.

#### TC-FR7-02: Invalid or incapable backend blocks key creation

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-7 | critical | automated |

##### Preconditions

- Configuration points to a reachable Transit implementation without required soft-delete/restore behavior or with an inaccessible mount.

##### Steps

1. Start the KMS controller.
2. Read KMSBackend status.
3. Attempt to create a ManagedKey.

##### Expected Results

- Backend state is `MISCONFIGURED` with normalized missing-capability or permission reason.
- ManagedKey creation returns `FailedPrecondition` naming the unavailable required capability without exposing credentials or raw provider responses.

#### TC-FR7-03: Configuration rejects ambiguous defaults and unsupported backend types

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-6 | high | automated |

##### Preconditions

- Helm/schema validation tools are available.

##### Steps

1. Validate values containing two tenant defaults.
2. Validate a policy referencing a missing backend.
3. Validate an unsupported backend type.

##### Expected Results

- Each configuration fails validation with the offending field path.
- No deployment manifest is accepted with ambiguous defaults, dangling references, or an unknown backend enum.

### FR-8: Give Cloud Infrastructure Admins read-only KMS health and availability visibility

#### TC-FR8-01: Health API distinguishes ready and unavailable backends

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-7 | high | automated |

##### Preconditions

- A configured backend can be made reachable and unreachable during the test.

##### Steps

1. Get backend status while OpenBao is ready.
2. Seal or stop OpenBao and wait for the next probe.
3. Get backend status again.

##### Expected Results

- The first response reports `READY`, required capabilities, and a last-check timestamp.
- The second reports `UNAVAILABLE`, a later timestamp, and a redacted normalized reason.
- Neither response contains tokens, certificates, tenant key counts, or tenant key identities.

#### TC-FR8-02: CLI renders backend availability without lifecycle controls

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-8 | high | automated |

##### Preconditions

- The CLI is authenticated as Cloud Infrastructure Admin and the backend is unavailable.

##### Steps

1. Run `osac list kms-backends`.
2. Run `osac describe kms-backend <name>`.
3. Inspect available subcommands for that identity.

##### Expected Results

- List and describe show `UNAVAILABLE`, last check time, capabilities, and normalized reason.
- Output contains no key inventory or credentials.
- Lifecycle commands invoked by this identity return `PermissionDenied`.

### FR-9: Return actionable outcomes and an unambiguous reported state, with API/CLI end-to-end coverage

#### TC-FR9-01: Terminal provider failure preserves confirmed state and actionable reason

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-2 | critical | automated |

##### Preconditions

- An active key is at version `1`, and the provider returns a non-retryable policy conflict for rotation.

##### Steps

1. Request rotation.
2. Wait for the operation to reach a terminal state.
3. Get the ManagedKey.

##### Expected Results

- State is `FAILED`, active version remains `1`, and current operation is `FAILED_TERMINAL`.
- The Failed condition reason is `ProviderPolicyConflict` and its message identifies the corrective configuration category without raw provider data.

#### TC-FR9-02: Controller restart resumes an in-progress operation

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-1 | critical | automated |

##### Preconditions

- A rotation desired state is persisted and provider execution is paused.

##### Steps

1. Stop the controller after the operation enters `APPLYING`.
2. Allow the provider effect to occur.
3. Restart the controller and wait for periodic reconciliation.

##### Expected Results

- The restarted controller observes the existing provider effect and records `SUCCEEDED`.
- Exactly one new material generation exists.
- The key does not remain indefinitely in an unqualified unknown state.

#### TC-FR9-03: Public API end-to-end lifecycle journey

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-1 | critical | automated |

##### Preconditions

- A deployed Fulfillment Service, PostgreSQL, Keycloak, and OpenBao 2.6+ Transit backend are available.

##### Steps

1. As Tenant Admin, create and view a key.
2. As an authorized service, add then remove an association.
3. Rotate, revoke, recover, and destroy the key through public declarative updates.
4. Delete destroyed metadata.

##### Expected Results

- Each operation exposes its interim and terminal state through the public API.
- Rotation retains the old generation, revocation blocks Transit use, recovery restores it, and destruction removes the provider key only after association removal.
- Cross-tenant and unauthorized access remain denied throughout the journey.

#### TC-FR9-04: CLI end-to-end lifecycle journey

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-4 | critical | automated |

##### Preconditions

- The OSAC CLI is authenticated as Tenant Admin against a deployed environment with a ready Transit backend.

##### Steps

1. Create and describe a key.
2. Rotate, revoke, and recover with `--wait`.
3. Destroy the unassociated key with `--wait`.

##### Expected Results

- Every command exits zero only on its specified terminal state and prints the operation/request identity.
- Describe output reflects active version `2` after rotation, `REVOKED` after revoke, `ACTIVE` after recovery, and `DESTROYED` after destruction.
- Any server rejection is printed with its gRPC reason and actionable message.

## Gaps

### Requirement Coverage Gaps

All derived PRD requirement anchors have test cases.

### Interface Change Coverage Gaps

All interface changes are exercised by test cases.

## Summary

| Metric | Count |
|--------|-------|
| Total test cases | 30 |
| Critical | 21 |
| High | 9 |
| Medium | 0 |
| Low | 0 |
| Automated | 30 |
| Manual | 0 |
| Requirements with test cases | 9 / 9 |
| Interface changes with test cases | 9 / 9 |
