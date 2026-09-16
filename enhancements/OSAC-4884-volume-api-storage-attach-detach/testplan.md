# Testplan - OSAC-4884

## Overview

- **Feature:** OSAC-4884 - Volume API Storage Attach and Detach
- **Total test cases:** 24
- **Requirements covered:** 12 of 12
- **Interface changes covered:** 7 of 7

The published PRD has no formal FR/NFR labels. The FR-1 through FR-10 and NFR-1 through NFR-2 identifiers below are the normalized identifiers recorded in `01-context.md`.

## Test Cases

### FR-1: Equivalent public gRPC, REST, CLI, and UI behavior

#### TC-FR1-01: Create and inspect an attachment through public gRPC and REST

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-1 | critical | automated |

##### Preconditions

- A tenant owns an available Volume and an eligible ComputeInstance.
- The public VolumeAttachment API is enabled.

##### Steps

1. Create a VolumeAttachment through public gRPC.
2. Read the returned attachment through public REST.
3. Delete the attachment through public REST.
4. Read the resource until it is absent or the documented detached terminal state is returned.

##### Expected Results

- Create returns an attachment ID and a state of `PENDING` or `READY`.
- REST returns the same attachment ID, volume reference, target reference, and lifecycle state.
- Delete returns success and the attachment transitions through `DELETING` before the resource is removed.

#### TC-FR1-02: Create and delete an attachment through CLI and UI

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-3, IC-4 | high | manual |

##### Preconditions

- An authorized user can access the CLI and UI.
- A usable Volume and eligible ComputeInstance exist.

##### Steps

1. Create the attachment with `osac volume-attachment create`.
2. Confirm the CLI displays the attachment state.
3. Use the UI to display the same Volume and initiate detach.
4. Confirm the UI displays progress and completion.

##### Expected Results

- CLI output contains the attachment ID and one of the documented lifecycle states.
- UI presents attach/detach only to the authorized user and displays `PENDING`, `READY`, `DELETING`, or `FAILED` from the API.
- UI does not expose vendor IDs, backend credentials, or raw CSI secrets.

### FR-2: Direct BMaaS and VMaaS targets, including VM disks

#### TC-FR2-01: Attach a volume to BMaaS and VMaaS targets

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-1 | critical | automated |

##### Preconditions

- An eligible BMaaS instance and VMaaS ComputeInstance exist.
- Two available Volumes exist.

##### Steps

1. Create a VolumeAttachment for the BMaaS instance.
2. Create a VolumeAttachment for the VMaaS ComputeInstance.
3. Reconcile both attachments.

##### Expected Results

- Each attachment contains the correct typed target reference.
- Both relationships reach `READY` when the backend confirms attachment.
- A CaaS cluster/node identifier supplied as a direct target is rejected.

#### TC-FR2-02: Attach VM boot and additional disks through the consuming workflow

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-1 | high | automated |

##### Preconditions

- A VMaaS workflow supports a boot Volume and an additional Volume.

##### Steps

1. Provision or update the VM workflow with a boot disk Volume and an additional disk Volume.
2. Observe the resulting VolumeAttachment relationships.

##### Expected Results

- The boot and additional disk relationships reference the same VM target and distinct Volumes.
- Each relationship reaches `READY` or exposes a concrete terminal error.

### FR-3: CaaS uses PVC/CSI and the Volume API adapter

#### TC-FR3-01: CSI publish/unpublish converges the attachment relationship

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-5 | critical | automated |

##### Preconditions

- A CaaS PVC provisions an existing OSAC Volume.
- The OSAC CSI driver is configured with the Volume API endpoint.

##### Steps

1. Cause the CSI external-attacher to invoke `ControllerPublishVolume` for a node.
2. Observe the VolumeAttachment relationship.
3. Cause `ControllerUnpublishVolume` for the same volume and node.

##### Expected Results

- Publish creates or converges a relationship for the CSI target and returns success only after `READY` or a deadline error.
- Unpublish converges the same relationship to detached and does not create a duplicate relationship.
- Kubernetes continues using the PVC/CSI workflow; no public CaaS direct-attach resource is required.

### FR-4: Observable progress, deadlines, and retry

#### TC-FR4-01: Pending status survives a caller deadline

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-2 | critical | automated |

##### Preconditions

- The fake backend delays attachment longer than the client deadline.

##### Steps

1. Create an attachment with a deadline shorter than backend completion.
2. Read the attachment after the request deadline.
3. Allow reconciliation to complete.

