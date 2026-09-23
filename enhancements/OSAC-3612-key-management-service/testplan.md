# Testplan — OSAC-3612

## Overview

- **Feature:** OSAC-3612 — Key Management Service: Key Lifecycle Management
- **Total test cases:** 32
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

- HashiCorp Vault Transit and the key-scoped consumer policy are ready, and the caller is a Tenant Admin in tenant `tenant-a`.

##### Steps

1. Create a ManagedKey named `data-key` with request ID `create-data-key-1` and without specifying `metadata.tenant`.
2. Get the returned key.
3. List ManagedKeys in `tenant-a`.

##### Expected Results

- Create returns only after Vault creation is confirmed, with a stable ManagedKey ID, `metadata.tenant=tenant-a`, purpose `ENCRYPT_DECRYPT`, active version `1`, no lifecycle timestamps or pending operation, and no key material.
- Get reads Vault and reports the same confirmed version.
- List contains `data-key` only in `tenant-a`.

#### TC-FR1-02: Cloud Provider Admin creates a provider-owned key

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-1 | critical | automated |

##### Preconditions

- HashiCorp Vault Transit is ready and the caller has existing Cloud Provider Admin access.

##### Steps

1. Create a ManagedKey with `metadata.tenant=system` and a request ID.
2. Read the private persisted object as the service identity.
3. Attempt creation with `metadata.tenant=shared` and with no tenant specified.
4. As a Tenant Admin, attempt creation with `metadata.tenant=system`.

##### Expected Results

- Create returns a public resource with active version `1` and no lifecycle timestamps or pending operation.
- The public and persisted key are attributed to the reserved `system` tenant, with no separate ownership field.
- The `shared` and unspecified-tenant requests are rejected without creating a key.
- The Tenant Admin request for `system` returns `PermissionDenied`.
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
3. Run `osac describe key cli-key`.

##### Expected Results

- Create prints the key ID and active version `1` after confirmation.
- List includes `cli-key`.
- Describe prints the owning tenant, `ENCRYPT_DECRYPT` purpose, derived active lifecycle, and active version `1` without backend paths or key material.

### FR-2: Expose confirmed lifecycle facts, active and retained versions, and meaningful interim status

#### TC-FR2-01: API reports an uncertain create outcome and explicit verification

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-2 | high | automated |

##### Preconditions

- The Transit test provider can apply key creation and then withhold its response until the client request times out.

##### Steps

1. Create a ManagedKey with request ID `create-timeout-1` and time out after Vault applies the effect.
2. List the tenant's keys by name before any retry.
3. Retry Create with `create-timeout-1` after the provider is available.

##### Expected Results

- List contains no unconfirmed key after the timeout; the internal request reservation retains the request ID.
- The retry observes the existing Vault key and policy, returns a key with active version `1` and no pending operation, and creates no second key.

#### TC-FR2-02: Resource events carry backend-neutral lifecycle status

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-2 | high | automated |

##### Preconditions

- An Events watch is active for a Tenant Admin's visible resources.

##### Steps

1. Create and rotate a ManagedKey.
2. Collect ManagedKey events through the successful Rotate response.
3. Inspect every public event payload.

##### Expected Results

- Events show `pending_operation.type=ROTATE` while the provider call is in progress and no pending operation after confirmation.
- The final payload reports active version `2`; version `1` is retained by being listed below the active generation.
- No event includes a Transit mount, backend object ID, credential, or key material.

#### TC-FR2-03: Get checks Vault while List remains a last-confirmed snapshot

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-2 | critical | automated |

##### Preconditions

- An active key is confirmed at version `1`, and the test can interrupt Vault and remove its key out of band.

##### Steps

1. Make Vault unavailable; call List and Get.
2. Restore Vault, remove the Transit key without an OSAC Destroy request, and call Get again.

##### Expected Results

- List still shows the last-confirmed key metadata; Get returns `Unavailable` rather than treating the snapshot as a live provider check.
- The later Get returns a normalized `BackendDrift` error; `destroyed_at` remains absent and OSAC does not label the out-of-band deletion as an authorized destruction.

### FR-3: Rotate a logical key while preserving its identity and retained material versions

