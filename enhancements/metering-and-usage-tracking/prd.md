# Metering and Usage Tracking

| Field       | Value                |
|-------------|----------------------|
| Author(s)   | masayag@redhat.com   |
| Jira        | [OSAC-985](https://redhat.atlassian.net/browse/OSAC-985) |
| Epic        | [OSAC-65](https://redhat.atlassian.net/browse/OSAC-65) (to be updated after PRD approval) |
| Date        | 2026-06-25           |
| Milestone   | 0.3                  |

## Glossary

| Term | Definition |
|------|-----------|
| **Event** | A discrete, immutable record of a resource lifecycle change. Events are the source of truth for billing-grade metering. |
| **Meter** | A named aggregation that turns events into a measurable quantity (e.g., total VM uptime grouped by tenant). |
| **Metric** | The aggregated output of a meter over a time window — the queryable result. |
| **Usage** | Measured consumption of a resource (e.g., CPU core-seconds consumed while a VM was running). |
| **Allocation** | Reserved capacity of a resource, regardless of whether it is actively used. |
| **Host type** | A provider-defined hardware class for worker nodes (e.g., `gpu-h100`, `cpu-only`). Different host types carry different prices. |
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
- CaaS metering supports per-host-type billing so that GPU and CPU workers are priced independently
- All metering is configurable — Cloud Provider Admins enable/disable meters per resource type
- The metering and costing stack runs on-premises under the provider's control — no data leaves the provider's infrastructure

### 2.2 Non-Goals

- Costing, billing, and quota enforcement in milestone 0.3 — deferred to milestone 0.4 (see §10 Future Phase)
- Workload-level metering inside tenant clusters (OSAC has no visibility into tenant-managed workloads)
- BMaaS, Storage-aaS, Object Storage, and Enclave metering (deferred to a future milestone)
- Network bandwidth metering (ingress/egress traffic per tenant) — unclear which component has access to the primary data; deferred to custom service metering if a networking vendor provides the data source

### 2.3 Services in Scope

| Service | Scope in 0.3 |
|---------|-------------|
| VMaaS | In scope |
| CaaS | In scope |
| MaaS | In scope (capabilities defined; data source ownership TBD — see §9.5) |
| BMaaS | Deferred |
| Enclave | Not applicable |

## 3. Capabilities

### 3.1 Cloud Provider Admin

- **CAP-1:** View aggregated usage across all tenants for a billing period, broken down by tenant, project, resource type, and template.
- **CAP-2:** Choose which meters are active for the deployment — enable metering for VMaaS, CaaS, and MaaS, disable meters for resource types that the provider does not offer or does not wish to charge for.
- **CAP-3:** View usage of cluster worker nodes broken down by host type (e.g., GPU vs CPU), so that different hardware classes can be priced independently.
- **CAP-17:** View AI model inference usage broken down by tenant, project, model, and GPU type — including input tokens, output tokens, cached tokens, and total tokens consumed.
- **CAP-18:** View GPU compute time consumed by inference workloads, broken down by GPU type (e.g., H100 vs B200), so that different accelerator classes can be priced independently.
- **CAP-4:** Receive accurate metering data for resources that exist for less than one minute — no resource goes unmetered due to brevity.

### 3.2 Cloud Infrastructure Admin

- **CAP-5:** Deploy, upgrade, and monitor the metering system using standard Kubernetes tooling — including adding or removing meters, updating the metering stack version, and observing pipeline health (ingestion lag, storage usage).
- **CAP-6:** Emit metering events for custom services not covered by built-in meters, so that providers can track consumption of additional offerings alongside core services.
- **CAP-7:** Configure retention periods for raw events and aggregated data independently.

### 3.3 Tenant Admin

- **CAP-8:** View usage for their own organization over a period of time, broken down by project, resource type, and template. Cannot see other tenants' data.
- **CAP-9:** View usage aggregated by project (including nested projects), so that costs can be attributed to specific teams, grants, or departments.

### 3.4 Tenant User

- **CAP-10:** View their own tenant's usage over a period of time — what resources are being consumed and for how long.

### 3.5 Cross-cutting

- **CAP-11:** VMaaS metering is consumption-based — only active VMs (while running) are metered. Allocated but idle VMs (stopped, paused) are not metered. Providers who need allocation-based charging for VMs should raise this during PRD review.
- **CAP-12:** CaaS metering is consumption-based — only active clusters (ready or progressing) are metered. Clusters in failed state are not metered. Providers who need allocation-based charging for clusters should raise this during PRD review.
- **CAP-19:** MaaS metering is consumption-based — charged per token and per inference request, not per allocated model instance. Metering events must be emitted within 30 seconds of the inference request completing, and the cost management stack must process them and update budget/quota balances within 60 seconds of receipt, so that subsequent requests can be evaluated against an up-to-date balance. These latency requirements do not apply to VMaaS or CaaS, where delays up to the polling interval are acceptable.
- **CAP-13:** When clusters are nested (OpenShift on OpenShift via Hosted Control Planes), resource consumption is not double-counted. The cost of the hosted control plane infrastructure is attributable to the hosted clusters, not counted independently alongside the parent cluster's resources.
- **CAP-14:** The metering system can be deployed independently without affecting existing OSAC provisioning. Metering system failure does not impact the provisioning or lifecycle of any resource.
- **CAP-15:** Upgrading the metering system does not cause loss of collected metering data or gaps in measurement of ongoing workloads.
- **CAP-16:** Duplicate events do not cause double-counting in any meter.

## 4. Operational Expectations

- Raw metering events must be retained for at least 7 days (configurable).
- Aggregated metering data must be retained for at least 13 months to support annual billing audits. The retention period must be configurable.
- The metering ingestion layer must scale to handle concurrent lifecycle events from multiple tenants' resources without dropping events or introducing delays that exceed the polling interval.
- Metering system failure must not affect OSAC provisioning operations.

## 5. Acceptance Criteria

### VMaaS

- [ ] A running VM generates usage data queryable as aggregated uptime, CPU core-seconds, and memory GiB-seconds per tenant
- [ ] A stopped or paused VM does not generate usage data
- [ ] VM usage can be broken down by tenant, project, template, and instance

### CaaS

- [ ] An active cluster generates separate usage data for the control plane and for each worker node set
- [ ] Worker node usage can be broken down by host type, enabling differentiated pricing for GPU vs CPU
- [ ] Peak worker node count per host type is visible within a billing window

### MaaS

- [ ] An inference request generates usage data with input tokens, output tokens, and total tokens queryable per tenant and per model
- [ ] MaaS usage can be broken down by tenant, project, model, and GPU type
- [ ] GPU compute time consumed by inference is queryable per GPU type
- [ ] A metering event is emitted within 30 seconds of an inference request completing, and processed within 60 seconds so that budget/quota balances reflect the consumption before the next request is evaluated

### Cross-cutting

- [ ] A Tenant Admin can view their own usage but cannot see other tenants' data
- [ ] A Cloud Provider Admin can view usage across all tenants
- [ ] A Cloud Provider Admin can disable a meter and no usage data is generated for that resource type
- [ ] A resource that exists for 30 seconds appears in the usage data
- [ ] Deploying the metering system does not require changes to existing OSAC resources or workflows
- [ ] A Tenant Admin can view usage grouped by project and see consumption per project within their tenant
- [ ] When a cluster runs on a cluster via Hosted Control Planes, the nested cluster's worker consumption is not double-counted against the parent
- [ ] Sending a duplicate event does not increase any meter value
- [ ] Raw events older than the configured retention period are purged
- [ ] Aggregated data from 13 months ago is still queryable
- [ ] A Cloud Infrastructure Admin can add a new meter via configuration update and query it after deployment
- [ ] Upgrading the metering system does not cause data loss or measurement gaps

## 6. Assumptions

- The metering and costing stack is deployed on-premises under the provider's control.
- Cloud Infrastructure Admins have cluster-admin access for installing the metering stack.
- OSAC does not currently support upgrades, so data migration and backward compatibility for metering data are not concerns in milestone 0.3.

## 7. Dependencies

- **Self-managed metering and costing stack** — an on-premises solution that provides event ingestion, meter aggregation, usage query capabilities, and (in milestone 0.4) costing capabilities including cost models, price lists, and billing support.
- **Durable event pipeline** — a reliable message delivery layer between OSAC and the metering stack.
- **OSAC provisioning controllers** — must integrate event emission for VMaaS and CaaS lifecycle transitions (changes land in the same milestone).

## 8. Risks

### 8.1 Cost management stack feature gaps

- **Owner:** OSAC platform team / Cost Management team
- **Mitigation:** The self-managed cost management stack may not yet support all capabilities required by this PRD and its future phases (e.g., provider/consumer cost models, price list lifecycle, FOCUS export). Feature development must be coordinated between OSAC and the cost management team.

### 8.2 Integration complexity

- **Owner:** OSAC platform team / Cost Management team
- **Mitigation:** OSAC resource types may not map directly to the cost management stack's existing data model. Prototype the integration early to surface mismatches.

### 8.3 Nested cluster cost attribution

- **Owner:** OSAC platform team
- **Mitigation:** Nested clusters (OpenShift on OpenShift via Hosted Control Planes) create a risk of double-counting. CAP-13 requires deduplication, but the attribution model (how to distribute infrastructure cost to hosted clusters) needs design validation.

## 9. Open Questions

### 9.1 Should Tenant Users see only their own resource usage or all usage within their tenant?

- **Owner:** OSAC platform team / UI team
- **Impact:** CAP-8, CAP-10. The metering system scopes data at the tenant level. Per-user filtering within a tenant is a UI/RBAC concern to be addressed in the Usage API or landing zone design.

### 9.2 Should OSAC provide a combined "current footprint" view joining live resource state with metering data?

- **Owner:** OSAC platform team / UI team
- **Impact:** The metering system provides consumption history; OSAC's resource listing provides current inventory. A combined view (e.g., "3 VMs running, X core-hours consumed this month") is a presentation concern to be addressed in the landing zone or Usage API.

### 9.3 How does tenant isolation integrate with the cost management stack's tenancy model?

- **Owner:** OSAC platform team / Cost Management team
- **Impact:** CAP-8 and the future provider/consumer cost model split (§10.1). The cost management stack may rely on an external identity system for organization-level isolation. The integration model between OSAC tenants and cost management organizations must be defined.

### 9.4 What is the integration contract between OSAC metering events and the cost management stack?

- **Owner:** OSAC platform team / Cost Management team
- **Impact:** §7 Dependencies. OSAC emits lifecycle events; the cost management stack must ingest them and map them to its internal data model. The contract (event format, transport) must be agreed upon before implementation.

### 9.5 Who is the source of MaaS metering events — OSAC or RHOAI?

- **Owner:** OSAC platform team / RHOAI team
- **Impact:** CAP-17, CAP-18, CAP-19. MaaS inference data (token counts, GPU compute time) originates from the AI model serving layer (e.g., vLLM, AI Gateway). It is not yet determined whether OSAC collects and forwards these events, or whether the AI serving layer emits them directly to the metering stack. This decision affects the integration architecture and which team owns the metering event emission for MaaS.

## 10. Future Phase: Costing, Billing, and Operational Controls

Milestone 0.3 delivers the metering foundation — event collection, aggregation, and usage queries. Subsequent milestones build on this foundation to provide the costing and operational capabilities that providers need to run a sovereign cloud business.

### 10.1 Costing and Billing (Milestone 0.4)

#### Provider and Consumer Cost Models

Cloud Provider Admins must be able to define at least two cost model perspectives per resource:
- **Provider cost model** — reflects actual infrastructure cost, visible only to provider users.
- **Consumer cost model** — reflects charges to the tenant, visible to tenant users.

Access to cost model perspectives must be governed by role assignment. Sovereign cloud tenants typically see only the consumer cost model.

#### Itemized Cost Breakdown

When the system calculates charges for a tenant, the result must be itemized by the categories defined in the price list (e.g., compute: $X, memory: $Y, GPU: $Z). The itemization must be returned via the API and displayed in the UI, enabling providers to present per-service bills comparable to hyperscaler invoices.

#### Price List Lifecycle

Price lists must have a validity period (effective-from and effective-to dates). Cloud Provider Admins must be able to:
- Define future price lists in advance (e.g., set 2027 prices in October 2026).
- Maintain historical price lists that apply to past billing periods.
- Trigger recalculation of a finalized period using a different price list.

#### Constant Currency

Cloud Provider Admins must be able to define fixed currency exchange rates per currency pair for a given validity period. Charges must be calculated using the defined constant rate, not a dynamic market rate.

#### Default Cost Model Assignment

Sovereign cloud providers may serve hundreds or thousands of tenants. The system must support default cost model assignment so that tenants receive a baseline cost model automatically unless a specific override is configured.

#### Plans, Rate Cards, and Subscriptions

Cloud Provider Admins can define pricing plans that map meters to rate cards. Plans support multiple pricing models: flat rate, per-resource and tiered. Tenants can be assigned to plans, and the system generates draft charges from aggregated usage at the end of each billing cycle.

### 10.2 Quota Enforcement and Budgets (Milestone 0.4)

#### Usage-Based Quotas

Cloud Provider Admins can define per-tenant usage limits that trigger warnings or block resource provisioning when approaching or exceeding the limit.

#### Budgets

Users can set spending budgets on a scope (tenant, project, resource type) for a configurable time period. Multiple budgets on the same scope must be supported. In a sovereign cloud deployment, some budgets are set by the provider while others are set by the tenant.

#### Alerting

Cloud Provider Admins and Tenant Admins receive notifications when usage or cost approaches threshold levels (e.g., 80%, 90%, 100% of budget or quota).

### 10.3 Metering Extensions (Milestone 0.4+)

#### BMaaS Metering

BMaaS metering is **allocation-based** — charged based on reserved hardware capacity, not active consumption. A bare metal server allocated to a tenant is metered for the duration of the allocation regardless of whether it is powered on or actively used.

#### Custom Metric-Based Rates

Advanced use cases require user-defined rate formulas over arbitrary metrics. Providers or service developers should be able to define custom metrics to collect and specify a calculation formula for deriving synthetic meters. This enables metering of domain-specific services (e.g., per-page-export, per-API-call) without requiring upstream changes.

#### Resource Units

Providers may price bundled resource sets as a single unit (e.g., 2 cores + 8 GiB RAM + 50 GB storage = 1 RU at a fixed rate). The system must support defining and tracking consumption in terms of resource units, not just individual resource dimensions.

### 10.4 Reporting and Interoperability (Milestone 0.4+)

#### FOCUS Format Export

The system must support exporting billing and usage data in [FOCUS](https://focus.finops.org/) format. FOCUS export enables integration with third-party FinOps tools and is becoming a baseline expectation for service providers.

#### Multicluster Cost Distribution

The system must support distributing the cost of shared infrastructure (e.g., management hub, container registry) across the consumer clusters that use them.

### 10.5 Future Capabilities (Milestone TBD)

- **Anomaly-based spending alerts** — detect unusual spending patterns beyond static threshold alerting
- **Cost forecasting** — predict future costs based on historical trends
- **AI-assisted cost analysis** — conversational interface for cost queries and cost spike explanations

---

## Cross-Cutting Dimensions

| Dimension | Scope in 0.3 |
|-----------|-------------|
| Tenant Onboarding | Not affected — no new roles, no auto-provisioned resources |
| Inventory | Not affected |
| Provisioning | Not affected — metering observes provisioning state, does not modify it |
| Networking | Not affected |
| Storage | Not affected — metering stack manages its own storage, separate from OSAC storage tiers |
| Installation | **Affected** — new deployment artifacts for the metering stack |

## Charge Calculation Model

OSAC provides usage data. The provider applies their own price schedule to generate charges. OSAC does not enforce prices or generate invoices in milestone 0.3. Milestone 0.4 introduces the costing layer to automate charge calculation (see §10.1).

### VMaaS

| Pricing Model | Meter | Formula | Example (2-core, 8 GiB VM, 1 hour) |
|--------------|-------|---------|--------------------------------------|
| Flat per-template | vm uptime | uptime × price/s | 3600s × $0.001/s = $3.60 |
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
| GPU compute | gpu-seconds (H100) | gpu-seconds × price/gpu-s | 3600 × $0.05 = $180.00 |

## Academic and Research Adaptation

Academic environments use the same metering infrastructure for cost recovery (non-profit) rather than revenue generation:

| Aspect | Commercial Provider | Academic/Research |
|--------|--------------------|-------------------|
| Billing model | Revenue generation | Cost recovery |
| Billing cycle | Continuous or hourly | Monthly |
| Attribution | Tenant → Organization | Tenant → Project → PI → Grant |
| Public IP / DNS | Metered | Disabled via CAP-2 |
| Data retention | Per provider policy | Extended per operational expectations |

OSAC's existing Project resource with hierarchical nesting maps to academic project/grant structures. Future extensions: `grant_id` via resource labels.
