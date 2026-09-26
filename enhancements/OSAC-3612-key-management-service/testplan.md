# Testplan — OSAC-3612

## Overview

- **Feature:** OSAC-3612 — Key Management Service: Key Lifecycle Management
- **Total test cases:** 29
- **Requirements covered:** 9 of 9 derived PRD requirement anchors
- **Interface changes covered:** 8 of 8

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

1. Create a ManagedKey named `data-key` without specifying `metadata.tenant`.
2. Get the returned key.
3. List ManagedKeys in `tenant-a`.

##### Expected Results

- Create returns only after Vault creation and the database insert are confirmed, with a stable ManagedKey ID, `metadata.tenant=tenant-a`, purpose `ENCRYPT_DECRYPT`, active version `1`, no lifecycle timestamps, and no key material.
- Get reports the committed version without making a Vault call.
- List contains `data-key` only in `tenant-a`.

#### TC-FR1-02: Cloud Provider Admin creates a provider-owned key

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-1 | critical | automated |

##### Preconditions

- HashiCorp Vault Transit is ready and the caller has existing Cloud Provider Admin access.

##### Steps

1. Create a ManagedKey with `metadata.tenant=system`.
2. Read the private persisted object as the service identity.
3. Attempt creation with `metadata.tenant=shared` and with no tenant specified.
4. As a Tenant Admin, attempt creation with `metadata.tenant=system`.

##### Expected Results

- Create returns a public resource with active version `1` and no lifecycle timestamps.
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

### FR-2: Expose confirmed lifecycle state, active version, retained versions, and actionable uncertainty after failed requests

#### TC-FR2-01: Create timeout can leave an orphaned backend key

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-2 | high | automated |

##### Preconditions

- The Transit test provider can apply key creation, and the test can force the final PostgreSQL commit to fail.

##### Steps

1. Create a ManagedKey named `create-timeout`; let Vault apply the effect, then fail the PostgreSQL commit.
2. List the tenant's keys by name and inspect Vault's `osac-<uuid>` keys.
3. Retry Create after the provider is available.

##### Expected Results

- List contains no unconfirmed key after the failed commit; Vault contains an orphaned key with no matching persisted ManagedKey ID.
- The retry creates a new key with active version `1`; it does not adopt the orphaned key or claim the first request succeeded.
- The operator comparison identifies the orphan for verified removal without deleting the retried key.

#### TC-FR2-02: Resource events carry committed lifecycle changes

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

- Events show the committed Create and Rotate results, with no interim operation event or request ID.
- The final payload reports active version `2`; version `1` is retained by being listed below the active generation.
- No event includes a Transit mount, backend object ID, credential, or key material.

#### TC-FR2-03: Get and List remain readable when Vault differs

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-2 | critical | automated |

##### Preconditions

- An active key is confirmed at version `1`, and the test can interrupt Vault and remove its key out of band.

##### Steps

1. Make Vault unavailable; call List and Get.
2. Restore Vault, remove the Transit key without an OSAC Destroy request, and call Get again.
3. Attempt Rotate on the key.

##### Expected Results

- List and Get both return last-committed key metadata while Vault is unavailable.
- Get still returns that metadata after the out-of-band deletion, with `destroyed_at` absent; it does not claim to have checked Vault.
- Rotate returns `FailedPrecondition` with redacted corrective guidance before changing Vault. OSAC does not label the missing key as an authorized destruction.

### FR-3: Rotate a logical key while preserving its identity and retained material versions

#### TC-FR3-01: Successful rotation promotes a new generation without changing key identity

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-1 | critical | automated |

##### Preconditions

- An active key exists at version `1`.

##### Steps

1. Call Rotate with the current metadata version.
2. Inspect the successful response.
3. Read the key again.

##### Expected Results

- The ManagedKey ID is unchanged.
- Active version is `2`, versions `1` and `2` remain listed, and no revocation or destruction timestamp is set.
- The successful response has no transition field or completed-operation history.

#### TC-FR3-02: A second completed Rotate is a new operation

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-1 | critical | automated |

##### Preconditions

- A Rotate has completed at version `2`.

##### Steps

1. Call Rotate again with the current metadata version.
2. Read Transit and the ManagedKey.

##### Expected Results

- Transit latest version advances to `3`.
- ManagedKey active version becomes `3`; versions `1`, `2`, and `3` remain listed.

