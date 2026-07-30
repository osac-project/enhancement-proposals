# Metering and Usage Tracking — Part 2e: Object Storage

| Field       | Value                |
|-------------|----------------------|
| Author(s)   | masayag@redhat.com   |
| Jira        | [OSAC-3444](https://redhat.atlassian.net/browse/OSAC-3444) |
| Date        | 2026-07-30           |

## Glossary

Terms defined in the [Part 1 PRD](/enhancements/OSAC-985-metering-and-usage-tracking/prd.md) apply here. Additional terms:

| Term | Definition |
|------|-----------|
| **Allocation metering** | Metering that runs for the duration a resource exists (creation to deletion), regardless of whether the resource is actively in use. Reflects the provider's physical capacity commitment. |
| **Consumption metering** | Metering that tracks actual usage of a resource (e.g., API request counts) as it occurs, independent of the resource's reserved capacity. |
| **Class A requests** | S3-aligned high-cost API operations: PUT, COPY, POST, LIST. |
| **Class B requests** | S3-aligned low-cost API operations: GET, SELECT, and all other requests. |

## 1. Problem Statement

OSAC provisions object storage buckets but has no mechanism to track their consumption over time. Object storage buckets reserve provisioned quota on the backend regardless of how much data is actually stored. Additionally, object storage usage is driven not only by capacity but also by API activity — a bucket serving millions of requests per day consumes significantly more provider resources in I/O and network bandwidth than an identically-sized archival bucket accessed once a month.

Without metering for object storage, Cloud Provider Admins have no usage data to account for either the storage capacity tenants hold or the API activity tenants generate, and Tenant Admins have no visibility into their object storage footprint across projects.

## 2. In Scope

- Object storage bucket metering — allocation-based metering for reserved bucket capacity (GiB-seconds) and consumption-based metering for API request counts (read and write operations)
- Dual metering model — provisioned quota tracked as GiB-seconds (allocation), and API request counts classified using S3-aligned categories: Class A (PUT/COPY/POST/LIST) and Class B (GET/SELECT/all other)
- Quota resize handling — when a bucket's quota is resized, subsequent metering intervals reflect the new capacity
- The ObjectStorageBucket resource depends on OSAC-2388

## 3. Out of Scope

- Block and file storage metering — tracked separately ([OSAC-3141](https://redhat.atlassian.net/browse/OSAC-3141))
- BMaaS metering — tracked separately ([OSAC-2506](https://redhat.atlassian.net/browse/OSAC-2506))
- Networking resource metering — tracked separately ([OSAC-3145](https://redhat.atlassian.net/browse/OSAC-3145))
- Network bandwidth metering — tracked separately ([OSAC-3149](https://redhat.atlassian.net/browse/OSAC-3149))
- Object storage API-level metering beyond the S3-aligned two-tier classification (Class A and Class B)
- Costing, billing, quota enforcement, and budget alerts — deferred to a separate PRD
- UI for viewing object storage usage — metering data is consumed by the billing system, which provides the user-facing usage views
- Workload-level metering inside tenant environments

## 4. User Stories

### Cloud Provider Admin

- As a Cloud Provider Admin, I want to view object storage usage across all tenants broken down by reserved capacity and API request counts (Class A: PUT/COPY/POST/LIST and Class B: GET/SELECT/all other), so that I can track both the storage space tenants hold and the API activity they generate.

### Tenant Admin

- As a Tenant Admin, I want to view my organization's object storage bucket usage broken down by project, capacity, and API request counts (Class A and Class B), so that I can attribute object storage usage to the teams that use them.

### Tenant User

- As a Tenant User, I want to view object storage bucket usage for the projects I belong to, broken down by capacity and API request counts (Class A and Class B), so that I can understand how my applications use object storage.

## 5. Capabilities

### 5.1 Object Storage Metering

- **CAP-1:** Object storage buckets are metered using a dual model — allocation (provisioned quota as GiB-seconds, not actual bytes stored) and consumption (API request counts classified using S3-aligned categories: Class A for PUT/COPY/POST/LIST and Class B for GET/SELECT/all other requests). When a bucket's quota is resized, the new capacity takes effect for subsequent metering intervals.

### 5.2 Query Dimensions

- **CAP-2:** Object storage usage is queryable by tenant, project, and bucket. Both allocation (GiB-seconds) and consumption (request counts by class) dimensions are independently queryable.

### 5.3 Cross-cutting

- **CAP-3:** Object storage usage data is available alongside existing metering data without additional admin configuration steps. All object storage meters use the same accuracy and data-availability guarantees as Part 1 meters (CAP-4, CAP-15, CAP-16).

## 6. Usage Calculation Model

OSAC captures usage data. Downstream systems (billing, quota, analytics) consume this data and apply their own logic. This section defines the metering units and accumulation rules for object storage, extending the usage calculation model from [Part 1](/enhancements/OSAC-985-metering-and-usage-tracking/prd.md).

Object storage uses a dual metering model:

1. **Allocation meter** — Provisioned quota tracked as GiB-seconds from creation to deletion. The allocation meter tracks the capacity reserved by the tenant at creation or resize, because backend storage is reserved at that size regardless of how much data is actually stored.

2. **Consumption meters** — API request counts using S3-aligned categories. Unlike block or file storage where usage is driven purely by reserved capacity over time, object storage usage is also driven by how actively the data is accessed. A 1 TiB bucket serving millions of Class B requests per day consumes significantly more provider resources in I/O and network bandwidth than an identically-sized archival bucket accessed once a month. The dual model gives providers two independent usage signals: storage capacity and API activity.

| Meter | Scope | Unit | Accumulation | Example (30 days) |
|-------|-------|------|-------------|-------------------|
| GiB-seconds (object storage allocation) | creation to deletion | GiB × seconds | provisioned quota × wall-clock duration | 500 GiB × 2,592,000s |
| Class A requests (object storage consumption) | continuous | count | total PUT/COPY/POST/LIST operations in period | 1,000,000 requests |
| Class B requests (object storage consumption) | continuous | count | total GET/SELECT/other operations in period | 10,000,000 requests |

## 7. Acceptance Criteria

- [ ] An object storage bucket generates capacity usage data (GiB-seconds) from creation to deletion, queryable per tenant and project
- [ ] An object storage bucket generates API request count usage data, broken down by Class A (PUT/COPY/POST/LIST) and Class B (GET/SELECT/all other) requests
- [ ] When a bucket's quota is resized, subsequent usage data reflects the new capacity
- [ ] Object storage usage can be broken down by tenant, project, and individual bucket
- [ ] Object storage usage data appears alongside existing metering data without additional admin setup
- [ ] Object storage meters record usage at per-second granularity for allocation, and per-request granularity for consumption
- [ ] Object storage usage totals are accurate — querying the same period twice returns consistent results
- [ ] Historical object storage usage data is available for at least 13 months
- [ ] Enabling object storage metering does not disrupt existing provisioning workflows

## 8. Assumptions

- Part 1 metering infrastructure is deployed and operational.
- Object storage meters are additive to the Part 1 metering deployment and require no separate infrastructure.
- The ObjectStorageBucket API (OSAC-2388) will be implemented before object storage metering.
- Allocation-based metering is supported by the Part 1 metering infrastructure without architectural changes.
- Consumption-based metering (API request counting) is supported by the Part 1 metering infrastructure, or will be extended to support it as part of this feature.

## 9. Dependencies

- **Part 1 metering infrastructure:** The metering infrastructure established by [Part 1](/enhancements/OSAC-985-metering-and-usage-tracking/prd.md) is a prerequisite. Part 2e extends but does not replace it.
- **OSAC-2388 (Object Storage API):** ObjectStorageBucket resource must exist in the fulfillment-service proto before object storage metering can be implemented.

## 10. Risks

### 10.1 Object Storage API does not exist yet

- **Owner:** OSAC platform team
- **Mitigation:** Object storage (OSAC-2388) API must be implemented before the object storage meters can be built. Object storage metering delivery is gated on this API. Coordinate with the storage team to align timelines.

### 10.2 Part 1 metering infrastructure not yet built

- **Owner:** OSAC platform team
- **Mitigation:** All Part 2e meters depend on the metering infrastructure (event pipeline, usage store) established by Part 1 (OSAC-985). Part 2e implementation cannot begin until Part 1 infrastructure is deployed.

### 10.3 Consumption metering may require infrastructure extensions

- **Owner:** OSAC platform team
- **Mitigation:** Part 1 was designed primarily around allocation-based meters. API request counting (consumption metering) may require extensions to the event pipeline to handle high-throughput event ingestion. Validate during design that the Part 1 infrastructure can support the request volume or plan extensions.

## Related PRDs

This PRD is part of the Metering Part 2 family:

- **Part 2a: BMaaS** — [OSAC-2506](https://redhat.atlassian.net/browse/OSAC-2506)
- **Part 2b: Block and File Storage** — [OSAC-3141](https://redhat.atlassian.net/browse/OSAC-3141)
- **Part 2c: Networking** — [OSAC-3145](https://redhat.atlassian.net/browse/OSAC-3145)
- **Part 2d: Network Bandwidth** — [OSAC-3149](https://redhat.atlassian.net/browse/OSAC-3149)
- **Part 2e: Object Storage** — this document (OSAC-3444)

---

## Provenance

Authored: draft @ prd 0.6.3 - 68284c8, workspace main @ ef4f3af

<!-- ai-workflow-provenance:{"schema_version":1,"provenance_kind":"session","workflow":"prd","workflow_version":"0.6.3","ai_workflows":"68284c8","source_repo":"ef4f3af","source_repo_branch":"main","commits_behind_main":0,"commits_ahead_main":1,"main_ref":"main","phases":["draft"],"authoring_modes":["skill"],"context_changed":false} -->
