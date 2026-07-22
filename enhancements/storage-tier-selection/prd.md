# ComputeInstance StorageTier Selection

| Field       | Value   |
|-------------|---------|
| Author(s)   | Carlo Lobrano |
| Jira        | https://redhat.atlassian.net/browse/OSAC-1710 |
| Date        | 2026-07-20 |

## Problem Statement

When a ComputeInstance is provisioned, all disks receive the same storage tier regardless of workload requirements. A database VM requiring high-IOPS storage and a dev/test VM that could use archive-tier storage both get the same QoS. The DiskSpec currently carries only a size — there is no mechanism for a user to specify which storage tier a disk should use. Without per-disk tier selection, OSAC cannot deliver differentiated storage to tenants despite having a multi-tier storage model.

## In Scope

- Per-disk storage tier selection for ComputeInstance boot disk and additional disks
- Storage tier as a mandatory field — provisioning fails if no tier is provided `[Clarify: R1.Q3, R2.Q1]`
- Independent tier selection per disk (boot disk and each additional disk can use different tiers)
- Validation that the requested tier exists at request time; clear error on failure
- Tier resolution precedence: user input, then CatalogItem defaults, then ComputeInstanceTemplate defaults `[Clarify: R2.Q1]`
- Tier immutability after ComputeInstance creation `[Clarify: R2.Q4]`
- VMaaS service only `[Clarify: R1.Q1]`

## Out of Scope

- CaaS cluster template tier selection `[Clarify: R1.Q1]`
- DiskSpec `source` field for pre-populated DataVolumes `[Clarify: R1.Q2]`
- OSAC-shipped template portability across CSP deployments `[Clarify: R2.Q5]`
- Developer environment storage backend and tier setup `[Clarify: R2.Q6]`
- StorageTier model definition (covered by OSAC-1110)
- StorageBackend registration (covered by OSAC-1111)
- Tenant-level StorageClass resolution (handled by WG-Storage)
- Storage quota or capacity management per tier

## User Stories

### Tenant User

- As a Tenant User, I want to select a storage tier for each disk when creating a ComputeInstance (e.g., "fast" for the boot disk, "archive" for an additional data disk), so that each disk gets the appropriate storage QoS for its workload.

- As a Tenant User, I want provisioning to fail with a clear error if I request a storage tier that is not available, so that I know immediately what went wrong instead of discovering a silent misconfiguration later.

- As a Tenant User, I want the storage tier on my disks to remain fixed after creation, so that my VM's storage characteristics are predictable and do not change unexpectedly.

### Cloud Provider Admin

- As a Cloud Provider Admin, I want to configure storage tier defaults in CatalogItems and ComputeInstanceTemplates, so that Tenant Users can provision VMs without needing to know which specific tier to select for each disk.

### Tenant Admin

- As a Tenant Admin, I want to create tenant-scoped CatalogItems with pre-configured storage tier values, so that my organization's users provision VMs with tiers that match our policies without manual selection.

## Dependencies

- **OSAC-1110 (StorageTier Definition & Private API):** Defines what storage tiers exist in the system. The StorageTier API must be available for the fulfillment service to validate that a requested tier exists. In Progress (Roy Golan).
- **OSAC-1111 (StorageBackend Definition & Private API):** Storage tiers are associated with a storage backend. The backend must be registered before tiers referencing it can be created. In Progress (Roy Golan).
- **OSAC-1992 (StorageTier API Integration into AAP):** Integrates the StorageTier API into AAP provisioning flows, replacing the legacy `STORAGE_TIERS` environment variable. Related but not blocking — AAP's `tenant_storage_class` role already resolves tier names to StorageClasses. In Progress (Will Gordon).

---

## Provenance

Authored: draft @ prd 0.5.0 - 92734a2, workspace main @ 0921467 (dirty)

<!-- ai-workflow-provenance:{"schema_version":1,"provenance_kind":"session","workflow":"prd","workflow_version":"0.5.0","ai_workflows":"92734a2","source_repo":"0921467 (dirty)","source_repo_branch":"main","commits_behind_main":0,"commits_ahead_main":1,"main_ref":"main","phases":["draft"],"authoring_modes":["skill"],"context_changed":false} -->
