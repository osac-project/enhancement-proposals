---
title: volume-api-storage-attach-and-detach
authors:
  - Roy Golan
creation-date: 2026-09-16
last-updated: 2026-09-16
tracking-link:
  - https://redhat.atlassian.net/browse/OSAC-4884
prd:
  - prd.md
---

# Volume API Storage Attach and Detach

## Summary

The design adds a first-class, tenant-scoped `VolumeAttachment` resource for BMaaS, VMaaS, and CaaS storage workflows. For VMaaS, the resource is declarative: the API records the desired attachment, the operator updates the VM provisioning input, AAP creates a PVC and references it from the KubeVirt VM, and the normal OSAC CSI flow binds that PVC to the already-existing OSAC Volume. BMaaS uses the operator's corresponding compute provisioning path; CaaS continues through standard PVC/CSI. The design provides public gRPC, REST, CLI, and UI behavior without exposing vendor-specific APIs or secrets.

## Motivation

The current Volume API records provisioning but not attachment. VMaaS disk provisioning is driven by ComputeInstance/AAP input and KubeVirt DataVolumes/PVCs, while the CSI driver owns the Kubernetes binding path. A direct vendor attach call would bypass the VM's PVC and KubeVirt disk model. The design therefore makes attachment intent declarative and lets the existing VMaaS provisioning and CSI controllers create the Kubernetes resources that represent the attachment.

## Proposal

The proposal is specified in section 4 Design, with workflow in section 4.1, schema and API changes in sections 4.2-4.3, security and tenancy in sections 4.5 and 4.7, and failure recovery in section 4.6.

### Workflow Description

Clients create and delete an immutable attachment relationship; the API records intent and the controller reconciles it to backend state. CaaS follows the same relationship through CSI publish/unpublish. See sections 4.1 and 4.6.

### API Extensions

The new public `VolumeAttachments` service and private CSI target variant are described in sections 4.2 and 4.3. The change is additive and uses generated public protos from private source protos.

### Implementation Details/Notes/Constraints

The database migration, controller ownership, CSI migration, and version-skew constraints are described in sections 4.1, 4.2, 4.6, and 8.

### Security Considerations

Authentication, OPA authorization, target validation, tenant isolation, and secret non-disclosure are described in sections 4.5 and 4.7.

### Failure Handling and Recovery

Transient retries, deadlines, idempotency, terminal failures, deletion guards, and operator recovery are described in section 4.6 and Support Procedures.

### RBAC / Tenancy

The resource is tenant-scoped and provider-admin access is explicitly bounded in section 4.7.

### Observability and Monitoring

Metrics, structured transitions, events, and recovery signals are specified in section 7.

### Risks and Mitigations

The principal risks are migration adoption, backend/provider availability, and races between target/volume deletion. Mitigations are durable attachment state, conservative finalizers, unique relationship constraints, and staged CSI rollout; see section 8 and Support Procedures.

### Drawbacks

The first-class resource adds API, persistence, controller, and migration complexity compared with direct vendor proxying. This cost is accepted because action-only or proxy-only designs cannot provide durable progress, tenant authorization, deletion safety, and cross-service lifecycle behavior.

## 1. Overview

This design adds a first-class `VolumeAttachment` resource that represents the desired and observed relationship between an OSAC Volume and an OSAC-managed BMaaS or VMaaS compute target. Creating the resource requests attachment; deleting it requests detachment. Fulfillment-service persists the relationship and lifecycle status, while the attachment controller dispatches the backend operation and retries until the requested state is reached.

The OSAC CSI driver adapts `ControllerPublishVolume` and `ControllerUnpublishVolume` to the same attachment lifecycle for CaaS. Existing volume IDs, vendor routing, idempotency, and no-op backends remain compatible. Public gRPC, REST, CLI, and UI clients consume the generated public resource API. See [PRD](prd.md) for requirements context.

## 2. Goals and Non-Goals

### Goals

- Let callers inspect and retry attachment progress after deadlines, process restarts, and client loss.
- Let authorized callers target BMaaS and VMaaS resources through typed references rather than arbitrary backend node identifiers.
- Preserve existing CSI-managed workloads while the new attachment lifecycle is enabled in a controlled migration.
- Prevent volume and compute-target deletion from leaving active storage relationships.
- Keep the public contract backend-neutral across direct compute, CSI, CLI, and UI workflows.

### Non-Goals

- A user-facing force-detach operation.
- Direct public attachment to CaaS clusters or nodes; CaaS continues through PVC and CSI.
- Direct exposure of vendor-specific attachment APIs, credentials, or vendor identifiers.
- Changes to volume creation, resizing, or deletion semantics unrelated to attachment protection.

## 3. Motivation / Background

Volume records currently contain provisioning state but no attachment relationship. The CSI driver handles controller publish/unpublish by proxying directly to vendor CSI controllers, which gives Kubernetes a working path but leaves fulfillment-service unable to authorize, persist, observe, or protect the relationship. The proxy also returns transient vendor failures to CSI sidecars rather than owning a durable retry state.

OSAC already uses a first-class `ExternalIPAttachment` resource for immutable bindings with pending, ready, failed, and deleting states. A volume attachment follows the same resource pattern, but its target set is limited to OSAC-managed BMaaS and VMaaS compute and its backend operation must honor volume access modes and storage backend capabilities.

## 4. Design

### 4.1 Architecture

`VolumeAttachment` is a public resource generated from private source protos. The fulfillment service is the API, authorization, persistence, and status authority. It validates the volume, target, tenancy, access mode, and uniqueness constraints, persists the request in `PENDING`, and reconciles it to an operator-side attachment intent. For VMaaS, `osac-operator` adds the attachment intent to the ComputeInstance provisioning input; AAP creates the PVC and adds the PVC to the KubeVirt VM definition. The PVC carries `osac.volume.id`, allowing the CSI driver to bind the existing OSAC Volume instead of provisioning a new one. BMaaS uses its operator/AAP compute provisioning path to consume the same attachment intent. A deletion request removes the attachment intent; AAP removes the PVC/VM disk reference, and CSI performs the normal unpublish path where applicable.

