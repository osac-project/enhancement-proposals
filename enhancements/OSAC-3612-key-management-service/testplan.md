# Testplan — OSAC-3612

## Overview

- **Feature:** OSAC-3612 — Key Management Service: Key Lifecycle Management
- **Total test cases:** 41
- **Requirements covered:** 10 of 10 derived PRD requirement anchors
- **Interface changes covered:** 9 of 9

The PRD has no FR/NFR identifiers. The FR-1 through FR-10 headings below are the traceability-only anchors defined in §1 of the design; FR-10 reflects the added initial-release direct crypto requirement.

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

- Create returns only after Vault creation and the database insert are confirmed, with a stable ManagedKey ID, `metadata.tenant=tenant-a`, purpose `ENCRYPT_DECRYPT`, `state=ACTIVE`, `versions=[1]`, no action request or lifecycle timestamps, no `active_version` field, and no key material.
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

- Create returns a public resource with `state=ACTIVE`, `versions=[1]`, no action request, and no lifecycle timestamps.
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

- Create prints the key ID and current generation `1`, derived from the final `versions` element, after confirmation.
- List includes `cli-key`.
- Describe prints the owning tenant, `ENCRYPT_DECRYPT` purpose, derived active lifecycle, and current generation `1` from `versions` without backend paths or key material.

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
- The retry creates a new key with `versions=[1]`; it does not adopt the orphaned key or claim the first request succeeded.
- The operator comparison identifies the orphan for verified removal without deleting the retried key.

#### TC-FR2-02: Resource events carry committed lifecycle changes

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-2 | high | automated |

##### Preconditions

- An Events watch is active for a Tenant Admin's visible resources.

##### Steps

1. Create and rotate a ManagedKey.
2. Collect ManagedKey events through the successful rotation Update response.
3. Inspect every public event payload.

##### Expected Results

- Events show the committed Create and Rotate changes, with no interim operation event. The Rotate payload includes the committed `action_request.action_trigger` and `last_rotation_timestamp`.
- The final payload lists generations `1` and `2` in ascending order; the final element is the current confirmed generation.
- No event includes a Transit mount, backend object ID, credential, or key material.

#### TC-FR2-03: Get and List remain readable when Vault differs

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-2 | critical | automated |

##### Preconditions

- An active key is confirmed at version `1`, and the test can interrupt Vault and remove its key out of band.

##### Steps

1. Make Vault unavailable; call List and Get.
2. Restore Vault, remove the Transit key without an OSAC Delete request, and call Get again.
3. Attempt a locked Update with a new `action_request` containing `rotate` and an action trigger.

##### Expected Results

- List and Get both return last-committed key metadata while Vault is unavailable.
- Get still returns that metadata after the out-of-band deletion; it does not claim to have checked Vault or to have destroyed the OSAC record.
- The rotation Update returns `FailedPrecondition` with redacted corrective guidance before changing Vault. OSAC does not label the missing key as an authorized destruction.

### FR-3: Rotate a logical key while preserving its identity and retained material versions

#### TC-FR3-01: Successful rotation promotes a new generation without changing key identity

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-1 | critical | automated |

##### Preconditions

- An active key exists at version `1`.

##### Steps

1. Call Update with `lock=true`, the current metadata version, `update_mask=action_request`, and a new nonzero `action_trigger` with `rotate: {}`.
2. Inspect the successful response.
3. Read the key again.

##### Expected Results

- The ManagedKey ID is unchanged.
- `versions` contains generations `1` and `2` in ascending order, with `2` current; no `active_version` or destruction timestamp is set. `state` remains `ACTIVE` and `revocation_timestamp` stays absent.
- The committed `action_request` echoes the action trigger and selected `rotate` action; `last_rotation_timestamp` records OSAC verification. There is no interim operation field or completed-operation history.

#### TC-FR3-02: A second completed Rotate is a new operation

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-1 | critical | automated |

##### Preconditions

- A Rotate has completed at version `2`.

##### Steps

