# Testplan - OSAC-4884

## Overview

- **Feature:** OSAC-4884 - Volume API Storage Attach and Detach
- **Total test cases:** 31
- **Requirements covered:** 12 of 12
- **Interface changes covered:** 7 of 7

The published PRD has no formal FR/NFR labels. The FR-1 through FR-10 and NFR-1 through NFR-2 identifiers below are normalized in the traceability table at the end of this document.

## Implementation Grounding

- Fulfillment-service unit and integration coverage uses Ginkgo/Gomega under `osac/fulfillment-service/internal/servers/`, `internal/controllers/`, `internal/database/migrations/`, and `it/`; use the ExternalIPAttachment server/controller suites and the Volume server/controller suites as patterns.
- CSI adapter coverage uses standard Go tests in `osac/osac-csi-driver/pkg/driver/controller_test.go`; reuse the existing vendor-controller mocks and tests for `AlreadyExists`, `NotFound`, `Unimplemented`, no-op backends, and retry errors.
- Operator controller coverage uses Ginkgo/Gomega/envtest under `osac/osac-operator/internal/controller/`; add `attachment_controller_test.go` beside `volume_controller_test.go` and target deletion tests beside `computeinstance_controller_test.go`.
- E2E coverage belongs in `osac/tests/e2e/storage/test_volume_attachment_lifecycle.py`, using `storage/conftest.py`, `tests/e2e/core/grpc_client.py`, `tests/e2e/core/osac_cli.py`, `tests/e2e/core/k8s_client.py`, and `tests/e2e/core/runner.py::poll_until`; follow the lifecycle structure in `test_tenant_storage_lifecycle.py` and `test_caas_cluster_storage.py`.
- VMaaS attachment tests must also inspect the AAP ComputeInstance provisioning input, the resulting PVC/PV and KubeVirt VM disk definition, following the storage flow in `osac/osac-operator/internal/controller/computeinstance_controller.go` and the storage roles under `osac/osac-aap/collections/ansible_collections/osac/`.
- The fake operator attachment reconciler must expose deterministic AAP success/failure, PVC creation, VM disk wiring, CSI bind, detach, inventory, and call-count controls for unit and integration tests.

## Test Cases

### FR-1: Equivalent public gRPC, REST, CLI, and UI behavior

#### TC-FR1-01 [AC-FR1-01] [Story: Cloud Provider Admin; Tenant Admin/User]: Create and inspect an attachment through public gRPC and REST

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-1 | critical | automated |

##### Preconditions

- A tenant owns an available Volume and an eligible ComputeInstance.
- The public VolumeAttachment API is enabled.

##### Steps

1. Create `vol-123` to target `ci-456` through public gRPC using `spec.volume.id = "vol-123"`, `spec.compute_instance.id = "ci-456"`, and `spec.readonly = false`.
2. Read the returned attachment through `GET /api/fulfillment/v1/volume_attachments/{id}`.
3. Delete the attachment through public REST.
4. Read the resource until `GET` returns `NotFound`.

##### Expected Results

- Create returns one attachment ID and a state of `PENDING` or `READY`; the returned spec contains `vol-123`, `ci-456`, and `readonly: false`.
- REST returns the same attachment ID, volume reference, target reference, and lifecycle state.
- Delete returns success and the attachment transitions through `DELETING` before `GET` returns `NotFound`.

#### TC-FR1-02 [AC-FR1-02] [Story: Cloud Provider Admin; Tenant Admin/User]: Create and delete an attachment through CLI and UI

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

#### TC-FR1-03 [AC-FR1-03] [Story: Cloud Infrastructure Admin]: Public API contract uses canonical routes and immutable fields

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-1 | high | automated |

##### Preconditions

- A public API test server is running with generated protos and REST gateway; use the fulfillment-service API integration harness.

##### Steps

1. Invoke `POST /api/fulfillment/v1/volume_attachments` with `vol-123`, `ci-456`, and `readonly: false`.
2. Invoke the canonical list, get, update, and delete routes.
3. Attempt to update `spec.volume` and `spec.compute_instance`.

##### Expected Results

- Routes return standard object/list response fields and JSON uses `compute_instance` snake_case.
- Metadata-only update succeeds; changing an immutable spec field returns `InvalidArgument`.

### FR-2: Direct BMaaS and VMaaS targets, including VM disks

