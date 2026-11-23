# VM snapshots and in-place restore

| Field | Value |
|-------|-------|
| Author(s) | Tzif |
| Jira | [OSAC-55](https://redhat.atlassian.net/browse/OSAC-55) |
| Date | 2026-11-23 |

## Problem Statement

Tenants can update their VMs, but OSAC gives them no way to save a recovery point first. If an upgrade fails, they cannot roll the VM's disks and configuration back to their pre-upgrade state through OSAC.

## In Scope

- In 0.6, tenants can create, list, inspect, and delete snapshots of their own VMs and request a restore through the OSAC console, API, and CLI. Deleting a VM also deletes its snapshots. [VM snapshots proposal](https://github.com/osac-project/enhancement-proposals/pull/48)
- Tenants can snapshot a running or stopped VM. For a running VM, KubeVirt attempts to quiesce the filesystems through the QEMU Guest Agent, using VSS on supported Windows guests. Successful quiescing provides filesystem consistency. If the agent is unavailable, the snapshot can still succeed with crash consistency. A stopped VM is captured offline.
- Tenants can see snapshot and restore progress and errors. For a snapshot, they can see whether it is ready to restore, which disks it includes or excludes, and KubeVirt's indications about guest-agent participation or a quiescing failure.
- The tenant must stop the original VM and wait until it is fully stopped before requesting a restore. If the VM is still running or shutting down, OSAC rejects the request before changing any disk and tells the tenant to retry once the VM is stopped.
- A tenant can restore a ready snapshot to its original VM. Restore overwrites the captured persistent boot and data disks with their snapshot contents and restores the captured VM configuration, including its instance type (ComputeClass), CPU, configured memory, devices, and network interfaces.
- If a captured disk was later removed from the VM, restore reattaches it with its snapshot-time data. OSAC associates its Volume record with the restored disk. If a disk was added after the snapshot and is still attached, restore detaches it from this VM, preserves its current data, and shows its Volume as detached from this VM. If OSAC cannot preserve such a disk, it rejects the restore before changing any disk and identifies the affected Volume.
- If the captured interfaces conflict with the VM's fixed tenant network attachment, OSAC rejects the restore before changing any disk. The error identifies the conflicting attachment.
- Once OSAC accepts a snapshot or restore, it rejects conflicting tenant requests on the same VM or affected Volumes. These include another snapshot or restore, power changes, VM or disk resize, disk attachment changes, and deletion of the VM, an affected Volume, or the snapshot being restored. OSAC also rejects a snapshot or restore if a conflicting change is already underway. Tenants can inspect progress, see which operation caused the conflict, and retry when the resources are ready.
- Before OSAC reports restore success or accepts another conflicting change, it adopts the restored VM settings as the desired configuration for the ComputeInstance. Each affected Volume record must identify the correct disk and reflect its actual attachment and capacity on the workload cluster. For example, if a tenant takes a snapshot of a small VM, resizes it to large, then restores the snapshot, the VM starts with the small instance type. Subsequent resizes, VM snapshots, and supported Volume expansions use the restored state.

## Out of Scope

- Standalone volume snapshots, including creating, listing, deleting, and restoring snapshots of an individual Volume. [OSAC-48](https://redhat.atlassian.net/browse/OSAC-48)
- Scheduled or event-triggered snapshots, cross-cluster transfer, and long-term archival.
- Cloning a VM from a snapshot, exporting a snapshot as an image, and custom guest application hooks. [VM snapshots proposal](https://github.com/osac-project/enhancement-proposals/pull/48)
- Dedicated provider storage monitoring and OSAC per-VM snapshot limits. Existing workload-cluster resource quotas apply.

## User Stories

### Tenant User

- As a Tenant User, I want to snapshot my VM before an upgrade so that I have a recovery point if the upgrade fails.
- As a Tenant User, I want to inspect my VM's snapshots so that I can select a ready recovery point that includes the disks I need.
- As a Tenant User, I want to restore my VM from that recovery point after I stop it so that I can boot it with its earlier configuration and data.
- As a Tenant User, I want normal lifecycle operations—such as resizing compute, expanding volumes, and taking new snapshots—to work on a restored VM so that I can continue operating it seamlessly after a rollback.
- As a Tenant User, I want to delete an obsolete snapshot so that I can discard a recovery point I no longer need.

### Cloud Provider Admin

- As a Cloud Provider Admin, I want deleting a VM to remove its snapshots so that they do not continue to consume storage.

## Assumptions

- The draft includes the CLI alongside the API and console based on the tentative 0.6 CLI scope.

## Dependencies

- Disk coverage includes all persistent boot and data disks on a workload-cluster StorageClass whose CSI driver supports snapshot and restore and has a matching VolumeSnapshotClass. OSAC-55 can ship independently of the standalone volume snapshot API and UI in OSAC-48. [KubeVirt snapshot and restore guide](https://kubevirt.io/user-guide/storage/snapshot_restore_api/)

---

## Provenance

Authored: revise @ prd 0.11.5 - ceab343, workspace main @ e5de8dc4a
Phases: draft, revise, revise, revise, revise, revise, revise, revise, revise

<!-- ai-workflow-provenance:{"schema_version":1,"provenance_kind":"session","workflow":"prd","workflow_version":"0.11.5","ai_workflows":"ceab343","source_repo":"e5de8dc4a","source_repo_branch":"main","commits_behind_main":0,"commits_ahead_main":251,"main_ref":"main","phases":["draft","revise","revise","revise","revise","revise","revise","revise","revise"],"authoring_modes":["skill"],"context_changed":false,"origin_untracked":false} -->