1. Call Update again with `lock=true`, the current metadata version, and `rotate: {}` with a new `action_trigger` in `action_request`.
2. Read Transit and the ManagedKey.

##### Expected Results

- Transit latest version advances to `3`.
- `versions` contains generations `1`, `2`, and `3` in ascending order, with `3` current.

#### TC-FR3-03: Retry records a rotation after database failure

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-2 | critical | automated |

##### Preconditions

- An active key is confirmed at version `1`, and the test can fail the request transaction's final commit after Vault rotates successfully.

##### Steps

1. Submit `action_request={action_trigger: 2, rotate: {}}` in a locked Update from version `1`; let Vault create version `2`, then fail the database commit.
2. Call Get and List, and inspect the persisted version records.
3. Retry Update with `lock=true` after the database recovers.

##### Expected Results

- The RPC fails; List and PostgreSQL still show only confirmed version `1`.
- Before retry, Get shows version `1`, the previous `action_request`, and no new rotation timestamp. The retry records Vault version `2`, the action trigger, and `last_rotation_timestamp` without another Rotate POST.

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

- The command exits zero only after the new current generation is confirmed and persisted.
- Describe reports current generation `2` from the final `versions` element and retained generation `1`.

#### TC-FR3-05: An early retry can create an extra retained version

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-2 | critical | automated |

##### Preconditions

- The Transit test provider can hold the first Rotate POST in flight while reads still report version `1`.

##### Steps

1. Submit `action_request={action_trigger: 2, rotate: {}}` in a locked Update and let the client time out while the first Transit POST is held.
2. Retry the locked Update with the same action, action trigger, and metadata version; let the second Transit POST finish first.
3. Release the first POST, call Get, then send a new Rotate Update.
4. Repeat with OSAC at version `7` and Vault at `14`, with versions `8` through `14` present.

##### Expected Results

- The retry sends a second POST and records version `2`; the delayed first POST then creates version `3` while Get still shows `2`.
- The next Update with `lock=true` records version `3` without another POST. In step 4, it records all seven missing versions.

#### TC-FR3-06: Action requests require one action and a new trigger in a locked Update

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-1 | critical | automated |

##### Preconditions

- An active key is at version `1`, and its last committed action request, if any, is known.

##### Steps

1. Attempt Create with `action_request` set.
2. Attempt to change `action_request` through Update with `lock=false`.
3. Attempt locked Updates with an absent request, a zero `action_trigger`, no selected `oneof` action, or `action_request` combined with a metadata edit.
4. After a successful Rotate, send a locked Update with the same action trigger and `rotate: {}`, then reuse that trigger with `revoke: {}`.
5. Attempt to set `state`, `revocation_timestamp`, or `last_rotation_timestamp` in an Update.

##### Expected Results

- Create and malformed Updates return `InvalidArgument`; `lock=false` is rejected under the locked Update contract. None has a Vault effect or changes committed state.
- Repeating the last committed trigger and action has no Vault effect. Reusing that trigger with another action returns `InvalidArgument`.
- Caller writes to `state` or lifecycle timestamps are rejected.
- `ManagedKeys` exposes no separate Rotate, Revoke, or Recover methods.

### FR-4: Revoke all versions, block normal use and new references, and permit explicit authorized recovery

#### TC-FR4-01: Revocation blocks existing Vault consumer tokens

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-5 | critical | automated |

##### Preconditions

- A key has two material versions and is active; a consumer token issued before revocation has only that key's policy.

##### Steps

1. Submit `action_request={action_trigger: 3, revoke: {}}` in a locked Update and wait for the synchronous response.
2. Use the pre-existing consumer token to attempt Vault Transit encrypt and decrypt against both retained versions.

##### Expected Results

- Vault rejects encryption and decryption under the updated key-specific ACL; the Transit key and both material versions still exist.
- A new normal consumer credential cannot bypass the denied policy, and an unrelated key remains usable.
- `state` becomes `REVOKED` and `revocation_timestamp` is set only after denial is verified. The committed `action_request` echoes the action trigger and Revoke action. The OSAC record and material versions remain.

