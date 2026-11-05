# Volume ownership and disk lifecycle for VMaaS ComputeInstances

| Field       | Value                       |
|-------------|-----------------------------|
| Author(s)   | Roy Golan (rgolan@redhat.com) |
| Jira        | https://redhat.atlassian.net/browse/OSAC-7318 |
| Date        | 2026-11-05                  |

## Problem Statement

A tenant user can today create a VMaaS ComputeInstance with a boot disk and
additional data disks, choosing each disk's size and storage tier and booting
from an OCI registry image. OSAC already records each disk as a tenant-scoped
volume, and deleting the ComputeInstance deletes those volumes. What the tenant
cannot do is manage that storage: the disk list is fixed at creation, no volume
says which ComputeInstance uses it, an existing volume cannot be added to a VM,
and deleting a volume does not remove the storage the VM actually runs on.

The gap matters because every other VMaaS storage journey the roadmap calls for
— attaching volumes at creation, attaching and detaching at runtime, booting
from a persisted volume, and moving storage between VMs — assumes a volume that
OSAC knows is owned by a specific ComputeInstance and knows is safe to destroy.
Without that model, tenants have no supported way to prepare storage before a VM
exists, to move storage to a rebuilt VM, or to know whether deleting a volume is
safe.

## In Scope

- Every volume records the ComputeInstance that owns or is using it, and a
  tenant can see that in volume list and get.
- A volume is used by at most one ComputeInstance at a time. Sharing a volume
  between two VMs is not supported. [Clarify: R1.Q1]
- A volume can be **added as a disk** to a ComputeInstance, whether the disk is
  declared when the ComputeInstance is created or added later while the VM is
  running.
- A volume can be **removed as a disk** from a ComputeInstance, including while
  the VM is running. [Clarify: R2.Q2]
- A volume can move between ComputeInstances by removing it as a disk from one
  and adding it as a disk to another.
- A volume can be **deleted** as a distinct action that removes the storage from
  the VM's cluster and from the storage array. Delete is refused while the
  volume is used by a ComputeInstance; the tenant must remove the disk first.
  [Clarify: R1.Q2]
- Adding or removing a disk keeps the volume and the storage the VM actually
  runs on in step, so a tenant never sees a volume report a state the VM does
  not reflect.
- Disk source support: a disk keeps the options tenants have today, including
  declaring content from an OCI registry image, such as
  `quay.io/my-org/golden-image`, when the disk is backed by an OSAC volume.
  [Clarify: R4.Q1]
- Deleting a ComputeInstance continues to delete the volumes provisioned with
  it, so no tenant storage is orphaned. VMaaS owns that behavior.
- A tenant can see whether a volume is available and not used by any
  ComputeInstance, in use by a named ComputeInstance, being deleted, or failed
  with a reason. Intermediate progress is surfaced as events.
- A delete that fails leaves the volume in a failed state with a reason, and the
  tenant can retry the delete.
- The Fulfillment API and the `osac` CLI expose adding a disk, removing a disk,
  and deleting a volume.

## Out of Scope

- Sharing a single volume between two ComputeInstances, such as a shared data
  volume for a cluster or a two-VM application.
- Disk sources beyond what VMaaS supports today: OSAC disk images, snapshots,
  and cloning an existing volume.
- Read-write and read-only volume modes, and booting a ComputeInstance from an
  existing persisted volume — tracked separately as OSAC-5903 and OSAC-4599.
- Console support for adding, removing, or deleting volumes.
- Quota semantics: enforcement follows existing Volume API behavior and is not
  changed here.
- Placement, scheduling, or late binding of a volume to a cluster; a
  ComputeInstance's cluster remains fixed.
- Bare metal and CaaS storage journeys beyond reuse of the same volume model.

## User Stories

### Cloud Provider Admin

- As a Cloud Provider Admin, I want volume ownership and use to be visible in
  OSAC regardless of which storage driver a VMaaS cluster runs, so that storage
  is observable through one supported service instead of vendor-specific side
  channels.

### Cloud Infrastructure Admin

- As a Cloud Infrastructure Admin, I want a volume to be diagnosable both as an
  OSAC volume and as storage on the VM's cluster, so that I can investigate a
  tenant storage problem whether the vendor driver was installed by OSAC or by
  the customer.

### Tenant Admin

- As a Tenant Admin, I want adding a disk to be refused when the volume and the
  ComputeInstance belong to different tenants, so that storage cannot cross
  tenant boundaries.

### Tenant User

- As a Tenant User, I want the storage created for my ComputeInstance's disks to
  appear as volumes owned by that ComputeInstance, so that I can tell which
  storage belongs to which VM.
- As a Tenant User, I want a disk I add to a running VM to keep the content
  options I have today, such as starting from a golden image at
  `quay.io/my-org/golden-image`, so that I can add application data storage
  without rebuilding the VM.
- As a Tenant User, I want to remove a disk from a running VM without destroying
  the volume, so that I can rearrange storage without losing data.
- As a Tenant User, I want to move a volume from an old VM to a rebuilt one by
  removing the disk and adding it to the new VM, so that my data follows the
  workload.
- As a Tenant User, I want deleting a volume that a VM is still using to be
  refused with a clear reason, so that I cannot destroy storage a running
  workload depends on.
- As a Tenant User, I want to see whether a volume is available, in use by a
  named VM, being deleted, or failed with a reason, so that I know when it is
  safe to use or delete without inspecting the cluster.
- As a Tenant User, I want a failed delete to be retryable, so that a transient
  storage problem does not leave me stuck with storage I cannot remove.

## Assumptions

- The only disk source VMaaS supports today is an OCI registry image reference,
  and it stays the only source this milestone must preserve.
- A ComputeInstance's target cluster is known when the instance is provisioned
  and does not change, so no placement decision is needed to add or remove a
  disk.
- Vendor storage drivers on the VM's cluster continue to perform the actual
  presentation of storage to a running VM; OSAC does not replace them.
- Tenant storage quota is enforced today by the Volume API, so adding a disk or
  creating a volume inherits that enforcement without new design.

## Dependencies

- **Volume API:** existing volume create and delete, quota enforcement, and
  storage tier selection are reused rather than redefined.
- **VMaaS ComputeInstance lifecycle:** owns deletion of the volumes provisioned
  with a ComputeInstance. This PRD states the user-visible outcome, not the
  mechanism.
- **Storage drivers on the VM's cluster:** perform the attach and detach that
  make an added or removed disk take effect on a running VM.
- **OSAC-5888 and OSAC-5889:** implementation tracks for the create-time and
  runtime disk journeys described here. They do not define separate user-facing
  scope.

---

## Provenance

Authored: draft @ prd 0.11.5 - 70405a6, workspace vmaas-volume-api @ 21e5dba7c (22 behind origin/main)
Phases: draft, draft

<!-- ai-workflow-provenance:{"schema_version":1,"provenance_kind":"session","workflow":"prd","workflow_version":"0.11.5","ai_workflows":"70405a6","source_repo":"21e5dba7c","source_repo_branch":"vmaas-volume-api","commits_behind_main":22,"commits_ahead_main":0,"main_ref":"main","phases":["draft","draft"],"authoring_modes":["skill"],"context_changed":false,"origin_untracked":false} -->