The CSI driver remains the CaaS and VMaaS data-plane entry point. For VMaaS it receives a normal PVC/CSI request, detects `metadata.annotations["osac.volume.id"]`, and binds that PVC to the existing OSAC Volume by creating a PersistentVolume with the OSAC volume ID and backend-specific context. It must not call CreateVolume for this path. `ControllerPublishVolume` and `ControllerUnpublishVolume` then use the existing vendor CSI proxy behavior. CaaS continues to use its regular PVC/CSI workflow. Kubernetes sidecar retries remain safe because the PVC/PV and VolumeAttachment relationship are keyed by the OSAC volume ID and target.

```mermaid
sequenceDiagram
    participant Client as gRPC/REST/CLI/UI client
    participant API as fulfillment-service API
    participant DB as PostgreSQL
    participant Operator as osac-operator
    participant AAP as AAP compute provisioning
    participant KubeVirt as KubeVirt VM
    participant CSI as OSAC CSI driver
    participant Vendor as vendor CSI controller

    Client->>API: Create VolumeAttachment
    API->>DB: Persist PENDING relationship
    API-->>Client: Attachment with PENDING status
    API->>Operator: Reconcile attachment intent
    Operator->>AAP: Add PVC + VM disk to provisioning input
    AAP->>KubeVirt: Create/update PVC and VM definition
    KubeVirt->>CSI: Normal PVC/CSI provisioning and publish
    CSI->>Vendor: Create/bind or publish existing OSAC Volume
    Vendor-->>CSI: CSI result
    CSI-->>KubeVirt: PVC/PV and attachment state
    Operator->>API: Feedback status and conditions
    Client->>API: Get/List attachment
    API-->>Client: Current status and message
    CSI->>API: Converge publish/unpublish relationship
    API->>DB: Reuse same relationship state machine
```

The diagram shows that the API request does not directly attach a vendor volume to a VM. It changes the declarative VM provisioning input; AAP and KubeVirt create the PVC/VM relationship, and the existing CSI data path performs the actual storage binding and publish operation.

The operator boundary is an internal attachment-intent reconciler, not a vendor execution RPC. It receives the VolumeAttachment relationship, validates that the target is an existing VMaaS ComputeInstance, and updates the ComputeInstance provisioning input consumed by the existing AAP workflow. It tracks the requested attachment ID and desired PVC/VM disk state in the operator-side intent status, retries AAP reconciliation through the existing provisioning lifecycle, and reports PVC/VM readiness through feedback. Vendor publish/unpublish remains in the existing CSI driver path; no provider Service, mTLS callback, or fulfillment-to-provider network hop is introduced.

Responsibilities:

- **Fulfillment-service:** public API, validation, tenant authorization, persistence, deletion guards, and feedback/status synchronization.
- **OSAC operator:** owns attachment intent, ComputeInstance/AAP input, target cleanup, and feedback status; it does not execute vendor CSI publish calls directly.
- **OSAC CSI driver:** handles the normal PVC/PV/CSI path. It recognizes `osac.volume.id`, binds an existing OSAC Volume without CreateVolume, and preserves vendor routing for publish/unpublish.
- **CLI/UI:** create/delete or attach/detach through the public resource API, display status conditions, and do not expose vendor details.

Lifecycle sequence: create assigns tenant metadata and the Volume owner-reference, persists `PENDING`, and creates the operator attachment intent. The operator adds its finalizer, updates the ComputeInstance provisioning input, and waits for AAP, PVC, KubeVirt, and CSI status. Delete changes the relationship to `DELETING`; the operator removes the PVC/VM disk intent and waits for normal CSI unpublish before removing its finalizer. Target controllers use the same target deletion guard and cleanup handshake. A terminal detach failure retains the operator finalizer and status for recovery.

### 4.1.1 VMaaS Existing-VM Attachment Flow

For an existing VMaaS `ComputeInstance`, the user attaches an already-created OSAC Volume by creating a `VolumeAttachment` whose target is the ComputeInstance. The API does not directly call CSI or mutate a vendor attachment:

1. `fulfillment-service` validates that the Volume is available, the ComputeInstance exists in the same tenant, and the relationship is not already present.
2. The service creates the public `VolumeAttachment` in `PENDING` and creates the operator-side attachment intent. The intent references the Volume ID, ComputeInstance ID, access mode, and desired read-only setting.
3. `osac-operator` reconciles the intent into the ComputeInstance provisioning input. The input contains the existing OSAC Volume ID and a deterministic PVC name/attachment ID, plus an annotation `osac.openshift.io/volume-id: <osac-volume-id>`.
4. AAP's VM provisioning playbook creates the PVC in the VM tenant namespace and adds that PVC to the KubeVirt VM's disk/volume definition. The PVC is not allowed to request dynamic provisioning; it is a claim for the already-existing OSAC Volume.
5. The OSAC CSI driver sees the PVC annotation `osac.volume.id: <osac-volume-id>`. Its CreateVolume path resolves the existing OSAC Volume, creates a PersistentVolume whose CSI source contains the OSAC volume ID and backend-specific volume context, and binds the PV to the PVC without provisioning a new backend volume.
6. KubeVirt causes the normal CSI ControllerPublish/NodeStage/NodePublish sequence. The CSI driver uses the existing backend/vendor routing, including `AlreadyExists`, `NotFound`, `Unimplemented`, and no-attach behavior.
7. Operator feedback observes the PVC, PV, VM disk, and CSI readiness, then updates the operator intent and fulfillment `VolumeAttachment` to `READY` or `FAILED`.