#### TC-FR4-02: Authorized recovery restores normal key use

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-1 | critical | automated |

##### Preconditions

- A tenant-owned key has `state=REVOKED` and `revocation_timestamp` set, and the caller is its Tenant Admin.

##### Steps

1. Submit `action_request={action_trigger: 4, recover: {}}` in a locked Update and wait for the synchronous response.
2. Get the key and perform a Vault Transit encrypt/decrypt round trip using a consumer token that existed before revocation.

##### Expected Results

- Success changes `state` to `ACTIVE`, clears `revocation_timestamp`, and commits the Recover action request without changing the key ID, final `versions` element, or `last_rotation_timestamp`. No interim operation field is exposed.
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

- Revoke exits zero only when `state=REVOKED`, `revocation_timestamp`, and the matching Revoke request are committed.
- Recover exits zero only when `state=ACTIVE`, absent `revocation_timestamp`, and the matching Recover request are committed.
- Both commands print the confirmed lifecycle state; Revoke includes its confirmation timestamp.

#### TC-FR4-04: Failed Recovery commit is reconciled on retry

**Tier:** component-integration

**Owner:** [DEV]

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-1 | critical | automated |

##### Preconditions

- A revoked key has a consumer token, and the test can fail the final database commit after Vault restores access.

##### Steps

1. Recover after Vault restores access, then fail the database commit.
2. Restore the database and retry Recover while Vault already allows use.

##### Expected Results

- The failed call does not claim recovery. Get still reports revoked although the consumer token can use Vault.
- The retry verifies access, sets `state=ACTIVE`, clears `revocation_timestamp`, and records the Recover action request without another policy write.

### FR-5: Define consumer-neutral key references and reject destruction while a consumer remains attached

#### TC-FR5-01: ManagedKeyLocalReference resolves a stable same-project key

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-5 | critical | automated |

##### Preconditions

- An active tenant-owned key exists in project `p1` of `tenant-a`, and a reference-validation unit fixture has an owning resource in that tenant and project.

##### Steps

1. Resolve `ManagedKeyLocalReference { name: "data-key" }` in the fixture's tenant and project scope.
2. Rotate the key and resolve the reference again using its canonical ID.

##### Expected Results

- Resolution fills the key ID and name, matching the existing typed-reference convention.
- The canonical ID is unchanged after rotation; no material generation or backend coordinate appears in the reference.

#### TC-FR5-02: Key reference validation enforces tenant, project, and lifecycle state

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-5 | critical | automated |

##### Preconditions

- One active key exists in project `p1` of `tenant-a`, one revoked key exists in project `p1` of `tenant-b`, and the reference-validation fixture can run under either tenant and in named projects.

##### Steps

1. Resolve the `tenant-a` key from a `tenant-b` fixture.
2. Resolve the revoked `tenant-b` key from the `tenant-b` fixture.
3. Resolve the active `tenant-a` key from a fixture in project `p2` of `tenant-a`.

##### Expected Results

- The cross-tenant reference returns `InvalidArgument` with reason `TenantMismatch`.
- The revoked-key request returns `FailedPrecondition` with reason `KeyNotActive`.
- The cross-project reference returns `InvalidArgument` with reason `ProjectMismatch`.
- Reference validation rejects all three requests without producing a canonical key reference.

#### TC-FR5-03: Delete destroys an unreferenced key and removes its metadata

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-4 | critical | automated |

##### Preconditions

- A key is active or revoked; OSAC-3612 has no concrete key-consuming resource.

##### Steps

1. Call ManagedKeys Delete for the key and wait for the result.
2. Verify the Transit key and key-specific policy are absent.
3. Call Get, List, and Describe for the destroyed key.
4. Repeat Delete with the same key ID.

##### Expected Results

- Delete succeeds only after provider deletion and the OSAC record removal commit.
- Get and Describe return `NotFound`, List omits the key, and the committed change emits an object-deleted event.
- A repeat after the OSAC row is gone returns `NotFound`, matching Secret Delete; a retry while the row remains is covered by TC-FR9-02.

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