#### TC-FR2-01 [AC-FR2-01] [Story: Cloud Infrastructure Admin]: Attach a volume to BMaaS and VMaaS targets

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-1 | critical | automated |

##### Preconditions

- An eligible BMaaS instance and VMaaS ComputeInstance exist.
- Two available Volumes exist.

##### Steps

1. Create a VolumeAttachment for the BMaaS instance.
2. Create a VolumeAttachment for the VMaaS ComputeInstance.
3. Reconcile both attachment intents.

##### Expected Results

- Each attachment contains the correct typed target reference.
- The BMaaS relationship reaches `READY` when its operator/backend workflow confirms attachment.
- The VMaaS relationship creates an operator attachment intent and does not invoke vendor attach directly from the API path.
- A CaaS cluster/node identifier supplied as a direct target is rejected.

#### TC-FR2-02 [AC-FR2-02] [Story: Tenant Admin/User]: Attach VM boot and additional disks through the consuming workflow

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-1 | high | automated |

##### Preconditions

- A VMaaS workflow supports a boot Volume and an additional Volume.

##### Steps

1. Create attachments for `vol-123` as the VM boot disk and `vol-456` as an additional disk on `ci-456`.
2. Observe the operator attachment intent and AAP provisioning input.
3. Observe the PVCs, PVs, and KubeVirt VM disk definition.
4. Observe the CSI controller path for the annotated PVCs.

##### Expected Results

- The boot and additional disk relationships reference the same VM target and distinct Volumes.
- AAP creates PVCs with `osac.volume.id=vol-123` and `osac.volume.id=vol-456`, and references both PVCs from the KubeVirt VM.
- CSI creates/binds PVs for the existing OSAC Volumes without calling fulfillment `CreateVolume`.
- Each relationship reaches `READY` only after PVC/PV binding, VM disk wiring, and CSI publish complete, or exposes a concrete terminal error.

### FR-3: CaaS uses PVC/CSI and the Volume API adapter

#### TC-FR3-01 [AC-FR3-01] [Story: Cloud Infrastructure Admin; Tenant Admin/User]: CSI publish/unpublish converges the attachment relationship

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

#### TC-FR4-01 [AC-FR4-01] [Story: Cloud Provider Admin]: Pending status survives a caller deadline

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

#### TC-FR4-02 [AC-FR4-02] [Story: Cloud Provider Admin]: Transient backend failure is retried

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

#### TC-FR4-03 [AC-FR4-03] [Story: Cloud Provider Admin]: Terminal attach failure remains visible and recoverable

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-2 | high | automated |

##### Preconditions

- The operator fake `AttachmentExecutor` returns a non-retryable error for `vol-123` and later can be switched to success.

##### Steps

1. Create the `vol-123` to `ci-456` attachment.
2. Read it after reconciliation.
3. Correct the fake executor and invoke the private `Signal` RPC as an authorized operator identity.

##### Expected Results

- The attachment reaches `FAILED` with a non-empty reason and message.
- It never reports `READY` while the operator executor is failing.
- Signaling after executor recovery retries the relationship and transitions it to `READY`.

#### TC-FR4-04 [AC-FR4-04] [Story: Cloud Infrastructure Admin]: Transient detach failure retries and terminal detach retains the finalizer

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-2, IC-6 | critical | automated |

##### Preconditions

- A `READY` attachment exists in the fulfillment-service integration harness.
- The fake `AttachmentExecutor` returns a transient detach error, then a terminal detach error.

##### Steps

1. Delete the attachment.
2. Observe retries and `next_attempt_at`.
3. Inspect the resource finalizer after the terminal error.

##### Expected Results

- The resource remains `DELETING` during the transient error and retry.
- After the terminal error, the resource remains present with a detach failure condition and its finalizer intact.
- No force-detach operation is invoked.

### FR-5: Idempotent repeated requests

#### TC-FR5-01 [AC-FR5-01] [Story: Tenant Admin/User]: Repeated attach and detach produce one relationship and no duplicate backend effect

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-1, IC-5 | critical | automated |

##### Preconditions

- A Volume and target exist; backend call counts are observable.

##### Steps

1. Submit the same attach request twice concurrently.
2. Wait for `READY`.
3. Submit a third attach request for the same Volume/target with `readonly: true`.
4. Submit detach twice concurrently.

##### Expected Results

