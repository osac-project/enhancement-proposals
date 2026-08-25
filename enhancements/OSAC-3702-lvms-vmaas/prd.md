# LVMS Node-Local Storage Backend for VMaaS

| Field       | Value   |
|-------------|---------|
| Author(s)   | Zoltan Szabo |
| Jira        | [OSAC-3702](https://redhat.atlassian.net/browse/OSAC-3702) |
| Date        | 2026-08-25 |

## Problem Statement

The OSAC storage control plane provisions tenant storage only from network-attached arrays — VAST today, and Pure FlashBlade via OSAC-2117. Single-node development environments have no such array; the only storage available is the local disk on the node. In those environments OSAC cannot offer any managed persistent storage, so operators fall back to configuring node-local storage by hand — outside OSAC — losing the opaque storage tier, the central inventory, and the single uniform driver that OSAC provides everywhere else. Without a node-local backend, OSAC cannot serve single-node development VMaaS deployments as a self-service platform.

## In Scope

*This release delivers LVMS for single-node VMaaS only. See Out of Scope for what is deferred to a future feature.*

- LVMS (node-local LVM) as a storage backend in the OSAC storage control plane, exposed through the same opaque storage tier and `osac-csi-driver` model defined in OSAC-2872 — tenants see a `local` tier, not LVMS internals.
- VMaaS onboarding installs and configures LVMS on the single-node cluster (hub == tenant) during tenant onboarding, so node-local storage is ready without manual setup.
- Volumes on the `local` tier are provisioned on node-local LVM volume groups. Because the storage is node-local, a volume is provisioned when its consuming workload is scheduled and is then pinned to that node — the standard Kubernetes behavior for node-local storage.
- ComputeInstance (VMaaS) workloads can consume the `local` tier for boot and additional disks using tenant-resolved StorageClasses.
- End-to-end volume lifecycle: provision → mount → data round-trips → delete releases both the OSAC inventory record and the underlying node-local volume. This end-to-end flow is the definition of done for this release.
- Central inventory tracking of `local`-tier volumes (tenant, tier, state, size), consistent with OSAC-2872.
- Clear, predictable failure when a node has insufficient local capacity to satisfy a request.
- E2E test covering the single-node VMaaS `local`-tier provision → mount → cleanup flow.
- Administrator documentation (node LVM prerequisites, registering the LVMS backend and `local` tier) and user documentation (consuming the `local` tier).

## Out of Scope

Deferred to a future feature (current scope is single-node VMaaS only):

- **CaaS / multi-cluster LVMS** — provisioning node-local storage on separate tenant clusters. CaaS tenant onboarding is tracked under OSAC-1332.
- **Multi-node capacity-aware scheduling** — selecting among multiple candidate nodes by free local capacity.
- **Volume expansion** for `local`-tier volumes.
- **Quota** enforcement for node-local storage.
- **Network / array backends** — VAST and Pure FlashBlade are already covered (OSAC-2872, OSAC-2117).
- **BMaaS storage integration.**

## User Stories

### Cloud Provider Admin

- As a Cloud Provider Admin, I want to register LVMS as a storage backend and define a `local` storage tier with LVMS as the provider, so that VMaaS onboarding provisions node-local storage from the correct backend without a remote array.
- As a Cloud Provider Admin, I want LVMS installed and configured automatically on the single-node cluster during VMaaS tenant onboarding, so that node-local storage is ready without manual intervention.
- As a Cloud Provider Admin, I want `local`-tier volumes tracked in the same central inventory as other backends, so that I can account for node-local storage usage the same way.
- As a Cloud Provider Admin, I want a clear error and a blocked status when a volume cannot be provisioned because the node lacks local capacity, so that I can add capacity and retry deterministically.

### Tenant Admin / Tenant User

- As a Tenant Admin or Tenant User, I want to attach a disk to a ComputeInstance using the `local` tier and have it provisioned on node-local disk without seeing any LVMS internals, so that I consume node-local storage through the same opaque storage-tier abstraction as remote backends.
- As a Tenant Admin or Tenant User, I want a `local`-tier disk to follow the standard behavior for node-local storage — provisioned when my ComputeInstance is scheduled and then kept on that node — so that behavior is predictable, accepting that such a ComputeInstance is pinned to its node.
- As a Tenant Admin or Tenant User, I want deleting a ComputeInstance to clean up its node-local volume and inventory record, so that storage is released and nothing leaks.

### Cloud Infrastructure Admin

- As a Cloud Infrastructure Admin, I want to prepare nodes with the local disks and volume group that LVMS carves volumes from, so that the `local` tier has capacity to provision.

## Assumptions

- The OSAC storage control plane (OSAC-2872) — Volume API, tier resolution, central inventory, and `osac-csi-driver` — supports a new backend provider with additive changes only. LVMS reuses this model rather than introducing a parallel storage path.
- In the single-node scope, the cluster where tenants run is the same cluster that runs the OSAC control plane (hub == tenant), so no cross-cluster provisioning is required in this release.
- Nodes have local disks and a volume group available for LVMS to consume; provisioning that hardware and capacity is a cluster/infrastructure prerequisite handled outside OSAC.
- LVMS targets single-node development environments where remote storage arrays are unavailable or unnecessary; it does not aim for feature parity with network backends (in particular, node-local volumes do not move between nodes).
- The LVMS installation tooling is available to the VMaaS onboarding automation.

## Dependencies

- **OSAC-2872 (Storage Control Plane):** provides the Volume API, tier resolution, central inventory, and `osac-csi-driver` that this backend plugs into. Must be in place for the `local` tier to resolve and provision end-to-end.
- **VMaaS tenant onboarding automation:** extended to install and configure LVMS on the single-node cluster during onboarding.
- **osac-csi-driver:** `local`-tier provisioning and mount route through the same driver as other backends.

---

## Provenance

Authored: draft @ prd 0.8.0 - 7efcedb, workspace fix/OSAC-3985-tier-guard-before-provision @ be68f168a

<!-- ai-workflow-provenance:{"schema_version":1,"provenance_kind":"session","workflow":"prd","workflow_version":"0.8.0","ai_workflows":"7efcedb","source_repo":"be68f168a","source_repo_branch":"fix/OSAC-3985-tier-guard-before-provision","commits_behind_main":0,"commits_ahead_main":2,"main_ref":"main","phases":["draft"],"authoring_modes":["skill"],"context_changed":false,"origin_untracked":false} -->