- The caller has an ordinary client token without `tenant-admin` or an existing administrator identity.

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

- The Cloud Infrastructure Admin caller has an ordinary client token: no `tenant-admin` realm role, no admin group membership, and no admin service-account identity. Read-only platform monitoring access is provisioned separately.

##### Steps

1. Invoke every ManagedKeys method.
2. Inspect the caller's effective key-management API permissions.

##### Expected Results

- ManagedKeys requests return `PermissionDenied`.
- The policy has no Cloud Infrastructure Admin predicate or KMS-specific API grant; read-only health is available through platform monitoring access.

### FR-7: Let Cloud Provider Admins configure transparent platform backends and policies without tenant selection

#### TC-FR7-01: Valid HashiCorp Vault Transit configuration becomes ready

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-6 | high | automated |

##### Preconditions

- Helm values define a `vault-transit` backend, one shared `kms.policy` selecting it with `algorithm=aes256-gcm96`, Transit backend with tenant namespaces as the initial certification candidate, and a key-scoped consumer credential path.

##### Steps

1. Deploy the service with the configuration.
2. Wait for startup configuration validation.
3. Create one tenant-owned and one provider-owned key.

##### Expected Results

- Key creation is admitted only after the required Vault access, mount, namespace, and policy checks pass. Provider conformance tests separately exercise rotation, revocation, recovery, and destruction against the supported Vault deployment.
- Both keys use the shared policy, are created in their ownership-specific Vault namespaces, and privately record the selected backend, which remains immutable for each key.
- Tenant-facing requests contain no backend or policy selector.

#### TC-FR7-02: Invalid or incapable backend blocks key creation

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-6 | critical | automated |

##### Preconditions

- Configuration points to Vault Transit with an inaccessible mount, missing tenant namespace support, or consumer credentials that bypass the key-specific policy.

##### Steps

1. Start the Fulfillment Service.
2. Read the redacted service diagnostic.
3. Attempt to create a ManagedKey.

##### Expected Results

- The diagnostic identifies the missing access or configuration category without sensitive details.
- ManagedKey creation returns `FailedPrecondition` naming the unavailable required capability without exposing credentials or raw provider responses.

#### TC-FR7-03: Configuration rejects invalid shared policy and unsupported backend types

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-6 | high | automated |

##### Preconditions

- Helm/schema validation tools are available.

##### Steps

1. Validate values missing the required shared policy.
2. Validate a shared policy referencing a missing backend or selecting an unsupported algorithm.
3. Validate an unsupported backend type.

##### Expected Results

- Each configuration fails validation with the offending field path.
- No deployment manifest is accepted with a missing policy, dangling backend reference, unsupported algorithm, or unknown backend type.

### FR-8: Give Cloud Infrastructure Admins read-only KMS health and availability visibility

#### TC-FR8-01: Existing monitoring shows key-operation failures without key data

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| — | high | automated |

##### Preconditions

- A configured backend can be made reachable and unreachable during the test. Prometheus scrapes the Fulfillment gRPC metrics Service; a Cloud Infrastructure Admin has read-only access to request metrics and operational logs. A separate Tenant Admin can create keys.

##### Steps

1. As the Tenant Admin, create a ManagedKey while Vault is ready; as the Cloud Infrastructure Admin, inspect the ManagedKeys `Create` request count and response code in Prometheus.
2. Seal or stop Vault, then as the Tenant Admin attempt to create another ManagedKey.
3. As the Cloud Infrastructure Admin, inspect the `Create` request count and response code in Prometheus and the redacted failure diagnostic in operational logs.

##### Expected Results

- `inbound_unary_request_count{service,method,code}` records the successful and failed ManagedKeys `Create` calls through the existing metrics Service on port 8002; the failed call has a non-OK response code and a redacted diagnostic identifying the backend failure category.
- The Cloud Infrastructure Admin can view these request signals and diagnostics without gaining ManagedKeys lifecycle access.
- Metrics and diagnostics contain no tokens, certificates, tenant key counts, or tenant key identities. No KMS-specific gauge, periodic probe, or alert is required; an idle backend outage is not detected by these request metrics.