- Both attach requests resolve to one attachment ID.
- The backend receives at most one effective attach operation.
- The mismatched `readonly` request returns `AlreadyExists` with the existing attachment ID and does not change `spec`.
- Both detach requests succeed without conflict, and the backend receives at most one effective detach operation.

#### TC-FR5-02 [AC-FR5-02] [Story: Cloud Infrastructure Admin]: Restart during detach resumes without duplicate effect

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-2, IC-5 | high | automated |

##### Preconditions

- A `READY` attachment exists and the fake `AttachmentExecutor` delays detach.

##### Steps

1. Delete the attachment.
2. Restart the operator attachment controller before vendor completion.
3. Allow reconciliation to resume.

##### Expected Results

- The persisted relationship remains `DELETING` across restart.
- Reconciliation resumes and the vendor receives one effective detach operation.
- The finalizer is removed only after detached state is confirmed.

#### TC-FR5-03 [AC-FR5-03] [Story: Cloud Infrastructure Admin]: Lost vendor response replays the same operation token

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-2, IC-5 | critical | automated |

##### Preconditions

- The fake `AttachmentExecutor` completes vendor attach for `vol-123`/`ci-456` but drops the result after recording operation token `token-attach-1`.
- A second operator reconcile can observe an expired `RUNNING` claim and vendor state.

##### Steps

1. Start two operator reconciles concurrently with operation token `token-attach-1`.
2. Let the first claim lease expire without a heartbeat.
3. Allow the second reconcile to compare-and-swap the claim and retry with the same operation token.
4. Read the Attachment CR status and vendor call ledger.

##### Expected Results

- One operator reconcile claims `token-attach-1`; the concurrent reconcile waits for or takes over that claim, and stale-owner execution is rejected.
- Recovery queries vendor state before retrying and produces one effective backend attachment with no stale owner in the Attachment CR status.
- The attachment reaches `READY` and the persisted operation ledger contains one token/result pair.

### FR-6: Access mode and backend capability

#### TC-FR6-01 [AC-FR6-01] [Story: Tenant Admin/User]: Supported multi-attachment succeeds

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

#### TC-FR6-02 [AC-FR6-02] [Story: Tenant Admin/User]: Unsupported multi-attachment is rejected

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

#### TC-FR6-03 [AC-FR6-03] [Story: Cloud Infrastructure Admin]: Concurrent attach and Volume deletion are serialized

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-1, IC-6 | high | automated |

##### Preconditions

- The migration test database contains `vol-123` and `ci-456`; the fake operator executor records vendor calls.

##### Steps

1. Submit attachment creation and Volume deletion concurrently.
2. Reconcile both requests to completion.

##### Expected Results

- The database leaves either a persisted active attachment and a blocked Volume deletion, or a rejected attachment with a completed Volume deletion.
- It never archives/deletes `vol-123` while an active helper row remains.
- No orphan vendor attachment exists after both operations settle.

### FR-7: No-op attachment backends

#### TC-FR7-01 [AC-FR7-01] [Story: Tenant Admin/User]: Node-local backend completes attach and detach as no-ops

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

#### TC-FR8-01 [AC-FR8-01] [Story: Tenant Admin/User]: Existing CSI Volume remains usable during adapter migration

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

#### TC-FR8-02 [AC-FR8-02] [Story: Cloud Infrastructure Admin]: CSI and service version skew preserve existing attachment behavior

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-5 | high | automated |

##### Preconditions

- An existing CSI Volume has legacy backend and vendor-ID context.
- The migration integration harness can run old/new service and CSI combinations.

##### Steps

1. Run old CSI against the new service with the feature disabled and publish/unpublish the Volume.
2. Run the new CSI against the old service.
3. Run the operator inventory migration and enable the new feature gate.
4. Publish/unpublish with the new CSI adapter, then roll back the adapter.

##### Expected Results

- Old CSI continues to use the compatible legacy path while the feature is disabled.
- New CSI readiness fails and no vendor operation is sent when the old service lacks the private capability.
- Inventory creates one adopted helper row per existing relationship before enablement.
- Rollback does not delete persisted records or detach an existing workload.

#### TC-FR8-03 [AC-FR8-03] [Story: Cloud Infrastructure Admin]: Inventory failure blocks CSI feature enablement

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-5 | high | automated |

##### Preconditions