The reverse path removes the PVC reference from the VM provisioning input, lets AAP remove the PVC/VM disk relationship, and waits for normal CSI unpublish before the operator reports detach complete. The OSAC Volume itself is not deleted by attachment removal. Boot-disk and additional-disk attachments use the same flow; the only difference is which VM disk list receives the PVC reference.

The PVC annotation is the bridge between the declarative VMaaS workflow and the existing CSI driver. `osac.volume.id` is authoritative for this pre-existing-volume path; a PVC with that annotation must not invoke fulfillment `CreateVolume`. A missing or invalid annotation follows the existing dynamic-provisioning behavior only for ordinary CaaS PVCs, not for an OSAC attachment intent.

### 4.2 Data Model / Schema Changes

Add a public `VolumeAttachment` resource following `ExternalIPAttachment`. The private source file imports `cleanapi/cleanapi.proto`, `google/api/annotations.proto`, `google/api/field_behavior.proto`, `google/protobuf/field_mask.proto`, `google/protobuf/timestamp.proto`, `buf/validate/validate.proto`, and the existing metadata, condition, Volume, ComputeInstance, and BareMetalInstance reference types. It declares `option (cleanapi.file).package = "osac.public.v1"` and `option (cleanapi.file).http_route_prefix_map = "private:fulfillment"`.

```protobuf
message VolumeAttachment {
  string id = 1;
  Metadata metadata = 2;
  VolumeAttachmentSpec spec = 3;
  VolumeAttachmentStatus status = 4;
}

message VolumeAttachmentSpec {
  option (buf.validate.message).cel = { expression: "has(this.compute_instance) || has(this.baremetal_instance) || has(this.csi_node)" };
  VolumeLocalReference volume = 1 [(google.api.field_behavior) = REQUIRED, (google.api.field_behavior) = IMMUTABLE];
  oneof target {
    ComputeInstanceLocalReference compute_instance = 2 [(google.api.field_behavior) = IMMUTABLE];
    BareMetalInstanceLocalReference baremetal_instance = 3 [(google.api.field_behavior) = IMMUTABLE];
    CsiNodeReference csi_node = 5 [(cleanapi.field).private = true];
  }                                           // exactly one, immutable
  bool readonly = 4 [(google.api.field_behavior) = IMMUTABLE];
}

message VolumeAttachmentStatus {
  VolumeAttachmentState state = 1 [(google.api.field_behavior) = OUTPUT_ONLY];
  optional string message = 2 [(google.api.field_behavior) = OUTPUT_ONLY];
  string volume_id = 3 [(google.api.field_behavior) = OUTPUT_ONLY];
  string target_id = 4 [(google.api.field_behavior) = OUTPUT_ONLY];
  repeated VolumeAttachmentCondition conditions = 5 [(google.api.field_behavior) = OUTPUT_ONLY];
  string hub = 6 [(cleanapi.field).private = true, (google.api.field_behavior) = OUTPUT_ONLY];
  int32 attempt_count = 7 [(google.api.field_behavior) = OUTPUT_ONLY];
  google.protobuf.Timestamp next_attempt_at = 8 [(google.api.field_behavior) = OUTPUT_ONLY];
}
```

Add the following messages and service methods to the private source protos; field numbers are reserved and are not reused. Public fields occupy numbers 1-4 and the private `csi_node` member is last at field 5, preserving CleanAPI field-number compatibility. `volume`, each public target, and `readonly` carry `google.api.field_behavior` annotations for `REQUIRED`/`IMMUTABLE`; `status` fields carry `OUTPUT_ONLY`; IDs use `buf.validate` non-empty constraints; a message-level CEL rule requires exactly one target; and `csi_node` plus `hub` use CleanAPI private annotations. `VolumeAttachmentCondition` imports the shared `condition_status_type.proto` and `google/protobuf/timestamp.proto`.