### FR-9: Return confirmed success or actionable failure, distinguish uncertain provider outcomes from committed key state, and cover API/CLI journeys

#### TC-FR9-01: Proven no-effect provider failure preserves confirmed state

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-2 | critical | automated |

##### Preconditions

- An active key is at version `1`, and the provider reports a policy conflict with proof that rotation had no effect.

##### Steps

1. Submit a new `action_request={action_trigger: 5, rotate: {}}` in a locked Update.
2. Get the ManagedKey after the synchronous RPC fails.

##### Expected Results

- The rotation Update returns a gRPC error with reason `ProviderPolicyConflict` and a redacted message identifying the corrective configuration category.
- Get still reports `versions=[1]`, `state=ACTIVE`, no rotation timestamp, and no new action request because the provider confirmed no effect.

#### TC-FR9-02: Failed database commit after Delete can be retried

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-1 | critical | automated |

##### Preconditions

- A live key has no concrete consumer reference, and the test can fail the final database commit after Vault deletes its key.

##### Steps

1. Call Delete; let Vault delete the key, then fail the database commit.
2. Call Get and List, then retry Delete with the same key ID.
3. Verify the Transit key, key-specific policy, and OSAC row are absent.

##### Expected Results

- The first Delete returns an error. Get and List still show the last committed key; neither call claims a live Vault check.
- The retry accepts already absent provider resources, completes any remaining policy cleanup, and commits removal of the OSAC row.
- No reference fence or operation record exists in OSAC-3612; the first concrete consumer must add the guard and cross-store failure protection.

#### TC-FR9-03: Public API end-to-end lifecycle journey

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-1 | critical | automated |

##### Preconditions

- A deployed Fulfillment Service, PostgreSQL, Keycloak, Transit backend are available.

##### Steps

1. As Tenant Admin, create and view a key.
2. Rotate, revoke, and recover the key through three locked public Updates, each with `update_mask=action_request`, a new action trigger, and one action message, then call Delete on the unreferenced key.
3. Verify Get returns `NotFound` and List omits the destroyed key.

##### Expected Results

- Create and the three lifecycle Updates return committed action requests and server-set `state`, `revocation_timestamp`, or `last_rotation_timestamp` as applicable. Delete confirms removal with an empty response. A timeout reports that its Vault effect may be uncertain; Delete can retry an existing OSAC row after Vault deletion.
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
3. Run `osac delete managedkeys <id>` for the unreferenced key; it calls ManagedKeys Delete.

##### Expected Results

- Every command exits zero only after its requested effect is confirmed and persisted.
- Describe output derives current generation `2` from `versions` after rotation, shows `state=REVOKED` with `revocation_timestamp` after revoke, and `state=ACTIVE` with no `revocation_timestamp` after recovery. After Delete, Describe returns `NotFound` and List omits the key.
- Any server rejection is printed with its gRPC reason and actionable message.

#### TC-FR9-05: Operator investigates unverifiable provider drift

**Tier:** component-integration

**Owner:** [DEV]

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-2 | high | manual |

##### Preconditions

- The operator CLI runbook and a Transit test deployment are available. The test can make the Vault version history incomplete.

##### Steps

1. Create a key at version `1`, advance Vault, then trim the retained version `1` out of band.
2. Attempt Update with `lock=true` and follow the runbook.

##### Expected Results

- The Update returns `FailedPrecondition` without adopting incomplete history or sending another Rotate POST.
- The runbook identifies the missing version and blocks further mutation; it neither invents a version nor exposes key material.

### FR-10: Discover visible keys and encrypt or decrypt small payloads through API and CLI

#### TC-FR10-01: Discovery follows tenant and project visibility

- **Tier:** component-integration
- **Owner:** [DEV]
- **Interface Change:** IC-7, IC-8
- **Priority:** high
- **Automation:** automated