- The operator inventory adapter reports that the vendor lacks `LIST_VOLUMES_PUBLISHED_NODES` or returns an inventory error.

##### Steps

1. Run the attachment migration Job.
2. Attempt to enable the attachment feature gate.
3. Attempt a new CSI publish operation.

##### Expected Results

- The migration Job records a failure reason and imports no partial relationship set.
- The feature gate remains disabled and an operator-visible alert identifies the backend.
- CSI readiness remains false and no new-path vendor publish is attempted.

#### TC-FR8-04 [AC-FR8-04] [Story: Cloud Infrastructure Admin]: Operator inventory changes restart the migration epoch

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-5 | high | automated |

##### Preconditions

- The operator inventory adapter returns a different inventory checksum on the second page of one migration epoch.

##### Steps

1. Run the migration Job through the first inventory page.
2. Change the fake operator inventory before the next page.
3. Allow the Job to finish.

##### Expected Results

- The Job discards the incomplete staging epoch and records the checksum mismatch.
- No partial private attachment records or helper rows become visible.
- A resumed Job starts a new epoch and promotes only a consistent inventory.

#### TC-FR8-05 [AC-FR8-05] [Story: Cloud Infrastructure Admin]: Migration Job crash resumes from a staged cursor

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-5 | high | automated |

##### Preconditions

- The operator inventory adapter exposes two inventory pages and the migration Job persists its first-page cursor.

##### Steps

1. Stop the migration Job after the first page is staged.
2. Restart the Job.
3. Allow inventory promotion to complete.

##### Expected Results

- The restarted Job resumes the same epoch at the persisted cursor.
- Each relationship is promoted once and the feature gate remains disabled until promotion commits.

#### TC-FR8-06 [AC-FR8-06] [Story: Cloud Infrastructure Admin]: Rollback fences in-flight new-path operations

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-5 | high | automated |

##### Preconditions

- The new feature gate is enabled and a `vol-123` attachment operation is `PENDING`.

##### Steps

1. Start rollback while an operator reconciliation is in flight.
2. Attempt an old-CSI publish and a new-CSI publish during rollback.
3. Allow the operator reconciliation and rollback fence to settle.

##### Expected Results

- Rollback enters a draining state and does not enable legacy mode until the pending operation is `READY`, `FAILED`, or explicitly recovered.
- Old CSI is rejected until the fence confirms no new-path operation is pending.
- New CSI readiness becomes false and no duplicate vendor operation is started.

### FR-9: Lifecycle safety

#### TC-FR9-01 [AC-FR9-01] [Story: Cloud Infrastructure Admin]: Target deletion cleans up its attachments

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

#### TC-FR9-02 [AC-FR9-02] [Story: Tenant Admin/User]: Attached Volume deletion is blocked

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

- Initial Volume deletion returns `FailedPrecondition` with the `volume_in_use` reason.
- The Volume is not archived or deleted while attached.
- Deletion succeeds after all attachments are removed.

#### TC-FR9-03 [AC-FR9-03] [Story: Cloud Infrastructure Admin]: Target deletion guard races with attachment creation

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-6 | critical | automated |

##### Preconditions

- `ci-456` exists and has no attachment.
- The integration harness can synchronize `BeginTargetDeletion` and attachment creation at the database lock.

##### Steps

1. Start target deletion for `ci-456`.
2. Concurrently create an attachment from `vol-123` to `ci-456`.
3. Allow both transactions and finalizers to settle.

##### Expected Results

- Exactly one ordering wins: either attachment creation returns `FailedPrecondition` because the target deletion guard is held, or the target deletion waits for and detaches the newly created relationship.
- The target finalizer is removed only after `TargetAttachmentsGone` succeeds.
- No active helper row or vendor attachment remains for `ci-456` after deletion.

#### TC-FR9-04 [AC-FR9-04] [Story: Cloud Infrastructure Admin]: Already-deleting target is quarantined during backfill

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-6 | critical | automated |

##### Preconditions

- `ci-456` has a deletion timestamp before the target-finalizer backfill Job starts and has one existing `READY` attachment.

##### Steps

1. Run the target backfill Job.
2. Attempt to create a new attachment to `ci-456`.
3. Observe the existing attachment and the target mirror until cleanup settles.

##### Expected Results