```protobuf
message VolumeLocalReference { string id = 1 [(buf.validate.field).string.min_len = 1]; }
message CsiNodeReference {
  string cluster_id = 1 [(buf.validate.field).string.min_len = 1];
  string node_id = 2 [(buf.validate.field).string.min_len = 1];
}
enum VolumeAttachmentState {
  VOLUME_ATTACHMENT_STATE_UNSPECIFIED = 0;
  VOLUME_ATTACHMENT_STATE_PENDING = 1;
  VOLUME_ATTACHMENT_STATE_READY = 2;
  VOLUME_ATTACHMENT_STATE_FAILED = 3;
  VOLUME_ATTACHMENT_STATE_DELETING = 4;
}
enum VolumeAttachmentConditionType {
  VOLUME_ATTACHMENT_CONDITION_TYPE_UNSPECIFIED = 0;
  VOLUME_ATTACHMENT_CONDITION_TYPE_ATTACHED = 1;
  VOLUME_ATTACHMENT_CONDITION_TYPE_DETACHED = 2;
  VOLUME_ATTACHMENT_CONDITION_TYPE_RECONCILING = 3;
}
message VolumeAttachmentCondition {
  VolumeAttachmentConditionType type = 1;
  ConditionStatus status = 2;
  string reason = 3;
  string message = 4;
  google.protobuf.Timestamp last_transition_time = 5;
}

message VolumeAttachmentsListRequest { optional int32 offset = 1; optional int32 limit = 2; optional string filter = 3; optional string order = 4; }
message VolumeAttachmentsListResponse { int32 size = 1; int32 total = 2; repeated VolumeAttachment items = 3; }
message VolumeAttachmentsGetRequest { string id = 1; }
message VolumeAttachmentsGetResponse { VolumeAttachment object = 1; }
message VolumeAttachmentsCreateRequest { VolumeAttachment object = 1; }
message VolumeAttachmentsCreateResponse { VolumeAttachment object = 1; }
message VolumeAttachmentsUpdateRequest { VolumeAttachment object = 1; google.protobuf.FieldMask update_mask = 2; bool lock = 3; }
message VolumeAttachmentsUpdateResponse { VolumeAttachment object = 1; }
message VolumeAttachmentsDeleteRequest { string id = 1; }
message VolumeAttachmentsDeleteResponse {}
message VolumeAttachmentsSignalRequest { option (cleanapi.message).private = true; string id = 1; }
message VolumeAttachmentsSignalResponse { option (cleanapi.message).private = true; }

service VolumeAttachments {
  rpc List(VolumeAttachmentsListRequest) returns (VolumeAttachmentsListResponse) { option (google.api.http) = { get: "/api/fulfillment/v1/volume_attachments" }; }
  rpc Get(VolumeAttachmentsGetRequest) returns (VolumeAttachmentsGetResponse) { option (google.api.http) = { get: "/api/fulfillment/v1/volume_attachments/{id}" response_body: "object" }; }
  rpc Create(VolumeAttachmentsCreateRequest) returns (VolumeAttachmentsCreateResponse) { option (google.api.http) = { post: "/api/fulfillment/v1/volume_attachments" body: "object" response_body: "object" }; }
  rpc Update(VolumeAttachmentsUpdateRequest) returns (VolumeAttachmentsUpdateResponse) { option (google.api.http) = { patch: "/api/fulfillment/v1/volume_attachments/{object.id}" body: "object" response_body: "object" }; }
  rpc Delete(VolumeAttachmentsDeleteRequest) returns (VolumeAttachmentsDeleteResponse) { option (google.api.http) = { delete: "/api/fulfillment/v1/volume_attachments/{id}" }; }
  rpc Signal(VolumeAttachmentsSignalRequest) returns (VolumeAttachmentsSignalResponse) { option (cleanapi.method).private = true; }
}
```

The operator adds a Kubernetes `VolumeAttachment` CRD (in its own API package), not a fulfillment protobuf:

```text
VolumeAttachmentSpec: volumeID, tenant, targetKind, targetID, readonly
VolumeAttachmentStatus: state, message, operationToken, claimGeneration,
  attemptCount, nextAttemptAt, vendorVolumeID, conditions
```

The CRD carries `osac.openshift.io/tenant` and `osac.openshift.io/owner-reference` metadata, uses the `osac.openshift.io/volume-attachment` finalizer, and is reconciled only by `osac-operator`.

The generated public schema contains `VolumeAttachment`, `VolumeAttachmentSpec` with `compute_instance`, `baremetal_instance`, and `readonly`, and all output fields. The private source marks `csi_node` and `hub` with `[(cleanapi.field).private = true]`; the operator-side Attachment CR and execution status are Kubernetes/operator implementation types and are not part of the public fulfillment API. `UpdateRequest.lock` remains public because it is the standard optimistic-lock field used by public OSAC resources. Every status field carries `(google.api.field_behavior) = OUTPUT_ONLY`. CI runs `uv run dev.py lint proto` and `uv run dev.py build protos` to verify public generation, field numbering, HTTP annotations, and generated Go clients.

`VolumeLocalReference` requires a stable Volume ID. `ComputeInstanceLocalReference` and `BareMetalInstanceLocalReference` resolve by ID; CLI name flags are resolved client-side to IDs before the API request, so the server never rewrites immutable `spec`. `CsiNodeReference` requires both an authorized CaaS cluster ID and non-empty node ID and is marked private with CleanAPI. The resource is immutable after creation; changing a target requires deleting an attachment and creating another one. `readonly` must be compatible with the CSI capability and volume access mode. Conditions use the shared `ConditionStatus` enum (`UNSPECIFIED`, `TRUE`, `FALSE`); top-level state remains the compatibility summary used by existing clients.

Add an attachment persistence table and active-relationship helper table using the existing numbered migration convention. The helper stores `(attachment_id, tenant, volume_id, target_kind, target_id, state)` and has a partial unique index for non-deleted relationships on `(volume_id, target_kind, target_id)`. Operator execution state, operation token, claim generation, retry schedule, and vendor result live in the operator Attachment CR status; fulfillment-service stores only the public resource status synchronized by feedback. All database transactions use the same lock order: Volume row, then target mirror row, then helper rows. Create attachment and delete Volume transactions reject objects with a deletion timestamp, then insert/check the helper row or return custom `volume_in_use` SQLSTATE mapped to `FailedPrecondition`.

Target deletion uses an explicit two-phase handshake because fulfillment PostgreSQL and Kubernetes cannot share a transaction. The target controller registers its finalizer when the target is created, and the rollout migration backfills it for existing targets. During deletion reconciliation it calls private `BeginTargetDeletion(target_kind, target_id)`, which briefly locks the target mirror row, marks it deleting, and commits a deletion guard before releasing the row lock. Attachment creation always locks the Volume first, then the target mirror row, and observes the committed guard; worker reconciliation uses the same Volume-then-target order. `BeginTargetDeletion` never holds a target lock while waiting on a Volume or helper row, so no reverse lock order exists. The target controller then calls `ListByTarget`; each relationship is moved to `DELETING` and detached. It removes the already-present target finalizer only after fulfillment-service returns `TargetAttachmentsGone`. A target delete request that cannot acquire the guard remains pending; attachment creation cannot race past it.

The target finalizer key is `osac.openshift.io/volume-attachment`. The rollout backfill Job upserts a target-mirror row and patches this finalizer only for existing ComputeInstance and BareMetalInstance objects without a deletion timestamp, recording a migration epoch and per-target result. It is idempotent and retries conflicts. A target already marked for deletion is quarantined in the mirror table instead of being patched: new attachment creation is rejected for that target, existing relationships are moved to `DELETING` and drained immediately, and the mirror retains the target ID until `TargetAttachmentsGone`. The feature gate remains disabled until every non-deleting target has the finalizer and every quarantined target has no active relationship. This avoids adding a finalizer after Kubernetes deletion has started.

