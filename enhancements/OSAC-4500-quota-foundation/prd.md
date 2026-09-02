# Quota Foundation

| Field       | Value   |
|-------------|---------|
| Author(s)   | Omer Vishlitzky |
| Jira        | [OSAC-4500](https://redhat.atlassian.net/browse/OSAC-4500) (Feature) · [OSAC-4220](https://redhat.atlassian.net/browse/OSAC-4220) (Outcome) |
| Date        | 2026-08-27 |

## Problem Statement

Cloud Provider Admins need controls that help them avoid running out of capacity. OSAC lets a tenant provision VMs, clusters, bare-metal hosts, storage, images, networks, and models with no upper bound on what the tenant may hold, so a single tenant can consume the deployment's shared capacity and block every other tenant. A Cloud Provider Admin has no way to enforce the limits they sold or to tell whether they have committed more than the hardware holds.

Tenants need controls that help them avoid unexpected spending. A Tenant User only finds out that a resource is unavailable when an order fails partway through provisioning, with no way to see beforehand how much of a limit is left or understand why.

Without usage quota, OSAC cannot be run as a commercial multi-tenant service, and budget quota and billing enforcement cannot be built on top of it.

## In Scope

Quota limits apply per **dimension**, a resource kind and its unit. The dimensions in scope, by service:

| Service | Dimensions | Unit |
|---------|-----------|------|
| VMaaS | vCPUs; memory; GPUs by type | cores / GiB / count per type |
| Block storage | volume count; capacity per storage tier | count / GiB |
| Images | tenant-uploaded image count; capacity | count / GiB |
| Networking | public IPs; NAT gateways; virtual networks | count |
| BMaaS | instances by type | count per type |
| CaaS | control planes | count |

The enforcement rules that apply across those dimensions:

- Quota is checked when a resource is created and when it is resized or scaled up. An order that would exceed a limit is rejected before any provisioning begins, and its usage is released if the order later fails.
- Quota limits are enforced atomically: multiple orders for the same tenant, submitted consecutively or at the same time, cannot together exceed a limit that any one of them would have been rejected for alone.
- A tenant's recorded usage stays accurate through failures, including a failed order or a failure inside OSAC during provisioning, so a failure never leaves usage overstated or understated.
- A resource composed of other resources also consumes quota for those underlying resources: a CaaS cluster's control plane counts against the CaaS dimension, while its worker nodes, provisioned as VMs or bare-metal hosts, draw on the corresponding VMaaS or BMaaS dimensions. When such an order is rejected, the reason identifies the underlying dimension and how it relates to the order, rather than a bare limit error.
- A resource counts against its tenant's limits from creation until deletion, whether it is running, idle, or stopped. A tenant's limits cover all of its resources regardless of deployment topology.
- Lowering a limit below current usage blocks new provisioning without terminating running resources, and the tenant's over-limit state (usage above the limit) is shown.

## Out of Scope

- Project-scoped and custom-label-scoped quota. Quota is scoped to the tenant.
- Budget quota. Limits denominated in currency rather than resources.
- Fair-share, borrowing, or preemption between tenants, and guaranteed minimum floors or tiered overcommit; a static limit does not flex into another tenant's idle allocation.
- Capacity reservation. A limit permits provisioning up to an amount; it does not reserve or guarantee the hardware. Sizing limits to real capacity is the provider's responsibility.
- Time-bounded allocations that expire and are renewed on a grant cycle.
- Quota on workloads running inside a tenant's own cluster or VM, which OSAC cannot observe.
- Rate limiting of the OSAC API itself for platform protection.
- MaaS token and request quota. This is a rate limit over a time window, a different kind of capability from the held-resource capacity quota covered here, and is planned as a future PRD.
- Historical usage reporting. This PRD covers current usage against limits; usage over a past time range is planned as a future PRD.

## User Stories

### Cloud Provider Admin

- As a Cloud Provider Admin, I want every dimension to default to zero until I configure otherwise, so that no tenant can provision anything before I have decided what it may hold.
- As a Cloud Provider Admin, I want a newly onboarded tenant to start with the default limits I have configured, so that every new tenant begins with the baseline I have set without my configuring it per tenant.
- As a Cloud Provider Admin, I want to raise or lower a tenant's limit for any dimension at any time, so that I can honor a contract change without disrupting the tenant's running resources.
- As a Cloud Provider Admin, I want to approve or deny a tenant's quota-increase request within OSAC, so that quota changes do not depend on an external system.
- As a Cloud Provider Admin, I want an audit record of every quota change that captures who changed it, when, the tenant and dimension affected, and the previous and new value, so that I can answer a contract or audit dispute.

### Tenant Admin

- As a Tenant Admin, I want to view my tenant's current usage against its limits, so that I can see how close we are to our limits and decide when to ask for more.
- As a Tenant Admin, I want to request additional quota and track the request's status, so that I can plan around the answer.
- As a Tenant Admin, I want to configure a warning threshold on a dimension, so that I control how much headroom I have to act before my users are blocked.
- As a Tenant Admin, I want to be notified when my tenant crosses that warning threshold, so that I can act before my users are blocked.

### Tenant User

- As a Tenant User, I want to see how much of a limit is left before I submit an order, so that I know whether the order will succeed.
- As a Tenant User, I want an order that would exceed a limit rejected immediately, with a message naming the dimension, the limit, and current usage, so that I understand why instead of hitting an opaque failure.

## Assumptions

- A tenant's current usage (what it holds at this instant) can be determined at request time without depending on the metering pipeline, which reports consumption integrated over time.
- The quota cost of an order is determinable when the order is submitted.
- Every resource composed of other resources exposes which underlying resource-type instances back it, so the quota system can attribute usage to the correct dimension.

## Dependencies

- **[Organizations](/enhancements/OSAC-1030-organizations):** Tenant is the quota scope; tenant identity must be present on every resource that consumes quota.
- **[Catalog Items v2](/enhancements/OSAC-3538-catalog-items-v2):** when an order is placed against a catalog item, its quota cost must be derivable at submission.
- **[Instance Types](/enhancements/OSAC-46-vm-instance-types), [Bare-Metal Instance Types](/enhancements/OSAC-1201-baremetal-instance-types), [Storage Tiers](/enhancements/OSAC-1110-storage-tier):** define the resource classes that limits are expressed against.
- **UI (osac-ux):** quota visibility and the increase-request workflow across personas (OSAC-4504 UX, OSAC-4505 UI).
- **[Notifications API](https://redhat.atlassian.net/browse/OSAC-75):** delivers the warning-threshold notification to the Tenant Admin.

---

## Provenance

Authored: draft @ prd 0.9.0 - f7f8c6d, workspace main @ 4a8ac6c
Final: revise @ prd 0.9.0 - 562b610, workspace main @ 63b090a

> Context changed between draft and revise.

<!-- ai-workflow-provenance:{"schema_version":1,"provenance_kind":"session","workflow":"prd","workflow_version":"0.9.0","ai_workflows":"562b610","source_repo":"63b090a","source_repo_branch":"main","commits_behind_main":0,"commits_ahead_main":0,"main_ref":"main","phases":["draft","revise","revise","respond","revise"],"authoring_modes":["skill"],"context_changed":true,"origin_untracked":false} -->
