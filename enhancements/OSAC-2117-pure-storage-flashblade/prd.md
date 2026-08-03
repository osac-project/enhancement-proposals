# Pure Storage FlashBlade File Storage (NFS) Provider for OSAC

| Field       | Value   |
|-------------|---------|
| Author(s)   | Danni Shi |
| Jira        | https://redhat.atlassian.net/browse/OSAC-2117 |
| Date        | 2026-07-21 |

## Problem Statement

OSAC supports only VAST as a file storage backend. Datacenters running Pure Storage FlashBlade hardware cannot provision tenant-isolated NFS storage through OSAC, forcing manual configuration outside the platform. Without FlashBlade support, OSAC cannot offer self-service file storage in Pure-equipped datacenters, limiting its viability as a multi-provider sovereign cloud platform.

## In Scope

- Pure FlashBlade as a file storage (NFS) provider for CaaS and VMaaS services
- Automated tenant onboarding: per-tenant isolated NFS storage provisioned automatically during tenant creation, including storage tier selection and tenant-isolated access controls
- Automated tenant offboarding: cleanup of all tenant storage resources and Realm release back to the available pool only after tenant state is fully removed or invalidated
- Realm pool management: Cloud Infrastructure Admins register and deregister pre-created FlashBlade Realms for use during tenant onboarding and offboarding — OSAC does not have array-admin privileges on FlashBlade and cannot create or modify Realms directly
- Realm exhaustion handling: clear error and blocked status when no Realms are available during tenant onboarding, with no partial tenant or Realm state left behind
- Persistent storage delivered through osac-csi-driver — the vendor CSI controller runs on the hub cluster and only the vendor node plugin runs on the tenant cluster
- Tenant-facing UI: Pure-backed StorageClasses visible to tenants in the console on their provisioned clusters
- Pure-backed StorageClasses provisioned as OSAC StorageClasses with the tier pointing at Pure, discoverable through the same channels as existing storage providers
- ComputeInstance (VMaaS) workloads can consume Pure-backed storage for boot and additional disks using tenant-resolved StorageClasses
- E2E test for tenant onboarding with a Pure file storage tier
- Administrator documentation (Realm registration guide, network prerequisites) and user documentation (consuming Pure-backed storage)

## Out of Scope

- Pure FlashBlade S3/object storage — object storage requires COSI; separate feature
- Pure FlashArray block storage — not deployed in current datacenter configurations
- RDMA / GPUDirect Storage validation — separate effort
- Keycloak-to-Pure RBAC mapping — separate effort
- SafeMode snapshots and immutable storage — separate effort
- BMaaS and MaaS services
- Admin-facing UI for Realm pool management or storage backend registration — each storage backend requires provider-specific configuration (e.g., Realm pools, VIP pools), making a unified cross-provider admin UI impractical; if admin UI is needed, it would be provider-specific and a separate feature

## User Stories

### Cloud Infrastructure Admin

- As a Cloud Infrastructure Admin, I want to register and deregister pre-created FlashBlade Realms with OSAC, so that tenants can be assigned Realms during the onboarding process without requiring array-admin privileges at runtime.

### Cloud Provider Admin

- As a Cloud Provider Admin, I want to register a Pure FlashBlade array as a storage backend and define storage tiers with Pure as the provider, so that tenant onboarding provisions NFS file storage from the correct backend.

- As a Cloud Provider Admin, I want tenant onboarding to automatically provision isolated NFS storage on Pure FlashBlade, so that tenants receive file storage without manual configuration.

- As a Cloud Provider Admin, I want tenant offboarding to clean up all tenant storage resources and release the FlashBlade Realm back to the available pool only after tenant state is fully removed or invalidated, so that no tenant data or access state leaks across Realm assignments.

- As a Cloud Provider Admin, I want to see a clear error and a blocked status when tenant onboarding cannot proceed because all FlashBlade Realms in the pool are checked out, so that I can take action — register more Realms or prioritize tenant teardowns.

- As a Cloud Provider Admin, I want tenant onboarding that fails due to Realm exhaustion to leave no partial allocation, so that retrying onboarding after capacity is added is deterministic and duplicate-free.

### Tenant Admin / Tenant User

- As a Tenant Admin or Tenant User, I want Pure-backed StorageClasses to appear automatically on my provisioned clusters using the same resolution as existing storage providers, so that I can create PVCs for NFS workloads without special configuration.
- As a Tenant Admin or Tenant User, I want to select from available storage tiers when creating persistent volumes, so that I can choose the performance and capacity characteristics appropriate for my workload.
- As a Tenant Admin or Tenant User, I want ComputeInstances to use Pure-backed storage for boot and additional disks when a Pure storage tier is configured, so that my VMs have persistent storage without special configuration.

## Assumptions

- Datacenter administrators pre-create FlashBlade Realms with capacity and network constraints before registering them with OSAC. OSAC does not create or modify Realms on FlashBlade.
- Workload clusters that consume Pure storage have network connectivity to both the FlashBlade management API and the NFS data network. This connectivity is established outside OSAC by datacenter and Pure administrators.
- Coordination between OSAC administrators and Pure Storage administrators is required for initial setup — Realm creation, network configuration, and credential provisioning happen outside OSAC.
- Physical Realm destruction is an external-only operation handled by Pure Storage administrators outside OSAC. OSAC can only release Realms back to the available pool; it cannot delete or destroy them.
- The existing storage provisioning model in OSAC works without changes for a new storage provider.

## Dependencies

- **Pure Storage administrators:** Must pre-create FlashBlade Realms, configure network connectivity between workload clusters and FlashBlade, and provide credentials before OSAC can provision Pure storage.
- **osac-csi-driver:** Pure storage integration must go through osac-csi-driver, which deploys the vendor CSI controller on the hub cluster and the vendor node plugin on the tenant cluster.
- **Compatible Pure FlashBlade AAP collection version:** Required for NFS storage automation during tenant onboarding.

## Open Questions

### OQ-1: Realm Reuse Model

**Owner:** Storage team / Pure Storage SME
**Impact:** Affects the teardown workflow, Realm pool sizing guidance for Cloud Provider Admins, and whether Realm registration is a one-time or ongoing task.

Can FlashBlade Realms be reused after tenant teardown — returned to the available pool for reassignment — or are Realms single-use, requiring the Cloud Infrastructure Admin to register replacements? If Realms are single-use, admins must coordinate with Pure Storage administrators to provision and register new Realms as the pool is exhausted.

---

## Provenance

Authored: revise @ prd 0.5.0 - 92734a2, workspace OSAC-2117 @ 1baec0f
Phases: draft, revise, revise, revise, revise, revise, revise

<!-- ai-workflow-provenance:{"schema_version":1,"provenance_kind":"session","workflow":"prd","workflow_version":"0.5.0","ai_workflows":"92734a2","source_repo":"1baec0f","source_repo_branch":"OSAC-2117","commits_behind_main":0,"commits_ahead_main":0,"main_ref":"main","phases":["draft","revise","revise","revise","revise","revise","revise"],"authoring_modes":["skill"],"context_changed":false} -->
