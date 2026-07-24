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
- Automated tenant offboarding: cleanup of all tenant storage resources and Realm release or destruction
- Realm pool management: admins register pre-created FlashBlade Realms via a configuration file, with credentials supplied as separately-created Kubernetes Secrets
- Realm exhaustion handling: clear error and blocked status when no Realms are available during tenant onboarding
- Pure CSI driver lifecycle management (installation and configuration on workload clusters)
- Tenant-facing UI: Pure-backed StorageClasses visible to tenants in the console on their provisioned clusters
- Pure-backed StorageClasses must integrate with OSAC's existing storage discovery contract — including tenant and storage-tier labels, tier matching, and exposure through tenant storage status — so they are discoverable by the console and workload consumers
- E2E test for tenant onboarding with a Pure file storage tier

## Out of Scope

- Pure FlashBlade S3/object storage — blocked on Pure's S3 CSI maturity; separate feature
- Pure FlashArray block storage — not deployed in current datacenter configurations
- RDMA / GPUDirect Storage validation — separate effort
- Keycloak-to-Pure RBAC mapping — separate effort
- SafeMode snapshots and immutable storage — separate effort
- BMaaS and MaaS services
- Admin-facing UI for Realm pool management or storage backend registration

## User Stories

### Cloud Infrastructure Admin

- As a Cloud Infrastructure Admin, I want to register a Pure FlashBlade array as a storage backend and define storage tiers with Pure as the provider, so that tenant onboarding provisions NFS file storage from the correct backend.

- As a Cloud Infrastructure Admin, I want to register pre-created FlashBlade Realms by creating Kubernetes Secrets containing Realm-scoped API keys and referencing them in a configuration file, so that OSAC can check out Realms during tenant provisioning without requiring array-admin privileges at runtime.

### Cloud Provider Admin

- As a Cloud Provider Admin, I want tenant onboarding to automatically provision isolated NFS storage on Pure FlashBlade — including per-tenant StorageClasses for each configured storage tier, secure credential setup, and tenant-isolated access controls — so that tenants receive file storage without manual configuration.

- As a Cloud Provider Admin, I want tenant offboarding to clean up all tenant storage resources on the workload cluster and release or destroy the FlashBlade Realm, so that storage resources are not leaked and Realms can be reclaimed.

- As a Cloud Provider Admin, I want to see a clear error and a blocked status when tenant onboarding cannot proceed because all FlashBlade Realms in the pool are checked out, so that I can take action — register more Realms or prioritize tenant teardowns.

### Tenant Admin / Tenant User

- As a Tenant Admin or Tenant User, I want Pure-backed StorageClasses to appear automatically on my provisioned clusters — discoverable through the console, tenant storage status, and kubectl — using the same tenant and storage-tier resolution as existing storage providers, so that I can create PVCs for NFS workloads without special configuration.
- As a Tenant Admin or Tenant User, I want to select from available storage tiers when creating persistent volumes, so that I can choose the performance and capacity characteristics appropriate for my workload.

## Assumptions

- Datacenter administrators pre-create FlashBlade Realms with capacity and network constraints before registering them with OSAC. OSAC does not create or modify Realms on FlashBlade.
- Workload clusters that consume Pure storage have network connectivity to both the FlashBlade management API and the NFS data network. This connectivity is established outside OSAC by datacenter and Pure administrators.
- Coordination between OSAC administrators and Pure Storage administrators is required for initial setup — Realm creation, network configuration, and API key generation happen outside OSAC.
- The existing storage provisioning model in OSAC works without changes for a new storage provider — only a new provider-specific automation role is needed.

## Dependencies

- **Pure Storage administrators:** Must pre-create FlashBlade Realms, configure network connectivity between workload clusters and FlashBlade, and generate Realm-scoped API keys before OSAC can provision Pure storage.
- **purestorage.flashblade Ansible collection:** The automation role depends on this collection for NFS filesystem, export policy, and directory service management.
- **Pure CSI driver (pure-csi):** Must be installable on workload clusters and compatible with the FlashBlade firmware version in use.

## Open Questions

### OQ-1: Realm Reuse Model

**Owner:** Storage team / Pure Storage SME
**Impact:** Affects the teardown workflow and Realm pool sizing guidance for Cloud Provider Admins.

Can FlashBlade Realms be reused after tenant teardown — OSAC wipes the Realm contents and refreshes API tokens, returning the Realm to the available pool — or are Realms single-use, destroyed on teardown and requiring the Cloud Infrastructure Admin to register replacements?

### OQ-2: Documentation and E2E Test Scope

**Owner:** Product / QE
**Impact:** Affects milestone deliverables list.

Are administrator documentation (Realm registration guide, network prerequisites) and user documentation (consuming Pure-backed storage) in scope for this milestone? Are detailed E2E test scenarios beyond the basic tenant onboarding test in scope?

---

## Provenance

Authored: revise @ prd 0.5.0 - 92734a2, workspace OSAC-2117 @ 1baec0f
Phases: draft, revise

<!-- ai-workflow-provenance:{"schema_version":1,"provenance_kind":"session","workflow":"prd","workflow_version":"0.5.0","ai_workflows":"92734a2","source_repo":"1baec0f","source_repo_branch":"OSAC-2117","commits_behind_main":0,"commits_ahead_main":0,"main_ref":"main","phases":["draft","revise"],"authoring_modes":["skill"],"context_changed":false} -->