#### TC-FR3-01: Rotation promotes one new generation without changing associations

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-1 | critical | automated |

##### Preconditions

- An active key at version `1` has one private consumer association.

##### Steps

1. Call Rotate with request ID `rotation-1` and the current metadata version.
2. Inspect the successful response.
3. Read the key and its private association.

##### Expected Results

- The ManagedKey ID and association key reference are unchanged.
- Active version is `2`, versions `1` and `2` remain listed, and no revocation or destruction timestamp is set.
- The successful response has no pending operation or completed-operation history.

#### TC-FR3-02: Reusing a rotation request ID is idempotent

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-1 | critical | automated |

##### Preconditions

- Rotation request `rotation-1` has completed at version `2`.

##### Steps

1. Call Rotate again with request ID `rotation-1`.
2. Read Transit and the ManagedKey.

##### Expected Results

- Transit latest version remains `2`.
- ManagedKey active version remains `2`; no new rotation is sent to Vault and no pending operation appears.

#### TC-FR3-03: Ambiguous rotation timeout is resolved by observation

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-2 | critical | automated |

##### Preconditions

- The provider test double applies rotation and then returns a timeout before the API handler receives a response.

##### Steps

1. Call Rotate from version `1` with request ID `rotation-timeout-1`.
2. Confirm the API returns a timeout and Get shows `pending_operation.type=ROTATE` with last confirmed version `1`.
3. Retry Rotate with `rotation-timeout-1`; read the final ManagedKey and provider state.

##### Expected Results

- The retry observes provider version `2`, advances the confirmed active version, and clears the pending marker.
- Provider version `3` is not created.
- The public object never sets `destroyed_at` or reports an unconfirmed active version.

#### TC-FR3-04: CLI rotation exposes request identity and completion

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-4 | high | automated |

##### Preconditions

- `cli-key` is active at version `1`.

##### Steps

1. Run `osac rotate key cli-key --request-id cli-rotation-1`.
2. Run `osac describe key cli-key`.

##### Expected Results

- The command prints `cli-rotation-1` and exits zero only after the new active version is confirmed and persisted.
- Describe reports active version `2` and retained version `1`.

#### TC-FR3-05: A timed-out rotation still in flight is not repeated

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-2 | critical | automated |

##### Preconditions

- The Transit test provider can hold the first Rotate POST in flight while reads still report version `1`.

##### Steps

1. Call Rotate with request ID `rotation-inflight-1` and let the client time out while the first POST is held.
2. Retry Rotate with the same request ID before releasing the first POST.
3. Let the first POST complete, then retry with the same request ID again.

##### Expected Results

- The first retry returns a verification-required error and issues no second Rotate POST; Get reports a pending rotation with last confirmed version `1`.
- The final retry confirms version `2`, clears the pending marker, and never creates version `3`.

### FR-4: Revoke all versions, block normal use and new associations, and permit explicit authorized recovery

#### TC-FR4-01: Revocation blocks existing Vault consumer tokens and new associations

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-5 | critical | automated |

##### Preconditions

- A key has two material versions and is active; a consumer token issued before revocation has only that key's policy.

##### Steps

1. Call Revoke with a request ID and wait for the synchronous response.
2. Use the pre-existing consumer token to attempt Vault Transit encrypt and decrypt against both retained versions.
3. Attempt to create a new ManagedKeyAssociation.

##### Expected Results

- Vault rejects encryption and decryption under the updated key-specific ACL; the Transit key and both material versions still exist.
- A new normal consumer credential cannot bypass the denied policy, and an unrelated key remains usable.
- Association creation returns `FailedPrecondition` with reason `KeyNotActive`.
- `revoked_at` is set only after denial is verified, `destroyed_at` is absent, and both version metadata records remain.

#### TC-FR4-02: Authorized recovery restores normal key use

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-1 | critical | automated |

##### Preconditions

- A tenant-owned key has `revoked_at` set, the caller is its Tenant Admin, and the provider fixture can pause recovery after the pending marker commits.

##### Steps

1. Start Recover with a request ID and pause the provider effect.
2. Get the key, then release the provider call and wait for the synchronous response.
3. Perform a Vault Transit encrypt/decrypt round trip using a consumer token that existed before revocation.