Volume status gains an output-only attachment summary only if list/get performance requires it; the attachment resource remains authoritative. No vendor volume ID, backend credential, or raw CSI secret is exposed through the public attachment resource.

### 4.3 API Changes

Add `VolumeAttachments` using the standard OSAC resource service pattern. The private source service uses standard request/response messages and CleanAPI generates the public service; `Signal` remains private and is used only for feedback-driven reconciliation:

| RPC | Public REST route | Behavior |
|---|---|---|
| `List` | `GET /api/fulfillment/v1/volume_attachments` | Lists authorized attachments; supports filter/order. |
| `Get` | `GET /api/fulfillment/v1/volume_attachments/{id}` | Returns desired target and observed lifecycle state. |
| `Create` | `POST /api/fulfillment/v1/volume_attachments` | Requests attach; returns `PENDING` or an already-satisfied `READY` object. |
| `Update` | `PATCH /api/fulfillment/v1/volume_attachments/{object.id}` | Metadata-only update; immutable spec fields are rejected. |
| `Delete` | `DELETE /api/fulfillment/v1/volume_attachments/{id}` | Requests detach; resource remains until detach completes. |

The public Volume API prerequisite `osac#743` must be available first. The private service also includes `Signal` for controller feedback, following existing attachment resources.

The private service adds these concrete controller messages and RPCs:

```protobuf
message TargetReference { string kind = 1; string id = 2; }
message BeginTargetDeletionRequest { TargetReference target = 1; }
message BeginTargetDeletionResponse { bool guard_acquired = 1; }
message ListByTargetRequest { TargetReference target = 1; }
message ListByTargetResponse { repeated string attachment_ids = 1; }
message TargetAttachmentsGoneRequest { TargetReference target = 1; }
message TargetAttachmentsGoneResponse { bool gone = 1; }
service VolumeAttachmentController {
  rpc BeginTargetDeletion(BeginTargetDeletionRequest) returns (BeginTargetDeletionResponse) { option (cleanapi.method).private = true; }
  rpc ListByTarget(ListByTargetRequest) returns (ListByTargetResponse) { option (cleanapi.method).private = true; }
  rpc TargetAttachmentsGone(TargetAttachmentsGoneRequest) returns (TargetAttachmentsGoneResponse) { option (cleanapi.method).private = true; }
}
```

They are private and are called by ComputeInstance and BareMetalInstance controllers during their finalizer workflow. `BeginTargetDeletion` acquires the target deletion guard; `ListByTarget` returns active relationship IDs; `TargetAttachmentsGone` succeeds only when the helper table has no relationship for the target.

Validation rules:

- `volume` is required and must resolve to an existing, non-deleted Volume in a usable state.
- Exactly one target oneof member is required; arbitrary node/backend strings are rejected.
- The referenced target must be an OSAC-managed BMaaS or VMaaS resource visible to the caller.
- The attachment is rejected if the volume access mode and backend capability do not permit the requested concurrent relationship.
- An existing active relationship for the same volume and target converges to idempotent success.
- Concurrent creates for the same `(volume, target, readonly)` lock the Volume row, retry a unique-index conflict by reading the winner, and return that existing object. A concurrent request with a different `readonly` value returns `AlreadyExists` with the existing attachment ID and does not change the desired state.
- A duplicate relationship to a different target is accepted only for supported multi-attachment modes/backend capabilities.
- Delete is idempotent when the relationship is already absent or fully detached.
- Client deadlines apply to the request; a deadline does not cancel durable reconciliation. The response or subsequent Get reports `PENDING`, `READY`, or `FAILED`.

Example:

```json
POST /api/fulfillment/v1/volume_attachments
{
  "object": {
    "metadata": {"name": "database-disk-vm1"},
    "spec": {
      "volume": {"id": "vol-123"},
      "compute_instance": {"id": "ci-456"},
      "readonly": false
    }
  }
}
```

The response contains the attachment ID and `status.state: PENDING` until the backend confirms attachment. A repeated request for the same logical relationship returns the existing object rather than creating duplicate work.

CLI adds public commands equivalent to `osac volume-attachment create`, `get`, `list`, and `delete`; command help follows the existing Markdown help conventions. UI adds attach/detach actions to authorized Volume and ComputeInstance views, shows `PENDING`, `READY`, `FAILED`, and `DELETING`, and disables destructive actions while attachment state makes them unsafe.

### 4.4 Scalability and Performance

Attachment reconciliation is bounded by the number of active relationships and backend operation time. API writes add one resource row and one status update per state transition. List queries require indexes on tenant, volume, target, and state. The unique relationship index makes idempotency an indexed lookup rather than a full scan.

The worker uses bounded concurrency and exponential backoff. It must not create an unbounded goroutine per request. Backend calls use the caller deadline for the initial request and controller-owned deadlines for later retries. The design assumes attachment cardinality is proportional to managed volumes and compute targets, not an unbounded event stream.

### 4.5 Security Considerations

Authentication remains in the existing gRPC interceptor chain. OPA rules authorize VolumeAttachment operations using the attachment tenant and referenced Volume/target tenants. Tenant users and tenant administrators may access only relationships within their tenant. Provider administrators may operate on resources in multiple tenants only through separately authorized same-tenant requests; no role can create a cross-tenant Volume-to-target relationship.

The server resolves references under authorization before creating the relationship, preventing an unauthorized caller from using an attachment as an existence oracle. Target IDs are validated against OSAC resource types, and vendor IDs, CSI secrets, backend endpoints, and raw node credentials remain private. CSI service identities receive only the internal permissions required to converge relationships for authorized tenant-scoped Volume resources.