**Preconditions:** Tenant `a` has active keys in its default project, named project `p1`, and sibling project `p2`. An encrypt-role JWT belongs to tenant `a` and has membership in `p1` but not `p2`; a different identity belongs to tenant `b`, which has a key. Fulfillment and PostgreSQL run for real.

**Steps:** List keys, Get each ID, then Encrypt by ID. Try tenant `b`'s key with the tenant `a` JWT. Repeat with a JWT lacking either crypto role. Attempt to create a key in an invisible named project as Tenant Admin.

**Expected results:** The caller discovers tenant `a` default and `p1` keys, but neither lists nor gets the `p2` or tenant `b` keys. Encrypt on either hidden key returns `NotFound`, including when its ID is known. The caller without a crypto role cannot List or Get. Create in an invisible project is rejected before Vault creates a key. A parent-project membership also exposes descendant-project keys.

#### TC-FR10-02: Encrypt and decrypt roles are independent

- **Tier:** Unit
- **Owner:** [DEV]
- **Interface Change:** IC-7, IC-8
- **Priority:** critical
- **Automation:** automated

**Steps:** Evaluate OPA and public handler authorization for encrypt-only, decrypt-only, both-role, Tenant Admin without crypto roles, ordinary client, and unrestricted administrator identities against a visible key. Also test a user with an encrypt realm role and organization claims for tenants `a` and `b`, including keys in each tenant and an invisible project.

**Expected results:** Each crypto role grants only its named operation plus Get/List; neither grants Create, Update, or Delete. The multi-tenant user can Encrypt visible keys in both claimed tenants, following existing realm-role semantics, but cannot access an invisible project. Tenant Admin lifecycle authority alone grants neither crypto operation. Existing unrestricted administrators retain both. Missing operation permission returns `PermissionDenied` without a Vault call.

#### TC-FR10-03: API round trip, payload limits, and input errors

- **Tier:** component-integration
- **Owner:** [DEV]
- **Interface Change:** IC-8
- **Priority:** critical
- **Automation:** automated

**Preconditions:** Fulfillment, PostgreSQL, REST gateway, Keycloak, and Transit run for real with an active key and tenant-scoped crypto-role JWT.

**Steps:** Encrypt and decrypt binary data through gRPC and REST, including a 65536-byte plaintext. Submit empty and 65537-byte plaintext, ciphertext longer than 131072 bytes, malformed ciphertext, and ciphertext from another key.

**Expected results:** Round trips recover identical bytes; REST represents plaintext bytes as base64. Encrypt returns an opaque Vault ciphertext string and confirmed generation `1`. Invalid inputs and failed decryption return redacted `InvalidArgument`, with no payload in events or persisted key data. Crypto calls do not increment key metadata version.

#### TC-FR10-04: Rotation switches encryption and retains decryption

- **Tier:** component-integration
- **Owner:** [DEV]
- **Interface Change:** IC-8
- **Priority:** critical
- **Automation:** automated

**Preconditions:** A real Transit key has confirmed generation `1`; provider conformance tests can observe Vault requests and force a failed OSAC commit after Rotate.

**Steps:** Encrypt before and after a successful Rotate, decrypt both ciphertexts, then rotate Vault while failing the OSAC commit and Encrypt again before reconciliation.

**Expected results:** The successful Rotate makes Encrypt use generation `2`, and both generation `1` and `2` ciphertexts decrypt. After an uncommitted Rotate, Encrypt explicitly selects the backend version mapped to the last OSAC-confirmed generation; it never silently uses Vault's new latest version. No existing ciphertext is re-encrypted.

#### TC-FR10-05: Revocation, recovery, and destruction control crypto use

- **Tier:** Contract
- **Owner:** [DEV]
- **Interface Change:** IC-8
- **Priority:** critical
- **Automation:** automated

**Preconditions:** A real Transit key has two retained generations, ciphertext from each, and a previously issued key-scoped consumer token.

**Steps:** Revoke, try Encrypt and Decrypt for both generations through OSAC and the previously issued Vault token, Recover, retry, then Delete and retry.

