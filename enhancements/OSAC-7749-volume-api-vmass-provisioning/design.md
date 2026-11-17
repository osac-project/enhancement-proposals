# Volume API owns VMaaS volume provisioning end-to-end

| Field       | Value                                                       |
|-------------|-------------------------------------------------------------|
| Author(s)   | Mark Bramnik <mbramnik@redhat.com>                          |
| Jira        | [OSAC-7749](https://redhat.atlassian.net/browse/OSAC-7749) (design task [OSAC-7321](https://redhat.atlassian.net/browse/OSAC-7321), outcome [OSAC-7318](https://redhat.atlassian.net/browse/OSAC-7318)) |
| PRD         | [prd.md](prd.md)                                            |
| Date        | 2026-11-17                                                  |

# 1. Overview

This design moves VMaaS ComputeInstance disk provisioning into the Volume
API's control loop. Today, disk registration creates Volume records in
fulfillment, while the real storage — CDI DataVolumes on the target
cluster — is created by the AAP `ocp_virt_vm` playbook; the two paths are
correlated only by an ID annotation, and the Volume record's own
vendor-provisioning leg fails for these volumes (OSAC-7670). The design
collapses the two paths into one: a Volume created with a ComputeInstance
owner is provisioned as a DataVolume by the osac-operator Volume
controller, in the same location as the owning instance, with a lifecycle
and failure reasons derived from the DataVolume, and cascade-deleted with
the instance. Ownerless (CaaS/CSI) volumes keep the existing
vendor-provisioner path unchanged. See [PRD](prd.md) for detailed
requirements.

The ComputeInstance create API remains the entry point; the Volume API is
called from it internally, and no public ComputeInstance API changes
[PRD: REQ-7] [User].

# 2. Goals and Non-Goals

## 2.1 Goals

- Select the provisioning strategy per Volume at the Volume CR
  reconciliation point: vendor CSI for ownerless volumes, DataVolume
  creation for ComputeInstance-owned volumes.
- Carry ownership and disk source on the Volume object so the provisioner
  has everything it needs without side channels.
- Derive volume state and failure reasons from the DataVolume's actual
  phase and conditions, through the existing operator→fulfillment
  feedback bridge.
- Reuse the existing cross-cluster finalizer chain for cascade delete
  instead of introducing any new agent or garbage-collection mechanism.
- Preserve the exact current DataVolume shape (registry source with
  node pull, blank sources, names, RWO) so VM behavior is unchanged.

## 2.2 Non-Goals

- Standalone volumes, add-disk, remove-disk, transfer, and hot-plug /
  hot-unplug — owned by the parent outcome OSAC-7318.
- A stable name mapping between an OSAC volume and its provisioned
  storage; DataVolume names keep the existing `<ci-name>-<disk-key>`
  derivation (OSAC-7318).
- Long-lived `PENDING` semantics for standalone volumes — a volume
  waiting for an owner before its target cluster and namespace can be
  resolved (OSAC-7318). This feature introduces `PENDING` as the initial
  state of every volume, with a quick transition to `CREATING` [User].
- Any change to the public ComputeInstance API surface, to networking
  contracts, or to the CaaS/CSI volume path.
- Backfill or migration of existing volumes and instances [PRD: REQ-7].

# 3. Motivation / Background

The current VMaaS disk flow has two independent provisioning paths per
disk. Fulfillment's disk registration creates a Volume record named
`ci-<ci-id>-<disk-key>` (with a placeholder LVMS node topology) and
resolves its ID into `ComputeInstance.status.volumes` and the CR's
`spec.diskVolumeIDs`. The fulfillment volume reconciler then creates an
`osacv1alpha1.Volume` CR on a randomly selected hub, where the operator's
Volume controller attempts vendor-CSI provisioning through
`VendorProvisioner` — which fails for these volumes, leaving them
`FAILED` ("volume provisioning failed") while the real disk is being
created elsewhere [Codebase:
`fulfillment-service/internal/controllers/computeinstance/disk_registration.go`].
Meanwhile the AAP `ocp_virt_vm` playbook creates the actual DataVolumes on
the target cluster (root disk from the OCI registry image, additional
disks blank), stamps the fulfillment Volume ID on them as an annotation,
creates the VirtualMachine referencing them, and deletes them on teardown
[Codebase: `osac-aap/collections/ansible_collections/osac/templates/roles/ocp_virt_vm/tasks/create_resources.yaml`].

The consequences are the problems the PRD states: no ownership tracking
(the Volume record has no back-reference to the instance), an untruthful
lifecycle (OSAC-7670: volumes report FAILED while their DataVolumes are
Bound and attached to running VMs), and two writers for one disk's
storage. Tier-to-StorageClass resolution and JIT StorageClass creation
also live inside the AAP playbook, outside the storage team's control
loop.

This design supersedes the VMaaS provisioning sections of
[OSAC-6037](https://github.com/osac-project/enhancement-proposals/blob/main/enhancements/OSAC-6037-storage-api-volume-lifecycle/design.md)
(per-disk Volume Create contract, physical side effects); its
registration recovery state machine and record-cleanup finalizer flow are
retained and extended. [User]

KubeVirt and CDI provide the synchronization guarantees this design
relies on: a VM may reference DataVolumes that are still importing —
KubeVirt holds the VMI unscheduled until every referenced DataVolume
finishes its import — but the DataVolume lifecycle is not tied to the VM
(reference-based DVs are not garbage-collected with it), so ordering and
teardown remain OSAC's responsibility [Research: Domain 1].

# 4. Design

## 4.1 Architecture

The provisioning decision moves to the Volume CR: the operator's Volume
controller reconciles `osacv1alpha1.Volume` CRs and branches on
`spec.owner` — ownerless CRs take the existing `VendorProvisioner` path
(CaaS, unchanged); ComputeInstance-owned CRs take a new VMaaS branch that
creates and watches a CDI DataVolume on the target cluster. Fulfillment
keeps owning the Volume record and the registration state machine, and
gains an ownership field; the AAP playbook keeps creating the
VirtualMachine, Secrets, and optional Service, but no longer creates,
resolves storage for, or deletes DataVolumes.

```mermaid
sequenceDiagram
    participant TU as Tenant User
    participant F as fulfillment-service
    participant H as hub cluster
    participant OP as osac-operator
    participant T as target cluster
    participant AAP as AAP job (ocp_virt_vm)

    TU->>F: Create ComputeInstance (disks, disk image)
    F->>F: CI reconciler calls the private Volume API:<br/>Volumes.Create (owner, source)<br/>→ records persist, start PENDING
    F->>H: Volume CRs on the CI's hub<br/>(volume reconciler, owner + source copied)
    F->>H: ComputeInstance CR (diskVolumeIDs)
    OP->>H: CI controller reads CI CR: resolve VM namespace,<br/>tier→StorageClass (+ JIT)
    OP->>H: Volume controller picks up Volume CR:<br/>CR phase → Progressing
    OP->>F: volume feedback controller:<br/>Volumes.Update — fulfillment state<br/>PENDING → CREATING
    OP->>T: create DataVolumes (create-or-adopt)
    OP->>H: Volume CR status: DataVolumeProvisioned
    OP->>AAP: launch provision job (VM only)
    AAP->>T: VirtualMachine references existing DataVolumes
    T-->>OP: DV phase: Succeeded/Failed
    OP->>H: Volume CR phase/conditions<br/>(Ready / Failed)
    OP->>F: feedback bridge: fulfillment state<br/>AVAILABLE / FAILED + message
    TU->>F: volume get/list: owner, AVAILABLE/FAILED + reason
```

The diagram shows the create flow. It deliberately uses each level's own
vocabulary — DataVolume phases (CDI), Volume CR phases (`Progressing`,
`Ready`, `Failed`), and fulfillment `VolumeState` values (`PENDING`,
`CREATING`, …); the state-mapping table below defines the translation.
The key handoffs: the CI reconciler
registers disks by calling the private Volume API (`Volumes.Create`),
which validates and persists the records with `owner` and `source`
(exactly one owner, never transiently ownerless) and sets the initial
`PENDING` state — the ComputeInstance flow does not write volume records
itself; the volume reconciler then reacts to the new records and creates
the Volume CRs on the CI's hub. The operator CI controller resolves
placement (VM namespace, StorageClasses) and publishes it on the CI CR
before launching the AAP job. The Volume controller's pickup of the
Volume CR (CR phase `Progressing`) is the signal for the first feedback
write: the volume feedback controller calls `Volumes.Update`, persisting
the `PENDING → CREATING` transition in fulfillment's database — this
write is asynchronous and does not gate DataVolume creation. The operator
Volume controller is the single writer of DataVolumes; and the feedback
bridge remains the only path from cluster state to fulfillment Volume
status, carrying both the `CREATING` transition and the terminal
`AVAILABLE`/`FAILED` states.

Component responsibilities:

- **fulfillment-service** — disk registration extends its create request
  with `spec.owner` and `spec.source`; the volume reconciler places
  CI-owned Volume CRs on the CI's hub instead of selecting one at random;
  CI delete requests volume deletion through the private Volume API
  (`Volumes.Delete`) and never removes volume records itself.
- **osac-operator, Volume controller** — new VMaaS branch: resolve the
  owning CI CR and the target namespace, resolve the StorageClass, create
  the DataVolume create-or-adopt on the target cluster, map DataVolume
  status to the Volume CR, delete the DataVolume on Volume CR deletion
  under a finalizer. The controller derives each volume's disk key (and
  therefore its DataVolume name) by matching the Volume CR's
  `osac.openshift.io/volume-uuid` label against the owning CI CR's
  `spec.diskVolumeIDs` map — the same map that feeds the VM spec, so
  naming has a single source of truth.
- **osac-operator, CI controller** — resolves the VM namespace and
  storage context (including JIT StorageClass creation, moved from AAP)
  *before* job launch, publishes the namespace on the CI CR, and gates
  AAP job launch on all owned volumes having created their DataVolumes.
- **osac-aap, `ocp_virt_vm`** — `create_resources` drops DataVolume
  creation and tier resolution; the VM spec keeps referencing the same
  DataVolume names; `delete_resources` drops DataVolume deletion and the
  DataVolume label sweep.
- **osac-operator, volume feedback controller** — unchanged mechanism;
  its source of truth (Volume CR phase/conditions) now also reflects
  DataVolume state.

### Target-location resolution [PRD: REQ-3]

"The same location as the owning ComputeInstance" resolves by
construction:

- **Hub:** the fulfillment volume reconciler inherits `status.hub` from
  the owning ComputeInstance record (replacing random hub selection for
  owned volumes), so the Volume CR is co-located with the CI CR.
- **Target cluster and namespace:** the operator's Volume controller
  reads the VM namespace from the owning CI CR's
  `status.virtualMachineReference.namespace` — the same value the CI
  controller already computes (the accepted NetworkAttachment namespace
  with provider networking, else the tenant namespace
  [Codebase: osac-operator/internal/controller/computeinstance_controller.go]).
  The target cluster is the operator's configured remote cluster. The
  DataVolume therefore lands in the exact namespace where the owning VM
  runs; no separate location negotiation exists.

The operator obtains target-cluster access through a kubeconfig Secret
supplied by the installer (the same credential AAP launch jobs use
today), consumed through the operator's existing remote-cluster
(multicluster-runtime) client. Compatibility of the remote-cluster
mechanism with provider networking is an open question (§9.1); if it
cannot be resolved, the AAP-transport alternative (§6) keeps this design
intact by swapping only the DataVolume writer.

### State mapping [PRD: REQ-4]

The Volume controller maps DataVolume state to the Volume CR, and the
existing feedback bridge maps the Volume CR to fulfillment `VolumeState`:

| DataVolume | Volume CR | Fulfillment `VolumeState` |
|---|---|---|
| (not yet picked up by the operator — no CR activity) | (no phase) | PENDING |
| Pending, ImportScheduled, ImportInProgress, WaitForFirstConsumer | Progressing | CREATING |
| Succeeded | Ready | AVAILABLE |
| Failed (+ condition reason/message) | Failed | FAILED, `status.message` = DV condition message |
| (CR deleting, DV delete in flight) | Deleting | DELETING |

**Initial state and the PENDING → CREATING transition.** Every volume
starts in `PENDING`: the private volumes server's `Create` sets it
(previously it set `CREATING`), and the fulfillment volume reconciler's
defaulting matches (UNSPECIFIED → PENDING). `PENDING` represents the
window between "volume record exists" and "the operator has started
provisioning" [User]. The transition to `CREATING` is not set by
fulfillment: the operator writes it on the Volume CR when it picks the
CR up and begins provisioning (phase `Progressing`), and the regular
volume feedback controller loop persists the new state in fulfillment's
database, because the status change must be reflected there for
consistency [User]. In the CI flow this window is short (about a
second); for the future standalone-volume flow `PENDING` will persist
until an attach resolves the target — that long-lived semantics is
OSAC-7318's, not this feature's. The initial state applies to all volume
creation flows, including CaaS/CSI volumes [User].

AVAILABLE is defined as DataVolume `Succeeded`, deliberately **not** as
PVC `Bound`: on WaitForFirstConsumer storage classes the PVC binds only
when the VM's virt-launcher pod consumes it, so a Bound-based definition
would never fire before the VM exists [Research: Domain 1].

### Ordering and the benign race

DataVolumes must exist before the AAP job applies the VirtualMachine
manifest (KubeVirt waits for imports, not for missing objects). The CI
controller therefore gates job launch on every owned Volume CR reporting
the `DataVolumeProvisioned` condition true. Import itself is not gated:
the VM is created while imports run, and KubeVirt holds the VMI
unscheduled until they finish [Research: Domain 1]. No other
orchestration between VM and disks exists or is needed.

### Deletion flow (cascade delete) [PRD: REQ-5]

Deleting a ComputeInstance cascades to its volumes through the same API
boundaries as creation — with the same responsibility rule: **the
ComputeInstance delete flow never removes volume records itself.** It
issues `Volumes.Delete` per disk through the private Volume API (the
existing `releaseFinalizerAfterVolumeCleanup` chain), so the decision of
what "deleting a volume" means — record removal, Volume CR teardown,
DataVolume deletion — stays inside the Volume API, owned by the storage
team [User]. The CI side only waits for the Volume API's answer before
releasing its own finalizer.

```mermaid
sequenceDiagram
    participant TU as Tenant User
    participant F as fulfillment-service
    participant H as hub cluster
    participant OP as osac-operator
    participant T as target cluster
    participant AAP as AAP job (ocp_virt_vm)

    TU->>F: Delete ComputeInstance
    F->>H: delete ComputeInstance CR
    OP->>AAP: deprovision job (VM only)
    AAP->>T: halt + delete VirtualMachine, Secrets, Service
    F->>F: CI cleanup calls the Volume API:<br/>Volumes.Delete per disk
    F->>H: volume reconciler deletes Volume CRs
    OP->>T: Volume controller deletes DataVolumes<br/>(retries while PVC in use)
    T-->>OP: DataVolumes gone
    OP->>H: release DV finalizer → Volume CRs removed
    OP->>F: feedback: DELETING → records archived
    TU->>F: volume get/list: volumes no longer listed
```

The diagram shows the delete flow. The key handoffs: the CI delete
path's only storage action is the `Volumes.Delete` call — record,
Volume CR, and DataVolume teardown all belong to the Volume API's
components; the AAP deprovision job deletes the VM, Secrets, and
optional Service, and no longer touches DataVolumes.

The chain, each link holding until the next verifiably completes (the
same "don't release until clean" semantics as OCM's Foreground deletion
[Research: Domain 3]):

1. Fulfillment's ComputeInstance finalizer — released only after every
   disk's Volume record is gone or in a terminal deleting state
   (existing `releaseFinalizerAfterVolumeCleanup` behavior).
2. Volume record deletion — the volume reconciler removes the Volume CR
   from the CI's hub.
3. The `osac.openshift.io/volume-datavolume` finalizer on the Volume CR
   — the operator's Volume controller deletes the DataVolume on the
   target cluster and releases the finalizer only once it is gone.

Two semantics the diagram cannot show:

- **Concurrency, not choreography.** The record cleanup and the VM
  teardown start together once deletion begins; there is no hard
  sequencing between "VM gone" and "DataVolume delete requested". The
  VM-first ordering is enforced softly: a DataVolume under a running VM
  has its PVC held by Kubernetes PVC protection, and the Volume
  controller retries until the deprovision job frees it (§4.6).
- **The future preserve option.** The PRD deletes volumes automatically
  "for now"; preserving a volume when its ComputeInstance is deleted is
  the remove-disk/detach territory of OSAC-7318. This design enables it
  structurally: because ownership is a field on the Volume rather than a
  naming convention, preserve-on-delete becomes a policy decision at the
  cleanup step (skip the `Volumes.Delete` for selected volumes), not a
  re-architecture.

## 4.2 Data Model / Schema Changes

### Fulfillment proto (`proto/private/osac/private/v1/volume_type.proto`)

```protobuf
// VolumeSpec additions (both immutable after creation):
message VolumeSpec {
  // ... existing storage_tier, size_gib, access_mode, topology ...

  // Owning workload. Set only by the system registration path;
  // public Create/Update rejects a non-empty value. Absent for
  // CaaS/CSI volumes and future standalone volumes.
  VolumeOwner owner = 5;

  // Disk source for VMaaS provisioning. Private.
  VolumeSource source = 6;
}

message VolumeOwner {
  // Type of the owning entity. New owner types are additive enum
  // values — the architect-agreed shape is a typed reference
  // (type + reference) reused by every owner kind [User].
  VolumeOwnerType type = 1 [(buf.validate.field).enum.defined_only = true];
  // Fulfillment record identifier of the owning entity named by type
  // (for ComputeInstance: the ComputeInstance id, e.g. "ci-...").
  // See §9.6 for the id-vs-name confirmation.
  string reference = 2 [(buf.validate.field).string.min_len = 1];
}

enum VolumeOwnerType {
  VOLUME_OWNER_TYPE_UNSPECIFIED = 0;
  VOLUME_OWNER_TYPE_COMPUTE_INSTANCE = 1;
  // VOLUME_OWNER_TYPE_CLUSTER = 2 — the CaaS owner kind in the agreed
  // model (owner {type: cluster, reference: <cluster id>}); add when
  // CaaS cluster ownership lands. Additive, no renumbering. The enum
  // carries only supported values — a pre-declared value would pass
  // validation and fail only at reconcile time.
}

message VolumeSource {
  oneof content {
    VolumeSourceRegistry registry = 1;
    VolumeSourceBlank blank = 2;
    // Future members (additive only): http, s3, gcs, pvc, snapshot,
    // upload — mirroring CDI DataVolumeSource.
  }
}

message VolumeSourceRegistry {
  // Full URL including scheme, CDI-compatible (e.g.
  // "docker://quay.io/containerdisks/fedora:41"). Composed by the CI
  // reconciler from DiskImage.source_ref; copied to the DataVolume
  // verbatim by the operator.
  string url = 1 [(buf.validate.field).string.min_len = 1];
  // PULL_METHOD_UNSPECIFIED is treated as NODE by the operator — the
  // only supported mode today: the node pulls the image so the import
  // needs no tenant network [Codebase: ocp_virt_vm role]. The
  // registration writes NODE explicitly.
  PullMethod pull_method = 2 [(buf.validate.field).enum.defined_only = true];
  enum PullMethod {
    PULL_METHOD_UNSPECIFIED = 0;
    PULL_METHOD_NODE = 1;
    // PULL_METHOD_POD — add when pod-network imports are supported
    // (mirrors CDI's RegistryPullMethod); additive, no renumbering.
    // The enum carries only supported values: a pre-declared value
    // would pass protovalidate and fail only at reconcile time.
  }
}

message VolumeSourceBlank {}

// VolumeStatus addition (private, written by the feedback path):
message VolumeStatus {
  // ... existing state, message, hub, ... ...
  DataVolumeReference data_volume = 11;  // name + namespace on target
}
```

Validation rules (protovalidate, not duplicated in Go):

- `owner` is either fully absent (ownerless CaaS volumes) or has both
  `type` and `reference` set; `type` must be `COMPUTE_INSTANCE` in this
  feature, and `reference` is non-empty. Consumers (CI-delete cleanup,
  registration recovery, same-tenant authorization) read `reference`
  directly — it is uniform across owner kinds.
- `source.content` has exactly one member set (server-side check —
  protovalidate has no oneof cardinality rule): `registry` for boot
  disks, `blank` for additional disks. `VolumeSourceRegistry.url` is
  non-empty; `pull_method` is `defined_only`, and `PULL_METHOD_UNSPECIFIED`
  is treated as `NODE` by the operator (the registration writes `NODE`
  explicitly).
- The private volumes server rejects `owner` on public Create/Update
  paths with `InvalidArgument` ("owner is system-managed"), matching the
  treatment of other system-managed fields. `source` is accepted only on
  the private (system) path.
- The registration path requires `owner` and `source` together — a
  VMaaS volume is created with exactly one owner and a known source
  [PRD: REQ-1] [User].
- The existing LVMS requirement that `topology.segments["osac.io/node"]`
  be present no longer applies to owned volumes: the registration stops
  sending the `osac-volume-registration-pending` placeholder, because
  owned volumes bypass the LVMS vendor path and DataVolume placement is
  handled by the target cluster's scheduler (§9.4).

`owner` is a public field (visible in volume get/list within the
tenant — the PRD's ownership-visibility story); `source` and
`data_volume` are private. The public Create path for standalone volumes
(OSAC-7318) will extend `owner` semantics; the field is a typed
reference (`type` + `reference`), the shape agreed with the architecture
team [User] — new owner types are additive enum values, and an
attachment representation can be added alongside it later without
reshaping the field [Research: Domain 2].

`VolumeSource` deliberately diverges from `DiskImage`'s shape
(`source_type` + `source_ref`): `DiskImage` is a tenant-facing catalog
object, while `VolumeSource` is a provisioning directive modeled as a
`oneof` mirroring CDI's `DataVolumeSource`, so future source kinds are
additive members rather than schema redesigns. The two meet at exactly
one translation point: the CI reconciler composes
`VolumeSourceRegistry.url = "docker://" + DiskImage.source_ref` (the
DiskImage reference is scheme-less today; the scheme is applied once,
here) with `pull_method: NODE`, and the operator copies `url` to the
DataVolume's registry source verbatim.

The `VolumeState` enum gains `VOLUME_STATE_PENDING = 6`, appended after
the existing values 0–5 to preserve wire compatibility. `Create` and the
reconciler defaulting set `PENDING` as the initial state for every
volume (see the state mapping in §4.1); `CREATING` arrives only through
the feedback path once the operator has started provisioning [User].

### Database

No schema migration. Volumes are stored as JSONB blobs; `owner`,
`source`, and `status.data_volume` are additive fields within the blob.
Existing rows without them are unaffected (ownerless CaaS volumes).

### CRD changes (`osac-operator/api/v1alpha1`)

```go
// VolumeSpec additions, both immutable:
type VolumeSpec struct {
    // ... existing StorageTier, SizeGiB, AccessMode, Topology ...
    // Owner identifies the fulfillment workload that owns this volume.
    // Empty for CaaS/CSI volumes.
    Owner *VolumeOwner `json:"owner,omitempty"`
    // Source describes the VMaaS disk source (registry image or blank).
    Source *VolumeSource `json:"source,omitempty"`
}

// VolumeOwner is the architect-agreed typed-reference shape:
type VolumeOwner struct {
    // +kubebuilder:validation:Enum=ComputeInstance
    Type VolumeOwnerType `json:"type"`
    // Reference is the fulfillment record id of the owning entity.
    // +kubebuilder:validation:MinLength=1
    Reference string `json:"reference"`
}

// VolumeSource mirrors the proto oneof using CDI's pointer-member
// idiom (Kubernetes CRDs have no oneof):
type VolumeSource struct {
    Registry *VolumeSourceRegistry `json:"registry,omitempty"`
    Blank    *VolumeSourceBlank    `json:"blank,omitempty"`
}

type VolumeSourceRegistry struct {
    // Full URL including scheme; copied to the DataVolume verbatim.
    URL string `json:"url"`
    // PullMethod carries only supported values (Unspecified, Node —
    // the kubebuilder enum matches). Unspecified is treated as Node
    // by the controller; the fulfillment registration writes Node
    // explicitly. Pod is added when pod-network imports are supported.
    PullMethod VolumePullMethod `json:"pullMethod,omitempty"`
}

type VolumeSourceBlank struct{}

// VolumeStatus additions:
type VolumeStatus struct {
    // ... existing Phase, Conditions, ... ...
    // DataVolumeRef names the CDI DataVolume provisioned for an owned
    // volume on the target cluster.
    DataVolumeRef *DataVolumeReference `json:"dataVolumeRef,omitempty"`
}
```

New condition type `DataVolumeProvisioned` (true once the DataVolume
object exists and is adopted by this controller) with reasons such as
`Created`, `Adopted`, `CreateFailed`, `Deleting`. A new finalizer
(`osac.openshift.io/volume-datavolume`) holds Volume CR deletion until
the DataVolume is gone.

The ComputeInstance CR gains no new fields; the CI controller sets
`status.virtualMachineReference.namespace` at the start of provisioning
(before job launch) instead of at job-launch time — the same value,
published earlier for the Volume controller to read.

## 4.3 API Changes

No new RPCs. The Volumes service (`List`, `Get`, `Create`, `Update`,
`Delete`, `Signal`) and the ComputeInstances service keep their shapes.

- **Public Volume type:** `spec.owner` becomes visible in Get/List
  responses (previously the field did not exist). Responses for
  CaaS/CSI volumes render it absent. Additive, non-breaking.
- **Public Volume Create/Update:** requests containing `spec.owner` are
  rejected with `InvalidArgument` — owner is system-managed.
- **Private Volume Create (registration path):** accepts `owner` and
  `source`; the pair is required for the registration flow.
- **Volume status:** `status.message` now carries DataVolume failure
  reasons (see IC-2); `status.data_volume` is private-only.

Example — volume get after CI creation:

```json
{
  "id": "vol-01j...",
  "metadata": { "name": "ci-<ci-id>-boot", "tenant": "tenant-a" },
  "spec": {
    "storageTier": "tier-netapp-san",
    "sizeGiB": 10,
    "accessMode": "READ_WRITE_ONCE",
    "owner": { "type": "COMPUTE_INSTANCE", "reference": "ci-01a1..." }
  },
  "status": { "state": "AVAILABLE", "message": "" }
}
```

Example — failed import:

```json
{
  "spec": { "owner": { "type": "COMPUTE_INSTANCE", "reference": "ci-01a1..." } },
  "status": {
    "state": "FAILED",
    "message": "DataVolume import failed: registry import: unauthorized"
  }
}
```

## 4.4 Scalability and Performance

Impact is bounded by ComputeInstance disk counts (today's deployments
show 1–5 disks per instance; volume counts scale linearly with
instances). The Volume controller adds one remote-cluster watch per
target cluster for DataVolumes (single target cluster in this deployment
model) and one Get of the owning CI CR per reconcile, cached through the
existing manager informers. Fulfillment adds two fields to the JSONB
blob — no query-path changes. AAP job payloads shrink (no storage-class
resolution, no DataVolume tasks). No new retention concerns: DataVolumes
live exactly as long as their Volume CRs.

## 4.5 Security Considerations

The design inherits the existing security model. Tenant isolation is
unchanged: the owner is stamped by the system registration path, which
copies tenant and project from the ComputeInstance — a volume and its
owner are same-tenant by construction, and public visibility rules
(tenant-scoped List/Get) apply to the owner field as to every other
field. DataVolumes created on the target cluster carry
`osac.openshift.io/tenant` (an improvement over today's AAP-created
DataVolumes, which deliberately carry only the volume-ID annotation) and
the `osac.openshift.io/storage-volume-id` annotation. The target-cluster
kubeconfig is a mounted Secret reused from the AAP credential path —
never logged, never serialized into job vars. `source.registry.url` is a
URL validated as a non-empty string (protovalidate), passed through to
the DataVolume registry source; no credentials are embedded
(registry pull secrets, when needed, use the node pull method, which
draws on the node's runtime credentials — unchanged from today).

## 4.6 Failure Handling and Recovery

| Failure | Behavior | Recovery / user visibility |
|---|---|---|
| Operator down or Volume CR not picked up | Volume stays `PENDING` — the record exists in fulfillment, no CR activity | User sees `PENDING`, which distinguishes "not picked up" from "provisioning in progress"; transitions resume when the operator does |
| DataVolume create fails (API error, missing SC, missing namespace) | Volume controller requeues with backoff; Volume CR condition `DataVolumeProvisioned=False` reason `CreateFailed`; CI stays un-provisioned (job not launched) | Volume shows `CREATING` with the create error in `status.message`; CI `Provisioned=False` with a storage reason |
| Registry import fails | DV phase `Failed`; Volume CR phase `Failed`; feedback bridge sets fulfillment `FAILED` with the DV condition's reason/message | `status.message` carries the importer's exit reason (REQ-4's visible failure) |
| Operator restarts mid-provision | Create-or-adopt: the controller finds the existing DV by name + `storage-volume-id` annotation and adopts it; CDI rejects spec updates, so the controller never re-applies the spec [Research: Domain 1] | No duplicate storage; states converge |
| AAP job fails after DVs created | VM not created; volumes remain `AVAILABLE`; CI reports the job failure and the job retry path re-runs (existing engine semantics) | Volumes are not deleted — they belong to the CI, which still exists |
| DV deletion blocked by PVC-in-use during CI teardown | Volume controller retries; the CI deprovision job halts and deletes the VM first, which frees the PVC | Volume CR finalizer holds deletion until the DV is gone; volume shows `DELETING` |
| Target cluster unreachable | Volume controller requeues; volume stays `CREATING`/`DELETING` with message | Existing hub-unreachability handling applies (hub decommission path unchanged) |
| Orphaned DataVolume (Volume CR deleted out-of-band) | On re-reconcile the controller re-creates the DV with the same name; CDI continues or re-imports | Idempotent by name + annotation |

The two-phase registration claim machine (NEVER_ATTEMPTED / UNKNOWN /
NON_COMMITTED_FAILURE / RESOLVED) is retained unchanged; it now also
stamps `owner` and `source`, and the "adopt on UNKNOWN" recovery
(`recoverUncertainDiskRegistration`) additionally matches on the owner
field when re-finding a volume by CEL filter.

## 4.7 RBAC / Tenancy

- **Operator hub RBAC:** the operator ClusterRole gains
  `cdi.kubevirt.io datavolumes` verbs `create`, `update`, `patch`,
  `delete` (today: get/list/watch only)
  [Codebase: osac-operator/config/rbac/role.yaml]. The chart clusterrole
  is updated in the same change.
- **Target cluster:** the remote kubeconfig's identity must be allowed
  to manage DataVolumes in tenant VM namespaces; this is the same
  credential AAP jobs use today, which already creates and deletes
  DataVolumes there — no new privilege is introduced, only a new client.
- **Fulfillment tenancy:** no new roles or policies. `spec.owner` is
  subject to the existing tenant-scoped visibility; the system
  registration path is the only writer (enforced by validation, §4.3).

## 4.8 Extensibility / Future-Proofing

The ownership field is a typed reference (`type` + `reference`, the
architect-agreed shape [User]) rather than a bare CI id, so BMaaS/CaaS
owners are additive enum values and, later, an attachment
representation (records or tickets, per the Cinder/EBS/Longhorn
precedents) can be added alongside it without reshaping the field
[Research: Domain 2] — this is the model
OSAC-7318 asked to be declared once. The VMaaS branch of the Volume
controller is a self-contained provisioning strategy behind the same CR;
if DataVolume creation is later moved behind the `VendorProvisioner`
interface or an AAP task (§6), the Volume CR contract defined here does
not change. The `PENDING` state introduced here as the initial state of
every volume extends naturally to the standalone-volume flow, where it
persists until an attach resolves the target (OSAC-7318) — the state and
its feedback-driven transition are shared, only the duration differs.

# 5. Interface Changes

## IC-1: Volume public API `spec.owner` field

**Requirements:** REQ-1

Volume Get/List responses include `spec.owner`
(`{type: "COMPUTE_INSTANCE", reference}` — the architect-agreed typed
reference) for
VMaaS volumes; absent for
CaaS/CSI volumes. Public Create/Update requests containing `owner` are
rejected with `InvalidArgument` ("owner is system-managed"). See §4.3
for the response schema and §4.2 for the field definition.

## IC-2: Volume lifecycle and failure reasons from DataVolume conditions

**Requirements:** REQ-4

`Volumes.Get`/`List` report `status.state` transitions
(PENDING → CREATING → AVAILABLE / FAILED / DELETING / DELETED) driven by
the DataVolume lifecycle: every volume starts `PENDING` at creation; the
transition to `CREATING` is written by the operator when it picks up the
Volume CR and persisted in fulfillment through the regular volume
feedback controller loop; `status.message` carries the DataVolume
condition's reason and message on failure. See §4.1 (state mapping,
including the PENDING → CREATING transition) and §4.6 (failure table).

## IC-3: ComputeInstance create provisions disks through the Volume API

**Requirements:** REQ-2, REQ-3, REQ-6

Creating a ComputeInstance with disks (including an OCI registry disk
image) results in DataVolumes created by the osac-operator Volume
controller — not by the AAP playbook — named
`<ci-name>-root-disk` / `<ci-name>-disk-N` in the VM namespace, with the
root disk using `source.registry.url: docker://<image>` and
`pullMethod: node`, additional disks `source.blank`, both RWO with the
tenant-resolved StorageClass. The AAP job creates only the
VirtualMachine, Secrets, and optional Service. See §4.1.

## IC-4: ComputeInstance cascade delete removes volumes and DataVolumes

**Requirements:** REQ-5

Deleting a ComputeInstance deletes its Volume records, Volume CRs, and
DataVolumes: the CI delete flow's only storage action is calling
`Volumes.Delete` per disk through the private Volume API — record, CR,
and DataVolume teardown belong to the Volume API (storage-team
ownership); the Volume controller holds a finalizer until the DataVolume
is gone; the AAP deprovision job deletes the VM (DataVolume teardown no
longer in its scope). After instance deletion, `volumes list` no longer
shows the instance's volumes and the DataVolumes are absent from the
target namespace. See §4.1 "Deletion flow" for the ordered flow, the
finalizer chain, and the concurrency semantics.

## IC-5: Tier→StorageClass resolution and JIT creation move to the operator

**Requirements:** REQ-2, REQ-3

The operator's CI-controller storage preparation resolves each disk's
tier to exactly one tenant StorageClass (fail-closed on ambiguity, same
rules as today's AAP `tenant_storage_class` role) and creates JIT
StorageClasses for requested tiers without a mapping (Go port of
`osac.service.storage_provider`'s `ensure_storage_class`, provisioning
target `vmaas`), before DataVolume creation. A CI create with an
unmapped tier succeeds through this path where previously the AAP
playbook performed the JIT step. See §4.1 and §9.2.

## IC-6: Operator RBAC and installer target-cluster configuration

**Requirements:** REQ-2, REQ-3

The operator ClusterRole/chart clusterrole gains DataVolume
create/update/patch/delete. The installer exposes the target-cluster
kubeconfig Secret consumed by the operator (value shape per §9.1's
resolution). See §4.7.

## IC-7: `ocp_virt_vm` template contract change

**Requirements:** REQ-2

The published `ocp_virt_vm` template no longer creates, resolves storage
for, or deletes DataVolumes: `create_resources` drops the DataVolume
tasks, the per-disk StorageClass resolution, and the volume-ID
assertions; `delete_resources` drops DataVolume deletion and the
DataVolume label sweep; the top-level create playbook drops JIT storage
provisioning and tenant-StorageClass validation. The VM spec still
references DataVolumes by their existing names. ComputeClass template
authors who overrode `create_step_resources` must not recreate
DataVolumes — the disablement is part of the template's new published
version. See §4.1 and §8.

# 6. Alternatives Considered

*Note on REQ-2's coexistence guarantee:* the requirement that ownerless
(CaaS/CSI) volumes keep the existing vendor-provisioner path produces no
new or modified interface — it is the absence of change on an existing
path (§4.1) and is verified through that path's existing surface.

**Keep AAP as the DataVolume writer (via the networktask engine).**
Launch a DataVolume task as an AAP job from the Volume controller
through the existing `internal/networktask` engine, reusing AAP's
target-cluster credentials and the generic task playbook pattern.
Pros: no operator target-cluster access needed (resolves §9.1 outright);
reuses the proven job/result contract; the Ansible DV modules already
exist. Cons: provisioning remains outside a continuous reconcile loop —
jobs are one-shot, so status truthfulness (REQ-4) needs polling jobs or
a new feedback channel; REQ-2's "one path owned by the Volume API"
becomes "one path executed by AAP on the Volume API's behalf". This is a
viable fallback and the design's component contracts (Volume CR owner/
source/status, feedback mapping) are intentionally transport-agnostic
[User]. Rejection reason for the primary choice: the operator already
reconciles Volume CRs continuously; a job-based writer reintroduces the
polling problem that caused OSAC-7670.

**Fulfillment volume reconciler creates DataVolumes directly.**
Pros: provisioning sits next to the Volume record; no operator changes.
Cons: fulfillment holds only hub kubeconfigs today; the VM namespace
resolution lives in the operator (NetworkAttachment status); both would
be duplicated; and fulfillment would gain a second Kubernetes-writing
surface (target clusters), crossing its current hub-only boundary.
Rejected: duplicates placement logic and widens fulfillment's blast
radius for no structural gain.

**OCM-style spoke agent (ManifestWork).** A pull-model agent on every
target cluster applying manifests declared on the hub, with built-in
status feedback and Foreground garbage collection. Pros: no hub-held
target kubeconfigs; battle-tested cross-cluster GC semantics. Cons:
OSAC runs no agent on tenant target clusters; deploying and operating
one for a single resource type is a new platform component.
Rejected: disproportionate [Research: Domain 3].

**Do nothing (keep both paths).** Pros: zero work. Cons: OSAC-7670
remains (untruthful FAILED states), no ownership tracking, and the
foundation for OSAC-7318's attach/transfer capabilities cannot be built.
Rejected: this is the PRD's problem statement.

**CI controller stamps the target namespace onto Volume CRs** (instead
of the Volume controller reading the CI CR). Pros: the Volume controller
needs no CI-CR watch. Cons: two spec writers on the Volume CR; the
namespace is observed state that already belongs on the CI CR. Rejected
in favor of single-writer CRs; the Volume controller adds a
ComputeInstance-CR watch mapped to owned Volume CRs via the
`osac.openshift.io/volume-uuid` label and the CI CR's `diskVolumeIDs`.

# 7. Observability and Monitoring

No new Prometheus metrics. New Kubernetes surfaces: the
`DataVolumeProvisioned` condition (reasons `Created`, `Adopted`,
`CreateFailed`, `Deleting`) and events on the Volume CR
(`DataVolumeCreated`, `DataVolumeCreateFailed`, `DataVolumeDeleted`),
plus CI-CR events when job launch is held waiting for volumes. The
existing feedback bridge, Volume `status.state`/`status.message`, and
ComputeInstance `Provisioned` condition reasons remain the
user-visible signals; the `VolumeRegistrationPending` /
`VolumeRegistrationFailed` reasons are replaced by
volume-provisioning reasons (`WaitingForDataVolume`,
`DataVolumeProvisioningFailed`).

# 8. Impact and Compatibility

- **Additive proto changes** (new `VolumeSpec.owner`/`source`,
  `VolumeStatus.data_volume`): non-breaking for existing clients; the
  CSI driver's CreateVolume flow (ownerless) is unaffected. Regenerate
  once via `make -C proto generate`.
- **No DB migration**; JSONB fields are additive. Existing rows render
  without owner.
- **CaaS/CSI volumes** keep the `VendorProvisioner` path unchanged —
  the branch condition is `spec.owner`, which is absent for them.
- **AAP template versioning:** the `ocp_virt_vm` changes ship as a new
  published template version through the existing config-as-code
  pipeline; the deployment model is full install followed by CI creation
  (no rolling upgrade, no in-flight instances at cutover) [User], so no
  dual-path window exists. OSAC does not support in-place upgrades;
  within that constraint the change is additive (new CIs only [PRD:
  REQ-7]).
- **Supersession:** OSAC-6037's VMaaS physical-side-effect sections are
  superseded; its registration-recovery and record-cleanup contracts are
  retained. The integration-testing documentation
  (`docs/INTEGRATION-TESTING.md` and the osac-aap/osac-operator
  touched-area maps) must be updated in the same PRs as the suite
  changes.
- **Out-of-band-created DataVolumes:** adoption is keyed on name +
  `osac.openshift.io/storage-volume-id` annotation, so a DV created by
  an older template run is adopted rather than duplicated.

# 9. Open Questions

## 9.1 How does the operator obtain target-cluster access under provider networking?

The operator's existing `--remote-cluster-kubeconfig` mechanism is
documented as incompatible with provider networking, while AAP jobs
receive the target kubeconfig via launch credentials today. The design
proposes an installer-supplied kubeconfig Secret consumed through the
remote-cluster client; whether the incompatibility is fundamental (e.g.
per-tenant target routing) or incidental needs verification.

- **Owner:** osac-operator maintainers (Roy Golan)
- **Impact:** §4.1 (target-location resolution); if unresolvable, the
  AAP-transport alternative in §6 becomes the primary path.

## 9.2 What is the scope of porting JIT StorageClass creation to Go?

`osac.service.storage_provider` (tier→StorageClass JIT for the `vmaas`
target, including LVMS and CSP backends, block-encryption passphrase
handling) must be ported to the operator's storage preparation. Which
backend behaviors (LVMS TopoLVM objects, CSP partitioning) are in this
feature's scope versus follow-up storage-team work?

- **Owner:** Storage team (Akshay Nadkarni)
- **Impact:** §4.1, IC-5; determines the size of the operator change
  and whether any tier backends need temporary exclusions.

## 9.3 Should `VolumeSpec.source` be public, and what owner shape does OSAC-7318 expect?

This design makes `source` private (the ComputeInstance's `disk_image`
is the user-facing surface) and `owner` a typed reference
(`type` + `reference`). OSAC-7318's
standalone-volume and DataSource work may require a public source and a
richer attachment record.

- **Owner:** OSAC-7318 outcome owner (Roy Golan) with API owners
- **Impact:** §4.2/§4.3; flipping `source` to public later is additive,
  but aligning now avoids churn in the public type.

## 9.4 Does removing the LVMS node-topology placeholder affect existing validation?

The registration stops sending
`topology.segments["osac.io/node"] = "osac-volume-registration-pending"`
for owned volumes, and the private server's LVMS node-segment
requirement is waived for owned volumes. Confirm no other consumer
(fulfillment validation, tier resolution, metering) depends on the
placeholder.

- **Owner:** Storage team (Akshay Nadkarni)
- **Impact:** §4.2 validation rules; small but touches shared
  validation logic in `private_volumes_server.go`.

## 9.5 Do metering consumers need changes for DataVolume-backed volumes?

Volume status fields `state`, `vendor_volume_id`, and
`provisioned_size_gib` carry metering annotations; for VMaaS volumes,
`vendor_volume_id` will be unset and `provisioned_size_gib` derives from
the DataVolume. Confirm osac-metering's expectations for VMaaS disks.

- **Owner:** metering team
- **Impact:** §4.2 (`VolumeStatus` fields), §7; may require populating
  `provisioned_size_gib` from the DV's PVC request.

## 9.6 Is `owner.reference` the fulfillment record id or the resource name?

The architect-agreed owner shape (`type` + `reference`) does not pin
down what `reference` identifies. This design defines it as the
fulfillment record id (e.g. `ci-…`), for three reasons: the disk
registration — the only writer — runs before the ComputeInstance CR
exists (registration gates CR dispatch), so a CR name cannot be known at
write time; the operator resolves the owning CI CR by the
`osac.openshift.io/computeinstance-uuid` label, which carries the
fulfillment id — CR names are generated (`vm-*`) and never carry the
tenant-facing name, so name-based matching is impossible on the cluster
side; and fulfillment-side logic (registration recovery, cleanup,
tenancy checks) keys on record ids. A tenant-facing name, if wanted for
readability in volume get/list, would be added alongside — id + name
pairs are the API's existing reference convention
(`DiskImageReference`, `StorageTierReference`).

- **Owner:** Storage team architect (owner-shape agreement thread)
- **Impact:** §4.2 field definition and the operator's owner-to-CR
  resolution (label lookup). Unchanged if id is confirmed; a
  name-based reference would add a fulfillment lookup hop to every
  operator reconcile.

---

## Provenance

Committed: commit @ design 0.15.0 - 922de34, workspace design/OSAC-7749 @ eb7f6ab

> Authoring phases not recorded this session (commit-time snapshot only).

<!-- ai-workflow-provenance:{"schema_version":1,"provenance_kind":"commit_only","workflow":"design","workflow_version":"0.15.0","ai_workflows":"922de34","source_repo":"eb7f6ab","source_repo_branch":"design/OSAC-7749","commits_behind_main":0,"commits_ahead_main":0,"main_ref":"main","phases":["commit"],"authoring_modes":["skill"],"context_changed":false,"origin_untracked":false} -->