### 4.6 Failure Handling and Recovery

| Failure | Control-plane behavior | User-visible result |
|---|---|---|
| Invalid volume or target | Reject before persistence with `InvalidArgument` or `NotFound`. | Request fails with named validation error. |
| Cross-tenant reference | OPA/interceptor rejects access. | `PermissionDenied`; no relationship is created. |
| Unsupported access/backend combination | Validate before dispatch. | `FailedPrecondition`; no backend call. |
| Backend transient failure | Keep relationship `PENDING`, record message, and retry at 1s, 2s, 4s, then exponential backoff capped at 5m for eight attempts. Persist `next_attempt_at` and attempt count. | `PENDING` status and progress message. |
| Backend terminal attach failure or exhausted retry budget | Set `FAILED`, retain diagnostic message, and stop automatic retries. An authorized provider/operator identity may call the private `Signal` RPC, which resets the retry schedule without changing `spec`. | `FAILED`; no false `READY` state. |
| Request deadline or lost AAP/CSI response | Leave durable relationship pending; operator reconciliation resumes from the Attachment CR status. Existing CSI `AlreadyExists`/`NotFound` handling converts ambiguous vendor state to one effective relationship. | Deadline error for the request; state remains observable and retry-safe. |
| Backend reports already attached | Treat as successful if it matches the requested volume/target relationship. | `READY`, no duplicate effect. |
| Backend reports already detached/not found | Treat as successful during detach. | Attachment deletion completes. |
| Node-local/no-attach backend | Mark operation successful without vendor controller call. | `READY` or completed delete. |
| Target deletion | The target delete transaction locks the target row, marks it deleting, and blocks new attachment inserts. Its finalizer requests detach for every helper row and is removed only after all relationships are gone. | Attachments enter `DELETING`; target cleanup does not leave stale active relationships. |
| Volume deletion while attached | The Volume delete transaction locks the Volume row and returns `FailedPrecondition` with SQLSTATE `volume_in_use` when any helper row exists. | Volume remains present until all attachments detach. |
| Controller restart | Reconcile persisted `PENDING`, `FAILED`, and `DELETING` relationships. | Progress resumes without client recreation. |

No force-detach path is provided. Terminal detach failure remains visible for operator recovery and the attachment finalizer prevents the relationship from disappearing while backend state is uncertain.

### 4.7 RBAC / Tenancy

`VolumeAttachment` is tenant-scoped and uses the same tenant metadata and owner-reference conventions as other tenant resources. The service assigns `metadata.annotations["osac.openshift.io/tenant"]` to the resolved tenant ID and `metadata.annotations["osac.openshift.io/owner-reference"]` to the parent Volume ID; callers cannot override either value. The Volume is the logical owner because the attachment protects its deletion, while target controllers discover attachments by indexed target reference for cleanup. Local references never accept a caller-supplied tenant ID. The Volume and target must belong to the same tenant; a cross-tenant relationship is rejected even for a provider administrator. Provider administrators operate across tenant environments by making separately authorized requests within each tenant, not by creating cross-tenant relationships. Names are resolved only within the caller's authorized tenant scope, so identical names in different tenants cannot collide.

The API adds create/get/list/update/delete permissions for tenant roles and corresponding provider-admin permissions. CSI identities use a dedicated internal policy path and cannot use public provider-admin authority. Attachment deletion and volume deletion checks execute inside the same authorization and persistence boundary to avoid a time-of-check/time-of-use gap.

The fulfillment-service controller creates/updates the operator Attachment CR and receives status through the existing operator feedback controller. The operator reconciler invokes `AttachmentExecutor` for BMaaS, VMaaS, and private `csi_node` targets. The executor resolves the StorageBackend, translates the request to the vendor CSI controller, and returns status to the reconciler; the CSI driver does not host a second attachment service.

### 4.8 Extensibility / Future-Proofing

The target oneof permits additional OSAC-managed compute target types without changing the relationship or retry model. The status state machine can carry conditions and backend-neutral messages without exposing vendor data. Keeping the public object declarative allows future watch/event interfaces and alternative backend workers without changing client intent semantics. CaaS remains an adapter rather than a second public attachment model.

## 5. Interface Changes

### IC-1: Public VolumeAttachment resource API

**Requirements:** FR-1, FR-2, FR-4, FR-5, FR-6, FR-7, FR-9, NFR-1

Add public gRPC and REST List/Get/Create/Update/Delete operations with typed Volume, ComputeInstance, and BareMetalInstance references; see sections 4.2 and 4.3.

### IC-2: Attachment lifecycle status

**Requirements:** FR-4, FR-5, FR-7, FR-9, FR-10

Expose `PENDING`, `READY`, `FAILED`, and `DELETING` state plus observable messages through Get/List and generated client types; see sections 4.2 and 4.6.

### IC-3: CLI volume-attachment commands

**Requirements:** FR-1, FR-4, FR-5, FR-9, FR-10

Add public `osac volume-attachment create|get|list|delete` commands that use the resource API and render lifecycle state; see section 4.3.

### IC-4: UI attach/detach behavior

**Requirements:** FR-1, FR-4, FR-5, FR-9, FR-10

Add authorized Volume and ComputeInstance attach/detach actions and status rendering; see section 4.3. UI field alignment requires validation against `osac-ui` and `osac-ux` when those repositories are available.

### IC-5: CSI publish/unpublish adapter

**Requirements:** FR-3, FR-5, FR-7, FR-8, FR-10

Change the OSAC CSI driver to recognize `osac.volume.id` on VMaaS PVCs, create/bind a PersistentVolume for the pre-existing OSAC Volume without invoking fulfillment CreateVolume, and preserve normal ControllerPublish/ControllerUnpublish, legacy volume-context/vendor-ID routing, and no-op backend behavior where applicable; see sections 4.1.1, 4.2, and 4.6.