##### Expected Results

- The create request returns a deadline error.
- The persisted attachment remains `PENDING` and can be retrieved by ID.
- The attachment later becomes `READY` without a second create operation.

#### TC-FR4-02: Transient backend failure is retried

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-2 | high | automated |

##### Preconditions

- The fake backend returns a transient error for the first two attach attempts and succeeds on the third.

##### Steps

1. Create the attachment.
2. Observe status and retry metrics between attempts.

##### Expected Results

- Status remains `PENDING` while retries are scheduled.
- Retry count increases and backoff prevents a tight retry loop.
- The relationship reaches `READY` after the successful backend attempt.

### FR-5: Idempotent repeated requests

#### TC-FR5-01: Repeated attach and detach produce one relationship and no duplicate backend effect

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-1, IC-5 | critical | automated |

##### Preconditions

- A Volume and target exist; backend call counts are observable.

##### Steps

1. Submit the same attach request twice concurrently.
2. Wait for `READY`.
3. Submit detach twice concurrently.

##### Expected Results

- Both attach requests resolve to one attachment ID.
- The backend receives at most one effective attach operation.
- Both detach requests succeed without conflict, and the backend receives at most one effective detach operation.

### FR-6: Access mode and backend capability

#### TC-FR6-01: Supported multi-attachment succeeds

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-1 | high | automated |

##### Preconditions

- A Volume advertises a multi-target access mode and its backend supports multiple attachments.
- Two eligible targets exist.

##### Steps

1. Attach the Volume to target A.
2. Attach the same Volume to target B.

##### Expected Results

- Both relationships are accepted and reach `READY`.
- Listing attachments returns two active relationships for the Volume.

#### TC-FR6-02: Unsupported multi-attachment is rejected

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-1 | high | automated |

##### Preconditions

- A Volume uses a single-target access mode or a backend that does not support concurrent attachment.
- It is already attached to target A.

##### Steps

1. Request attachment to target B.

##### Expected Results

- The request returns `FailedPrecondition`.
- No second active relationship is persisted.
- The backend receives no attach request for target B.

### FR-7: No-op attachment backends

#### TC-FR7-01: Node-local backend completes attach and detach as no-ops

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-2, IC-5 | high | automated |

##### Preconditions

- The Volume resolves to a backend with `attachRequired=false` or vendor endpoint `none`.

##### Steps

1. Create the attachment.
2. Delete the attachment.

##### Expected Results

- Attach reaches `READY` without a vendor controller call.
- Detach completes without a vendor controller call.
- Metrics identify both operations as no-op transitions.

### FR-8: CSI migration compatibility

#### TC-FR8-01: Existing CSI Volume remains usable during adapter migration

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-5 | critical | automated |

##### Preconditions

- A Volume and attachment were created using the legacy direct vendor proxy path.
- The Volume has existing `osac.backend` and vendor volume ID context.

##### Steps

1. Roll out the new CSI adapter.
2. Publish and unpublish the existing Volume.
3. Restart the CSI controller between operations.

##### Expected Results

- The existing Volume remains publishable without recreation.
- Legacy routing data is used until the relationship is adopted.
- Restart does not cause an unintended detach or duplicate attachment.

### FR-9: Lifecycle safety

#### TC-FR9-01: Target deletion cleans up its attachments

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-6 | critical | automated |

##### Preconditions

- A target has a `READY` VolumeAttachment.

##### Steps

1. Delete the compute target.
2. Observe the attachment and backend.

##### Expected Results

- The attachment enters `DELETING`.
- Backend detach is invoked before the relationship is removed.
- No active attachment remains after cleanup completes.

#### TC-FR9-02: Attached Volume deletion is blocked

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-6 | critical | automated |

##### Preconditions

- A Volume has a `READY` attachment.

##### Steps

1. Request Volume deletion.
2. Delete the VolumeAttachment.
3. Retry Volume deletion after detach completes.

##### Expected Results

- Initial Volume deletion returns `FailedPrecondition` or remains blocked by the in-use guard.
- The Volume is not archived or deleted while attached.
- Deletion succeeds after all attachments are removed.

### FR-10: Documentation and acceptance coverage

#### TC-FR10-01: Documentation matches the implemented contract

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-7 | high | manual |

##### Preconditions

- The design implementation and representative backend-neutral E2E environment are available.

##### Steps

