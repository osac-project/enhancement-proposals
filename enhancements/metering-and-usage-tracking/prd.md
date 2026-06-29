# Metering and Usage Tracking

| Field       | Value                |
|-------------|----------------------|
| Author(s)   | masayag@redhat.com   |
| Jira        | [OSAC-985](https://redhat.atlassian.net/browse/OSAC-985) |
| Epic        | [OSAC-65](https://redhat.atlassian.net/browse/OSAC-65) (to be updated after PRD approval) |
| Date        | 2026-06-28           |

## Glossary

| Term | Definition |
|------|-----------|
| **Event** | A discrete, immutable record of a resource lifecycle change. Events are the source of truth for billing-grade metering. |
| **Meter** | A named aggregation that turns events into a measurable quantity (e.g., total VM uptime grouped by tenant). |
| **Metric** | The aggregated output of a meter over a time window — the queryable result. |
| **Usage** | Measured consumption of a resource (e.g., CPU core-seconds consumed while a VM was running). |
| **Allocation** | Reserved capacity of a resource, regardless of whether it is actively used. |
| **Resource class** | A provider-defined category for differentiated pricing. Examples: host type for CaaS worker nodes (e.g., `gpu-h100`, `cpu-only`), template for VMaaS, machine class for BMaaS, storage tier for Storage-aaS. To the metering system, it is an opaque label used for grouping. |
| **Template** | A configuration defining a resource offering (cores, memory, node sets). In metering, `template` enables per-offering pricing. |
| **Cost Model** | A configuration mapping meters to rates, defining how consumption becomes charges. May differ by audience (provider-internal vs. tenant-facing). |
| **Price List** | A set of rates within a cost model with a defined validity period. |
| **Budget** | A spending limit on a scope (tenant, project, resource type) for a configurable time period. |
| **FOCUS** | [FinOps Open Cost and Usage Specification](https://focus.finops.org/) — a standard format for exchanging billing and usage data. |

## 1. Problem Statement

OSAC provisions and manages cloud resources (VMs, clusters, networks, storage, public IPs) but has no mechanism to track their consumption over time. Cloud Provider Admins need usage data to generate bills and enforce quotas. Tenant Admins need usage visibility to manage costs across their organization. Without a standard metering mechanism, each provider builds their own, leading to fragmented approaches and inconsistent data models. OSAC meters only what OSAC provisions — it is not a datacenter-wide metering solution.

Beyond raw metering, providers need a costing layer to define pricing models, generate itemized charges per tenant, and maintain price list histories. Providers and tenants have different cost views: a provider tracks actual infrastructure cost while a tenant sees the charges they are billed. OSAC must support both perspectives to serve the sovereign cloud business model.

## 2. Goals and Non-Goals

### 2.1 Goals

- Cloud Provider Admins can query aggregated usage data per tenant for billing and quota enforcement
- Tenant Admins can view their organization's usage with tenant-scoped access control
- All metered resources support per-second granularity
- CaaS metering supports per-resource-class billing so that different hardware classes (e.g., GPU vs CPU workers) can be priced independently
- All metering is configurable — Cloud Provider Admins enable/disable meters per resource type
- The metering and costing stack runs on-premises under the provider's control — no data leaves the provider's infrastructure

### 2.2 Non-Goals

- Costing, billing, and quota enforcement — deferred to a separate PRD
- Workload-level metering inside tenant clusters (OSAC has no visibility into tenant-managed workloads)
- BMaaS, Storage-aaS, Object Storage metering (deferred to a future PRD). When storage metering comes in scope, storage tier (e.g., fast, standard, archival — per the [tenant-storage-tiers](/enhancements/tenant-storage-tiers) EP) must be a pricing dimension.
- Networking resource metering — VirtualNetworks, Subnets, PublicIPs, NAT Gateways (deferred to a future PRD). When networking metering comes in scope, it covers multiple resource types with region as a dimension (per the [networking](/enhancements/networking) EP).
- Network bandwidth metering (ingress/egress traffic per tenant) — unclear which component has access to the primary data; deferred to custom service metering if a networking vendor provides the data source

### 2.3 Services in Scope

| Service | Scope |
|---------|-------|
| VMaaS | In scope |
| CaaS | In scope |
| MaaS | In scope (capabilities defined; data source ownership to be resolved during design) |
| BMaaS | Deferred |

## 3. Capabilities

### 3.1 Cloud Provider Admin

- **CAP-1:** View aggregated usage across all tenants for a billing period, broken down by tenant, resource type, and template.
- **CAP-2:** Choose which meters are active for the deployment — enable metering for VMaaS, CaaS, and MaaS, or disable meters for resource types that the provider does not offer or does not wish to charge for. A disabled meter stops event emission entirely — no events generated, no storage consumed, no pipeline load.
- **CAP-3:** View usage of tenant-provisioned cluster worker nodes broken down by resource class (e.g., GPU vs CPU), so that different hardware classes can be priced independently.
- **CAP-17:** View AI model inference usage broken down by tenant, model, and token type — including input tokens, output tokens, cached tokens, and total tokens consumed.
- **CAP-4:** Receive accurate metering data for resources that exist for less than one minute — no resource goes unmetered due to brevity.

### 3.2 Cloud Infrastructure Admin

- **CAP-5:** Deploy, upgrade, and monitor the metering system using standard Kubernetes tooling — including adding or removing meters, updating the metering stack version, and observing pipeline health (ingestion lag, storage usage). Example: a provider starts offering DBaaS and adds a new meter to track database instance uptime; or a provider stops offering a service and removes its meter to stop collecting unused data.
- **CAP-6:** Emit metering events for custom services not covered by built-in meters, so that providers can track consumption of additional offerings alongside core services.
- **CAP-7:** Configure retention periods for raw events and aggregated data independently.

### 3.3 Tenant Admin

- **CAP-8:** View usage for their own organization over a period of time, broken down by project, resource type, and template. Cannot see other tenants' data.
- **CAP-9:** View usage aggregated by project (including nested projects), so that costs can be attributed to specific teams, grants, or departments.

### 3.4 Tenant User

- **CAP-10:** View their own tenant's usage over a period of time — what resources are being consumed and for how long.

### 3.5 Cross-cutting

- **CAP-11:** VMaaS metering is consumption-based — only active VMs (while running) are metered. Allocated but idle VMs (stopped, paused) are not metered. Providers who need allocation-based charging for VMs should raise this during PRD review.
- **CAP-12:** CaaS metering is consumption-based — only active clusters (ready or progressing) are metered. Clusters in failed state are not metered. All metered resources belonging to a cluster (control plane, worker nodes, and — when in scope — storage, networking) must be attributable to the parent cluster so that the full cost of a cluster can be queried as a unified view. Providers who need allocation-based charging for clusters should raise this during PRD review.
- **CAP-19:** MaaS metering is consumption-based — charged per token and per inference request, not per allocated model instance. GPU infrastructure cost is embedded in the provider's per-token/per-model pricing. Metering events must be emitted within 30 seconds of the inference request completing, and processed within 60 seconds of receipt, so that downstream systems (e.g., quota enforcement, when available) can evaluate against near-real-time balances. These latency requirements do not apply to VMaaS or CaaS, where delays up to the polling interval are acceptable.
- **CAP-14:** The metering system can be deployed independently without affecting existing OSAC provisioning. Some providers may prefer to use their own metering solution — independent deployment ensures OSAC emits lifecycle events that any metering system can consume.
- **CAP-15:** Upgrading the metering system does not cause loss of collected metering data or gaps in measurement of ongoing workloads.
- **CAP-16:** Duplicate events do not cause double-counting in any meter.

## 4. Operational Expectations

- Raw metering events must be retained for at least 7 days (configurable).
- Aggregated metering data must be retained for at least 13 months to support annual billing audits. The retention period must be configurable.
- The metering ingestion layer must scale to handle concurrent lifecycle events from multiple tenants' resources without dropping events or introducing delays that exceed the polling interval.

## 5. Acceptance Criteria

### VMaaS

- [ ] A running VM generates usage data queryable as aggregated uptime per tenant. Both instance-type-seconds (for flat-rate pricing) and core-seconds / GiB-seconds (for resource-based pricing) are available.
- [ ] A stopped or paused VM does not generate usage data
- [ ] VM usage can be broken down by tenant, project, template, and instance

### CaaS

- [ ] An active cluster generates separate usage data for the control plane and for each worker node set
- [ ] Worker node usage can be broken down by resource class, enabling differentiated pricing for GPU vs CPU
- [ ] All metered resources belonging to a cluster (control plane, worker nodes) can be queried as a unified cluster-level usage view

### MaaS

- [ ] An inference request generates usage data with input tokens, output tokens, and total tokens queryable per tenant and per model
- [ ] MaaS usage can be broken down by tenant, project, and model
- [ ] A metering event is emitted within 30 seconds of an inference request completing, and processed within 60 seconds so that downstream systems (e.g., quota enforcement, when available) can evaluate against near-real-time balances

### Cross-cutting

- [ ] A Tenant Admin can view their own usage but cannot see other tenants' data
- [ ] A Cloud Provider Admin can view usage across all tenants
- [ ] A Cloud Provider Admin can disable a meter and no events are emitted for that resource type
- [ ] A resource that exists for 30 seconds appears in the usage data
- [ ] Deploying the metering system does not require changes to existing OSAC resources or workflows
- [ ] A Tenant Admin can view usage grouped by project and see consumption per project within their tenant
- [ ] Sending a duplicate event does not increase any meter value
- [ ] Raw events older than the configured retention period are purged
- [ ] Aggregated data from 13 months ago is still queryable
- [ ] A Cloud Infrastructure Admin can add a new meter via configuration update and query it after deployment
- [ ] Upgrading the metering system does not cause data loss or measurement gaps

## 6. Assumptions

- The metering and costing stack is deployed on-premises under the provider's control.
- Cloud Infrastructure Admins have cluster-admin access for installing the metering stack.

## 7. Dependencies

- **Self-managed metering and costing stack** — an on-premises solution that provides event ingestion, meter aggregation, and usage query capabilities.
- **Durable event pipeline** — a reliable message delivery layer between OSAC and the metering stack.
- **OSAC provisioning controllers** — must integrate event emission for VMaaS and CaaS lifecycle transitions.

## 8. Risks

### 8.1 Cost management stack feature gaps

- **Owner:** OSAC platform team / Cost Management team
- **Mitigation:** The self-managed cost management stack may not yet support all capabilities required by this PRD. Feature development must be coordinated between OSAC and the cost management team.

### 8.2 Integration complexity

- **Owner:** OSAC platform team / Cost Management team
- **Mitigation:** OSAC resource types may not map directly to the cost management stack's existing data model. Prototype the integration early to surface mismatches.

## 9. Open Questions

### 9.1 Should Tenant Users see only their own resource usage or all usage within their tenant?

- **Owner:** OSAC platform team / UI team
- **Impact:** CAP-8, CAP-10. The metering system scopes data at the tenant level. Per-user filtering within a tenant is a UI/RBAC concern to be addressed in the Usage API or landing zone design. The [Organizations](/enhancements/organizations) EP defines project-level permissions (e.g., `VIEW_PROJECT`) — metering data visibility should respect these same permissions so users only see usage for projects they have access to.

### 9.2 Should OSAC provide a combined "current footprint" view joining live resource state with metering data?

- **Owner:** OSAC platform team / UI team
- **Impact:** The metering system provides consumption history; OSAC's resource listing provides current inventory. A combined view (e.g., "3 VMs running, X core-hours consumed this month") is a presentation concern to be addressed in the landing zone or Usage API.

### 9.3 What should happen when the metering system is unavailable?

- **Owner:** OSAC platform team
- **Impact:** CAP-14. Three options: (1) block provisioning when metering is unavailable, to prevent untracked resources; (2) allow provisioning and accept temporary metering gaps; (3) allow provisioning with a reconciliation service that periodically syncs OSAC's provisioned resource state with the metering system, ensuring all resources are eventually metered. The right choice may be configurable per provider. Failure types also matter — failing to record a provisioning event is different from a temporary processing delay.

## Charge Calculation Model

OSAC provides usage data. The provider applies their own price schedule to generate charges. OSAC does not enforce prices or generate invoices. A separate PRD will address the costing layer to automate charge calculation.

### VMaaS

The primary VMaaS grouping dimension is the instance type name (per the [vm-instance-types](/enhancements/vm-instance-types) EP). Core-seconds and GiB-seconds are derived dimensions available for providers who prefer resource-based pricing over flat-rate per instance type.

| Pricing Model | Meter | Formula | Example (2-core, 8 GiB VM, 1 hour) |
|--------------|-------|---------|--------------------------------------|
| Flat per-instance-type | vm uptime | uptime × price/s | 3600s × $0.001/s = $3.60 |
| Per-core | cpu core-seconds | core-seconds × price | 7200 × $0.0001 = $0.72 |
| Per-memory | memory GiB-seconds | GiB-seconds × price | 28800 × $0.00005 = $1.44 |
| Combined | cpu + memory | sum | $0.72 + $1.44 = $2.16 |

### CaaS

| Component | Meter | Formula | Example (1 hour, 2 GPU + 1 CPU worker) |
|-----------|-------|---------|----------------------------------------|
| Control plane | cluster uptime | uptime × price_cp | 3600s × $0.01 = $36.00 |
| GPU workers | worker node-seconds (gpu-h100) | node-seconds × price_gpu | 7200 × $0.02 = $144.00 |
| CPU workers | worker node-seconds (cpu-only) | node-seconds × price_cpu | 3600 × $0.005 = $18.00 |
| **Total** | | | **$198.00/hour** |

### MaaS

| Component | Meter | Formula | Example |
|-----------|-------|---------|---------|
| Input tokens | input tokens | tokens × price/1K tokens | 1M × $0.003/1K = $3.00 |
| Output tokens | output tokens | tokens × price/1K tokens | 500K × $0.015/1K = $7.50 |
| Cached tokens | cached tokens | tokens × discounted price/1K | 200K × $0.0015/1K = $0.30 |
