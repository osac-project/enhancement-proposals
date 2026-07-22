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
| **Usage** | Measured consumption of a resource (e.g., instance-type-seconds consumed while a VM was running). |
| **Allocation** | Reserved capacity of a resource, regardless of whether it is actively used. |
| **Resource class** | A provider-defined category for differentiated pricing. Examples: host type for CaaS worker nodes (e.g., `gpu-h100`, `cpu-only`), template for VMaaS, machine class for BMaaS, storage tier for Storage-aaS. To the metering system, it is an opaque label used for grouping. |
| **Service** | An offering that can be purchased from a service provider, and can include many types of usage or other charges (e.g., a cloud database service may include compute, storage, and networking charges). In OSAC, a catalog item (per the [catalog-items](/enhancements/catalog-items) EP) maps to a Service — it's what the tenant provisions from. A single Service may bundle multiple independently priceable components (e.g., compute, OS entitlement, boot storage for VMaaS; control plane, workers, cluster version for CaaS). The metering system carries catalog item and template references so that downstream systems can trace charges back to the originating Service. |
| **Price List** | A comprehensive list of prices offered by a service provider. |
| **Billing Period** | The time window that an organization receives an invoice for, inclusive of the start date and exclusive of the end date. |
| **Budget** | A spending limit on a scope (tenant, project, resource type) for a configurable time period. |
| **FOCUS** | [FinOps Open Cost and Usage Specification](https://focus.finops.org/) — an open-source specification that defines requirements for billing data. |

## 1. Problem Statement

OSAC provisions and manages cloud resources (VMs, clusters, networks, storage, public IPs) but has no mechanism to track their consumption over time. Cloud Provider Admins need usage data to generate bills and enforce quotas. Tenant Admins need usage visibility to manage costs across their organization. Without a standard metering mechanism, each provider builds their own, leading to fragmented approaches and inconsistent data models. OSAC meters only what OSAC provisions — it is not a datacenter-wide metering solution.

Beyond raw metering, providers need a pricing layer to define rate schedules, generate itemized charges per tenant, and maintain price list histories. Providers and tenants have different views of the same usage data: a provider sees consumption across all tenants as input to billing, while a tenant sees only their own consumption and the resulting charges. OSAC does not track the provider's infrastructure cost (hardware, power, cooling) — that remains internal to the provider. OSAC must support both perspectives to serve the sovereign cloud business model.

## 2. Goals and Non-Goals

### 2.1 Goals

- Cloud Provider Admins can query aggregated usage data per tenant as input to billing and quota enforcement systems
- Tenant Admins can view their organization's usage with tenant-scoped access control
- All metered resources support per-second granularity
- CaaS metering supports per-resource-class billing so that different hardware classes (e.g., GPU vs CPU workers) can be priced independently
- The metering and costing stack runs on-premises under the provider's control — no data leaves the provider's infrastructure
- Tenant Admins and Tenant Users can view their organization's usage through the osac-ui console; Cloud Provider Admins can view usage across all tenants through the same console

### 2.2 Non-Goals

- Costing, billing, and quota enforcement — deferred to a separate PRD
- Workload-level metering inside tenant clusters, VMs, or hosts (OSAC has no visibility into tenant-managed workloads)
- BMaaS, Storage-aaS, Object Storage metering (deferred to a future PRD). When storage metering comes in scope, storage tier (e.g., fast, standard, archival — per the [tenant-storage-tiers](/enhancements/OSAC-172-tenant-storage-tiers) EP) must be a pricing dimension.
- Networking resource metering — VirtualNetworks, Subnets, PublicIPs, NAT Gateways (deferred to a future PRD). When networking metering comes in scope, it covers multiple resource types with region as a dimension (per the [networking](/enhancements/OSAC-356-networking) EP).
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
- **CAP-2:** View usage of tenant-provisioned cluster worker nodes broken down by resource class (e.g., GPU vs CPU), so that different hardware classes can be priced independently.
- **CAP-3:** View AI model inference usage broken down by tenant, model, and token type — including input tokens, output tokens, cached tokens, and total tokens consumed.
- **CAP-4:** Receive accurate metering data for resources that exist for less than one minute — no resource goes unmetered due to brevity. The minimum metering resolution is 1 second; sub-second resources are not captured.

### 3.2 Cloud Infrastructure Admin

- **CAP-5:** Deploy, upgrade, and monitor the metering system — including adding or removing meters, updating the metering stack version, and observing pipeline health (ingestion lag, storage usage). Example: a provider starts offering DBaaS and adds a new meter to track database instance uptime; or a provider stops offering a service and removes its meter to stop collecting unused data.
- **CAP-6:** Register and configure meters for custom services not covered by built-in meters — for example, by defining a new meter name, its unit, and its grouping dimensions via a configuration update — so that providers can track consumption of additional offerings alongside core services.
- **CAP-7:** Configure retention periods for raw events and aggregated data independently.

### 3.3 Tenant Admin

- **CAP-8:** View usage for their own organization over a period of time, broken down by project, resource type, and template. Cannot see other tenants' data.
- **CAP-9:** View usage aggregated by project (including nested projects), so that costs can be attributed to specific teams, grants, or departments.

### 3.4 Tenant User

- **CAP-10:** View their own tenant's usage over a period of time — what resources are being consumed and for how long.

### 3.5 Cross-cutting

- **CAP-11:** VMaaS metering is consumption-based. Compute metering (instance-type-seconds) runs only while the VM is active (running). Stopped and paused VMs do not actively consume host compute resources, so compute is not metered in those states. However, resources allocated to a VM that remain reserved regardless of VM state — including storage volumes, public IPs, and DNS records — continue to consume infrastructure capacity (storage space, IP pool addresses, DNS service entries) and must continue to be metered for the full duration of the VM's existence, even while the VM is stopped or paused. VMs in failed state are not metered (see D-5). All metered resources belonging to a VM (and — when in scope — storage, public IPs) must be attributable to the parent VM so that the full cost of a VM can be queried as a unified view.
- **CAP-12:** CaaS metering is consumption-based — only active clusters (ready or progressing) are metered. A failed cluster is not reliably serving workloads and its constituent nodes may be in an indeterminate state; metering a failed cluster risks double-counting alongside any replacement the provider spins up. All metered resources belonging to a cluster (control plane, worker nodes, and — when in scope — storage, networking) must be attributable to the parent cluster so that the full cost of a cluster can be queried as a unified view.
- **CAP-13:** MaaS metering is consumption-based — charged per token and per inference request, not per allocated model instance. GPU infrastructure cost is embedded in the provider's per-token/per-model pricing. MaaS usage data is available for query within 60 seconds of an inference request completing, so that downstream systems (e.g., quota enforcement, when available) can evaluate against near-real-time balances. This latency requirement does not apply to VMaaS or CaaS, where delays up to the polling interval are acceptable.
- **CAP-14:** The metering system can be deployed independently without affecting existing OSAC provisioning. Providers who use their own metering solution can consume OSAC's lifecycle data without deploying the built-in metering stack.
- **CAP-15:** Upgrading the metering system does not cause loss of collected metering data or gaps in measurement of ongoing workloads.
- **CAP-16:** Duplicate events do not cause double-counting in any meter.
- **CAP-17:** Metering data includes catalog item and template references for any metered resource, enabling downstream systems to trace charges back to the originating catalog offer.

## 4. Operational Expectations

- Raw metering events must be retained for at least 7 days (configurable).
- Aggregated metering data must be retained for at least 13 months to support annual billing audits. The retention period must be configurable.
- The metering ingestion layer must scale to handle concurrent lifecycle events from multiple tenants' resources without dropping events or introducing delays that exceed the polling interval.

## 5. Acceptance Criteria

### VMaaS

- [ ] A running VM generates usage data queryable as aggregated instance-type-seconds per tenant, broken down by instance type
- [ ] A stopped or paused VM does not generate compute usage data (instance-type-seconds)
- [ ] Storage, public IP, and DNS resources allocated to a stopped or paused VM continue to generate metering data for the duration of the VM's existence
- [ ] VM usage can be broken down by tenant, project, template, and instance
- [ ] A billing system can determine the catalog item, instance type, and OS image for any metered VM from the metering data alone

### CaaS

- [ ] An active cluster generates separate usage data for the control plane and for each worker node set
- [ ] Worker node usage can be broken down by resource class, enabling differentiated pricing for GPU vs CPU
- [ ] All metered resources belonging to a cluster (control plane, worker nodes) can be queried as a unified cluster-level usage view
- [ ] A billing system can determine the catalog item, cluster version, and per-node-set host type for any metered cluster from the metering data alone

### MaaS

- [ ] An inference request generates usage data with input tokens, output tokens, cached tokens, and total tokens queryable per tenant and per model
- [ ] MaaS usage can be broken down by tenant, project, and model
- [ ] A billing system can determine the model, provider, and subscription for any metered inference request from the metering data alone
- [ ] A metering event is emitted within 30 seconds of an inference request completing, and processed within 60 seconds so that downstream systems (e.g., quota enforcement, when available) can evaluate against near-real-time balances

### Cross-cutting

- [ ] A Tenant Admin can view their own usage but cannot see other tenants' data
- [ ] A Tenant Admin can view their organization's usage in the osac-ui console, broken down by project
- [ ] A Tenant User can view usage for the projects they belong to in the osac-ui console
- [ ] A Cloud Provider Admin can view usage across all tenants
- [ ] A Cloud Provider Admin can view usage across all tenants in the osac-ui console
- [ ] A resource that exists for 30 seconds appears in the usage data (verifies CAP-4; sub-second resources are not captured)
- [ ] Deploying the metering system does not require changes to existing OSAC resources or workflows
- [ ] A Tenant Admin can view usage grouped by project and see consumption per project within their tenant
- [ ] Sending a duplicate event does not increase any meter value
- [ ] Raw events older than the configured retention period are purged
- [ ] Aggregated data from 13 months ago is still queryable
- [ ] A Cloud Infrastructure Admin can add a new meter via configuration update and query it after deployment
- [ ] Metering data for any resource includes catalog item and template references traceable to the originating catalog offer
- [ ] Upgrading the metering system does not cause data loss or measurement gaps

## 6. Assumptions

- The metering and costing stack is deployed on-premises under the provider's control.
- Cloud Infrastructure Admins have cluster-admin access for installing the metering stack.

## 7. Dependencies

- **Self-managed metering and costing stack** — an on-premises solution that provides event ingestion, meter aggregation, and usage query capabilities.
- **Durable event pipeline** — a reliable message delivery layer between OSAC and the metering stack.
- **OSAC VMaaS and CaaS provisioning** — must emit lifecycle events on resource state transitions.

## 8. Risks

### 8.1 Cost management stack feature gaps

- **Owner:** OSAC platform team / Cost Management team
- **Mitigation:** The self-managed cost management stack may not yet support all capabilities required by this PRD. Feature development must be coordinated between OSAC and the cost management team.

### 8.2 Integration complexity

- **Owner:** OSAC platform team / Cost Management team
- **Mitigation:** OSAC resource types may not map directly to the cost management stack's existing data model. Prototype the integration early to surface mismatches.

## 9. Decisions

### D-1. Tenant User usage visibility

Tenant Users see usage for projects they have access to, not all tenant usage. The metering system scopes data at the tenant level; the Usage API applies project-level RBAC filtering using the same permissions defined in the [Organizations](/enhancements/organizations) EP (e.g., `VIEW_PROJECT`).

### D-2. Metering system unavailability

Metering failures must not affect provisioning. All metering data is eventually captured, even during metering system outages, with no gaps in the billing record.

### D-3. Tenant-defined Services (catalog items)

The metering system carries catalog item references for all resources regardless of whether the catalog item is provider-defined or tenant-defined (CAP-17). The billing system joins metering data with the catalog item to resolve rates. The provider sees infrastructure-level consumption; the tenant sees their custom Service view. The decomposition is a billing concern, not a metering concern.

### D-4. Allocation-based metering for VMaaS and CaaS

VMaaS and CaaS compute meters remain consumption-based only. Stopped or paused VMs do not accrue compute usage. There is no "stopped cluster" concept — clusters are either active or being deleted. Providers who want to recover cost for idle resources can do so through subsidiary resource meters (storage volumes, public IPs) that run regardless of VM state, or through billing policy on the catalog item reservation. Physical resource reservation (GPU nodes, bare metal hosts) is addressed by BMaaS allocation-based metering in a separate PRD.

### D-5. Failed-state metering

Resources in failed state are not metered, regardless of the cause of failure. The metering system does not distinguish tenant-caused errors from provider-caused errors — programmatic failure attribution is unreliable. If a resource was briefly metered before transitioning to failed, the metering system adjusts prior intervals retroactively. Providers who need to handle SLA breach credits for provider-caused outages should do so through billing policy outside the metering system.

## 10. Charge Calculation Model

OSAC provides usage data. The provider applies their own price schedule to generate charges. OSAC does not enforce prices or generate invoices. A separate PRD will address the costing layer to automate charge calculation.

### Metering Units and Relationship to Existing OSAC Instance Types

OSAC already defines instance types for VMaaS (per the [vm-instance-types](/enhancements/OSAC-46-vm-instance-types) EP) and host classes for CaaS worker nodes (e.g., `gpu-h100`, `cpu-only`). The metering system does not define, replace, or constrain these — it treats the instance type name and host class name as opaque string labels used for grouping. No changes to the existing instance type or host class model are required.

VMaaS metering uses `instance-type-seconds` as its single meter. This aligns with how commercial clouds operate — CSPs define instance types that bundle CPU, RAM, and fixed boot disk into a named unit, and billing is expressed as uptime × rate per instance type. The instance type name from the OSAC catalog is used directly as a grouping dimension; the metering system is agnostic to the hardware composition behind the name. Storage is implicitly bundled when the CSP defines instance types that include a fixed boot disk.

For CaaS, worker node pricing is per-node-seconds grouped by host class — the same instance-type-seconds model applied at the node level. The control plane is a separate flat-rate meter.

### VMaaS

`instance-type-seconds` measures how long (in seconds) a VM of a specific instance type is running. The instance type is the natural billing unit for VMaaS — it is what the tenant chose from the catalog, it encodes the hardware bundle (CPU, RAM, boot disk), and it maps directly to the provider's pricing schedule. Measuring in seconds aligns with commercial cloud billing practices and ensures all consumption is captured regardless of how briefly the VM runs.

| Meter | Formula | Example (1 hour) |
|-------|---------|-----------------|
| instance-type-seconds | uptime × price/s | 3600s × $0.001/s = $3.60 |

### CaaS

CaaS uses two meters because its cost structure has two independent components. The **control plane** is a dedicated infrastructure component that runs on behalf of the tenant regardless of worker count — it has a fixed cost to the provider that must be recovered independently. **Worker nodes** are the primary compute resource and vary significantly in cost by hardware class: a GPU node carries far higher infrastructure cost than a CPU node. Metering workers grouped by host class enables differentiated pricing that reflects this cost difference.

| Component | Meter | Formula | Example (1 hour, 2 GPU + 1 CPU worker) |
|-----------|-------|---------|----------------------------------------|
| Control plane | cluster uptime | uptime × price_cp | 3600s × $0.01 = $36.00 |
| GPU workers | worker node-seconds (gpu-h100) | node-seconds × price_gpu | 7200 × $0.02 = $144.00 |
| CPU workers | worker node-seconds (cpu-only) | node-seconds × price_cpu | 3600 × $0.005 = $18.00 |
| **Total** | | | **$198.00/hour** |

### MaaS

MaaS uses per-token meters rather than per-time meters because inference cost is proportional to the number of tokens processed and generated, not wall-clock time. Three token types are metered separately: **input tokens** (the prompt the model must process), **output tokens** (the generated response — more expensive per token because they are generated sequentially), and **cached tokens** (input tokens served from a prompt cache at significantly lower compute cost, enabling the provider to pass a discount to tenants).

| Component | Meter | Formula | Example |
|-----------|-------|---------|---------|
| Input tokens | input tokens | tokens × price/1K tokens | 1M × $0.003/1K = $3.00 |
| Output tokens | output tokens | tokens × price/1K tokens | 500K × $0.015/1K = $7.50 |
| Cached tokens | cached tokens | tokens × discounted price/1K | 200K × $0.0015/1K = $0.30 |
