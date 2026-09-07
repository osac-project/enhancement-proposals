# Metering for Block Storage

| Field       | Value                |
|-------------|----------------------|
| Author(s)   | masayag@redhat.com   |
| Jira        | [OSAC-3141](https://redhat.atlassian.net/browse/OSAC-3141) |
| Date        | 2026-09-07           |

## Problem Statement

OSAC provisions block storage volumes but has no mechanism to track their consumption over time. Block volumes consume provider capacity from the moment they are created until they are deleted, regardless of whether they are actively in use — a block volume occupies backend disk space whether the parent VM is running or not. A block volume's actual backend footprint is opaque to tenants — thin provisioning, compression, deduplication, and snapshots make physical consumption variable and unpredictable. The tenant's only actionable number is the logical capacity they provisioned.

Without metering for block storage, Cloud Provider Admins have no usage data to account for the storage capacity tenants hold, and Tenant Admins have no visibility into their block-storage footprint across projects and storage tiers. This gap grows as OSAC adds new storage types — every new storage resource added without metering is usage the provider cannot track.

## In Scope

- Block storage metering — allocation-based metering for standalone Volumes (OSAC-984) by storage tier and capacity (GiB-seconds)
- Parent-child attribution so that block storage volumes attached to VMs or clusters can be attributed to the parent resource in a unified usage view
- Applies across VMaaS (block volumes on ComputeInstances) and CaaS (volumes on ClusterOrders)

## Out of Scope

- File storage metering — tracked separately ([OSAC-4940](https://redhat.atlassian.net/browse/OSAC-4940))
- Object storage metering — tracked separately ([OSAC-3444](https://redhat.atlassian.net/browse/OSAC-3444))
- BMaaS metering, including block storage volumes attached to bare metal hosts — tracked separately ([OSAC-2506](https://redhat.atlassian.net/browse/OSAC-2506))
- Networking resource metering — tracked separately ([OSAC-3145](https://redhat.atlassian.net/browse/OSAC-3145))
- Network bandwidth metering — tracked separately ([OSAC-3149](https://redhat.atlassian.net/browse/OSAC-3149))
- Costing, billing, quota enforcement, and budget alerts — deferred to a separate PRD
- VM boot disk storage tier attribution — tracked separately
- OSAC UI views for storage usage — downstream billing and usage systems provide presentation of the metering data
- Workload-level metering inside tenant environments

## User Stories

### Cloud Provider Admin

- As a Cloud Provider Admin, I want to access block storage usage across all tenants broken down by the storage tiers configured in OSAC (e.g., fast, standard, archival) and capacity, so that I can account for the block-storage capacity each tenant holds by tier without separately registering each tier in the metering system.

### Tenant Admin

- As a Tenant Admin, I want to access my organization's block storage usage broken down by project, storage tier, and volume, so that I can identify which teams consume the most storage capacity and on which tier.

### Tenant User

- As a Tenant User, I want to access block storage usage for the projects I belong to, broken down by volume and storage tier, so that I can track how much storage capacity my workloads consume and on which tier.

## Acceptance Criteria

- [ ] A block storage volume generates usage data (GiB-seconds) for the period it holds allocated capacity — from when it becomes available for use until it is deleted — queryable per tenant, storage tier, and capacity
- [ ] A block storage volume that fails to provision and never becomes available generates no usage data
- [ ] When a block volume is resized, usage data reflects the new capacity from the point the resize takes effect; a resize that fails or is reverted leaves usage data unchanged
- [ ] Storage usage can be broken down by storage tier, tenant, project, and individual volume
- [ ] A block storage volume attached to a stopped VM continues generating usage data
- [ ] A block storage volume attached to a VM or cluster can be attributed to the parent resource in a unified usage view
- [ ] Storage usage data appears alongside existing metering data without additional admin setup
- [ ] Storage meters record usage at per-second granularity — a volume existing for 30 seconds appears in usage data
- [ ] Storage usage totals are accurate — querying the same period twice returns consistent results
- [ ] Raw storage metering events are retained for at least 7 days (configurable), per Part 1 metering requirements
- [ ] Aggregated storage usage data is retained for at least 13 months (configurable), per Part 1 metering requirements
- [ ] Enabling storage metering does not disrupt existing provisioning workflows

## Assumptions

- Part 1 metering infrastructure is deployed and operational.
- Storage metering is added to the existing Part 1 metering service without requiring separate tenant or administrator setup.
- The tenant-facing block storage Volume API will be implemented before block storage metering.
- The Part 1 metering service supports allocation-based metering for block storage.

## Dependencies

- **Part 1 metering infrastructure:** The metering infrastructure established by [Part 1](/enhancements/OSAC-985-metering-and-usage-tracking/prd.md) is a prerequisite. Block storage metering extends but does not replace it.
- **OSAC-984 (Storage Volume API):** A tenant-facing block storage Volume resource must exist before block storage metering can be implemented, and must expose a stable association between a volume and its parent resource (VM or cluster) so usage can be attributed to that parent. The mechanism for this association is a design concern for OSAC-984 and this feature's enhancement proposal.

---

## Provenance

Authored: revise @ prd 0.9.0 - 562b610, workspace main @ c30b1b6d9

> This document's phase history does not include an initial /draft — structure was not verified against the template from origin.

<!-- ai-workflow-provenance:{"schema_version":1,"provenance_kind":"session","workflow":"prd","workflow_version":"0.9.0","ai_workflows":"562b610","source_repo":"c30b1b6d9","source_repo_branch":"main","commits_behind_main":0,"commits_ahead_main":0,"main_ref":"main","phases":["revise"],"authoring_modes":["skill"],"context_changed":false,"origin_untracked":true} -->