#### TC-FR3-03: Failed database commit after rotation leaves an uncommitted Vault version

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-2 | critical | automated |

##### Preconditions

- An active key is confirmed at version `1`, and the test can fail the request transaction's final commit after Vault rotates successfully.

##### Steps

1. Call Rotate from version `1`; let Vault create version `2`, then fail the database commit.
2. Call Get and List, and inspect the persisted version records.
3. Attempt another Rotate, then follow the operator verification procedure.

##### Expected Results

- The RPC fails; List and PostgreSQL still show only confirmed version `1`.
- Get returns committed version `1` and does not create a `ManagedKeyVersion` for version `2`; the next Rotate returns `FailedPrecondition` after observing the mismatch and sends no second POST.
- The repair procedure verifies the retained Vault versions before updating the OSAC generation mapping; no automatic retry sends a second Rotate POST.

#### TC-FR3-04: CLI rotation reports confirmed completion

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-4 | high | automated |

##### Preconditions

- `cli-key` is active at version `1`.

##### Steps

1. Run `osac rotate key cli-key`.
2. Run `osac describe key cli-key`.

##### Expected Results

- The command exits zero only after the new active version is confirmed and persisted.
- Describe reports active version `2` and retained version `1`.

#### TC-FR3-05: An early retry can create an extra retained version

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-2 | critical | automated |

##### Preconditions

- The Transit test provider can hold the first Rotate POST in flight while reads still report version `1`.

##### Steps

1. Call Rotate and let the client time out while the first POST is held.
2. Retry Rotate with the current metadata version and let the second POST finish first.
3. Release the first POST, then inspect Transit and ManagedKey through Get and attempt another Rotate.

##### Expected Results

- The first timeout warns that its POST may still finish; the retry issues a second Rotate POST, whose successful response confirms version `2`.
- The delayed first POST creates version `3`, which remains in Vault with version `2`; Get shows last-committed version `2` without a live Vault claim.
- The next Rotate returns `FailedPrecondition` after observing the mismatch. The operator repair procedure must add the observed generation before further lifecycle changes.

### FR-4: Revoke all versions, block normal use and new references, and permit explicit authorized recovery

#### TC-FR4-01: Revocation blocks existing Vault consumer tokens

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-5 | critical | automated |

##### Preconditions

- A key has two material versions and is active; a consumer token issued before revocation has only that key's policy.

##### Steps

1. Call Revoke and wait for the synchronous response.
2. Use the pre-existing consumer token to attempt Vault Transit encrypt and decrypt against both retained versions.

##### Expected Results

- Vault rejects encryption and decryption under the updated key-specific ACL; the Transit key and both material versions still exist.
- A new normal consumer credential cannot bypass the denied policy, and an unrelated key remains usable.
- `revoked_at` is set only after denial is verified, `destroyed_at` is absent, and both version metadata records remain.

#### TC-FR4-02: Authorized recovery restores normal key use

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-1 | critical | automated |

##### Preconditions

- A tenant-owned key has `revoked_at` set, and the caller is its Tenant Admin.

##### Steps

1. Call Recover and wait for the synchronous response.
2. Get the key and perform a Vault Transit encrypt/decrypt round trip using a consumer token that existed before revocation.

##### Expected Results

- Success clears `revoked_at` without changing the ID or active version; no interim transition field is exposed.
- The restored key-specific policy permits the round trip and returns the original plaintext to the fixture.
- Existing version metadata remains present.

#### TC-FR4-03: CLI revoke and recover show confirmed outcomes

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
- Both commands print the lifecycle derived from the confirmed timestamp.

### FR-5: Define consumer-neutral key references and reject destruction while a consumer remains attached

#### TC-FR5-01: ManagedKeyLocalReference resolves a stable same-tenant key

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-5 | critical | automated |

##### Preconditions

- An active tenant-owned key exists in `tenant-a`, and a reference-validation unit fixture has an owning resource in that tenant.

##### Steps

1. Resolve `ManagedKeyLocalReference { name: "data-key" }` in the fixture's tenant scope.
2. Rotate the key and resolve the reference again using its canonical ID.

##### Expected Results

- Resolution fills the key ID and name, matching the existing typed-reference convention.
- The canonical ID is unchanged after rotation; no material generation or backend coordinate appears in the reference.

#### TC-FR5-02: Key reference validation enforces tenant and lifecycle state

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-5 | critical | automated |