1. Follow the documented public attach procedure.
2. Follow the documented detach and operator-recovery procedure.
3. Compare documented states/errors with observed API, CLI, UI, and logs.

##### Expected Results

- Documentation names the public request/response surfaces, states, authorization behavior, retries, deadline behavior, migration behavior, and no-force-detach recovery.
- Documented error names and states match observed responses.

#### TC-FR10-02: Automated representative attach and detach E2E flow

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-7 | critical | automated |

##### Preconditions

- The backend-neutral E2E fixture provides one tenant, one authorized caller, one Volume, and one eligible compute target.

##### Steps

1. Create a VolumeAttachment through the public API.
2. Poll the resource until it reaches `READY`.
3. Delete the VolumeAttachment.
4. Poll until detach completes and the relationship is absent.

##### Expected Results

- The public API returns one attachment ID and the resource reaches `READY`.
- The backend records one attach and one detach operation for the same Volume/target relationship.
- The attachment is absent after detach and the Volume remains usable for a subsequent operation.

### NFR-1: 0.3 delivery and tenant isolation

#### TC-NFR1-01: Tenant isolation and provider administration are enforced

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-1 | critical | automated |

##### Preconditions

- Tenant A owns a Volume and ComputeInstance.
- Tenant B has a normal tenant role; a provider administrator has provider-level permission.

##### Steps

1. Tenant B attempts to create, get, list, and delete Tenant A's attachment.
2. The provider administrator creates and manages an attachment between Tenant A's Volume and Tenant A's ComputeInstance.
3. The provider administrator attempts to create an attachment between Tenant A's Volume and Tenant B's ComputeInstance.

##### Expected Results

- Tenant B receives `PermissionDenied` and sees no Tenant A attachment in list results.
- The provider administrator can operate on the Tenant A attachment according to provider policy.
- The cross-tenant relationship is rejected with `FailedPrecondition` and no attachment row is created.
- Audit/structured logs identify the caller and tenant without exposing secrets.

### NFR-2: Explicit non-goals remain excluded

#### TC-NFR2-01: Force detach and direct CaaS target operations are unavailable

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-1, IC-3 | medium | automated |

##### Preconditions

- Public API and CLI clients are available.

##### Steps

1. Attempt to invoke a force-detach field, RPC, or CLI flag.
2. Attempt to create a direct attachment using a CaaS node/cluster target.

##### Expected Results

- No force-detach operation or accepted force flag exists.
- The CaaS direct target is rejected with `InvalidArgument` or `FailedPrecondition`.
- Standard PVC/CSI attachment remains the supported CaaS path.

### Additional lifecycle and contract coverage

#### TC-FR4-03: Terminal attach failure remains visible and recoverable

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-2 | high | automated |

##### Preconditions

- The fake backend returns a non-retryable attach error.

##### Steps

1. Create the attachment.
2. Read it after reconciliation.
3. Correct the fake backend and signal the attachment.

##### Expected Results

- The attachment reaches `FAILED` with a non-empty reason and message.
- It never reports `READY` while the backend is failing.
- Signaling after backend recovery retries the relationship and transitions it to `READY`.

#### TC-FR4-04: Transient detach failure retries and terminal detach retains the finalizer

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-2, IC-6 | critical | automated |

##### Preconditions

- A `READY` attachment exists.
- The fake backend first returns a transient detach error, then a terminal detach error.

##### Steps

1. Delete the attachment.
2. Observe retries and status.
3. Inspect the resource finalizer after the terminal error.

##### Expected Results

- The resource remains `DELETING` during the transient error and retry.
- After the terminal error, the resource remains present with a detach failure condition and its finalizer intact.
- No force-detach operation is invoked.

#### TC-FR5-02: Restart during detach resumes without duplicate effect

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-2, IC-5 | high | automated |

##### Preconditions

- A `READY` attachment exists and the backend delays detach.

##### Steps

1. Delete the attachment.
2. Restart the attachment worker before backend completion.
3. Allow reconciliation to resume.

##### Expected Results

- The persisted relationship remains `DELETING` across restart.
- Reconciliation resumes and issues one effective detach operation.
- The finalizer is removed only after detached state is confirmed.

#### TC-FR6-03: Concurrent attach and Volume deletion are serialized

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-1, IC-6 | high | automated |

##### Preconditions

- A usable Volume and target exist.

##### Steps

1. Submit attachment creation and Volume deletion concurrently.
2. Reconcile both requests to completion.

