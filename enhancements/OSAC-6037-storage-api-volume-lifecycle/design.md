# Storage API Integration for ComputeInstance Volume Lifecycle

| Field | Value |
|-------|-------|
| Author(s) | Tzif |
| Jira | [OSAC-6037](https://redhat.atlassian.net/browse/OSAC-6037) |
| Design task | [OSAC-6040](https://redhat.atlassian.net/browse/OSAC-6040) |
| PRD | [prd.md](prd.md) |
| Date | 2026-10-14 |
| Status | Draft for review; runtime compatibility is unverified |

# 1. Overview

For OSAC 0.4, VM boot and additional disks use StorageClasses served by OSAC CSI. Kubernetes selects placement, external-provisioner invokes CSI CreateVolume, and OSAC CSI calls the private Storage API. The existing Volume reconciler/operator provisions the backend. CDI continues importing the boot image and preparing blank additional disks. This reuses the existing creation chain and adds ComputeInstance ownership of correlation and cleanup. [User: draft the approach that reuses dynamic OSAC CSI provisioning]

The [PRD](prd.md) requires a Storage API Volume for every required disk, deletion through that API, and IDs in ComputeInstance status/UI. This design owns backend lifecycle and the status/API contract. UI presentation, implementation and testing belong to a separate design and work; the feature-level UI requirement remains applicable. [User: UI is separate design and work] Fulfillment records each allocation atomically with Volume creation and rejects new allocations after parent deletion begins. The proposed lifecycle applies to newly created managed ComputeInstances; existing disks are never silently adopted or replaced. The deletion-policy ambiguity is retained in Section 9.1. Source baseline: `d30e35d27bcda4d55097323f5bc3ccb313a4c390`; [pinned PRD](https://github.com/osac-project/enhancement-proposals/blob/3da4e31a12a626f0571a42f076c89333c11a3e01/enhancements/OSAC-6037-storage-api-volume-lifecycle/prd.md). The relative PRD link resolves when published alongside the PRD.

# 2. Goals and Non-Goals

## 2.1 Goals

- Reuse Kubernetes scheduling, external-provisioner, OSAC CSI, CDI and the existing Volume provider boundary.
- Establish one durable allocation identity per immutable ComputeInstance disk before backend provisioning can begin.
- Pin managed Volumes to the ComputeInstance hub and preserve scheduler-selected local-storage topology.
- Complete cleanup through retriable reconciliation with authoritative evidence and a retained parent finalizer.
- Preserve tenant/project attribution and one-way public ComputeInstance-to-Volume correlation.

## 2.2 Non-Goals

- UI changes and UI tests, including VM console presentation and Enclave Wizard behavior; these belong to separate design and work. This design supplies the API and installer-schema contracts they consume. [User]
- No separate attach/detach API or independent attachment-status model; OSAC-4884 remains separate.
- No public Volume-to-ComputeInstance reverse link, disk sharing, snapshots/backups, or attached-volume resize/migration.
- No legacy disk adoption, disk replacement or in-place upgrade mechanism.
- No general-purpose storage scheduler or new vendor provisioning layer.

# 3. Motivation / Background

Current AAP VM provisioning creates DataVolumes using per-tier StorageClasses. LVMS and VAST roles select vendor CSI provisioners; that path does not create OSAC Volume records. OSAC CSI already calls private Volume Create, polls availability and returns the OSAC Volume ID as the CSI handle, but current VM wiring does not select that path. Hub CSI installation exists as an optional installer dependency. [Codebase: `osac-aap/.../ocp_virt_vm/tasks/create_resources.yaml`; `osac-csi-driver/pkg/driver/controller.go`; `osac-installer/charts/osac/Chart.yaml`]

In delayed dynamic provisioning, node selection precedes CSI Create and PV creation. OSAC CSI already forwards the first preferred topology into the Storage API. A pre-bound PVC with `volumeName` does not enter the same scheduler path, making static PV projection a larger placement change. [Research: Section Placement and Deployment Findings, P7–P8]

Two existing behaviors require changes: Volume reconciliation selects its hub independently, and CSI Delete returns while backend cleanup is asynchronous. Discovering IDs only after a PV appears also misses a successful API create whose response or subsequent PV creation is lost. [Research: P2, D2–D6]

# 4. Design

## 4.1 Architecture

### Creation and responsibilities

```mermaid
sequenceDiagram
    participant VM as Compute lifecycle / AAP
    participant K8s as CDI / scheduler / provisioner
    participant CSI as OSAC CSI
    participant API as Private Storage API / database
    participant Vol as Volume reconciler / operator
    VM->>K8s: Create managed DataVolume and VM
    K8s->>K8s: Create PVC and select node
    K8s->>CSI: CreateVolume with claim metadata and topology
    CSI->>API: Create with managed disk context
    API->>API: Lock parent; persist Volume, allocation and public ID
    API-->>CSI: Volume ID, CREATING
    Vol->>Vol: Provision backend on pinned hub/node
    CSI->>API: Poll Volume availability
    CSI-->>K8s: CSI handle = OSAC Volume ID
    K8s->>K8s: Bind PV, import disk, start VM
```

The sidecar initiates CSI Create after placement; AAP initiates the flow by declaring Kubernetes objects. The database transaction establishes identity before the asynchronous backend action. Storage availability, image population and VM readiness remain separate boundaries. The diagram omits existing feedback/watch messages for readability. [Research: H7–H8, P7; PRD: In Scope, creation bullet]

| Component | Responsibility in this proposal |
|-----------|----------------------------------|
| Fulfillment ComputeInstance server/reconciler | Mark new instances as managed; serialize create/delete races; own allocation records and public disk IDs; coordinate final cleanup. |
| Operator ComputeInstance controller/feedback | Pass managed disk context to AAP; report workload cleanup acknowledgement; preserve fulfillment-owned IDs; guard Ready against unresolved required storage. |
| AAP | Select dedicated managed VM StorageClasses; create annotated DataVolumes; stop VM/VMI and delete DataVolumes/PVCs on parent deletion. |
| OSAC CSI controller | Resolve and validate the requesting claim's managed context; call private Create using the selected topology; reuse backend translation and polling. |
| Volume reconciler/operator | Honor the pinned hub; preserve provider operation identity; establish backend deletion completion. |
| Installer | Deploy required driver/configuration and publish matching values/schema contracts. |

### Workload objects and placement

Managed VM StorageClasses use `csi.osac.openshift.io`, `WaitForFirstConsumer`, `Retain`, the resolved tier, explicit tenant/project, and `osac.managed-compute: "true"`. AAP resolves a distinct managed class for each required tier; it never falls back to a vendor class for a managed instance. Existing vendor installation/setup remains available for OSAC CSI's provider routes. VM JIT class creation is changed alongside tenant class resolution so it cannot recreate a vendor class under the managed name. Use deterministic names derived from tenant, project and tier IDs with truncation/hash handling within Kubernetes name limits. [Codebase: `osac-aap/playbook_osac_create_compute_instance.yml`; tenant storage resolution; Research: P4–P5]

Each managed DataVolume carries the existing tenant/owner annotations plus proposed `osac.openshift.io/compute-instance-id`, `osac.openshift.io/disk-key`, and `osac.openshift.io/storage-lifecycle: managed-v1`. Disk keys are `boot` and `disk-1` … `disk-N`, matching the immutable additional-disk order. AAP obtains these values from controller-owned inputs. Preserve the root DataVolume's existing non-apply creation behavior.

For the first implementation, set `cdi.kubevirt.io/storage.usePopulator: "false"` on these DataVolumes. This selects CDI's direct importer path while the PVC remains dynamically provisioned by CSI. It keeps a single target claim per disk for correlation and avoids introducing temporary-population-claim traversal into the initial contract. Registry and blank sources remain unchanged. The supported runtime matrix must demonstrate this path; it is not claimed as already validated. [Research: H3–H6, P6; Section 9.2]

The CSI resolver uses sidecar parameters `csi.storage.k8s.io/pvc/name` and `csi.storage.k8s.io/pvc/namespace`, fetches the current PVC, and follows its UID-qualified DataVolume owner reference. It verifies the managed annotations, expected `<compute-resource-name>-root-disk` / `-disk-N` name, tenant namespace/project, and owning ComputeInstance CR. The authoritative CR must match the fulfillment ID and managed lifecycle marker; labels alone are insufficient. The API independently checks the parent, disk spec and tenant/project. Unexpected owners, temporary claims or missing metadata fail without falling back to standalone creation. [Research: H7; Codebase: CSI chart enables `--extra-create-metadata`]

Resolver failures return `INVALID_ARGUMENT` for malformed/missing request metadata, `FAILED_PRECONDITION` for a stale or unsupported owner chain, and `PERMISSION_DENIED` for unauthorized tenant context. These failures occur before private Create is called.

Reuse `controller.clusterID` as the canonical registered Hub ID for the shared VM CSI installation. The managed request includes that ID; private Create requires it to equal the ComputeInstance's persisted hub. It stamps Volume `status.hub` from the parent before commit. Managed Volume reconciliation refuses a missing hub instead of selecting another. For LVMS, `osac.io/node` remains mandatory and comes from scheduler topology. Returning an existing allocation uses its stored topology, never a new request's node. An incompatible later topology produces `FAILED_PRECONDITION` and retains the existing allocation for cleanup; it does not allocate another disk. [Research: P2, P7; Codebase: `volume_reconciler_function.go:selectHub`]

### Deletion ordering

1. ComputeInstance Delete locks the same parent row used by managed Create, persists deletion intent and retains the managed-storage finalizer. Every subsequent managed Create is rejected, including retries for an existing slot.
2. The operator/AAP halts the VM, waits for VMI absence, deletes the VM/DataVolumes/PVCs, and reports a private workload-cleanup acknowledgement tied to the current ComputeInstance CR UID. Errors retain workflow finalizers. Fulfillment persists this acknowledgement before the CR disappears; CR absence alone is not the acknowledgement.
3. Managed PVs remain under Retain. The operator storage-cleanup helper verifies the recorded PVC UIDs are gone, no consuming pods remain and matching VolumeAttachments are absent. It then reports the workload references released. API failure or an unpublish operation still in progress is not release evidence. The acknowledgement includes the observed managed PV names/UIDs; the allocation ledger supplies volumes for which no PV exists.
4. Fulfillment calls private Volume Delete for every recorded allocation. It waits for the Volume subsystem's confirmed backend deletion. Missing/decommissioned-hub shortcuts cannot mark managed volumes cleaned up. Lost provider-create outcomes remain pending until the stable provider identity is reconciled and removed.
5. The operator removes retained PVs using UID preconditions after backend cleanup; fulfillment waits for this cleanup acknowledgement, then removes its managed-storage and ordinary parent finalizers. Namespace cleanup occurs after the required acknowledgements.

The ComputeInstance CR therefore retains a storage-cleanup finalizer while its normal AAP deletion finalizer may complete. Fulfillment exposes private cleanup stage/allocated IDs to that CR; operator feedback only updates its own acknowledgement fields. An API Volume can exist without any PV, so cleanup always starts from the ledger. [PRD: In Scope, deletion; Research: D3–D6]

## 4.2 Data Model / Schema Changes

All fields below are proposals; allocate protobuf field numbers during implementation without reusing existing tags.

| Model | Addition / constraint |
|-------|------------------------|
| Public `ComputeInstanceStatus` | `repeated ComputeInstanceVolume volumes`; each entry has `disk_key: string`, `volume_id: string`. Only committed IDs appear; sorted boot then additional-disk order. IDs are immutable for this lifecycle. |
| Private ComputeInstance lifecycle state | `storage_lifecycle: managed-v1`, cleanup stage, and UID-qualified workload/PV cleanup acknowledgements. Set only by service/controller principals; hidden by cleanapi. No marker denotes legacy handling. |
| Private `VolumesCreateRequest` | Optional private `compute_instance_disk` context from Section 4.3. No new parent field on the public or private Volume object. |
| Private `VolumesDeleteRequest` | Optional private `compute_instance_id`, used only for authorized managed cleanup and checked against the ledger. |
| ComputeInstance CR | Private-to-platform `spec.storageLifecycle`, cleanup instructions/allocated volume IDs; `status.storageCleanup` contains stage, current CR UID and released PV references. These are workload/platform control fields, not public attachment status. |
| Volume private provider context | Persist operation identity before vendor create; record whether outcome/cleanup is unresolved. It must survive a controller restart without inventing a new backend operation. |

Add an internal `compute_instance_volume_allocations` table with primary key `(compute_instance_id, disk_key)`, unique `volume_id`, and fields `tenant`, `project`, `hub_id`, `datavolume_uid`, `pvc_uid`, `pvc_namespace`, `pvc_name`, `csi_name`, immutable-spec fingerprint, and `cleanup_complete_at` (nullable). IDs/UIDs are opaque strings; disk keys are validated against the parent spec. The parent owns these records; no reverse relationship is added to the Volume API. Volume IDs remain usable for archival lookup, so a foreign key must not prevent Volume archival. Allocation rows are retained while the parent is live or deleting and retired atomically with parent archival after confirmed cleanup; archived parent status retains the public IDs. No legacy backfill occurs.

Managed Create uses the existing request transaction: lock parent row; validate eligibility; look up the slot; create Volume and allocation record; update only `status.volumes`; commit together. Any error reports to `Tx.ReportError` and rolls back all effects, including the transactional outbox. Concurrent requests for the same slot serialize; a duplicate returns the same record only when every immutable input and source UID matches. A different claim UID does not silently adopt an existing disk. [Codebase: `fulfillment-service/docs/CODEWALK.md`, transaction-per-request and outbox; Research: D2–D3]

Only the managed allocation service writes public `status.volumes`. Existing operator feedback uses explicit masks and must never replace that field. Add server-side ownership checks for broad/private status updates, plus reconciliation repair from the allocation table. The ordinary state/condition writer remains the existing feedback controller.

## 4.3 API Changes

Use existing private gRPC `Volumes.Create`/`Delete`, extending their requests with cleanapi-private context. Managed CSI calls use gRPC; existing REST paths and public Volume Create request bodies do not acquire these fields. Add no attach/detach RPC. [PRD: Dependencies]

Managed Create context:

```json
{
  "compute_instance_disk": {
    "compute_instance_id": "<parent-id>",
    "disk_key": "boot",
    "hub_id": "<registered-hub-id>",
    "datavolume_uid": "<uid>",
    "pvc_namespace": "<tenant-workload-namespace>",
    "pvc_name": "<compute-resource-name>-root-disk",
    "pvc_uid": "<uid>"
  }
}
```

`object` retains the existing tier/size/access-mode/topology shape. CSI retains its stable sidecar create name in metadata; the allocation slot supplies the stronger parent/disk idempotency key. The server derives tenant/project and hub from the parent, compares all submitted values, resolves the immutable tier by canonical reference/name mapping, and verifies sufficient capacity for the parent disk. This proposal preserves the current filesystem/RWO VM contract; CDI scratch claims are not managed VM disks and must use a separately configured scratch class. They never consume a parent disk slot. No cluster ID or vendor credentials are exposed in public status.

| Condition | Result |
|-----------|--------|
| Malformed context, missing disk key/UID, invalid size/access mode | `INVALID_ARGUMENT`; no rows committed. |
| Inaccessible/cross-tenant parent or unauthorized lifecycle context | `PERMISSION_DENIED`; no existence details returned. |
| Authorized caller, nonexistent parent | `NOT_FOUND`; no allocation. |
| Parent deleting/legacy, hub mismatch, missing LVMS node, incompatible placement or unknown required disk | `FAILED_PRECONDITION`; no new allocation. |
| Existing slot with changed tier/capacity/access mode/source UID | `ALREADY_EXISTS`; existing ID is not adopted or replaced. |
| Retry with identical live parent/slot/spec/source | Return original Volume, including CREATING/FAILED state; never create another. |
| Database serialization conflict / temporarily unavailable dependency | `ABORTED` / `UNAVAILABLE`; retry with the same identity. |

Private Delete checks managed ownership in the same transaction as deletion intent. For an allocated VM Volume it requires a deleting parent and persisted workload-release acknowledgement; otherwise return `FAILED_PRECONDITION`. CSI Delete on a managed volume cannot bypass that check. The parent coordinator handles Retain allocations. Standalone Volume behavior is preserved in the proposed compatibility policy; public deletion of managed volumes returns `FAILED_PRECONDITION`. This policy is conditional on resolving Section 9.1, not declared an approved PRD interpretation.

Public ComputeInstance Get/List expose the new read-only `status.volumes`. Public updates cannot set or replace it. CLI JSON/YAML output includes the additive fields through the normal API; no new command is introduced. Add a `StorageReady` condition to existing condition mappings, initialized false when a managed ComputeInstance is created: false until required allocations are AVAILABLE and disk population/binding is complete; true alone does not assert guest readiness. Existing VM Ready remains gated by its current checks and this required-storage condition. Cleanup reports `StorageCleanupPending`/`StorageCleanupFailed` as reason strings on existing deletion/progress conditions, not as attachment states.

## 4.4 Scalability and Performance

For N required disks, storage overhead is N allocation rows, N public status entries and N Volume resources. Create/delete performs O(N) work per instance; per-slot requests use indexed lookup and a short parent-row transaction. Vendor calls and CSI availability polling occur after commit, outside the database lock. No deployment size or latency SLA is asserted by the PRD.

Reuse existing CSI bounded backoff and reconciliation queues. Wake the parent on managed Volume transitions through the existing signal/watch mechanism; periodic reconciliation remains recovery for missed notifications. Cleanup retains state indefinitely while evidence is incomplete rather than expiring ownership after a timeout. No tenant-wide scan is required on the create/delete path. [Codebase: fulfillment event/outbox/reconciler patterns; Research: D3–D6]

## 4.5 Security Considerations

Managed StorageClasses and controller-authored lifecycle markers are administrator-controlled. The CSI resolver verifies Kubernetes owner UIDs and authoritative ComputeInstance context; the API validates tenant/project/hub and immutable disk inputs again. No arbitrary PVC annotation is accepted as authority to adopt a Volume. Managed requests cannot fall back to CSI's current default tenant. Cleanup uses recorded immutable IDs, UID-preconditioned Kubernetes deletion, and the parent ledger rather than user-editable display names.

Use existing authenticated private-service access and existing TLS/credential mechanisms. Hub CSI is a privileged platform component: its Kubernetes read access and private API permission are scoped/documented explicitly. Credentials, backend context and tenant identities do not appear in public volume correlations or unredacted logs. Validate cross-tenant negative paths at the real API boundary, not only with mocked clients. [Codebase: repository tenancy conventions; Research: H9, P5]

## 4.6 Failure Handling and Recovery

| Failure | Recovery / observable result |
|---------|------------------------------|
| API commit succeeds, CSI loses response | Same slot returns the committed ID; parent status already contains it. |
| Process dies before commit | Transaction/outbox rollback; retry creates at most one record. |
| Concurrent parent Delete and managed Create | Parent lock establishes order: create first is recorded for cleanup; delete first rejects create. |
| Storage ready but PV creation or image import fails | Allocation remains visible; retry reuses it; parent deletion can clean it without a PV. |
| Another disk fails | Keep successful disks and report StorageReady=false; retry failed work without replacing successful IDs. Parent deletion cleans every recorded allocation. |
| Claim recreated with another UID | Refuse automatic reuse/reformatting; report a conflict and retain allocation. No transparent disk replacement. |
| Scheduler retries another node | Existing local allocation keeps its node; incompatible retry fails visibly. A new node is allowed only before any allocation transaction commits. |
| Missing driver/class/configuration | VM remains pending with a prerequisite reason; no vendor-class fallback. |
| Volume provider create times out / response is lost | Reconcile the stable provider identity; retain an unresolved-operation marker. Never infer that no storage exists from an empty returned ID. |
| Delete accepted but provider resource remains | Keep Volume DELETING and parent finalizers; retry until authoritative absence/completion. |
| Hub gone, API inaccessible, conflicting PV UID | Retain cleanup state and report failure; no automatic abandonment or deletion of a replacement resource. |
| Operator feedback races with allocation update | Mask/ownership enforcement preserves public disk IDs; reconcile repairs from the ledger. |

Provider lifecycle changes are part of the implementation when needed for these guarantees. In particular, LVMS currently creates a generated LogicalVolume before persisting its reference and its delete helper returns after submitting Kubernetes deletion. Persist a chosen LogicalVolume operation name before creation, retry using that identity, preserve UID validation, and wait for that LogicalVolume's confirmed removal before reporting DELETED. Existing recorded generated names remain valid. VAST uses the stable OSAC resource name for vendor CSI Create; qualify its idempotency and Delete completion contract. A provider with an ambiguous operation cannot be reported cleaned up. [Codebase: `lvms_vendor_provisioner.go`, `vast_vendor_provisioner.go`; Research: D5–D6]

## 4.7 RBAC / Tenancy

No new tenant persona or public lifecycle permission is introduced. ComputeInstance Get/List visibility governs disk IDs; Volume visibility remains independently tenant/project scoped. Service roles gain only the private managed-operation fields they need.

CSI controller RBAC adds get/list/watch for PVCs, DataVolumes and ComputeInstance CRs required by its resolver. Prefer namespace-scoped access where deployment topology permits; a shared hub controller needs explicit cross-namespace read grants. Operator storage cleanup needs PV/VolumeAttachment read access and managed PV deletion, with runtime tenant/UID checks on these cluster-scoped resources. Tenant users cannot edit the managed StorageClasses or platform ComputeInstance CRs. Retain the existing `osac.openshift.io/tenant` and applicable `osac.openshift.io/owner-reference` annotations on generated resources. [Codebase: root/operator AGENTS and tenancy conventions]

## 4.8 Extensibility / Future-Proofing

Disk keys are stable because this feature's disk list is immutable. Keep backend translation in the Volume subsystem and CSI routing; no vendor fields enter the public ComputeInstance model. The allocation table is private lifecycle state, not a general attachment inventory. OSAC-4884 must define any later attachment contract independently.

# 5. Interface Changes

The PRD has no numbered requirements. References below name its actual sections/bullets; the test plan uses short local aliases solely for test IDs.

## IC-1: Managed VM DataVolume and StorageClass contract

**Requirements:** In Scope—creation; Dependencies—private Storage API.

AAP/tenant resolution emits managed classes and the lifecycle/parent/disk annotations from Section 4.1, selects direct CDI population, and preserves registry/blank sources. Unknown/missing managed classes fail without vendor fallback. CDI scratch storage remains distinct.

## IC-2: CSI managed request resolution and topology

**Requirements:** In Scope—creation; Dependencies—private Storage API.

CSI Create consumes sidecar claim metadata, verifies the UID-qualified owner chain, and sends managed context and scheduler topology. It returns the Storage API ID as `VolumeId`, preserves existing vendor context translation, and applies the retry/error rules in Section 4.3.

## IC-3: Private Volume Create and atomic allocation persistence

**Requirements:** In Scope—creation, deletion, visibility; Dependencies—private Storage API.

Private `VolumesCreateRequest` gains managed context. The server atomically persists the Volume, parent-owned allocation and public ID, pins hub placement, and serializes with parent deletion. The additive database table and request fields are defined in Sections 4.2–4.3.

## IC-4: ComputeInstance public disk correlations

**Requirements:** In Scope—visibility; Out of Scope—reverse linkage and attachment state.

Get/List and ordinary CLI JSON/YAML expose read-only `status.volumes[{disk_key,volume_id}]`; no vendor/hub/claim details appear. Private feedback cannot overwrite this field. Existing instances return an empty collection without adoption.

## IC-5: Managed Volume deletion authorization

**Requirements:** In Scope—deletion; Out of Scope—standalone deletion; Dependencies—private Storage API.

Private Delete gains an optional parent cleanup context and validates parent deletion/release acknowledgement. The proposed public managed-delete rejection and standalone compatibility policy remain conditional on Section 9.1.

## IC-6: ComputeInstance cleanup acknowledgements and finalizers

**Requirements:** In Scope—deletion.

CR/API-private lifecycle fields carry workload release and PV cleanup acknowledgements. Parent completion requires all ledger allocations cleaned, including those with no PV. AAP deletion, operator cleanup and fulfillment ordering follow Section 4.1.

## IC-7: Backend cleanup completion and provider operation identity

**Requirements:** In Scope—creation, deletion.

Volume provider reconciliation retains durable operation identity and reports DELETED only after confirmed backend removal. Managed hub-absence shortcuts cannot clear finalizers. LVMS pending deletion and lost-create recovery are explicit changed behaviors.

## IC-8: Deployment values, schema and service permissions

**Requirements:** In Scope—creation; Dependencies—private Storage API.

VMaaS release profiles enable existing `csiDriver.enabled` and require a real fulfillment connection (`allowStub=false`). Expose/document `csiDriver.controller.clusterID` as the registered Hub ID for this route, with matching umbrella schema. Installation supplies it after hub registration before managed provisioning becomes ready; empty/mismatched identity blocks the managed path. Validate vendor sockets, driver registration, managed class creation, RBAC and CSI readiness on each workload hub. This prerequisite also applies to additional hubs, not only the fulfillment installation cluster.

The release installation sequence waits for the declared compatible fulfillment/operator/CSI image versions to finish rollout (observed generation current, all desired replicas ready, no old replicas) before enabling managed class resolution. The operator exposes the resulting managed-storage prerequisite condition to provisioning; JIT resolution requires it. Unsupported mixed versions must not be enabled. Additive protobuf fields alone are not a compatibility handshake: an older server can ignore them. This proposal relies on the enforced release installation prerequisite, not an automatic wire-version negotiation. [Codebase: installer composition and release profiles; Research: deployment findings]

Changing installer defaults/schema invokes the Enclave pipeline. This design owns installer values/schema delivery; downstream plugin uptake and Wizard rendering/validation are an external delivery dependency for the separate UI/Enclave design and work. Hand off the field names, types, defaults and validation constraints, and link that work before declaring Wizard support available. This design's decomposition includes the installer contract and dependency reference; the separate work owns UI implementation and tests. [Codebase: `docs/agent-context/enclave-wizard-pipeline.md`; User: UI scope separation]

## IC-10: Storage readiness and cleanup diagnostics

**Requirements:** In Scope—creation, deletion, visibility.

The API/CR condition mappings add StorageReady and the documented cleanup reason strings. Structured events in Section 7 identify allocation/recovery/cleanup transitions. VM Ready is not inferred from Volume AVAILABLE alone.

# 6. Alternatives Considered

| Decision | Alternative and benefit | Cost / reason for this proposal |
|----------|-------------------------|--------------------------------|
| Dynamic CSI creation | VMaaS creates Volumes, then storage projects static PVs; direct early control of IDs | Requires a separate pre-allocation placement handshake and PV projector. Existing dynamic CSI already carries node topology and calls the API. |
| Allocation identity | Observe `PV.spec.csi.volumeHandle` only; fewer writes | Misses successful API creates before PV persistence. Atomic parent-owned records close that failure window. |
| CDI population | Retain automatic populators; follows CSI defaults | Requires validating temporary-claim ownership/rebinding and reclaim behavior. Direct population keeps one target identity; runtime qualification remains required. |
| API integration | New managed allocation RPC | Provides a distinct endpoint but duplicates Create plumbing. An optional private context reuses validation, persistence and generation patterns. |
| Cleanup ownership | Delete reclaim policy and CSI-driven backend delete | Uses existing sidecar reclamation but does not cover no-PV allocations and currently acknowledges too early. Retain plus parent coordination gives one explicit completion boundary. |
| Allocation storage | Store recovery fields only in ComputeInstance status | Avoids a table but couples multiple feedback writers to durable ownership state. A small indexed table plus controlled public projection isolates the invariant. |
| Compatibility | Adopt existing vendor PVs | Requires provider identity/import semantics outside the approved lifecycle scope. Preserve existing objects on their legacy path. |
| Do nothing | Retain vendor CSI VM provisioning | Leaves VM disks absent from Storage API inventory and fails the PRD. |

These choices follow the research comparison and the user's preference for existing-code reuse. The additional lifecycle bookkeeping is justified by the no-orphan requirement; it does not replace Kubernetes scheduling. [Research: Section Recommended Approach, Section Retry and Deletion Findings]

# 7. Observability and Monitoring

Emit structured transition events `ManagedDiskAllocated`, `ManagedDiskRecovered`, `ManagedDiskConflict`, `ManagedDiskCleanupPending`, and `ManagedDiskCleaned` using existing logging/event conventions. Include ComputeInstance ID, disk key, Volume ID when known, hub ID and a sanitized reason. Do not include credentials or backend attributes. Suppress repeated identical pending events; log state changes and bounded retry summaries.

StorageReady and deletion reason strings are the user-visible signals. A stuck cleanup retains its allocation IDs for operator diagnosis. Existing reconciliation/CSI error metrics remain applicable; no new metric names, alert thresholds or latency SLA are introduced. [PRD: visibility and coordinated cleanup; Codebase: controller status/event patterns]

# 8. Impact and Compatibility

Public API fields and condition enums are additive, but clients must tolerate unknown conditions. New managed request fields are private and must be absent from generated public descriptors. Regenerate shared protos once (`make -C proto generate`) and operator CRDs/deep copies/Helm CRDs with owning generators; generated files are never edited manually. Publish the additive API contract for the separate UI design/work to consume. UI API-baseline adoption, presentation decisions and UI tests are owned there.

Introduce schema and compatible server/controller code before routing new VM classes to OSAC CSI, using the release installation gate in IC-8. An old server may ignore the added private request fields, so mixed CSI/server versions are unsupported and cannot pass that gate. A deployment with missing managed-capable components is not eligible to provision a new managed VM. Existing unmarked instances continue their original class/deletion path and are not backfilled; tests cover mixed objects. No in-place upgrade support is claimed.

All currently required VM tier/provider combinations must be accounted for before release. LVMS and VAST are explicit qualification targets from the inspected VM paths. The current OSAC VAST provisioner explicitly rejects protocols other than block; any required NFS-backed tier needs provider implementation under IC-7 as well as qualification. Filesystem/raw-block mode, VAST protocol variants, CDI scratch needs and any additional advertised tiers must be resolved in the runtime matrix (Section 9.2), with missing provider work included rather than quietly excluding a tier. Default hub CSI enablement, credentials and additional-hub installation are deployment impacts, not merely a StorageClass rename. [Codebase: `osac-operator/internal/controller/vast_vendor_provisioner.go:CreateVolume`]

The accompanying [test plan](testplan.md) distinguishes behavioral mappings, runnable harnesses and unexecuted integration evidence. No implementation tests or cluster experiments were run during this drafting phase.

# 9. Open Questions

## 9.1 Does the deletion restriction apply only to ComputeInstance-managed Volumes?

- **Owner:** Storage and VMaaS maintainers / PRD owner.
- **Impact:** Section 4.3 and IC-5 propose rejecting standalone deletion of managed disks while preserving existing standalone Volume CRUD. The PRD's broad wording overlaps OSAC-984. This policy needs an explicit answer before the API behavior is finalized; the test plan marks its corresponding assertions conditional.

## 9.2 Which runtime/provider matrix must qualify the managed VM path?

- **Owner:** Storage, VMaaS and deployment maintainers.
- **Impact:** Section 4.1, Section 8 and IC-1/2/8 need the supported KubeVirt/CDI/CSI releases, LVMS/VAST mode/protocol combinations, CDI scratch configuration and any additional VM tiers. Source evidence supports the candidate mechanics; no deployed import/mount/I/O/delete result is available. A failed required combination creates implementation work or an architecture revision, not an implicit backend exclusion.

## 9.3 Does private parent-owned allocation bookkeeping satisfy the excluded reverse-link boundary?

- **Owner:** Storage and VMaaS maintainers / PRD owner.
- **Impact:** Section 4.2 keeps association only in internal ComputeInstance lifecycle state and public ComputeInstance status; Volume objects expose no parent or attachment state. Confirm that the PRD exclusion concerns the Volume-facing contract and permits the internal ownership needed for atomic recovery and deletion protection.

---

## Provenance

Authored: revise @ design 0.11.5 - 1c6e8de, workspace design/OSAC-6040 @ d30e35d27
Phases: draft, revise, revise

<!-- ai-workflow-provenance:{"schema_version":1,"provenance_kind":"session","workflow":"design","workflow_version":"0.11.5","ai_workflows":"1c6e8de","source_repo":"d30e35d27","source_repo_branch":"design/OSAC-6040","commits_behind_main":0,"commits_ahead_main":250,"main_ref":"main","phases":["draft","revise","revise"],"authoring_modes":["skill"],"context_changed":false,"origin_untracked":false} -->
