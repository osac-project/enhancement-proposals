# Billing Integration MVP

| Field       | Value                |
|-------------|----------------------|
| Author(s)   | Moti Asayag          |
| Jira        | [OSAC-3784](https://redhat.atlassian.net/browse/OSAC-3784) |
| Date        | 2026-08-09           |

## Glossary

Terms are aligned with [FOCUS](https://focus.finops.org/) (FinOps Open Cost and Usage Specification) where applicable. [User]

| Term | Definition |
|------|------------|
| Billing account | A container for resources and/or services that are billed together in an invoice (FOCUS). In OSAC, each tenant maps to one billing account in the billing provider. |
| Billing period | The time window that an organization receives an invoice for, inclusive of the start date and exclusive of the end date (FOCUS). In OSAC, billing periods are fixed calendar months. [Clarify: R1.Q1] |
| Billing provider | The external billing system that OSAC integrates with to manage pricing, cost calculation, and invoicing. Maps to the FOCUS concepts of invoice issuer and data generator. In OSAC: Monetize360 (M360) or Red Hat Cost Management (Koku). |
| Billing provider adapter | The pluggable integration component that connects OSAC's usage data pipeline to a billing provider. Each OSAC deployment configures one active adapter. |
| Charge | A line item representing a cost incurred for resource or service usage within a billing period. Corresponds to a row in a FOCUS cost and usage dataset. |
| Draft invoice | An invoice for a billing period that has not been finalized or issued. Corresponds to an invoice in a FOCUS open billing period. Cloud Provider Admins review and export draft invoices before submitting them to external payment systems. |
| FOCUS | [FinOps Open Cost and Usage Specification](https://focus.finops.org/) — an open-source specification that defines requirements for billing data. |
| Meter | A named aggregation that turns events into a measurable quantity (e.g., total VM uptime grouped by tenant). Defined in the metering PRD (OSAC-985). |
| Pricing plan | A named collection of rate cards that defines the pricing terms for a tenant. Cloud Provider Admins assign pricing plans to tenants; a default plan applies to unassigned tenants. |
| Rate card | A mapping of a resource type to a per-unit price within a pricing plan. Rate cards define how usage of a specific resource type is priced. |
| Resource type | A classification of a billable resource that determines its pricing. In OSAC, resource types correspond to the sizing profile of a provisioned resource (e.g., instance types for VMaaS, host types for CaaS worker nodes). Aligns with the FOCUS ResourceType dimension. |
| Service | An offering that can be purchased from a service provider, which may include multiple types of charges (FOCUS). In OSAC, a catalog item maps to a Service. OSAC services in scope for this MVP: VMaaS and CaaS. |
| Usage | Measured consumption of a resource (e.g., instance-type-seconds consumed while a VM was running). Defined in the metering PRD (OSAC-985). |

## Problem Statement

OSAC's metering layer (OSAC-985) captures resource consumption for VMaaS, CaaS, and future services, but no mechanism exists to convert usage data into charges, define pricing for service offerings, or present costs to tenants. Cloud Provider Admins cannot generate invoices or track revenue, Tenant Admins cannot attribute costs to teams or budgets, and Tenant Users have no visibility into their consumption costs. Without billing integration, each sovereign cloud deployment must build its own billing pipeline from scratch, duplicating effort and fragmenting the operational model.

## In Scope

- **Pluggable billing provider adapter** with one active provider per deployment. Initial providers: Monetize360 (M360) and Red Hat Cost Management (Koku).
- **Billing system as pricing source of truth** — OSAC fetches prices from the active billing provider. Prices are not independently maintained in OSAC.
- **VMaaS and CaaS billing** — billing models and charge calculation for the two services with existing metering (OSAC-985 milestone 0.3). Billing for other services (MaaS, BMaaS, Storage, Networking) activates via separate Features as their respective metering becomes available.
- **Tenant-to-billing-account lifecycle** — creating a tenant in OSAC creates a corresponding billing account in the billing provider; deleting a tenant deactivates the billing account.
- **API, CLI, and UI surfaces** — billing capabilities (cost views, invoice listing, pricing plan management) are accessible via the fulfillment-service gRPC/REST API, the `osac` CLI, and the OSAC web console. UI implementation may be phased across milestones.
- **Billing RBAC** — billing operations require specific authorization. Provider cost data and pricing management are restricted to provider-level roles. Tenant cost and invoice data is scoped to the tenant's own billing account.

## Out of Scope

- **Payment processing and gateway integration** — OSAC generates draft invoices; payment collection and PCI compliance are handled externally.
- **Quota enforcement and budget alerts** — tracked separately as OSAC-998.
- **Workload-level metering** — OSAC meters resources it provisions, not workloads running inside tenant clusters.
- **Billing provider UI** — the billing provider's own administration interface; this PRD covers OSAC-side surfaces only.
- **Real-time cost streaming** — OSAC-side push/streaming mechanisms (WebSocket, SSE). Tenants query billing costs on demand; the billing system processes metering events in near-real-time, but OSAC does not push cost updates. [Clarify: R1.Q5]
- **Multi-provider per deployment** — each OSAC deployment configures one billing provider. Per-tenant provider selection is deferred.
- **Bulk billing operations** — batch pricing plan assignment, bulk recalculation, and bulk invoice export are deferred.
- **Ad-hoc credits, refunds, and adjustments** — managed within the billing provider's own interface.
- **Billing data residency** — per-tenant billing data residency by region is enforced by the billing provider, not by OSAC.
- **Catalog item pricing enrichment** — enriching catalog items with live prices from the billing system is a separate Feature (OSAC-3793). [Clarify: R1.Q4]
- **Billing for services beyond VMaaS and CaaS** — MaaS (OSAC-3794), BMaaS (OSAC-3795), Storage (OSAC-3796), and Networking (OSAC-3797) billing activate via separate Features as metering lands.

## User Stories

### Cloud Provider Admin

- As a Cloud Provider Admin, I want to configure a billing provider adapter for my OSAC deployment, so that usage data flows automatically to my chosen billing system (M360 or RH Cost Management) without custom integration work.

- As a Cloud Provider Admin, I want to create pricing plans with rate cards that define per-unit prices per resource type, so that I can set different rates for different tenants based on their service agreements and hardware classes.

- As a Cloud Provider Admin, I want to assign pricing plans to tenants, so that each tenant's usage is charged according to their agreed terms. A default plan applies to tenants without a specific assignment. When a plan's rates change, affected tenants' future charges reflect the updated rates. [Clarify: R1.Q3]

- As a Cloud Provider Admin, I want to view draft invoices per tenant for a billing period showing charges itemized by service and resource type, so that I can review charges before exporting them to my payment system.

- As a Cloud Provider Admin, I want billing operations (pricing plan management, invoice review, cost model configuration) restricted to users with billing-specific permissions, so that only authorized personnel can modify pricing or access financial data. Billing RBAC supports separation of duties where required — for example, pricing plan creation and invoice approval can be assigned to separate roles.

- As a Cloud Provider Admin, I want all billing-related administrative actions (pricing plan changes, plan-to-tenant assignments, invoice generation, cost model modifications) to produce audit log entries, so that I can satisfy compliance and regulatory audit requirements.

### Cloud Infrastructure Admin

- As a Cloud Infrastructure Admin, I want to deploy and configure the billing provider adapter as part of the OSAC installation — including secure credential storage for the billing provider's API — so that billing integration is operational from day one without exposing credentials in plaintext configuration.

- As a Cloud Infrastructure Admin, I want to switch the billing provider adapter (e.g., from M360 to RH Cost Management) via configuration, so that provider migrations do not require code changes or redeployment of OSAC core services.

- As a Cloud Infrastructure Admin, I want to monitor the health of the billing integration through standard OSAC observability (Prometheus metrics for sync lag, error rate, and queue depth; structured logs for sync failures and adapter lifecycle events), so that I can detect and resolve billing pipeline issues before they affect invoice accuracy.

### Tenant Admin

- As a Tenant Admin, I want to view my organization's accumulated costs for the current and past billing periods, broken down by service type (VMaaS, CaaS) and resource, so that I can manage my organization's cloud spending.

- As a Tenant Admin, I want to view costs aggregated by Project (including nested Projects), so that I can attribute spending to teams and departments within my organization. [Clarify: R1.Q2]

- As a Tenant Admin, I want to view past invoices and itemized charge breakdowns for my organization, so that I can reconcile charges with my internal budgets and respond to billing inquiries from my users.

### Tenant User

- As a Tenant User, I want to view the estimated cost of my currently running resources, so that I can understand my consumption footprint. Estimated cost reflects charges calculated by the billing system from metering events processed in near-real-time. [Clarify: R1.Q5]

- As a Tenant User, I want to view my tenant's cost history over time, so that I can spot trends and understand what drives my spending.

## Assumptions

- The metering layer (OSAC-985) is operational and collecting usage data for VMaaS and CaaS before billing integration begins.

- The billing provider (M360 or RH Cost Management) is deployed and reachable from the OSAC deployment. OSAC does not manage the billing provider's lifecycle.

- The billing system supports the pricing models required by this PRD (flat rate, per-unit). If a billing provider lacks a capability, that feature is unavailable in that deployment until the provider supports it.

- Tenant isolation in the billing system aligns with OSAC's tenant model: each OSAC tenant maps to one billing customer/account. The mapping mechanism is defined during billing provider adapter configuration.

- Billing system unavailability does not block tenant provisioning or resource lifecycle operations. Tenant creation succeeds and the corresponding billing account is created when the billing system becomes available; usage data is delivered when connectivity is restored.

- The billing system processes metering events in near-real-time. Tenants querying their estimated costs see charges derived from recently processed usage data. [Clarify: R1.Q5]

- OSAC deployments are expected to support up to hundreds of tenants with thousands of active resources generating usage data per billing period.

- Each OSAC deployment operates with a single base billing currency. Multi-base-currency deployments are not supported.

- All user-supplied pricing data (amounts, currency codes, validity periods) is validated on input. Negative prices and non-ISO-4217 currency codes are rejected.

- Zero-cost or trial tenants are modeled as regular tenants assigned to a pricing plan with zero-rate cards. OSAC does not have a separate trial mode.

- Usage data delivery to the billing system is idempotent — retrying a failed delivery does not result in double-counted usage or duplicate charges.

- Billing data retention (invoices, cost records, usage history) is governed by the billing provider's own retention policies. OSAC does not independently manage billing data lifecycle.

- When billing integration is enabled on a deployment with existing tenants, billing accounts are created for those tenants. Pre-existing usage data (generated before billing activation) is not retroactively billed.

- Billing integration can be disabled without affecting resource provisioning or lifecycle operations.

- Billing data (prices, costs, invoices, tenant consumption) is financially sensitive. It is protected by OSAC's existing data protection mechanisms (encryption in transit and at rest).

## Dependencies

- **OSAC-985 — Metering and Usage Tracking:** Provides the usage data pipeline that billing consumes. Metering must be operational for VMaaS and CaaS before billing can calculate charges.

- **Billing provider deployment:** M360 or RH Cost Management must be deployed and configured independently. OSAC integrates via the billing provider's APIs.

- **OSAC Catalog (OSAC-1531, OSAC-2452):** Catalog items must exist for the services being billed. The billing integration does not create catalog items but relies on their existence for pricing plan configuration.

- **OSAC-998 — Quota Management:** Billing cost data may feed into quota enforcement in a future milestone. This PRD does not implement quota logic but does not preclude it.

- **Documentation:** User-facing documentation for billing management (pricing plan setup, invoice workflows, cost visibility) and API reference for billing endpoints are delivered with the feature.

---

## Provenance

Committed: commit @ prd 0.8.0 - 7efcedb, workspace prd/OSAC-3784 @ 975a5e0 (2 behind origin/main, dirty)

> Authoring phases not recorded this session (commit-time snapshot only).

<!-- ai-workflow-provenance:{"schema_version":1,"provenance_kind":"commit_only","workflow":"prd","workflow_version":"0.8.0","ai_workflows":"7efcedb","source_repo":"975a5e0 (dirty)","source_repo_branch":"prd/OSAC-3784","commits_behind_main":2,"commits_ahead_main":1,"main_ref":"main","phases":["commit"],"authoring_modes":["skill"],"context_changed":false,"origin_untracked":false} -->