- The Job does not add `osac.openshift.io/volume-attachment` to the deleting target.
- New attachment creation returns `FailedPrecondition` and creates no helper row.
- The existing attachment is drained, the mirror retains `ci-456` until `TargetAttachmentsGone`, and the feature gate remains disabled until quarantine is empty.

### FR-10: Documentation and acceptance coverage

#### TC-FR10-01 [AC-FR10-01] [Story: All personas]: Documentation matches the implemented contract

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

#### TC-FR10-02 [AC-FR10-02] [Story: All personas]: Automated representative attach and detach E2E flow

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
- The automated test is implemented in `osac/tests/e2e/storage/test_volume_attachment_lifecycle.py` and polls with `tests/e2e/core/runner.py::poll_until`.

### NFR-1: 0.3 delivery and tenant isolation

#### TC-NFR1-01 [AC-NFR1-01] [Story: Cloud Provider Admin; Tenant Admin/User]: Tenant isolation and provider administration are enforced

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

#### TC-NFR2-01 [AC-NFR2-01] [Story: Cloud Infrastructure Admin]: Force detach and direct CaaS target operations are unavailable

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

## Requirement Traceability

The test-case metadata tables use the design workflow's `Interface Change`, `Priority`, and `Automation` fields. This table maps each normalized requirement to the source PRD user story and observable acceptance behavior.

The per-test `Story` and `AC` fields are keyed by test-case ID in the `Per-test Story and Acceptance Traceability` table below. The PRD has no formal acceptance-criteria IDs, so `AC-FR*-NN` values are stable normalized anchors to the corresponding PRD In Scope bullet and user-story behavior; they are not new requirements. This preserves the design workflow metadata format while keeping each test's source story and observable acceptance behavior explicit.

| Requirement | PRD user story | Acceptance behavior | Test cases |
|---|---|---|---|
| FR-1 | Cloud Provider Admin; Tenant Admin/User | gRPC, REST, CLI, and UI expose equivalent lifecycle behavior | TC-FR1-01, TC-FR1-02, TC-FR1-03 |
| FR-2 | Cloud Infrastructure Admin; Tenant Admin/User | BMaaS and VMaaS targets, including boot/additional disks | TC-FR2-01, TC-FR2-02 |
| FR-3 | Cloud Infrastructure Admin; Tenant Admin/User | CaaS remains PVC/CSI and uses the Volume API adapter | TC-FR3-01 |
| FR-4 | Cloud Provider Admin | Pending, retry, deadline, terminal failure, and final outcomes are observable | TC-FR4-01, TC-FR4-02, TC-FR4-03, TC-FR4-04 |
| FR-5 | Tenant Admin/User | Repeated desired-state requests converge without duplicate effects | TC-FR5-01, TC-FR5-02, TC-FR5-03 |
| FR-6 | Tenant Admin/User | Access mode/backend capability controls concurrent attachments | TC-FR6-01, TC-FR6-02, TC-FR6-03 |
| FR-7 | Tenant Admin/User | No-attach backends complete attach/detach as no-ops | TC-FR7-01 |
| FR-8 | Tenant Admin/User | Existing CSI Volumes remain usable during migration | TC-FR8-01, TC-FR8-02, TC-FR8-03, TC-FR8-04, TC-FR8-05, TC-FR8-06 |
| FR-9 | Tenant Admin/User; Cloud Infrastructure Admin | Target cleanup and attached-Volume deletion protection | TC-FR9-01, TC-FR9-02, TC-FR9-03, TC-FR9-04, TC-FR6-03 |
| FR-10 | All personas | Documentation, representative E2E, retries, invalid targets, cross-tenant failures, backend failures, and CSI migration | TC-FR10-01, TC-FR10-02, TC-FR2-01, TC-FR4-02, TC-FR4-03, TC-FR4-04, TC-FR8-01, TC-FR8-02, TC-NFR1-01 |
| NFR-1 | Cloud Provider Admin | Tenant isolation and provider-level administration | TC-NFR1-01 |
| NFR-2 | Cloud Infrastructure Admin | No force detach or direct CaaS target API | TC-NFR2-01 |

### Per-test Story and Acceptance Traceability