##### Preconditions

- One active key exists in `tenant-a`, one revoked key exists in `tenant-b`, and the reference-validation fixture can run under either tenant.

##### Steps

1. Resolve the `tenant-a` key from a `tenant-b` fixture.
2. Resolve the revoked `tenant-b` key from the `tenant-b` fixture.

##### Expected Results

- The cross-tenant reference returns `InvalidArgument` with reason `TenantMismatch`.
- The revoked-key request returns `FailedPrecondition` with reason `KeyNotActive`.
- Reference validation rejects both requests without producing a canonical key reference.

#### TC-FR5-03: Unreferenced key is destroyed permanently before metadata deletion

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-4 | critical | automated |

##### Preconditions

- A key is active or revoked; OSAC-3612 has no concrete key-consuming resource.

##### Steps

1. Call ManagedKeys Delete before destroying the key.
2. Run `osac destroy key <key>` and wait for the CLI result.
3. Verify the provider key is absent and Get reports `destroyed_at`.
4. Call ManagedKeys Delete for the destroyed key.

##### Expected Results

- Delete before destruction returns `FailedPrecondition`; Destroy sets `destroyed_at` only after Vault deletion and the database commit succeed.
- Delete then removes the OSAC metadata.

### FR-6: Enforce Tenant Admin, Cloud Provider Admin, Tenant User, and Cloud Infrastructure Admin boundaries

#### TC-FR6-01: Tenant Admin cannot access another tenant's keys

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-7 | critical | automated |

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
| IC-7 | high | automated |

##### Preconditions

- The caller is an authenticated Tenant User without the Tenant Admin role.

##### Steps

1. Invoke each ManagedKeys CRUD and lifecycle method.

##### Expected Results

- Every request returns `PermissionDenied`, and no key data is returned.

#### TC-FR6-03: Existing Cloud Provider Admin access remains broad

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-7 | critical | automated |

##### Preconditions

- Tenant-owned keys exist in two tenants and a provider-owned key exists in `system`.

##### Steps

1. Authenticate as an existing administrator.
2. List, get, and update each key within valid lifecycle transitions.

##### Expected Results

- The administrator can access all three keys under existing universal tenancy behavior.
- Each key's `metadata.tenant` remains unchanged, including `system` for the provider-owned key.

#### TC-FR6-04: Cloud Infrastructure Admin has no key lifecycle authority

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-7 | critical | automated |

##### Preconditions

- The caller has a Cloud Infrastructure Admin identity without Tenant Admin or Cloud Provider Admin privileges.

##### Steps

1. Invoke every ManagedKeys method.
2. Inspect the role's key-management API permissions.

##### Expected Results

- ManagedKeys requests return `PermissionDenied`.
- The role has no KMS-specific API grant; read-only health is available through platform monitoring access.

### FR-7: Let Cloud Provider Admins configure transparent platform backends and policies without tenant selection

#### TC-FR7-01: Valid HashiCorp Vault Transit configuration becomes ready

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-6 | high | automated |

##### Preconditions

- Helm values define a `vault-transit` backend, tenant/provider default policies, Vault Enterprise or HCP Vault Dedicated namespaces, and a key-scoped consumer credential path.

##### Steps

1. Deploy the service with the configuration.
2. Wait for backend readiness validation.
3. Create one tenant-owned and one provider-owned key.

##### Expected Results

- Key creation is admitted only after the required Vault access, mount, namespace, and policy checks pass; `osac_kms_backend_ready{backend}` reports `1`. Provider conformance tests separately exercise rotation, revocation, recovery, and destruction against the supported Vault deployment.
- Each key privately records the configured immutable backend and corresponding default policy.
- Tenant-facing requests contain no backend or policy selector.

#### TC-FR7-02: Invalid or incapable backend blocks key creation

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-6 | critical | automated |

##### Preconditions

- Configuration points to Vault Transit with an inaccessible mount, missing tenant namespace support, or consumer credentials that bypass the key-specific policy.

##### Steps

1. Start the Fulfillment Service.
2. Read the backend readiness metric and redacted service diagnostic.
3. Attempt to create a ManagedKey.

##### Expected Results

- The readiness metric is `0`, and the diagnostic identifies the missing access or configuration category without sensitive details.
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

#### TC-FR8-01: Monitoring reports backend availability without key data

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-8 | high | automated |

##### Preconditions

