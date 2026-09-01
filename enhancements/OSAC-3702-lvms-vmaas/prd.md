# LVMS Node-Local Storage Backend for VMaaS

| Field       | Value   |
|-------------|---------|
| Author(s)   | Zoltan Szabo |
| Jira        | [OSAC-3702](https://redhat.atlassian.net/browse/OSAC-3702) |
| Date        | 2026-08-25 |

## Problem Statement

The OSAC storage control plane provisions tenant storage only from network-attached arrays — VAST today, and Pure FlashBlade via OSAC-2117. Single-node development environments have no such array; the only storage available is the local disk on the node. In those environments OSAC cannot offer any managed persistent storage, so operators fall back to configuring node-local storage by hand — outside OSAC — losing the opaque storage tier, the central inventory, and the single uniform driver that OSAC provides everywhere else. Without a node-local backend, OSAC cannot serve single-node development, testing, and CI/CD VMaaS deployments as a self-service platform. This feature targets those environments specifically — not production workloads.

## In Scope

*This release adds LVMS as a node-local storage backend for single-node VMaaS, extending OSAC's existing storage offering (OSAC-2872). Admins register LVMS and define an LVMS-backed tier; it uses the same tier model and onboarding path as remote backends, so no new provisioning or install path is introduced. See Out of Scope for what is deferred to a future feature. LVMS is a Block backend type; the tier name is admin-defined and is not a protocol or backend-type designation.*

- **An LVMS-backed storage tier backed by node-local storage.** Platform admins register LVMS as a backend and define a tier backed by it; tenants see an opaque tier, not LVMS internals — the same experience, tier model, and onboarding path as remote backends (OSAC-2872).
- **Automatic setup during VMaaS onboarding.** Onboarding a single-node deployment configures the LVMS-backed tier end to end, leaving a usable local storage path ready without manual steps.
- **Node-local provisioning behavior.** An LVMS-backed volume is provisioned when its ComputeInstance is scheduled and then stays on that node; consequently a ComputeInstance using LVMS-backed storage is pinned to its node.
- **ComputeInstance consumption.** VMaaS workloads can use the LVMS-backed tier for boot and additional disks.
- **Full volume lifecycle with cleanup.** Provision → mount → data round-trips → delete; deleting a ComputeInstance releases both its node-local storage and its inventory record, so capacity is not leaked. This end-to-end flow is the definition of done for this release.
- **Inventory tracking.** LVMS-backed volumes are tracked centrally (tenant, tier, state, size), consistent with other backends.
- **Predictable capacity failure.** When a node lacks local capacity, provisioning fails predictably and leaves no partial volume or inventory record.
- **Interfaces.** The LVMS-backed tier appears through the same tenant-facing channels (console and CLI) as other storage tiers; no LVMS-specific UI is added.
- **Test and documentation.** An E2E test covers the single-node provision → mount → cleanup flow (including that the volume stays on its scheduled node); admin docs cover node prerequisites and backend/tier registration; user docs cover consuming the LVMS-backed tier.

## Out of Scope

Deferred to a future feature (current scope is single-node VMaaS only):

- **CaaS / multi-cluster LVMS** — provisioning node-local storage on separate tenant clusters. CaaS tenant onboarding is tracked under OSAC-1332.
- **Multi-node capacity-aware scheduling** — selecting among multiple candidate nodes by free local capacity.
- **Volume expansion** for LVMS-backed volumes.
- **Quota** enforcement for node-local storage.
- **Network / array backends** — VAST and Pure FlashBlade are already covered (OSAC-2872, OSAC-2117).
- **BMaaS storage integration.**
- **Production use** — LVMS as a node-local backend is not intended or supported for production workloads. Once a deployment profile flag is available (see Dependecies), LVMS will only be registerable in development/test profile installations.

## User Stories

### Cloud Provider Admin

- As a Cloud Provider Admin, I want to register LVMS as a storage backend and define a storage tier with LVMS as the provider, so that VMaaS onboarding provisions node-local storage from the correct backend without a remote array.
- As a Cloud Provider Admin, I want LVMS configured automatically on the single-node cluster during VMaaS tenant onboarding, so that node-local storage is ready without manual intervention.
- As a Cloud Provider Admin, I want LVMS-backed volumes tracked in the same central inventory as other backends, so that I can account for node-local storage usage the same way.
- As a Cloud Provider Admin, I want volume provisioning to fail predictably when a node lacks local capacity — with no partial volume or inventory record left behind — so that I can resolve the capacity issue and reprovision.

### Tenant Admin / Tenant User

- As a Tenant Admin or Tenant User, I want to attach a disk to a ComputeInstance using an LVMS-backed tier and have it provisioned on node-local disk without seeing any LVMS internals, so that I consume node-local storage through the same opaque storage-tier abstraction as remote backends.
- As a Tenant Admin or Tenant User, I want the LVMS-backed tier disk to follow the standard behavior for node-local storage — provisioned when my ComputeInstance is scheduled and then kept on that node — so that behavior is predictable, accepting that such a ComputeInstance is pinned to its node.
- As a Tenant Admin or Tenant User, I want deleting a ComputeInstance to clean up its node-local volume and inventory record, so that storage capacity is released.

### Cloud Infrastructure Admin

- As a Cloud Infrastructure Admin, I want to prepare nodes with the local disks and volume group that LVMS carves volumes from, so that the LVMS-backed tier has capacity to provision.

## Assumptions

- The LVMS-backed tier uses the same onboarding, provisioning, and inventory experience as remote backends (OSAC-2872), adding no new tenant-facing or admin-facing workflow.
- In the single-node scope, the control plane and tenant workloads share one cluster, so no cross-cluster provisioning is required in this release.
- Nodes have local disks and a volume group available for LVMS to consume; provisioning that hardware and capacity is a cluster/infrastructure prerequisite handled outside OSAC.
- LVMS targets single-node development environments where remote storage arrays are unavailable or unnecessary; it does not aim for feature parity with network backends (in particular, node-local volumes do not move between nodes).
- The LVMS installation tooling is available to the VMaaS onboarding automation.
- LVMS backend registration requires a deployment-level development/test profile flag (see Dependencies). This flag is a cross-cutting concern proposed separately; once available, LVMS is gated behind it alongside other dev-only capabilities.

## Dependencies

- **OSAC-2872 (Storage Control Plane):** provides the storage tier model, driver, central inventory, and onboarding path this backend plugs into. Must be in place for the LVMS-backed tier to provision end to end.
- **VMaaS tenant onboarding automation:** extended to install and configure LVMS on the single-node cluster during onboarding.
- **Deployment Profile Flag (proposed):** a deployment-level `deployment.profile` (or equivalent) Helm value that distinguishes development/test from production installations. LVMS registration is gated behind this flag. Until the flag lands, LVMS falls back to `lvms.enabled` (default: false) as an interim gate.

---

## Provenance

Authored: draft @ prd 0.8.0 - 7efcedb, workspace main @ 62ad8a38b

<!-- ai-workflow-provenance:{"schema_version":1,"provenance_kind":"session","workflow":"prd","workflow_version":"0.8.0","ai_workflows":"7efcedb","source_repo":"62ad8a38b","source_repo_branch":"main","commits_behind_main":0,"commits_ahead_main":0,"main_ref":"main","phases":["draft"],"authoring_modes":["skill"],"context_changed":false,"origin_untracked":false} -->
