# Metering and Usage Tracking — Part 2b: Block and File Storage

| Field       | Value                |
|-------------|----------------------|
| Author(s)   | masayag@redhat.com   |
| Jira        | [OSAC-3141](https://redhat.atlassian.net/browse/OSAC-3141) |
| Date        | 2026-07-26           |

## Glossary

Terms defined in the [Part 1 PRD](/enhancements/OSAC-985-metering-and-usage-tracking/prd.md) apply here. Additional terms:

| Term | Definition |
|------|-----------|
| **Allocation metering** | Metering based on the logical capacity the tenant requested (provisioned size), running from creation to deletion regardless of whether the resource is actively in use. For block storage, actual backend consumption is opaque to the tenant due to thin provisioning, compression, deduplication, and snapshots — the provisioned size is the only number the tenant can reason about and act on. |
| **Storage tier** | A provider-defined storage performance category (e.g., fast, standard, archival). The required metering dimension for all storage resources. |

## 1. Problem Statement

OSAC provisions storage resources — block volumes and file shares — but has no mechanism to track their consumption over time. Storage resources consume provider capacity from the moment they are created until they are deleted, regardless of whether they are actively in use. A block volume's actual backend footprint is opaque to tenants — thin provisioning, compression, deduplication, and snapshots make physical consumption variable and unpredictable. The tenant's only actionable number is the logical capacity they provisioned. File shares similarly consume provider resources from creation, though the appropriate metering model (provisioned capacity vs actual consumption) depends on how OSAC models the File service.

Without metering for these resources, Cloud Provider Admins have no usage data to account for the storage capacity tenants hold, and Tenant Admins have no visibility into their storage footprint across projects and storage tiers. This gap grows as OSAC adds new storage types — every new storage resource added without metering is usage the provider cannot track.

## 2. In Scope

- Block storage metering — allocation-based metering for standalone Volumes (OSAC-984) by storage tier and capacity (GiB-seconds)
- File storage metering — metering for FileShares (OSAC-2387) by storage tier and capacity (GiB-seconds). The metering model (allocation-based vs consumption-based) is an open question — see Open Questions
- Parent-child attribution — extending [Part 1](/enhancements/OSAC-985-metering-and-usage-tracking/prd.md) CAP-11 and CAP-12 so that storage volumes attached to VMs, clusters, or bare metal hosts can be attributed to the parent resource in a unified usage view
- Applies across VMaaS (block/file volumes on ComputeInstances), CaaS (volumes on ClusterOrders), and BMaaS (volumes on bare metal hosts)

## 3. Out of Scope

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

- As a Cloud Provider Admin, I want to view storage usage across all tenants broken down by storage tier (fast, standard, archival) and capacity, so that I can account for the storage capacity each tenant holds by tier.
- As a Cloud Provider Admin, I want storage usage to be automatically grouped by the storage tiers I have configured in OSAC, so that each tier (e.g., NVMe SSD, HDD archival) is metered independently — without requiring a separate registration step in the metering system.

### Tenant Admin

- As a Tenant Admin, I want to view my organization's storage usage broken down by project, storage tier, and volume, so that I can identify which teams consume the most storage capacity and on which tier.

### Tenant User

- As a Tenant User, I want to view storage usage for the projects I belong to, broken down by volume and storage tier, so that I can track how much storage capacity my workloads consume and on which tier.

## 5. Capabilities

### 5.1 Block and File Storage Metering

- **CAP-1:** Block storage volumes are metered using allocation-based metering from creation to deletion. The metering unit is GiB-seconds per storage tier.
- **CAP-2:** File storage shares are metered by storage tier from creation to deletion. The metering unit is GiB-seconds, but whether the meter tracks provisioned capacity (allocation model, as with block storage) or actual consumed capacity depends on the file storage service model — see Open Questions.

### 5.2 Query Dimensions and Attribution

- **CAP-3:** Storage usage is queryable by storage tier, capacity, tenant, and project. Storage tier is a required metering dimension as specified by [Part 1](/enhancements/OSAC-985-metering-and-usage-tracking/prd.md).
- **CAP-4:** Storage volumes attached to a VM, cluster, or bare metal host are attributable to the parent resource, extending Part 1 CAP-11 and CAP-12 so that the full usage of a parent resource can be queried as a unified view including all subsidiary storage.

### 5.3 Cross-cutting

- **CAP-5:** Storage usage data is available alongside existing metering data without additional admin configuration steps. All storage meters use the same accuracy and data-availability guarantees as Part 1 meters (CAP-4, CAP-15, CAP-16).

## 6. Usage Calculation Model

OSAC captures usage data. Downstream systems (billing, quota, analytics) consume this data and apply their own logic. This section defines the metering units and accumulation rules for storage, extending the usage calculation model from [Part 1](/enhancements/OSAC-985-metering-and-usage-tracking/prd.md).

Block storage uses allocation meters because the tenant's actual backend consumption is opaque — thin provisioning, compression, deduplication, and snapshots make the physical footprint variable and unpredictable. The provisioned size (logical allocation) is the only number tenants can reason about and act on. The storage tier is the primary metering dimension — different tiers represent different performance and capacity characteristics.

File storage metering uses the same GiB-seconds unit, but the metering basis (provisioned capacity vs actual consumed capacity) is an open question. Industry precedent is split: AWS EFS meters by consumed storage, GCP Filestore by provisioned capacity, and Azure Files uses both models depending on the tier. The decision depends on how OSAC models the File service — see Open Questions.

| Meter | Scope | Unit | Accumulation | Example (30 days) |
|-------|-------|------|-------------|-------------------|
| GiB-seconds per tier (block allocation) | creation to deletion | GiB × seconds | capacity × wall-clock duration | 100 GiB × 2,592,000s |
| GiB-seconds per tier (file — model TBD) | creation to deletion | GiB × seconds | provisioned or consumed capacity × wall-clock duration | 50 GiB × 2,592,000s |

## 7. Acceptance Criteria

- [ ] A block storage volume generates usage data (GiB-seconds) from creation to deletion, queryable per tenant, storage tier, and capacity
- [ ] A file storage share generates usage data (GiB-seconds) from creation to deletion, queryable per tenant, storage tier, and capacity
- [ ] When a block volume or file share is resized, subsequent usage data reflects the new capacity
- [ ] Storage usage can be broken down by storage tier, tenant, project, and individual volume
- [ ] A storage volume attached to a stopped VM continues generating usage data (extending Part 1 CAP-11)
- [ ] A storage volume attached to a VM, cluster, or bare metal host can be attributed to the parent resource in a unified usage view
- [ ] Storage usage data appears alongside existing metering data without additional admin setup
- [ ] Storage meters record usage at per-second granularity — a volume existing for 30 seconds appears in usage data
- [ ] Storage usage totals are accurate — querying the same period twice returns consistent results
- [ ] Historical storage usage data is available for at least 13 months
- [ ] Enabling storage metering does not disrupt existing provisioning workflows

## 8. Open Questions

1. **File storage metering model — allocation vs consumption?** Should file storage meter by provisioned capacity (the size the tenant requested, as with block storage) or by actual consumed capacity (bytes stored)? Industry precedent is split — AWS EFS uses consumed storage, GCP Filestore uses provisioned, Azure Files uses both models (provisioned for SSD, consumed for HDD). The decision depends on how OSAC models the File service. **Owner: storage team.**

## 9. Assumptions

- Part 1 metering infrastructure is deployed and operational.
- Storage meters are additive to the Part 1 metering deployment and require no separate infrastructure.
- Tenant-facing storage APIs (Volume, FileShare) will be implemented before storage metering.
- Storage metering can be delivered incrementally as each storage API becomes available — block and file storage meters are independent and do not depend on each other.
- Allocation-based metering (confirmed for block storage) is supported by the Part 1 metering infrastructure without architectural changes. File storage may use the same model or a consumption-based model — see Open Questions.

## 10. Dependencies

- **Part 1 metering infrastructure:** The metering infrastructure established by [Part 1](/enhancements/OSAC-985-metering-and-usage-tracking/prd.md) is a prerequisite. Part 2b extends but does not replace it.
- **OSAC-984 (Storage Volume API):** Tenant-facing block storage Volume resource must exist in the fulfillment-service proto before storage metering can be implemented.
- **OSAC-2387 (File Storage API):** FileShare resource must exist in the fulfillment-service proto before file storage metering can be implemented.

## 11. Risks

### 11.1 Storage APIs do not exist yet

- **Owner:** OSAC platform team
- **Mitigation:** Block storage (OSAC-984) and file storage (OSAC-2387) APIs must be implemented before their respective meters can be built. Storage metering delivery is gated on these APIs. Coordinate with the storage team to align timelines.

### 11.2 Part 1 metering infrastructure not yet built

- **Owner:** OSAC platform team
- **Mitigation:** All Part 2b meters depend on the metering infrastructure (event pipeline, usage store) established by Part 1 (OSAC-985). Part 2b implementation cannot begin until Part 1 infrastructure is deployed.

## Related PRDs

This PRD is part of the Metering Part 2 family:

- **Part 2a: BMaaS** — [OSAC-2506](https://redhat.atlassian.net/browse/OSAC-2506)
- **Part 2b: Block and File Storage** — this document (OSAC-3141)
- **Part 2c: Networking** — [OSAC-3145](https://redhat.atlassian.net/browse/OSAC-3145)
- **Part 2d: Network Bandwidth** — [OSAC-3149](https://redhat.atlassian.net/browse/OSAC-3149)
- **Part 2e: Object Storage** — [OSAC-3444](https://redhat.atlassian.net/browse/OSAC-3444)

---

## Provenance

Authored: revise @ prd 0.6.3 - 68284c8, workspace main @ ef4f3af
Phases: revise, revise, revise

<!-- ai-workflow-provenance:{"schema_version":1,"provenance_kind":"session","workflow":"prd","workflow_version":"0.6.3","ai_workflows":"68284c8","source_repo":"ef4f3af","source_repo_branch":"main","commits_behind_main":0,"commits_ahead_main":1,"main_ref":"main","phases":["revise","revise","revise"],"authoring_modes":["skill"],"context_changed":false} -->
