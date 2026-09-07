# Metering for Block Storage

| Field       | Value                |
|-------------|----------------------|
| Author(s)   | masayag@redhat.com   |
| Jira        | [OSAC-3141](https://redhat.atlassian.net/browse/OSAC-3141) |
| Date        | 2026-09-07           |

## Glossary

Terms defined in the [Part 1 PRD](/enhancements/OSAC-985-metering-and-usage-tracking/prd.md) apply here. Additional terms:

| Term | Definition |
|------|-----------|
| **Allocation metering** | Metering based on the logical capacity the tenant requested (provisioned size), running from creation to deletion regardless of whether the resource is actively in use. For block storage, actual backend consumption is opaque to the tenant due to thin provisioning, compression, deduplication, and snapshots — the provisioned size is the only number the tenant can reason about and act on. |
| **Storage tier** | A provider-defined storage performance category (e.g., fast, standard, archival). The required metering dimension for all storage resources. |

## 1. Problem Statement

OSAC provisions block storage volumes but has no mechanism to track their consumption over time. Block volumes consume provider capacity from the moment they are created until they are deleted, regardless of whether they are actively in use — a block volume occupies backend disk space whether the parent VM is running or not. A block volume's actual backend footprint is opaque to tenants — thin provisioning, compression, deduplication, and snapshots make physical consumption variable and unpredictable. The tenant's only actionable number is the logical capacity they provisioned.

Without metering for block storage, Cloud Provider Admins have no usage data to account for the storage capacity tenants hold, and Tenant Admins have no visibility into their block-storage footprint across projects and storage tiers. This gap grows as OSAC adds new storage types — every new storage resource added without metering is usage the provider cannot track.

## 2. In Scope

- Block storage metering — allocation-based metering for standalone Volumes (OSAC-984) by storage tier and capacity (GiB-seconds)
- Parent-child attribution — extending [Part 1](/enhancements/OSAC-985-metering-and-usage-tracking/prd.md) CAP-11 and CAP-12 so that block storage volumes attached to VMs, clusters, or bare metal hosts can be attributed to the parent resource in a unified usage view
- Applies across VMaaS (block volumes on ComputeInstances), CaaS (volumes on ClusterOrders), and BMaaS (volumes on bare metal hosts)

## 3. Out of Scope

- File storage metering — tracked separately ([OSAC-4940](https://redhat.atlassian.net/browse/OSAC-4940))
- Object storage metering — tracked separately ([OSAC-3444](https://redhat.atlassian.net/browse/OSAC-3444))
- BMaaS metering — tracked separately ([OSAC-2506](https://redhat.atlassian.net/browse/OSAC-2506))
- Networking resource metering — tracked separately ([OSAC-3145](https://redhat.atlassian.net/browse/OSAC-3145))
- Network bandwidth metering — tracked separately ([OSAC-3149](https://redhat.atlassian.net/browse/OSAC-3149))
- Costing, billing, quota enforcement, and budget alerts — deferred to a separate PRD
- VM boot disk storage tier attribution — tracked separately
- UI for viewing storage usage — metering data is consumed by the billing system, which provides the user-facing usage views
- Workload-level metering inside tenant environments

## 4. User Stories

### Cloud Provider Admin

- As a Cloud Provider Admin, I want to view block storage usage across all tenants broken down by the storage tiers configured in OSAC (e.g., fast, standard, archival) and capacity, so that I can account for the block-storage capacity each tenant holds by tier without separately registering each tier in the metering system.

### Tenant Admin

- As a Tenant Admin, I want to view my organization's block storage usage broken down by project, storage tier, and volume, so that I can identify which teams consume the most storage capacity and on which tier.

### Tenant User

- As a Tenant User, I want to view block storage usage for the projects I belong to, broken down by volume and storage tier, so that I can track how much storage capacity my workloads consume and on which tier.

## 5. Capabilities

### 5.1 Block Storage Metering

- **CAP-1:** Block storage volumes are metered using allocation-based metering from creation to deletion. The metering unit is GiB-seconds per storage tier.

### 5.2 Query Dimensions and Attribution

- **CAP-3:** Storage usage is queryable by storage tier, capacity, tenant, and project. Storage tier is a required metering dimension as specified by [Part 1](/enhancements/OSAC-985-metering-and-usage-tracking/prd.md).
- **CAP-4:** Block storage volumes attached to a VM, cluster, or bare metal host are attributable to the parent resource, extending Part 1 CAP-11 and CAP-12 so that the full usage of a parent resource can be queried as a unified view including all subsidiary storage.

### 5.3 Cross-cutting

- **CAP-5:** Storage usage data is available alongside existing metering data without additional admin configuration steps. All storage meters use the same accuracy and data-availability guarantees as Part 1 meters (CAP-4, CAP-15, CAP-16).

## 6. Usage Calculation Model

OSAC captures usage data. Downstream systems (billing, quota, analytics) consume this data and apply their own logic. This section defines the metering units and accumulation rules for block storage, extending the usage calculation model from [Part 1](/enhancements/OSAC-985-metering-and-usage-tracking/prd.md).

Block storage uses allocation meters because the tenant's actual backend consumption is opaque — thin provisioning, compression, deduplication, and snapshots make the physical footprint variable and unpredictable. The provisioned size (logical allocation) is the only number tenants can reason about and act on. The storage tier is the primary metering dimension — different tiers represent different performance and capacity characteristics.

| Meter | Scope | Unit | Accumulation | Example (30 days) |
|-------|-------|------|-------------|-------------------|
| GiB-seconds per tier (block allocation) | creation to deletion | GiB × seconds | capacity × wall-clock duration | 100 GiB × 2,592,000s |

## 7. Acceptance Criteria

- [ ] A block storage volume generates usage data (GiB-seconds) from creation to deletion, queryable per tenant, storage tier, and capacity
- [ ] When a block volume is resized, subsequent usage data reflects the new capacity
- [ ] Storage usage can be broken down by storage tier, tenant, project, and individual volume
- [ ] A block storage volume attached to a stopped VM continues generating usage data (extending Part 1 CAP-11)
- [ ] A block storage volume attached to a VM, cluster, or bare metal host can be attributed to the parent resource in a unified usage view
- [ ] Storage usage data appears alongside existing metering data without additional admin setup
- [ ] Storage meters record usage at per-second granularity — a volume existing for 30 seconds appears in usage data
- [ ] Storage usage totals are accurate — querying the same period twice returns consistent results
- [ ] Historical storage usage data is available for the retention period defined by Part 1 metering requirements (duration: TBD)
- [ ] Enabling storage metering does not disrupt existing provisioning workflows

## 8. Assumptions

- Part 1 metering infrastructure is deployed and operational.
- Storage meters are additive to the Part 1 metering deployment and require no separate infrastructure.
- The tenant-facing block storage Volume API will be implemented before block storage metering.
- Allocation-based metering (confirmed for block storage) is supported by the Part 1 metering infrastructure without architectural changes.

## 9. Dependencies

- **Part 1 metering infrastructure:** The metering infrastructure established by [Part 1](/enhancements/OSAC-985-metering-and-usage-tracking/prd.md) is a prerequisite. Block storage metering extends but does not replace it.
- **OSAC-984 (Storage Volume API):** Tenant-facing block storage Volume resource must exist in the fulfillment-service proto before block storage metering can be implemented.

## 10. Risks

### 10.1 Block storage API does not exist yet

- **Owner:** OSAC platform team
- **Mitigation:** The block storage (OSAC-984) API must be implemented before its meters can be built. Block storage metering delivery is gated on this API. Coordinate with the storage team to align timelines.

### 10.2 Part 1 metering infrastructure not yet built

- **Owner:** OSAC platform team
- **Mitigation:** All block storage meters depend on the metering infrastructure (event pipeline, usage store) established by Part 1 (OSAC-985). Block storage metering implementation cannot begin until Part 1 infrastructure is deployed.

## Related PRDs

This PRD is part of the OSAC metering family:

- **Metering for BMaaS** — [OSAC-2506](https://redhat.atlassian.net/browse/OSAC-2506)
- **Metering for Block Storage** — this document (OSAC-3141)
- **Metering for File Storage** — [OSAC-4940](https://redhat.atlassian.net/browse/OSAC-4940)
- **Metering for Networking** — [OSAC-3145](https://redhat.atlassian.net/browse/OSAC-3145)
- **Metering for Network Bandwidth** — [OSAC-3149](https://redhat.atlassian.net/browse/OSAC-3149)
- **Metering for Object Storage** — [OSAC-3444](https://redhat.atlassian.net/browse/OSAC-3444)

---

## Provenance

Authored: revise @ prd 0.6.3 - 68284c8, workspace main @ ef4f3af
Final: revise @ prd 0.9.0 - 562b610, workspace HEAD @ d165396

> Context changed between revise and revise.

> This document's phase history does not include an initial /draft — structure was not verified against the template from origin.

<!-- ai-workflow-provenance:{"schema_version":1,"provenance_kind":"session","workflow":"prd","workflow_version":"0.9.0","ai_workflows":"562b610","source_repo":"d165396","source_repo_branch":"HEAD","commits_behind_main":0,"commits_ahead_main":0,"main_ref":"main","phases":["revise","revise","revise","revise"],"authoring_modes":["skill"],"context_changed":true,"origin_untracked":true} -->
