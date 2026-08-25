# LVMS Node-Local Storage Backend for VMaaS

| Field       | Value   |
|-------------|---------|
| Author(s)   | Zoltan Szabo |
| Jira        | [OSAC-3702](https://redhat.atlassian.net/browse/OSAC-3702) |
| Date        | 2026-08-25 |

## Problem Statement

The OSAC storage control plane provisions tenant storage only from network-attached arrays — VAST today, and Pure FlashBlade via OSAC-2117. Single-node development environments have no such array; the only storage available is the local disk on the node. In those environments OSAC cannot offer any managed persistent storage, so operators fall back to configuring node-local storage by hand — outside OSAC — losing the opaque storage tier, the central inventory, and the single uniform driver that OSAC provides everywhere else. Without a node-local backend, OSAC cannot serve single-node development VMaaS deployments as a self-service platform.

## In Scope

*This release delivers LVMS as a `local` storage tier for single-node VMaaS only, extending OSAC's existing storage offering (OSAC-2872) with a node-local backend. It uses the same storage tier and onboarding path as remote backends, so no new provisioning or install path is introduced. See Out of Scope for what is deferred to a future feature.*

- **A `local` storage tier backed by node-local storage.** Platform admins register LVMS as a backend and define a `local` tier; tenants see an opaque tier, not LVMS internals — the same experience, tier model, and onboarding path as remote backends (OSAC-2872).
- **Automatic setup during VMaaS onboarding.** Onboarding a single-node deployment configures the `local` tier end to end, leaving a usable local storage path ready without manual steps.
- **Node-local provisioning behavior.** A `local`-tier volume is provisioned when its ComputeInstance is scheduled and then stays on that node; consequently a ComputeInstance using `local` storage is pinned to its node.
- **ComputeInstance consumption.** VMaaS workloads can use the `local` tier for boot and additional disks.
- **Full volume lifecycle with cleanup.** Provision → mount → data round-trips → delete; deleting a ComputeInstance releases both its node-local storage and its inventory record, so capacity is not leaked. This end-to-end flow is the definition of done for this release.
- **Inventory tracking.** `local`-tier volumes are tracked centrally (tenant, tier, state, size), consistent with other backends.
- **Predictable capacity failure.** When a node lacks local capacity, provisioning fails predictably and leaves no partial volume or inventory record.
- **Interfaces.** The `local` tier appears through the same tenant-facing channels (console and CLI) as other storage tiers; no LVMS-specific UI is added.
- **Test and documentation.** An E2E test covers the single-node provision → mount → cleanup flow (including that the volume stays on its scheduled node); admin docs cover node prerequisites and backend/tier registration; user docs cover consuming the `local` tier.

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
- In the single-node scope, the control plane and tenant workloads share one cluster, so no cross-cluster provisioning is required in this release.
- Nodes have local disks and a volume group available for LVMS to consume; provisioning that hardware and capacity is a cluster/infrastructure prerequisite handled outside OSAC.
- LVMS targets single-node development environments where remote storage arrays are unavailable or unnecessary; it does not aim for feature parity with network backends (in particular, node-local volumes do not move between nodes).
- The LVMS installation tooling is available to the VMaaS onboarding automation.

## Dependencies

- **OSAC-2872 (Storage Control Plane):** provides the storage tier model, driver, central inventory, and onboarding path this backend plugs into. Must be in place for the `local` tier to provision end to end.
- **VMaaS tenant onboarding automation:** extended to install and configure LVMS on the single-node cluster during onboarding.

---

## Provenance

Authored: draft @ prd 0.8.0 - 7efcedb, workspace main @ 62ad8a38b

<!-- ai-workflow-provenance:{"schema_version":1,"provenance_kind":"session","workflow":"prd","workflow_version":"0.8.0","ai_workflows":"7efcedb","source_repo":"62ad8a38b","source_repo_branch":"main","commits_behind_main":0,"commits_ahead_main":0,"main_ref":"main","phases":["draft"],"authoring_modes":["skill"],"context_changed":false,"origin_untracked":false} -->