##### Expected Results

- While Recover is in flight, `pending_operation.type=RECOVER` is visible; success clears both `pending_operation` and `revoked_at` without changing the ID or active version.
- The restored key-specific policy permits the round trip and returns the original plaintext to the fixture.
- Existing version metadata remains present.

#### TC-FR4-03: CLI revoke and recover show interim and terminal outcomes

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-4 | high | automated |

##### Preconditions

- The CLI is authenticated with lifecycle authority over an active key.

##### Steps

1. Run `osac revoke key cli-key`.
2. Run `osac recover key cli-key`.

##### Expected Results

- Revoke exits zero only with a confirmed `revoked_at` timestamp.
- Recover exits zero only after `revoked_at` is cleared.
- Both commands print the request ID and the lifecycle derived from the confirmed timestamp.

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

1. Call Destroy with a request ID.
2. Read the ManagedKey and Transit key.

##### Expected Results

- Destroy returns `FailedPrecondition` with reason `KeyInUse` and no consumer identity.
- `destroyed_at` remains absent and no pending destruction or internal destruction record is created.
- Transit key material remains present.

#### TC-FR5-04: Association creation and destruction admission are race-safe

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-5 | critical | automated |

##### Preconditions

- An active key has no associations and the test can synchronize concurrent database transactions.

##### Steps

1. Concurrently submit association creation and a Destroy request.
2. Allow both transactions to finish.
3. Inspect the pending/destroyed markers and association rows.

##### Expected Results

- Exactly one transaction wins the key-row lock first.
- If association creation commits, destruction returns `KeyInUse`; if destruction commits, association creation returns `KeyNotActive`.
- No committed association refers to a key whose destruction was admitted.

#### TC-FR5-05: Unassociated key is destroyed permanently before metadata deletion

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-4 | critical | automated |

##### Preconditions

- A key has no associations and is active or revoked; the provider fixture can pause destruction after the pending marker commits.

##### Steps

1. Start `osac destroy key <key>` and pause the provider deletion.
2. Get the key, then release the provider call and wait for the CLI result.
3. Verify the provider key is absent.
4. Call ManagedKeys Delete for the destroyed key.

##### Expected Results

- The key exposes `pending_operation.type=DESTROY` while deletion is unresolved and sets `destroyed_at` only after Transit returns not found under the committed destroy intent.
- Delete then removes the OSAC metadata.
- Calling Delete before provider-confirmed destruction returns `FailedPrecondition`.

### FR-6: Enforce Tenant Admin, Cloud Provider Admin, Tenant User, and Cloud Infrastructure Admin boundaries

#### TC-FR6-01: Tenant Admin cannot access another tenant's keys

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-9 | critical | automated |

##### Preconditions

- Tenant-owned keys exist in `tenant-a` and `tenant-b`, and a provider-owned key exists in `system`; caller administers only `tenant-a`.

##### Steps

1. List ManagedKeys.
2. Get and update the `tenant-b` key by ID, then Get the `system` key by ID.

##### Expected Results

- List contains only `tenant-a` keys.
- Get and Update for the `tenant-b` key and Get for the `system` key return `NotFound` without disclosing their existence.

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
- Each key's `metadata.tenant` remains unchanged, including `system` for the provider-owned key.

#### TC-FR6-04: Cloud Infrastructure Admin can read only backend health

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-9 | critical | automated |

##### Preconditions

- The caller has only the `cloud-infrastructure-admin` realm role.

##### Steps

1. List and get KMSBackend status.
2. Invoke every ManagedKeys method.
3. Inspect the available KMSBackends methods and CLI commands.

##### Expected Results

- KMSBackends Get and List return normalized health data.
- ManagedKeys requests return `PermissionDenied`.
- KMSBackends exposes only Get and List methods, and the CLI offers no backend mutation command.

### FR-7: Let Cloud Provider Admins configure transparent platform backends and policies without tenant selection

#### TC-FR7-01: Valid HashiCorp Vault Transit configuration becomes ready

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-6 | high | automated |

##### Preconditions

- Helm values define a `vault-transit` backend, tenant/provider default policies, Vault Enterprise or HCP Vault Dedicated namespaces, and a key-scoped consumer credential path.