| Test case | Story | AC |
|---|---|---|
| TC-FR1-01 | Cloud Provider Admin; Tenant Admin/User | AC-FR1-01: Public gRPC/REST attach, status, and detach |
| TC-FR1-02 | Cloud Provider Admin; Tenant Admin/User | AC-FR1-02: CLI/UI expose equivalent authorized lifecycle |
| TC-FR1-03 | Cloud Infrastructure Admin | AC-FR1-03: Canonical routes, snake_case fields, immutable spec |
| TC-FR2-01 | Cloud Infrastructure Admin | AC-FR2-01: BMaaS and VMaaS typed targets are accepted; CaaS direct target rejected |
| TC-FR2-02 | Tenant Admin/User | AC-FR2-02: VM boot and additional disks use attachment lifecycle |
| TC-FR3-01 | Cloud Infrastructure Admin; Tenant Admin/User | AC-FR3-01: CaaS PVC/CSI publish/unpublish uses the private relationship |
| TC-FR4-01 | Cloud Provider Admin | AC-FR4-01: Deadline leaves observable pending state |
| TC-FR4-02 | Cloud Provider Admin | AC-FR4-02: Transient backend failure is retried with progress |
| TC-FR4-03 | Cloud Provider Admin | AC-FR4-03: Terminal attach failure is visible and recoverable by authorized Signal |
| TC-FR4-04 | Cloud Infrastructure Admin | AC-FR4-04: Detach retry and terminal finalizer retention are observable |
| TC-FR5-01 | Tenant Admin/User | AC-FR5-01: Repeated attach/detach is idempotent |
| TC-FR5-02 | Cloud Infrastructure Admin | AC-FR5-02: Restart resumes detach without duplicate effect |
| TC-FR5-03 | Cloud Infrastructure Admin | AC-FR5-03: Same operation token deduplicates concurrent/lost-response retries |
| TC-FR6-01 | Tenant Admin/User | AC-FR6-01: Supported multi-attachment succeeds |
| TC-FR6-02 | Tenant Admin/User | AC-FR6-02: Unsupported multi-attachment returns FailedPrecondition |
| TC-FR6-03 | Cloud Infrastructure Admin | AC-FR6-03: Volume deletion and attachment creation are serialized |
| TC-FR7-01 | Tenant Admin/User | AC-FR7-01: No-attach backend completes as a no-op |
| TC-FR8-01 | Tenant Admin/User | AC-FR8-01: Existing CSI Volume remains usable after adapter rollout |
| TC-FR8-02 | Cloud Infrastructure Admin | AC-FR8-02: Version-skew matrix preserves safe routing |
| TC-FR8-03 | Cloud Infrastructure Admin | AC-FR8-03: Inventory capability/error blocks feature enablement |
| TC-FR8-04 | Cloud Infrastructure Admin | AC-FR8-04: Inventory checksum change discards staging epoch |
| TC-FR8-05 | Cloud Infrastructure Admin | AC-FR8-05: Migration crash resumes cursor and promotes once |
| TC-FR8-06 | Cloud Infrastructure Admin | AC-FR8-06: Rollback drains and fences in-flight new-path operations |
| TC-FR9-01 | Cloud Infrastructure Admin | AC-FR9-01: Target deletion detaches before finalizer removal |
| TC-FR9-02 | Tenant Admin/User | AC-FR9-02: Attached Volume deletion returns volume_in_use |
| TC-FR9-03 | Cloud Infrastructure Admin | AC-FR9-03: Target deletion guard prevents orphan attachment |
| TC-FR9-04 | Cloud Infrastructure Admin | AC-FR9-04: Already-deleting target is quarantined during backfill |
| TC-FR10-01 | All personas | AC-FR10-01: Documentation matches public contract and recovery |
| TC-FR10-02 | All personas | AC-FR10-02: Automated representative attach/detach E2E passes |
| TC-NFR1-01 | Cloud Provider Admin; Tenant Admin/User | AC-NFR1-01: Tenant isolation and provider policy are enforced |
| TC-NFR2-01 | Cloud Infrastructure Admin | AC-NFR2-01: Force detach and direct CaaS target remain unavailable |

## Gaps

### Requirement Coverage Gaps

All normalized PRD requirements have test cases.

### Interface Change Coverage Gaps

All interface changes are exercised by test cases.

## Summary

| Metric | Count |
|--------|-------|
| Total test cases | 31 |
| Critical | 14 |
| High | 16 |
| Medium | 1 |
| Low | 0 |
| Automated | 29 |
| Manual | 2 |
| Requirements with test cases | 12 / 12 |
| Interface changes with test cases | 7 / 7 |