**Expected results:** Revoke denies both operations for every version through both paths. Recover permits new encryption and decryption of retained ciphertext. After Delete, both OSAC methods return `NotFound`; previously stored ciphertext is permanently undecryptable. The management credential is not used for direct crypto.

#### TC-FR10-06: Crypto calls serialize with lifecycle changes and deny uncertain access

- **Tier:** component-integration
- **Owner:** [DEV]
- **Interface Change:** IC-8
- **Priority:** critical
- **Automation:** automated

**Steps:** Hold an Encrypt call in Vault while Revoke begins; release it and observe completion order. Separately fail the OSAC commit after Vault applies Revoke or Recover, then attempt both crypto methods.

**Expected results:** Revoke confirms only after the in-flight Encrypt finishes, and subsequent crypto calls fail. When OSAC still says active but Vault denies after failed Revoke commit, no call succeeds. When OSAC still says revoked but Vault allows after failed Recover commit, no call succeeds. A provider outage returns `Unavailable` without claiming a state change.

#### TC-FR10-07: Crypto payloads stay out of logs

- **Tier:** Unit
- **Owner:** [DEV]
- **Interface Change:** IC-8
- **Priority:** critical
- **Automation:** automated

**Steps:** Invoke server and client logging interceptors with Encrypt and Decrypt requests and responses while body logging is enabled, including with redaction disabled. Inspect structured error, metric, and event outputs.

**Expected results:** Neither plaintext nor ciphertext appears in any log or event; metrics contain method, code, and duration without payload labels. Server responses and caller buffers retain their original bytes.

#### TC-FR10-08: CLI uses standard streams without exposing plaintext in arguments

- **Tier:** component-integration
- **Owner:** [DEV]
- **Interface Change:** IC-9
- **Priority:** critical
- **Automation:** automated

**Preconditions:** The `fulfillment-service/it/` harness runs a built CLI and deployed Fulfillment API with a ready Transit backend.

**Steps:** Discover an active visible key, pipe binary input to `osac encrypt key <id>`, pipe the resulting ciphertext to `osac decrypt key <id>`, and attempt decrypted output to an interactive terminal.

**Expected results:** CLI output round trips byte-for-byte. Decrypt refuses interactive-terminal output; neither command accepts plaintext as an argument or logs payloads. A caller outside the named project cannot discover or use its key.

#### TC-FR10-09: Deployed user journey crosses identity, API, database, and Vault

- **Tier:** E2E
- **Owner:** [QE]
- **Interface Change:** IC-7, IC-8, IC-9
- **Priority:** critical
- **Automation:** automated

**Steps:** In a deployed environment, assign independent crypto roles and project memberships to tenant JWT identities; discover a named-project key, encrypt and decrypt via gRPC/REST and CLI, rotate, revoke, recover, and delete it. Try an identity belonging only to another tenant, a same-tenant identity without project membership, and a single-tenant service JWT throughout.

**Expected results:** Only callers with the operation role and required tenant/project visibility can discover or use the key. An identity belonging only to another tenant cannot access it; a single-tenant service JWT can use only its tenant's keys. Rotation retains decryption of old ciphertext; revocation denies both operations; recovery restores them; deletion prevents further decryption. No lifecycle mutation becomes available to a crypto-only caller.

## Direct crypto planning evidence

The following rows cover the added behavior. Locations marked **proposed** do not yet provide execution evidence. Each `[DEV]` case belongs with the implementation that changes that boundary; the deployed `[QE]` case belongs in the cross-component suite. Unit tests mock external services, component integration uses deployed Fulfillment and PostgreSQL, and Contract tests require real Transit policy and key behavior rather than an HTTP stub.