##### Steps

1. Deploy the service with the configuration.
2. Wait for backend conformance checks.
3. Create one tenant-owned and one provider-owned key.

##### Expected Results

- Backend state becomes `READY` only after the required rotation, revocation, recovery, and destruction checks pass; its public response does not include a capability matrix.
- Each key privately records the configured immutable backend and corresponding default policy.
- Tenant-facing requests contain no backend or policy selector.

#### TC-FR7-02: Invalid or incapable backend blocks key creation

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-7 | critical | automated |

##### Preconditions

- Configuration points to Vault Transit with an inaccessible mount, missing tenant namespace support, or consumer credentials that bypass the key-specific policy.

##### Steps

1. Start the Fulfillment Service.
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

1. Get backend status while HashiCorp Vault is ready.
2. Seal or stop Vault and wait for the next probe.
3. Get backend status again.

##### Expected Results

- The first response reports `READY` and a last-check timestamp.
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

- List and describe show `UNAVAILABLE`, last check time, and a normalized reason.
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

1. Call Rotate with a request ID.
2. Get the ManagedKey after the synchronous RPC fails.

##### Expected Results

- Rotate returns a gRPC error with reason `ProviderPolicyConflict` and a redacted message identifying the corrective configuration category.
- Get still reports active version `1`, no revocation or destruction timestamp, and no pending operation because the provider confirmed no effect.

#### TC-FR9-02: Service restart requires explicit same-ID retry after Vault succeeds

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-1 | critical | automated |

##### Preconditions

- A Rotate request ID and pre-operation version are committed before the provider call.

##### Steps

1. Apply the Vault rotation, then stop the API process before the final database commit.
2. Restart the service and Get the key before any retry.
3. Retry Rotate with the original request ID.

##### Expected Results

- The Get response shows `pending_operation.type=ROTATE` and last confirmed version `1`; no background process silently finalizes it.
- The same-ID retry observes the existing Vault effect, advances the active version to `2`, and clears the pending marker.
- Exactly one new material generation exists.
- The key does not remain indefinitely in an unqualified unknown state.

#### TC-FR9-03: Public API end-to-end lifecycle journey

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-1 | critical | automated |

##### Preconditions

- A deployed Fulfillment Service, PostgreSQL, Keycloak, and supported HashiCorp Vault Transit backend are available.

##### Steps

1. As Tenant Admin, create and view a key.
2. As an authorized service, add then remove an association.
3. Rotate, revoke, recover, and destroy the key through public lifecycle RPCs.
4. Delete destroyed metadata.

##### Expected Results

- Each successful lifecycle RPC returns confirmed version/timestamp fields; timeouts retain a pending marker and the same request ID for explicit verification and retry.
- Rotation retains the old generation, revocation denies normal Vault Transit use through existing consumer tokens, recovery restores it, and destruction removes the provider key only after association removal.
- Cross-tenant and unauthorized access remain denied throughout the journey.

#### TC-FR9-04: CLI end-to-end lifecycle journey

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-4 | critical | automated |

##### Preconditions

- The OSAC CLI is authenticated as Tenant Admin against a deployed environment with a ready Transit backend.

##### Steps

1. Create and describe a key.
2. Rotate, revoke, and recover through synchronous CLI commands.
3. Destroy the unassociated key.

##### Expected Results

- Every command exits zero only after its requested effect is confirmed and persisted, and prints the request ID.
- Describe output reflects active version `2` after rotation, `revoked_at` after revoke, cleared `revoked_at` after recovery, and `destroyed_at` after destruction.
- Any server rejection is printed with its gRPC reason and actionable message.

## Gaps

### Requirement Coverage Gaps

All derived PRD requirement anchors have test cases.

### Interface Change Coverage Gaps

All interface changes are exercised by test cases.

## Summary

| Metric | Count |
|--------|-------|
| Total test cases | 32 |
| Critical | 23 |
| High | 9 |
| Medium | 0 |
| Low | 0 |
| Automated | 32 |
| Manual | 0 |
| Requirements with test cases | 9 / 9 |
| Interface changes with test cases | 9 / 9 |
