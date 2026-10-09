# Metering for File Storage

| Field       | Value                |
|-------------|----------------------|
| Author(s)   | masayag@redhat.com   |
| Jira        | [OSAC-4940](https://redhat.atlassian.net/browse/OSAC-4940) |
| Date        | 2026-09-07           |

## Glossary

Terms defined in the [Part 1 PRD](/enhancements/OSAC-985-metering-and-usage-tracking/prd.md) apply here. Additional terms:

| Term | Definition |
|------|-----------|
| **Allocation metering** | Metering based on the logical capacity the tenant requested (provisioned size), running from creation to deletion regardless of whether the resource is actively in use. |
| **Consumption metering** | Metering based on the actual capacity consumed (bytes stored), sampled over time rather than fixed at provisioning. |
| **Storage tier** | A provider-defined storage performance category (e.g., fast, standard, archival). The required metering dimension for all storage resources. |

## 1. Problem Statement

OSAC provisions file shares but has no mechanism to track their consumption over time. A file share reserves capacity on the storage backend from creation until deletion, regardless of whether the data is actively accessed. Unlike block storage — where the tenant's actionable number is unambiguously the provisioned size — the appropriate metering model for file storage (provisioned capacity vs actual consumed capacity) depends on how OSAC models the File service.

Without metering for file storage, Cloud Provider Admins have no usage data to account for the file-share capacity tenants hold, and Tenant Admins have no visibility into their file-storage footprint across projects and storage tiers. This gap grows as OSAC adds new storage types — every new storage resource added without metering is usage the provider cannot track.

## 2. In Scope

- File storage metering — metering for FileShares (OSAC-2387) by storage tier and capacity (GiB-seconds). The metering model (allocation-based vs consumption-based) is an open question — see Open Questions
- Parent-child attribution — extending [Part 1](/enhancements/OSAC-985-metering-and-usage-tracking/prd.md) CAP-11 and CAP-12 so that file shares attached to VMs, clusters, or bare metal hosts can be attributed to the parent resource in a unified usage view
- Applies across VMaaS (file shares on ComputeInstances), CaaS (file shares on ClusterOrders), and BMaaS (file shares on bare metal hosts)

## 3. Out of Scope

- Block storage metering — tracked separately ([OSAC-3141](https://redhat.atlassian.net/browse/OSAC-3141))
- Object storage metering — tracked separately ([OSAC-3444](https://redhat.atlassian.net/browse/OSAC-3444))
- BMaaS metering — tracked separately ([OSAC-2506](https://redhat.atlassian.net/browse/OSAC-2506))
- Networking resource metering — tracked separately ([OSAC-3145](https://redhat.atlassian.net/browse/OSAC-3145))
- Network bandwidth metering — tracked separately ([OSAC-3149](https://redhat.atlassian.net/browse/OSAC-3149))
- Costing, billing, quota enforcement, and budget alerts — deferred to a separate PRD
- UI for viewing storage usage — metering data is consumed by the billing system, which provides the user-facing usage views
- Workload-level metering inside tenant environments

## 4. User Stories

### Cloud Provider Admin

- As a Cloud Provider Admin, I want to view file storage usage across all tenants broken down by storage tier (fast, standard, archival) and capacity, so that I can account for the file-share capacity each tenant holds by tier.

### Cloud Infrastructure Admin

- As a Cloud Infrastructure Admin, I want file storage usage to be automatically grouped by the storage tiers I have configured in OSAC, so that each tier is metered independently — without requiring a separate registration step in the metering system.

### Tenant Admin

- As a Tenant Admin, I want to view my organization's file storage usage broken down by project, storage tier, and file share, so that I can attribute file-storage consumption to the teams that use it.

### Tenant User

- As a Tenant User, I want to view file storage usage for the projects I belong to, broken down by file share and storage tier, so that I can track how much file-storage capacity my workloads consume and on which tier.

## 5. Capabilities

### 5.1 File Storage Metering

- **CAP-1:** File storage shares are metered by storage tier from creation to deletion. The metering unit is GiB-seconds, but whether the meter tracks provisioned capacity (allocation model, as with block storage) or actual consumed capacity depends on the file storage service model — see Open Questions.

### 5.2 Query Dimensions and Attribution

- **CAP-2:** File storage usage is queryable by storage tier, capacity, tenant, and project. Storage tier is a required metering dimension as specified by [Part 1](/enhancements/OSAC-985-metering-and-usage-tracking/prd.md).
- **CAP-3:** File shares attached to a VM, cluster, or bare metal host are attributable to the parent resource, extending Part 1 CAP-11 and CAP-12 so that the full usage of a parent resource can be queried as a unified view including all subsidiary storage.

### 5.3 Cross-cutting

- **CAP-4:** File storage usage data is available alongside existing metering data without additional admin configuration steps. All file storage meters use the same accuracy and data-availability guarantees as Part 1 meters (CAP-4, CAP-15, CAP-16).

## 6. Usage Calculation Model

OSAC captures usage data. Downstream systems (billing, quota, analytics) consume this data and apply their own logic. This section defines the metering units and accumulation rules for file storage, extending the usage calculation model from [Part 1](/enhancements/OSAC-985-metering-and-usage-tracking/prd.md).

File storage metering uses the GiB-seconds unit, but the metering basis (provisioned capacity vs actual consumed capacity) is an open question. Industry precedent is split: AWS EFS meters by consumed storage, GCP Filestore by provisioned capacity, and Azure Files uses both models depending on the tier. The decision depends on how OSAC models the File service — see Open Questions. The storage tier is the primary metering dimension — different tiers represent different performance and capacity characteristics.

| Meter | Scope | Unit | Accumulation | Example (30 days) |
|-------|-------|------|-------------|-------------------|
| GiB-seconds per tier (file — model TBD) | creation to deletion | GiB × seconds | provisioned or consumed capacity × wall-clock duration | 50 GiB × 2,592,000s |

## 7. Acceptance Criteria

- [ ] A file storage share generates usage data (GiB-seconds) from creation to deletion, queryable per tenant, storage tier, and capacity
- [ ] When a file share is resized, subsequent usage data reflects the new capacity
- [ ] File storage usage can be broken down by storage tier, tenant, project, and individual file share
- [ ] A file share attached to a VM, cluster, or bare metal host can be attributed to the parent resource in a unified usage view
- [ ] File storage usage data appears alongside existing metering data without additional admin setup
- [ ] File storage meters record usage at per-second granularity — a file share existing for 30 seconds appears in usage data
- [ ] File storage usage totals are accurate — querying the same period twice returns consistent results
- [ ] Historical file storage usage data is available for at least 13 months
- [ ] Enabling file storage metering does not disrupt existing provisioning workflows

## 8. Open Questions

1. **File storage metering model — allocation vs consumption?** Should file storage meter by provisioned capacity (the size the tenant requested, as with block storage) or by actual consumed capacity (bytes stored)? Industry precedent is split — AWS EFS uses consumed storage, GCP Filestore uses provisioned, Azure Files uses both models (provisioned for SSD, consumed for HDD). The decision depends on how OSAC models the File service. A consumption-based model also implies periodic sampling of file-share size, which may require extending the Part 1 metering infrastructure — validate during design. **Owner: storage team.**

## 9. Assumptions

- Part 1 metering infrastructure is deployed and operational.
- File storage meters are additive to the Part 1 metering deployment and require no separate infrastructure (subject to the metering-model decision — a consumption model may require a sampling extension; see Open Questions).
- The tenant-facing FileShare API (OSAC-2387) will be implemented before file storage metering.

## 10. Dependencies

- **Part 1 metering infrastructure:** The metering infrastructure established by [Part 1](/enhancements/OSAC-985-metering-and-usage-tracking/prd.md) is a prerequisite. File storage metering extends but does not replace it.
- **OSAC-2387 (File Storage API):** FileShare resource must exist in the fulfillment-service proto before file storage metering can be implemented.

## 11. Risks

### 11.1 File storage API does not exist yet

- **Owner:** OSAC platform team
- **Mitigation:** The file storage (OSAC-2387) API must be implemented before its meters can be built. File storage metering delivery is gated on this API. Coordinate with the storage team to align timelines.

### 11.2 Part 1 metering infrastructure not yet built

- **Owner:** OSAC platform team
- **Mitigation:** All file storage meters depend on the metering infrastructure (event pipeline, usage store) established by Part 1 (OSAC-985). File storage metering implementation cannot begin until Part 1 infrastructure is deployed.

### 11.3 Consumption-based model may require infrastructure extensions

- **Owner:** OSAC platform team
- **Mitigation:** If the metering-model open question resolves to consumption-based metering, periodic sampling of actual file-share size may require extending the Part 1 event pipeline. Validate during design whether the Part 1 infrastructure supports the required sampling, or plan the extension.

## Related PRDs

This PRD is part of the OSAC metering family:

- **Metering for BMaaS** — [OSAC-2506](https://redhat.atlassian.net/browse/OSAC-2506)
- **Metering for Block Storage** — [OSAC-3141](https://redhat.atlassian.net/browse/OSAC-3141)
- **Metering for File Storage** — this document (OSAC-4940)
- **Metering for Networking** — [OSAC-3145](https://redhat.atlassian.net/browse/OSAC-3145)
- **Metering for Network Bandwidth** — [OSAC-3149](https://redhat.atlassian.net/browse/OSAC-3149)
- **Metering for Object Storage** — [OSAC-3444](https://redhat.atlassian.net/browse/OSAC-3444)

---

## Provenance

Authored: draft @ prd 0.9.0 - 562b610, workspace HEAD @ d165396

<!-- ai-workflow-provenance:{"schema_version":1,"provenance_kind":"session","workflow":"prd","workflow_version":"0.9.0","ai_workflows":"562b610","source_repo":"d165396","source_repo_branch":"HEAD","commits_behind_main":0,"commits_ahead_main":0,"main_ref":"main","phases":["draft"],"authoring_modes":["skill"],"context_changed":false,"origin_untracked":false} -->
