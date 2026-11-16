# Volume ownership and disk lifecycle for VMaaS ComputeInstances

| Field       | Value                       |
|-------------|-----------------------------|
| Author(s)   | Roy Golan (rgolan@redhat.com) |
| Jira        | https://redhat.atlassian.net/browse/OSAC-7318 |
| Date        | 2026-11-05                  |

## Problem Statement

A tenant user can today create a VMaaS ComputeInstance with a boot disk and
additional data disks, choosing each disk's size and storage tier and selecting
an existing DiskImage for the boot disk. OSAC records the disks as
tenant-scoped volumes and correlates them with the ComputeInstance, but a
tenant cannot see the current volume-to-VM use or manage it after creation: the
disk list is fixed, an existing volume cannot be added to a VM, and deleting a
volume can affect storage that a VM is using.

For this PRD, **create volume** provisions storage, **add disk** attaches a
volume to a ComputeInstance, **remove disk** detaches it while retaining the
volume, and **delete volume** destroys the storage. Without a visible,
manageable relationship between a volume and the ComputeInstance using it,
tenants cannot safely add or move storage or know whether deletion is safe.

## In Scope

- A tenant can see in Volume Get/List which ComputeInstance currently has a
  volume added as a disk.
- A volume is used by at most one ComputeInstance at a time. Sharing a volume
  between two VMs is not supported. [Clarify: R1.Q1]
- The volume and ComputeInstance must belong to the same tenant and project.
  [Clarify: R5.Q4]
- A volume can be **added as a disk** to a ComputeInstance, whether the disk is
  declared when the ComputeInstance is created or added later while the VM is
  running.
- A volume can be **removed as a disk** from a ComputeInstance, including while
  the VM is running. [Clarify: R2.Q2]
- A volume can move between ComputeInstances by removing it as a disk from one
  and adding it as a disk to another.
- A volume can be moved only between ComputeInstances on the same VMaaS cluster.
  A cross-cluster add request is rejected with a clear reason. [Clarify: R6.Q2]
- A volume can be **deleted** as a distinct action that removes the storage from
  the VM's cluster and from the storage array. Delete is refused while the
  volume is used by a ComputeInstance; the tenant must remove the disk first.
  [Clarify: R1.Q2]
- After an add or remove succeeds, the volume's reported ComputeInstance use
  matches the disk configuration visible on that ComputeInstance.
- If add or remove fails, the last confirmed volume-to-ComputeInstance
  association remains visible, the failure reason is shown, and the tenant can
  retry the operation. [Clarify: R5.Q3]
- The existing boot-disk image-selection behavior remains available when the
  boot disk is backed by a Volume. Users select a DiskImage as they do today;
  they do not provide a raw registry URL. [Clarify: R5.Q2]
- VMaaS is expected to delete the volumes currently added to a ComputeInstance
  when that instance is deleted. Removing a disk and adding the volume to a
  different ComputeInstance transfers the current relationship, so deleting the
  former instance does not delete or block a volume now used by the latter.
  A separate warning or confirmation step is not required by this Feature.
  This is a tentative lifecycle assumption for independently created and
  transferred volumes. [Clarify: R5.Q1, R6.Q1]
- A tenant can see whether a volume is available and not used by any
  ComputeInstance, in use by a named ComputeInstance, being deleted, or failed
  with a reason. Existing Volume lifecycle states remain visible; the
  ComputeInstance-use relationship is also visible through Volume Get/List and
  the `osac` CLI. Intermediate operation progress is surfaced as events.
- A delete that fails leaves the volume in a failed state with a reason, and the
  tenant can retry the delete.
- The Fulfillment API and the `osac` CLI expose adding a disk, removing a disk,
  and deleting a volume.

## Out of Scope

- Sharing a single volume between two ComputeInstances, such as a shared data
  volume for a cluster or a two-VM application.
- New image-source options, raw registry URLs in the ComputeInstance request,
  and image sources for data disks. OSAC DiskImages, snapshots, and cloning an
  existing volume are not added by this Feature.
