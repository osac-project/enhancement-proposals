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
- Storage tier as a mandatory field — provisioning fails if no tier is resolved after applying the precedence chain (user input, CatalogItem defaults, Template defaults) `[Clarify: R1.Q3, R2.Q1]`
- Independent tier selection per disk (boot disk and each additional disk can use different tiers)
- Validation that the requested tier exists at request time; clear error on failure
- Tier resolution precedence: user input, then CatalogItem defaults, then ComputeInstanceTemplate defaults `[Clarify: R2.Q1]`
- Tier immutability after ComputeInstance creation `[Clarify: R2.Q4]`
- VMaaS service only `[Clarify: R1.Q1]`
- UI support for tier selection in the ComputeInstance creation flow
- Documentation updates for the storage tier selection capability

## Out of Scope

- CaaS cluster template tier selection `[Clarify: R1.Q1]`
- Pre-populated disk images as a source for new disks `[Clarify: R1.Q2]`
- OSAC-shipped template portability across CSP deployments `[Clarify: R2.Q5]`
- Developer environment storage backend and tier setup `[Clarify: R2.Q6]`
- StorageTier model definition (covered by OSAC-1110)
- StorageBackend registration (covered by OSAC-1111)
- Tenant-level StorageClass resolution (handled by WG-Storage)
- Storage quota or capacity management per tier
- E2E test coverage (implementation detail for design phase)

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

- **OSAC-1110 (StorageTier Definition & Private API):** Defines what storage tiers exist in the system. The StorageTier API must be available for tier validation at request time. In Progress (Roy Golan).
- **OSAC-1111 (StorageBackend Definition & Private API):** Storage tiers reference a storage backend. A backend must be registered before tiers referencing it can be created. In Progress (Roy Golan).
- **OSAC-1992 (StorageTier API Integration into Provisioning):** Integrates the StorageTier API into provisioning flows. Related but not blocking — the provisioning system already resolves tier names to storage classes. In Progress (Will Gordon).

## Risks

### 1. No storage tiers defined at tenant provisioning time

If no StorageTier resources have been created (OSAC-1110 dependency), no ComputeInstance can be provisioned because tier selection is mandatory. Early deployments or environments where the storage team has not yet configured tiers will fail all VM creation requests.
- **Owner:** Storage WG
- **Mitigation:** OSAC-1110 must be completed and at least one tier configured before ComputeInstance provisioning is usable. Installation documentation must include tier setup as a prerequisite.

---

## Provenance

Authored: respond @ prd 0.5.0 - 92734a2, workspace main @ 0921467 (dirty)
Phases: draft, respond

<!-- ai-workflow-provenance:{"schema_version":1,"provenance_kind":"session","workflow":"prd","workflow_version":"0.5.0","ai_workflows":"92734a2","source_repo":"0921467 (dirty)","source_repo_branch":"main","commits_behind_main":0,"commits_ahead_main":1,"main_ref":"main","phases":["draft","respond"],"authoring_modes":["skill"],"context_changed":false} -->