##### Expected Results

- The database leaves either a persisted active attachment and a blocked Volume deletion, or a rejected attachment with a completed Volume deletion.
- It never archives/deletes the Volume while an active attachment row remains.
- No orphan backend attachment exists after both operations settle.

#### TC-FR1-03: Public API contract uses canonical routes and immutable fields

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-1 | high | automated |

##### Preconditions

- A public API test server is running with generated protos and REST gateway.

##### Steps

1. Invoke the canonical snake_case REST create, list, get, update, and delete routes.
2. Attempt to update `spec.volume` and the target.

##### Expected Results

- Routes use `/api/fulfillment/v1/volume_attachments` and return standard object/list response fields.
- JSON fields use `compute_instance` and other snake_case names.
- Metadata-only update succeeds; changing an immutable spec field returns `InvalidArgument`.

#### TC-FR8-02: CSI and service version skew preserve existing attachment behavior

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-5 | high | automated |

##### Preconditions

- An existing CSI Volume has legacy backend and vendor-ID context.
- Test deployments can run old/new service and CSI combinations.

##### Steps

1. Run old CSI against the new service and publish/unpublish the Volume.
2. Run new CSI against the service before the new attachment API is enabled.
3. Roll back the CSI adapter and repeat publish/unpublish.

##### Expected Results

- Old CSI continues to use the compatible legacy path.
- New CSI refuses or falls back visibly when the attachment API is unavailable; it does not silently drop the request.
- Rollback does not delete persisted attachment records or detach an existing workload.

## Requirement Traceability

The test-case metadata tables use the design workflow's `Interface Change`, `Priority`, and `Automation` fields. This table maps each normalized requirement to the source PRD user story and observable acceptance behavior.

| Requirement | PRD user story | Acceptance behavior | Test cases |
|---|---|---|---|
| FR-1 | Cloud Provider Admin; Tenant Admin/User | gRPC, REST, CLI, and UI expose equivalent lifecycle behavior | TC-FR1-01, TC-FR1-02, TC-FR1-03 |
| FR-2 | Cloud Infrastructure Admin; Tenant Admin/User | BMaaS and VMaaS targets, including boot/additional disks | TC-FR2-01, TC-FR2-02 |
| FR-3 | Cloud Infrastructure Admin; Tenant Admin/User | CaaS remains PVC/CSI and uses the Volume API adapter | TC-FR3-01 |
| FR-4 | Cloud Provider Admin | Pending, retry, deadline, terminal failure, and final outcomes are observable | TC-FR4-01, TC-FR4-02, TC-FR4-03, TC-FR4-04 |
| FR-5 | Tenant Admin/User | Repeated desired-state requests converge without duplicate effects | TC-FR5-01, TC-FR5-02 |
| FR-6 | Tenant Admin/User | Access mode/backend capability controls concurrent attachments | TC-FR6-01, TC-FR6-02, TC-FR6-03 |
| FR-7 | Tenant Admin/User | No-attach backends complete attach/detach as no-ops | TC-FR7-01 |
| FR-8 | Tenant Admin/User | Existing CSI Volumes remain usable during migration | TC-FR8-01, TC-FR8-02 |
| FR-9 | Tenant Admin/User; Cloud Infrastructure Admin | Target cleanup and attached-Volume deletion protection | TC-FR9-01, TC-FR9-02, TC-FR6-03 |
| FR-10 | All personas | Documentation, representative E2E, retries, invalid targets, cross-tenant failures, backend failures, and CSI migration | TC-FR10-01, TC-FR10-02, TC-FR2-01, TC-FR4-02, TC-FR4-03, TC-FR4-04, TC-FR8-01, TC-FR8-02, TC-NFR1-01 |
| NFR-1 | Cloud Provider Admin | Tenant isolation and provider-level administration | TC-NFR1-01 |
| NFR-2 | Cloud Infrastructure Admin | No force detach or direct CaaS target API | TC-NFR2-01 |

## Gaps

### Requirement Coverage Gaps

All normalized PRD requirements have test cases.

### Interface Change Coverage Gaps

All interface changes are exercised by test cases.

## Summary

| Metric | Count |
|--------|-------|
| Total test cases | 24 |
| Critical | 11 |
| High | 12 |
| Medium | 1 |
| Low | 0 |
| Automated | 22 |
| Manual | 2 |
| Requirements with test cases | 12 / 12 |
| Interface changes with test cases | 7 / 7 |