| Component and behavior | Requirement / IC | Tier and owner | Cases and suite | Command / prerequisites | Real and simulated boundary |
|---|---|---|---|---|---|
| Fulfillment method authorization and project-filtered DAO | FR-6, FR-10 / IC-7, IC-8 | Unit [DEV] and component-integration [DEV] | TC-FR10-01, 02; existing `internal/auth/`, proposed `it/` key access cases | `ginkgo run -r internal` from `fulfillment-service/`; component suite: `make -C ../osac-installer test PLATFORM=kind PROFILE=dev NS=osac SUITE=fulfillment` from `fulfillment-service/`, with Keycloak and PostgreSQL | Unit OPA/handler tests mock providers; component suite runs Fulfillment, auth, and database, with Vault required for Create and crypto steps. |
| gRPC, REST gateway, payload validation, and CLI | FR-10 / IC-8, IC-9 | component-integration [DEV] | TC-FR10-03, 08; proposed `fulfillment-service/it/` cases | Same component suite command; requires Transit and tenant JWT identities | Deployed API, gateway, CLI, PostgreSQL, Keycloak, and Vault run for real; no downstream OSAC consumer runs. |
| Vault Transit key-scoped credentials and policy revocation | FR-4, FR-10 / IC-8 | Contract [DEV] | TC-FR10-05; proposed provider conformance suite | **Unresolved:** no existing real-Transit contract command is documented. The `[DEV]` work must add a runnable suite and command before claiming coverage. | Real Vault Transit and ACL policy evaluation are required; HTTP mocks alone do not qualify. |
| Confirmed version selection, lifecycle locks, and failed commits | FR-3, FR-4, FR-9, FR-10 / IC-8 | component-integration [DEV] | TC-FR10-04, 06; proposed `fulfillment-service/it/` fault-injection cases | **Unresolved:** the current component suite has no documented Vault-plus-database-commit fault-injection command. Add the fixtures and command in `[DEV]` work. | Fulfillment, PostgreSQL, and Transit must run for real; only the controlled commit failure is injected. |
| gRPC logging interception | FR-10 / IC-8 | Unit [DEV] | TC-FR10-07; extend `internal/logging/logging_interceptor_test.go` | `ginkgo run internal/logging` from `fulfillment-service/` | Real serialization and redaction code; gRPC handler and Vault are mocked. |
| Deployed identity-to-Vault journey | FR-10 / IC-7, IC-8, IC-9 | E2E [QE] | TC-FR10-09; proposed `tests/e2e/kms/test_managed_key_crypto.py` | **Unresolved:** no runnable KMS suite or command exists. `[QE]` adds the suite and its execution command with deployed Fulfillment, Keycloak, PostgreSQL, Vault Transit, and CLI. | All named services run for real. No operator or storage consumer is part of this journey. |

## Gaps

### Requirement Coverage Gaps

All derived PRD requirement anchors have planned test cases. The new real-Transit Contract harness, Vault-plus-database fault-injection component harness, and deployed KMS E2E suite are proposed and are not yet execution-ready; their owning `[DEV]` and `[QE]` work must establish commands and fixtures. No concrete consumer binding is added by OSAC-3612, so the deployed FR-5 `KeyInUse` check, reference-versus-Delete race, and failed database commit after Vault deletion with a live reference cannot be exercised here. [OSAC-2389](https://redhat.atlassian.net/browse/OSAC-2389) owns the first storage consumer's reference field, forward validation, reverse Delete guard, and any durable fence needed to prevent new references after an uncertain deletion. Its `[DEV]` work must cover reference validation, the guard race, and cross-store failure at Unit, Contract, and component-integration tiers; its `[QE]` work must cover the deployed storage binding and blocked destruction journey.

### Interface Change Coverage Gaps

All nine interface changes have planned test cases for behavior delivered by OSAC-3612. FR-8 uses existing operational interfaces and has no new interface change. IC-5's deployed consumer enforcement is deferred to OSAC-2389 as described above. IC-8's real-Transit contract suite and IC-9's deployed CLI case require the proposed harness work noted above.

## Summary

| Metric | Count |
|--------|-------|
| Total test cases | 41 |
| Critical | 31 |
| High | 10 |
| Medium | 0 |
| Low | 0 |
| Automated | 40 |
| Manual | 1 |
| Requirements with test cases | 10 / 10 |
| Interface changes with test cases | 9 / 9 |