### IC-6: Lifecycle deletion protection

**Requirements:** FR-9, FR-10

Change Volume and compute-target deletion behavior to block unsafe volume deletion and initiate attachment cleanup; see sections 4.2 and 4.6.

### IC-7: Authorization and operator recovery documentation

**Requirements:** FR-10, NFR-1, NFR-2

Document gRPC, REST, CLI, UI, progress, error, authorization, migration, and terminal detach recovery semantics; see sections 4.5 through 4.7.

## 6. Alternatives (Not Implemented)

### First-class VolumeAttachment resource (selected)

- **Pros:** Matches `ExternalIPAttachment`, supports durable status and retries, makes deletion protection and target cleanup explicit, and works for BMaaS/VMaaS as well as CSI adapters.
- **Cons:** Adds a resource, controller, persistence, API surface, and migration logic.
- **Reason selected:** The PRD requires observable asynchronous lifecycle and a design-defined object model; the existing OSAC attachment pattern provides the closest implementation boundary.

### Action-only Attach/Detach RPCs

- **Pros:** Smaller initial API surface and direct correspondence to user actions.
- **Cons:** Does not naturally persist desired state, list relationships, recover after restart, protect deletion, or represent a deadline-exceeded operation.
- **Reason rejected:** Fails the durable progress, lifecycle safety, and retry requirements without recreating a resource model behind the RPC.

### Kubernetes VolumeAttachment as the public source of truth

- **Pros:** Existing CaaS controllers already understand Kubernetes attachment semantics and CSI retries.
- **Cons:** Does not represent BMaaS/VMaaS targets, couples public OSAC tenancy to cluster internals, and cannot protect fulfillment Volume deletion across all compute services.
- **Reason rejected:** CaaS is only one delivery path; direct OSAC compute targets require a control-plane relationship.

### Continue direct vendor CSI proxying

- **Pros:** Lowest immediate code change and preserves current CSI routing.
- **Cons:** No public OSAC lifecycle, durable status, control-plane authorization, target cleanup, or volume deletion guard.
- **Reason rejected:** It is the temporary OSAC-4187 path and does not satisfy the feature requirements.

## 7. Observability and Monitoring

- Emit structured attachment transition events containing attachment ID, volume ID, target kind/ID, state, attempt number, and error class; never log CSI secrets or vendor credentials.
- Add counters for attach attempts, detach attempts, successful transitions, terminal failures, transient retries, idempotent convergences, and no-op operations.
- Add gauges for pending and deleting attachment counts and a histogram for backend operation duration.
- Emit Kubernetes events or equivalent operator events when an attachment enters `FAILED` or remains `DELETING` beyond the configured recovery threshold.
- Expose attachment state and last error through the existing resource status and logs so operators can recover terminal detach failures without backend-specific user access.

## Risks and Mitigations

| Risk | Mitigation |
|---|---|
| A CSI publish succeeds before the API response and the client retries. | Use the immutable `(volume, target)` relationship key and treat backend already-attached responses as idempotent success. |
| Target deletion races with attachment creation. | Resolve target state under transaction, index attachments by target, and have the target controller block finalizer removal until attachment cleanup completes. |
| A backend worker loses connectivity while an attachment is pending. | Persist `PENDING`, use bounded exponential backoff, expose retry counters, and resume reconciliation after restart. |
| Migration creates a duplicate or detaches an existing CSI relationship. | Preserve legacy volume context/vendor IDs, adopt on first CSI operation, and never delete an unknown existing attachment solely because its control-plane row is absent. |
| A public status exposes backend implementation details. | Return only backend-neutral state, reason, and message; keep vendor IDs, endpoints, and secrets private. |

Security review is owned by fulfillment-service authorization maintainers and OSAC platform security reviewers; storage and CSI maintainers review provider and migration behavior.

## 8. Impact and Compatibility

The public API addition is backward-compatible for existing clients. The database migration is additive. Existing Volumes require no recreation and gain attachment protection once the new service is deployed.

CSI migration uses an explicit feature-negotiation matrix and never silently falls back after a durable relationship has been recorded:

| Fulfillment service | CSI driver | Behavior |
|---|---|---|
| Old | Old | Legacy direct vendor publish/unpublish remains active. |
| New, attachment feature disabled | Old | Legacy direct vendor publish/unpublish remains active. |
| New, attachment feature enabled | Old | Legacy path remains active until the operator migration gate verifies vendor inventory; the service does not create new-path records from old CSI calls. |
| New, attachment feature enabled | New | New CSI calls create/converge the private `csi_node` relationship; the operator executes vendor CSI operations. Legacy calls are rejected with `FailedPrecondition` if the private relationship API is unavailable rather than being silently routed outside durable state. |
| Old | New | New CSI readiness fails because the required private API capability is absent; no publish/unpublish operation is accepted. |

Before enabling the new path, an operator migration Job uses the extracted vendor CSI routing package to inventory published nodes through the vendor `LIST_VOLUMES_PUBLISHED_NODES` capability. It writes results to an operator-owned staging table with a migration epoch, snapshot token, cursor, and page checksums. A vendor without that CSI capability is not eligible for the new feature gate. The Job promotes stable results to private `csi_node` Attachment CRs and fulfillment helper rows only after every configured backend inventory succeeds. A restarted Job resumes its epoch while the vendor snapshot token remains valid; if the token or checksum changes, it aborts the epoch, deletes staged rows, and starts a new one. No partial relationship set is visible. Rollback disables the new path, leaves adopted Attachment CRs intact, and permits the old CSI path only after the operator confirms no new-path reconcile is pending for that target.

