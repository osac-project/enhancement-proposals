# Metering and Usage Tracking — Part 2b: Storage

| Field       | Value                |
|-------------|----------------------|
| Author(s)   | masayag@redhat.com   |
| Jira        | [OSAC-3141](https://redhat.atlassian.net/browse/OSAC-3141) |
| Date        | 2026-07-26           |

## Glossary

Terms defined in the [Part 1 PRD](/enhancements/metering-and-usage-tracking/prd.md) apply here. Additional terms:

| Term | Definition |
|------|-----------|
| **Allocation metering** | Metering that runs for the duration a resource exists (creation to deletion), regardless of whether the resource is actively in use. Reflects the provider's physical capacity cost. |
| **Storage tier** | A provider-defined storage performance and cost category (e.g., fast, standard, archival). The required pricing dimension for all storage resources. |

## 1. Problem Statement

OSAC provisions storage resources — block volumes, file shares, and object storage buckets — but has no mechanism to track their consumption over time. Storage resources consume provider capacity from the moment they are created until they are deleted, regardless of whether they are actively in use. A block volume occupies backend disk space whether the parent VM is running or not. A file share reserves capacity on the storage backend from creation. An object storage bucket reserves provisioned quota on the backend regardless of how much data is actually stored.

Without metering for these resources, Cloud Provider Admins have no usage data to account for the storage capacity tenants hold, and Tenant Admins have no visibility into their storage footprint across projects and storage tiers. This gap grows as OSAC adds new storage types — every new storage resource added without metering is usage the provider cannot track.

## 2. In Scope

- Block storage metering — allocation-based metering for standalone volumes by storage tier and capacity (GiB-seconds)
- File storage metering — allocation-based metering for shared file storage by storage tier and capacity (GiB-seconds)
- Object storage bucket metering — allocation-based metering for reserved bucket capacity (GiB-seconds) and consumption-based metering for API request counts (read and write operations)
- Parent-child attribution — extending [Part 1](/enhancements/metering-and-usage-tracking/prd.md) CAP-11 and CAP-12 so that storage volumes attached to VMs, clusters, or bare metal hosts can be attributed to the parent resource in a unified usage view

## 3. Out of Scope

- BMaaS metering — tracked separately ([OSAC-2506](https://redhat.atlassian.net/browse/OSAC-2506))
- Networking resource metering — tracked separately ([OSAC-3145](https://redhat.atlassian.net/browse/OSAC-3145))
- Network bandwidth metering — tracked separately ([OSAC-3149](https://redhat.atlassian.net/browse/OSAC-3149))
- Costing, billing, quota enforcement, and budget alerts — deferred to a separate PRD
- Object storage API-level metering by individual operation type (PUT, GET, LIST, DELETE) — this PRD meters read vs. write request counts in aggregate. The ObjectStorageBucket resource depends on OSAC-2388.
- VM boot disk storage tier attribution — requires `storage_tier_id` on ComputeInstanceDisk, tracked separately
- Workload-level metering inside tenant environments

## 4. User Stories

### Cloud Provider Admin

- As a Cloud Provider Admin, I want to view storage usage across all tenants broken down by storage tier (fast, standard, archival) and capacity, so that I can price storage according to the tier's cost to the provider.
- As a Cloud Provider Admin, I want to view object storage usage across all tenants broken down by reserved capacity and API request counts (read/write), so that I can track both the storage space tenants hold and the API activity they generate. Object storage usage has two independent drivers: stored capacity (backend disk space) and access frequency (I/O and network). A high-traffic bucket consumes more provider resources than an archival one at the same capacity, so both dimensions must be visible for accurate usage tracking.

### Cloud Infrastructure Admin

- As a Cloud Infrastructure Admin, I want storage usage to be automatically grouped by the storage tiers I have configured in OSAC, so that each tier (e.g., NVMe SSD, HDD archival) can be priced independently in the provider's rate schedule — without requiring a separate registration step in the metering system.

### Tenant Admin

- As a Tenant Admin, I want to view my organization's storage usage broken down by project, storage tier, and volume, so that I can identify which teams consume the most storage capacity and on which tier.
- As a Tenant Admin, I want to view my organization's object storage bucket usage broken down by project, capacity, and API request counts, so that I can attribute object storage costs to the teams that use them.

### Tenant User

- As a Tenant User, I want to view storage usage for the projects I belong to, broken down by volume and storage tier, so that I can track how much storage capacity my workloads consume and on which tier.
- As a Tenant User, I want to view object storage bucket usage for the projects I belong to, broken down by capacity and API request counts, so that I can understand how my applications use object storage.

## 5. Capabilities

### 5.1 Block and File Storage Metering

- **CAP-1:** Block storage volumes are metered using allocation-based metering from creation to deletion. The metering unit is GiB-seconds per storage tier.
- **CAP-2:** File storage shares are metered using the same allocation model as block storage — GiB-seconds per storage tier from creation to deletion.

### 5.2 Object Storage Metering

- **CAP-3:** Object storage buckets are metered using a dual model — allocation (provisioned quota as GiB-seconds, not actual bytes stored) and consumption (API request counts for read and write operations). The allocation meter tracks the bucket's provisioned quota — the capacity reserved by the tenant at creation or resize — because backend storage is reserved at that size regardless of how much data is actually stored. When a bucket's quota is resized, the new capacity takes effect for subsequent metering intervals. Unlike block or file storage where cost is driven purely by reserved capacity over time, object storage cost is also driven by how actively the data is accessed. A 1 TiB bucket serving millions of read requests per day costs the provider significantly more in I/O and network bandwidth than an identically-sized archival bucket accessed once a month. The dual model lets providers price both dimensions independently: storage capacity at one rate and API activity at another.

### 5.3 Query Dimensions and Attribution

- **CAP-4:** Storage usage is queryable by storage tier, capacity, tenant, and project. Storage tier is a required pricing dimension as specified by [Part 1](/enhancements/metering-and-usage-tracking/prd.md).
- **CAP-5:** Storage volumes attached to a VM, cluster, or bare metal host are attributable to the parent resource, extending Part 1 CAP-11 and CAP-12 so that the full usage of a parent resource can be queried as a unified view including all subsidiary storage.

### 5.4 Cross-cutting

- **CAP-6:** Storage meters are additive to the Part 1 metering deployment and require no separate infrastructure. All storage meters use the same per-second granularity, deduplication, and retention requirements as Part 1 (CAP-4, CAP-15, CAP-16).

## 6. Charge Calculation Model

OSAC provides usage data. The provider applies their own price schedule to generate charges. This section defines the metering units and formulas for storage, extending the charge calculation model from [Part 1](/enhancements/metering-and-usage-tracking/prd.md).

Storage uses allocation meters because storage capacity is reserved from creation and cannot be shared with other tenants. The storage tier determines the rate — NVMe SSD costs more per GiB than HDD archival. Object storage adds a consumption meter for API request counts alongside the allocation meter for reserved capacity.

| Meter | Formula | Example |
|-------|---------|---------|
| GiB-seconds per tier (block/file allocation) | capacity × duration × rate/GiB-s | 100 GiB × 2592000s × $0.000000015 = $3.89 (30 days, fast tier) |
| GiB-seconds per tier (object storage allocation) | capacity × duration × rate/GiB-s | 500 GiB × 2592000s × $0.000000010 = $12.96 (30 days) |
| API read requests (object storage consumption) | count × rate/request | 10,000,000 × $0.0000004 = $4.00 |
| API write requests (object storage consumption) | count × rate/request | 1,000,000 × $0.000005 = $5.00 |

## 7. Acceptance Criteria

- [ ] A block storage volume generates usage data (GiB-seconds) from creation to deletion, queryable per tenant, storage tier, and capacity
- [ ] A file storage share generates usage data (GiB-seconds) from creation to deletion, queryable per tenant, storage tier, and capacity
- [ ] An object storage bucket generates capacity usage data (GiB-seconds) from creation to deletion, queryable per tenant and storage tier
- [ ] An object storage bucket generates API request count usage data, broken down by read and write operations
- [ ] When a storage volume or object storage bucket is resized, subsequent usage data reflects the new capacity
- [ ] Storage usage can be broken down by storage tier, tenant, project, and individual volume
- [ ] A storage volume attached to a stopped VM continues generating usage data (extending Part 1 CAP-11)
- [ ] A storage volume attached to a VM or cluster can be attributed to the parent resource in a unified usage view
- [ ] Storage meters are additive to the Part 1 metering deployment and require no separate infrastructure
- [ ] All Part 1 cross-cutting acceptance criteria (per-second granularity, deduplication, retention, independent deployment) apply to storage meters

## 8. Assumptions

- Part 1 metering infrastructure is deployed and operational.
- Tenant-facing storage APIs (Volume, FileShare) will be implemented before storage metering. Object storage metering depends on OSAC-2388 (Object Storage API).
- Allocation-based metering is supported by the Part 1 metering infrastructure without architectural changes — allocation meters use different start/stop state semantics.

## 9. Dependencies

- **Part 1 metering infrastructure:** The metering infrastructure established by [Part 1](/enhancements/metering-and-usage-tracking/prd.md) is a prerequisite. Part 2b extends but does not replace it.
- **OSAC-984 (Storage Volume API):** Tenant-facing block storage Volume resource must exist in the fulfillment-service proto before storage metering can be implemented.
- **OSAC-2387 (File Storage API):** FileShare resource must exist in the fulfillment-service proto before file storage metering can be implemented.
- **OSAC-2388 (Object Storage API):** ObjectStorageBucket resource must exist in the fulfillment-service proto before object storage metering can be implemented.

## 10. Risks

### 10.1 Storage APIs do not exist yet

- **Owner:** OSAC platform team
- **Mitigation:** Block storage (OSAC-984), file storage (OSAC-2387), and object storage (OSAC-2388) APIs must be implemented before their respective meters can be built. Storage metering delivery is gated on these APIs. Coordinate with the storage team to align timelines.

### 10.2 Part 1 metering infrastructure not yet built

- **Owner:** OSAC platform team
- **Mitigation:** All Part 2b meters depend on the metering infrastructure (event pipeline, provider adapters) established by Part 1 (OSAC-985). Part 2b implementation cannot begin until Part 1 infrastructure is deployed.

## 11. Open Questions

### 11.1 Object storage API metering granularity

- **Owner:** OSAC platform team
- **Impact:** CAP-3. Should object storage metering distinguish between different API operation types (PUT/GET/LIST/DELETE) with separate meters, or aggregate all operations into read vs. write categories? This PRD aggregates into read vs. write. Fine-grained per-operation metering would increase dimensionality but give providers more pricing flexibility.

## Related PRDs

This PRD is part of the Metering Part 2 family:

- **Part 2a: BMaaS** — [OSAC-2506](https://redhat.atlassian.net/browse/OSAC-2506)
- **Part 2b: Storage** — this document (OSAC-3141)
- **Part 2c: Networking** — [OSAC-3145](https://redhat.atlassian.net/browse/OSAC-3145)
- **Part 2d: Network Bandwidth** — [OSAC-3149](https://redhat.atlassian.net/browse/OSAC-3149)