- Moving volumes between VMaaS clusters.
- Read-write and read-only volume modes, and booting a ComputeInstance from an
  existing persisted volume — tracked separately as OSAC-5903 and OSAC-4599.
- Web UI support for adding, removing, or deleting volumes.
- Quota behavior. This Feature does not add or define quota enforcement.
- Placement, scheduling, or late binding of a volume to a cluster; a
  ComputeInstance's cluster remains fixed.
- BMaaS and CaaS disk-lifecycle workflows. The volume relationship model may
  be reusable by those services, but their user journeys are not delivered here.

## User Stories

### Cloud Provider Admin

- As a Cloud Provider Admin, I want volume ownership and use to be visible in
  OSAC regardless of which storage driver a VMaaS cluster runs, so that storage
  is observable through one supported service instead of vendor-specific side
  channels.

### Cloud Infrastructure Admin

- As a Cloud Infrastructure Admin, I want to see which ComputeInstance is using
  each volume and whether the volume is ready, so that I can diagnose tenant
  storage problems.

### Tenant Admin

- As a Tenant Admin, I want adding a disk to be refused when the volume and the
  ComputeInstance are in different projects, so that storage remains within my
  authorized project scope. Cross-tenant requests are rejected by tenant
  isolation.

### Tenant User

- As a Tenant User, I want to see which ComputeInstance currently uses each
  volume, so that I can manage and move my storage safely.
- As a Tenant User, I want to add an existing volume as a disk to a new or
  running ComputeInstance, so that I can use pre-provisioned storage without
  recreating the volume.
- As a Tenant User, I want to keep selecting an existing DiskImage for a
  ComputeInstance boot disk when that disk is Volume-backed, so that the current
  boot-image workflow continues to work.
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
- As a Tenant User, I want a failed add or remove operation to preserve the last
  confirmed disk association and be retryable, so that I can recover without
  losing track of which VM is using the volume. [Clarify: R5.Q3]

## Assumptions

- VMaaS continues to select boot images through the existing DiskImage
  mechanism; this Feature does not add image sources for data disks.
- A ComputeInstance's target cluster is known when the instance is provisioned
  and does not change, so no placement decision is needed to add or remove a
  disk.
- VM storage capabilities continue to be provided by the target cluster; this
  Feature does not add a storage backend.
- The tentative delete-with-current-ComputeInstance policy for independently
  created and transferred volumes remains an open product question. This Feature
  does not require a separate pre-delete warning or confirmation step.

## Dependencies

- **Volume API:** existing volume create and delete, lifecycle reporting, and
  storage tier selection are reused rather than redefined. This Feature does
  not assert existing quota enforcement or define quota behavior.
- **VMaaS ComputeInstance lifecycle:** owns deletion of volumes currently added
  to a ComputeInstance under the tentative policy above.
- **VMaaS storage on the target cluster:** supports adding and removing disks
  from a ComputeInstance.
- **OSAC-4884:** provides the common Volume API attach/detach capability.
- **OSAC-5888:** tracks adding pre-existing volumes at ComputeInstance creation
  time; its current Feature description says those volumes remain reusable
  after VM deletion.
- **OSAC-5889:** tracks runtime add/remove disk for existing ComputeInstances.
  Its current VM-deletion boundary differs from the tentative policy in this
  PRD and remains to be aligned.

---

## Provenance

Authored: draft @ prd 0.11.5 - 70405a6, workspace vmaas-volume-api @ 21e5dba7c (22 behind origin/main)
Final: respond @ prd 0.11.5 - 70405a6, workspace vmaas-volume-api @ 21e5dba7c (194 behind origin/main)

> Context changed between draft and respond.

<!-- ai-workflow-provenance:{"schema_version":1,"provenance_kind":"session","workflow":"prd","workflow_version":"0.11.5","ai_workflows":"70405a6","source_repo":"21e5dba7c","source_repo_branch":"vmaas-volume-api","commits_behind_main":194,"commits_ahead_main":0,"main_ref":"main","phases":["draft","draft","respond","respond","respond","respond"],"authoring_modes":["skill"],"context_changed":true,"origin_untracked":false} -->