- A configured backend can be made reachable and unreachable during the test.

##### Steps

1. Observe the backend readiness metric while HashiCorp Vault is ready.
2. Seal or stop Vault and wait for the next probe.
3. Observe the metric, alert, and redacted diagnostic after the backend becomes unavailable.

##### Expected Results

- The readiness metric changes from `1` to `0`; the alert fires after the configured five-minute interval, and the diagnostic gives a normalized reason.
- Cloud Infrastructure Admins can view these signals through platform monitoring access.
- Metrics and diagnostics contain no tokens, certificates, tenant key counts, or tenant key identities.

### FR-9: Return confirmed success or actionable failure, distinguish uncertain provider outcomes from committed key state, and cover API/CLI journeys

#### TC-FR9-01: Proven no-effect provider failure preserves confirmed state

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-2 | critical | automated |

##### Preconditions

- An active key is at version `1`, and the provider reports a policy conflict with proof that rotation had no effect.

##### Steps

1. Call Rotate.
2. Get the ManagedKey after the synchronous RPC fails.

##### Expected Results

- Rotate returns a gRPC error with reason `ProviderPolicyConflict` and a redacted message identifying the corrective configuration category.
- Get still reports active version `1` with no revocation or destruction timestamp because the provider confirmed no effect.

#### TC-FR9-02: Failed database commit after Destroy requires operator verification

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-1 | critical | automated |

##### Preconditions

- A live key has no concrete consumer reference, and the test can fail the final database commit after Vault deletes its key.

##### Steps

1. Call Destroy; let Vault delete the key, then fail the database commit.
2. Call Get and List, then attempt another Destroy.
3. Verify Vault absence through operator tooling and follow the destruction repair procedure.

##### Expected Results

- Destroy returns an error. Get and List still show the last committed key without `destroyed_at`; neither call claims a live Vault check.
- The next Destroy returns `FailedPrecondition` after observing the missing provider key and does not silently set `destroyed_at`.
- No reference fence or operation record exists in OSAC-3612; operator verification and repair are needed before metadata deletion.

#### TC-FR9-03: Public API end-to-end lifecycle journey

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-1 | critical | automated |

##### Preconditions

- A deployed Fulfillment Service, PostgreSQL, Keycloak, and supported HashiCorp Vault Transit backend are available.

##### Steps

1. As Tenant Admin, create and view a key.
2. Rotate, revoke, recover, and destroy the unreferenced key through public lifecycle RPCs.
3. Delete destroyed metadata.

##### Expected Results

- Each successful lifecycle RPC returns confirmed version/timestamp fields; a timeout reports that its Vault effect may be uncertain and directs the caller to verification before retry.
- Rotation retains the old generation, revocation denies normal Vault Transit use through existing consumer tokens, recovery restores it, and destruction removes the provider key.
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
3. Destroy the unreferenced key.

##### Expected Results

- Every command exits zero only after its requested effect is confirmed and persisted.
- Describe output reflects active version `2` after rotation, `revoked_at` after revoke, cleared `revoked_at` after recovery, and `destroyed_at` after destruction.
- Any server rejection is printed with its gRPC reason and actionable message.

## Gaps

### Requirement Coverage Gaps

All derived PRD requirement anchors have test cases. No concrete consumer binding is added by OSAC-3612, so the deployed FR-5 `KeyInUse` check, reference-versus-Destroy race, and failed database commit after Vault deletion with a live reference cannot be exercised here. [OSAC-2389](https://redhat.atlassian.net/browse/OSAC-2389) owns the first storage consumer's reference field, forward validation, reverse Destroy guard, and any durable fence needed to prevent new references after an uncertain deletion. Its `[DEV]` work must cover reference validation, the guard race, and cross-store failure at Unit, Contract, and component-integration tiers; its `[QE]` work must cover the deployed storage binding and blocked destruction journey.

### Interface Change Coverage Gaps

All interface changes have test cases for behavior delivered by OSAC-3612. IC-5's deployed consumer enforcement is deferred to OSAC-2389 as described above.

## Summary

| Metric | Count |
|--------|-------|
| Total test cases | 29 |
| Critical | 21 |
| High | 8 |
| Medium | 0 |
| Low | 0 |
| Automated | 29 |
| Manual | 0 |
| Requirements with test cases | 9 / 9 |
| Interface changes with test cases | 8 / 8 |