The staging table is `(migration_epoch, backend, snapshot_token, cursor, page_checksum, rows_json, state)` with a unique `(migration_epoch, backend, cursor)` key. Epoch states are `RUNNING`, `STABLE`, `PROMOTED`, and `ABORTED`; promotion changes all backend rows from `STABLE` to `PROMOTED` in one transaction, while any checksum or backend failure changes the epoch to `ABORTED` and deletes its staged rows. The operator feature gate stores the promoted epoch and rejects Attachment CR reconciles from older epochs. Rollback first changes the gate to `DRAINING`, waits for operator reconciles to reach a terminal result, then enables `LEGACY`; it cannot enable legacy mode while an Attachment CR is pending.

Downgrade must leave existing attachment records intact and retain the legacy CSI proxy fallback. Operators must not delete attachment rows as part of rollback; unresolved relationships remain visible for the next upgraded controller.

## UX Alignment

The `osac-ui` and `osac-ux` checkouts are not present in this workspace, so no matching `@temp-api` TypeScript definition could be inspected. The backend contract uses the existing OSAC resource shape and snake_case proto fields. Before implementation, the UI team must map `spec.volume`, `spec.compute_instance`/`spec.baremetal_instance`, `status.state`, `status.message`, and `status.conditions` to the generated UI types; no backend field should be renamed to match a UI-only convention.

## 9. Open Questions

### 9.1 UI repository alignment

**Question:** Which `osac-ui` and `osac-ux` revisions define the attach/detach UI placement and generated API field names?

**Owner:** OSAC UI maintainers

**Impact:** Determines the concrete UI component and UX Alignment mapping for IC-4; the backend contract remains as specified in section 4.3.

## Test Plan

Detailed behavioral coverage is in [testplan.md](testplan.md). It covers every normalized PRD requirement and every interface change.

### Unit Tests

- Validate typed references, immutable specs, access-mode/backend capability checks, duplicate relationship convergence, no-op backends, and state transitions.
- Test authorization decisions, tenant filtering, deletion guards, finalizer behavior, transient retry classification, deadline handling, and terminal failures.
- Test CSI adapter mapping, legacy fallback, vendor AlreadyExists/NotFound behavior, and controller restart reconciliation.

### Integration Tests

- Exercise API/database/controller lifecycle with a fake backend: create, pending, retry, ready, delete, deleting, and failed states.
- Verify volume deletion is blocked while attached and target deletion initiates cleanup.
- Verify public REST/gRPC and CLI behavior, generated API compatibility, and OPA tenant/provider authorization.

### E2E Tests

- Add the backend-neutral representative flow to `osac/tests/e2e/storage/test_volume_attachment_lifecycle.py`, using the existing storage fixtures and polling helpers.
- Cover retry after transient backend failure, invalid target, cross-tenant denial, terminal backend failure, and CSI migration without recreating an existing volume.

## Graduation Criteria

- Public gRPC, REST, CLI, and UI contracts are implemented and documented.
- BMaaS and VMaaS direct attachment and CaaS CSI adapter flows pass required automated coverage.
- Existing CSI volumes continue operating through upgrade and the attachment lifecycle survives service/driver restarts.
- No-force-detach recovery is documented and observable through status, events, metrics, and logs.
- Helm values, operator Attachment CRDs/RBAC, shared vendor-routing configuration, migrations, metrics, and installer sequencing are validated in the supported installation path.
- `osac-ui` and `osac-ux` are available and the generated UI field mapping is reviewed before UI acceptance.
- The OSAC 0.3 release acceptance suite passes, including the representative E2E and all specified negative scenarios.

## Upgrade / Downgrade Strategy

Upgrade uses additive schema/API deployment first, then controller/worker deployment, then CSI adapter rollout. New clients are enabled only after the service and worker support the attachment resource. Existing CSI attachments remain on legacy routing until adopted; no automatic detach is performed solely due to migration.

Rollback keeps the additive schema and attachment records. The CSI driver falls back to legacy vendor routing when the attachment API is unavailable, while operators resolve any pending relationships after the service is restored. Volume deletion remains conservative whenever an active attachment record exists.

## Version Skew Strategy

The service supports old CSI clients sending standard publish/unpublish calls during a rolling update. The new CSI driver requires the private attachment API capability during readiness and does not invoke vendor publish/unpublish when the capability is unavailable. The new API is not enabled for user-facing direct operations until `osac#743`, generated public clients, operator Attachment CRDs/RBAC, shared vendor-routing code, and the operator inventory migration gate are deployed.

## Support Procedures

- Inspect `VolumeAttachment.status.state`, `status.message`, structured transition logs, retry counters, pending/deleting gauges, and backend operation duration.
- For `FAILED` attach, correct the target/backend condition and signal or retry reconciliation; do not manually mutate status.
- For `DELETING`, verify backend attachment state and target availability. The resource remains protected until detach is confirmed; no force-detach API is available.
- If the attachment controller is unavailable, existing workloads continue using already-attached volumes, while new transitions remain pending and visible.
- Disablement must stop new attachment requests and leave existing relationships/status records intact. Re-enabling the controller resumes reconciliation without recreating volumes.

## Infrastructure Needed

Implementation uses the existing fulfillment-service, osac-operator, osac-csi-driver, osac-installer, and workspace E2E infrastructure. It adds a fulfillment-service attachment migration, operator Attachment CRDs/controllers/RBAC, shared vendor-routing code extracted from `osac-csi-driver/pkg/proxy`, operator feature-gate configuration, attachment metrics, and Helm values. `osac-installer` must deploy these in dependency order: database migration, fulfillment API, operator CRDs/RBAC, operator/CSI rollout, operator inventory migration, then feature enablement. No provider Service, mTLS callback, or CSI-side provider endpoint is required. The `osac-ui` and `osac-ux` checkouts must be available for UI implementation and UX type alignment.
