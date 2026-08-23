# Billing Integration MVP

| Field       | Value                |
|-------------|----------------------|
| Author(s)   | Moti Asayag          |
| Jira        | [OSAC-3784](https://redhat.atlassian.net/browse/OSAC-3784) |
| Date        | 2026-08-23           |

## Glossary

Terms are aligned with [FOCUS](https://focus.finops.org/) (FinOps Open Cost and Usage Specification) where applicable. The **Source** column marks each entry as FOCUS-defined (used with FOCUS semantics) or OSAC-specific. OSAC-3793 uses this glossary for shared billing terms.

| Term | Source | Definition |
|------|--------|------------|
| Billable component | OSAC | Any component of a provisioned resource that has an associated rate (which may be $0), whether or not its usage is metered. Metered billable components are billable dimensions (see below); non-metered billable components — for example, a paid add-on operator, a software license bundled with a resource, or a setup fee — incur cost without a metered quantity. Every billable component of a provisioned resource must have a rate so that no cost-incurring component is silently unbilled. |
| Billable dimension | OSAC | A metered billable component: a metered quantity that incurs cost and must carry a rate — for example, VMaaS instance-type uptime (an instance type encapsulates CPU, memory, and GPU). Defined by the metering design (OSAC-985). |
| Billing account | FOCUS | A container for resources and/or services that are billed together in an invoice. In OSAC, each tenant is associated with exactly one billing account in the billing provider; a single billing account may back multiple tenants (1:N account-to-tenant). |
| Billing currency | FOCUS | The single base currency in which a billing account's charges are denominated. In OSAC, each billing account uses one immutable base currency; billing across multiple currencies is achieved by provisioning separate billing accounts. |
| Billing period | FOCUS | The time window that an organization receives an invoice for, inclusive of the start date and exclusive of the end date. In OSAC, the billing period is configurable by the Cloud Provider Admin (for example, a calendar month or a custom cycle aligned to fiscal or procurement periods); the active billing provider must support the configured period. |
| Billing provider | FOCUS | The external billing system that OSAC integrates with to manage pricing, cost calculation, and invoicing. Maps to the FOCUS concepts of invoice issuer and data generator. In OSAC: Monetize360 (M360) or Red Hat Cost Management (Koku). |
| Billing provider adapter | OSAC | The OSAC-side connection from a deployment to exactly one billing provider. Cloud Infrastructure Admins install and switch it; Cloud Provider Admins manage rates, billing period, and tenant onboarding. |
| Charge | FOCUS | A line item representing a cost incurred for resource or service usage within a billing period. Corresponds to a row in a FOCUS cost and usage dataset. May be negative to represent a discount or credit. |
| Credit | FOCUS | A monetary amount granted to a tenant — trial, promotional, or contractual — that offsets charges as usage is rated at normal rates. Tracked by the billing system as a per-tenant credit balance. |
| Draft invoice | FOCUS | An invoice for a billing period that has not been finalized or issued. Corresponds to an invoice in a FOCUS open billing period. Cloud Provider Admins review and export draft invoices before submitting them to external payment systems. |
| FOCUS | reference | [FinOps Open Cost and Usage Specification](https://focus.finops.org/) — an open-source specification that defines requirements for billing data. |
| Meter | OSAC | A named aggregation that turns events into a measurable quantity (e.g., total VM uptime grouped by tenant and project). Defined in the metering PRD (OSAC-985). |
| Pricing plan | OSAC | A named collection of rate cards that defines the pricing terms for a tenant. Cloud Provider Admins assign pricing plans to tenants; a default plan applies to unassigned tenants. |
| Rate card | OSAC | A mapping of a billable component to a rate within a pricing plan. Rate cards define how a specific billable component is priced (for example, a per-unit price for a metered resource type). A rate may be negative to express a discount. |
| Resource type | FOCUS | A classification of a billable resource that determines its pricing. In OSAC, resource types correspond to the sizing profile of a provisioned resource (e.g., instance types for VMaaS, host types for CaaS worker nodes). Aligns with the FOCUS ResourceType dimension. |
| Service | FOCUS | An offering that can be purchased from a service provider, which may include multiple types of charges. In OSAC, a catalog item maps to a Service. OSAC services in scope for this MVP: VMaaS and CaaS. |
| Usage | OSAC | Measured consumption of a resource (e.g., instance-type-seconds consumed while a VM was running). Defined in the metering PRD (OSAC-985). |

## Problem Statement

OSAC's metering layer (OSAC-985) captures resource consumption for VMaaS, CaaS, and future services, but no mechanism exists to convert usage data into charges, define pricing for service offerings, or present costs to tenants. Cloud Provider Admins cannot generate invoices or track revenue, Tenant Admins cannot attribute costs to teams or budgets, and Tenant Users have no visibility into their consumption costs. Without billing integration, each sovereign cloud deployment must build its own billing pipeline from scratch, duplicating effort and fragmenting the operational model.

## In Scope

- **One billing system per deployment** — each OSAC deployment uses one billing provider. Initial providers: Monetize360 (M360) and Red Hat Cost Management (Koku).
- **Billing system as pricing source of truth** — prices are not independently maintained in OSAC. Rate changes take effect for future charges going forward. Every billable component of a provisioned resource must have a corresponding rate in the tenant's effective pricing plan (or the default plan) — both metered components (billable dimensions defined by OSAC-985) and non-metered components (for example, a paid add-on operator, a software license, or a setup fee). OSAC surfaces billable components that lack a rate so that no cost-incurring component is silently unbilled. Pricing applies to the resource's billable components, not to the catalog item; browse-time catalog price display is OSAC-3793.
- **Registration before charging** — billable dimensions and non-metered components are registered in the billing system with a rate before their data is delivered, so incoming usage and non-metered charges can be matched to a rate. Introducing a new billable dimension or component requires it to be registered with a rate first.
- **Charges for non-metered components** — a provisioned resource may include billable components whose cost is not derived from metered usage (for example, a paid add-on operator on a CaaS cluster, a software license bundled with a VM image, or a setup fee). OSAC prices these components, presents their rates as part of the provisioned resource's cost, and delivers their charges to the billing system so they appear on the invoice alongside metered usage. The active billing provider must be able to represent non-usage charges; how such charges are delivered is a design concern.
- **Configurable billing period** — the Cloud Provider Admin configures the billing period for the deployment (for example, a calendar month or a custom cycle); the active billing provider must support the configured period.
- **VMaaS and CaaS billing** — charge calculation for the two services with existing metering (OSAC-985). Billing for other services activates via separate Features as their metering becomes available (see Out of Scope).
- **Pricing input validation** — currency codes are restricted to active ISO-4217 codes, and amounts must be well-formed. Negative rates are permitted, to express discounts and credits.
- **Tenant-to-billing-account lifecycle** — creating a tenant in OSAC provisions a corresponding billing account in the billing provider (idempotently, with retry on provider unavailability and no duplicate accounts). A billing account may back multiple tenants (1:N). Deleting a tenant does not hide past invoices while the billing provider still retains that data; the provider deletes account data per its own retention policy. OSAC does not independently store, mirror, or delete billing data. An explicit billing cutover boundary defines when usage begins and ceases to accrue.
- **Billing resilience** — billing system unavailability does not block tenant provisioning or resource lifecycle operations. Account creation and usage delivery are retried idempotently when connectivity is restored, with no double-counted usage or duplicate charges.
- **Invoice idempotency** — regenerating or retrying a draft invoice for the same tenant and billing period returns or reuses the existing draft rather than creating a duplicate.
- **API, CLI, and UI surfaces** — cost views, invoice listing, pricing plan management, billing-period configuration, and billing-provider installation are accessible via the OSAC API, the `osac` CLI, and the OSAC web console. UI may be API/CLI-first this milestone. Console views match the persona stories below. Two `osac-ux` prototype concepts are not in this MVP (prepaid/subscription billing-model selector and affiliate identifier — see Out of Scope).
- **Billing RBAC and visibility boundaries** — billing operations require specific authorization, and cost/invoice data is scoped to the tenant's own billing account. Tenant Admins see tenant-wide cost history and invoices; Tenant Users see only the cost of resources and projects they have access to. Project membership bounds visibility so financial data is not exposed across unrelated teams.

## Out of Scope

- **Payment processing and gateway integration** — OSAC generates draft invoices; payment collection and PCI compliance are handled externally.
- **Quota enforcement and budget alerts** — tracked separately as OSAC-998.
- **Workload-level metering** — OSAC meters resources it provisions, not workloads running inside tenant clusters.
- **Billing provider UI** — the billing provider's own administration interface; this PRD covers OSAC-side surfaces only. Functionality native to the billing provider (invoicing, tax, payment, refunds) is delegated to it.
- **Trial, promotional, and ad-hoc credits, refunds, and adjustments** — granted and managed in the billing provider's own interface. OSAC treats an existing credit balance as an offset against normal rates (see Assumptions); it does not provide a credit-granting UI.
- **Per-user cost attribution and user wallets** — the MVP attributes cost at tenant and project scope only. Per-user consumption views and per-user prepaid wallets are a known future need (e.g., MOC 2.0 requests) and are tracked separately.
- **Prepaid and subscription billing models** — the MVP bills tenants on a pay-as-you-go basis (charges accrue into a draft invoice per billing period). Per-tenant prepaid balances and recurring subscription models (the osac-ux prototype's billing-model selector) are deferred.
- **Reseller and affiliate billing** — affiliate/reseller attribution and reseller-specific pricing (the osac-ux prototype's affiliate identifier) are deferred.
- **MaaS billing** — depends on MaaS metering, which is not yet available; tracked independently (OSAC-3794). It does not gate this MVP.
- **Multi-currency billing** — each billing account uses a single immutable base currency. Billing tenants in different currencies is achieved by provisioning separate billing accounts; native multi-currency per account, and reseller/multi-region local-currency billing, are deferred.
- **Multi-provider per deployment** — each OSAC deployment uses one billing provider. Per-tenant provider selection is deferred.
- **Historical data replay across a provider switch** — switching the billing provider takes effect from the switch point forward at a billing-period boundary; OSAC does not replay prior usage into the new provider, and historical records remain with the previous provider.
- **Bulk billing operations** — batch pricing plan assignment, bulk recalculation, and bulk invoice export are deferred.
- **Billing data residency** — per-tenant billing data residency by region is enforced by the billing provider, not by OSAC.
- **Catalog item pricing enrichment** — enriching catalog items with live prices from the billing system is a separate Feature (OSAC-3793).
- **Billing for services beyond VMaaS and CaaS** — BMaaS (OSAC-3795), Storage (OSAC-3796), and Networking (OSAC-3797) billing activate via separate Features as metering lands. MaaS (OSAC-3794) is covered by the MaaS-billing item above.

## User Stories

### Cloud Provider Admin

- As a Cloud Provider Admin, I want tenant usage to be charged in the billing system that has been installed for my deployment (M360 or RH Cost Management), so that I can manage pricing and invoices there without building a custom billing pipeline.

- As a Cloud Provider Admin, I want to configure the billing period for my deployment (for example, a calendar month or a custom cycle), so that billing aligns with my customers' fiscal and procurement cycles rather than being locked to a fixed calendar month.

- As a Cloud Provider Admin, I want to create pricing plans with rate cards that define rates for billable components (for example, a per-unit price for a resource type) — including discounts expressed as negative rates — so that I can set different rates for different tenants based on their service agreements and hardware classes.

- As a Cloud Provider Admin, I want every billable component of a provisioned resource registered in the billing system with a rate — both the metered dimensions defined by OSAC-985 (for example VMaaS instance types, which encapsulate CPU, memory, and GPU) and non-metered components such as a paid add-on operator or a software license — and to be alerted when one has no rate, so that nothing that incurs cost is silently unbilled, whether the resource was provisioned from the catalog or directly. Browse-time catalog price display is OSAC-3793.

- As a Cloud Provider Admin, I want to assign pricing plans to tenants, so that each tenant's usage is charged according to their agreed terms. A default plan applies to tenants without a specific assignment. When a plan's rates change, affected tenants' future charges reflect the updated rates.

- As a Cloud Provider Admin, I want to view draft invoices per tenant for a billing period showing charges itemized by service and resource type, so that I can review charges before exporting them to my payment system. Regenerating or retrying an invoice for the same tenant and billing period returns the existing draft rather than creating a duplicate.

- As a Cloud Provider Admin, I want billing operations (pricing plan management, billing-period configuration, invoice review) restricted to users with billing-specific permissions, so that only authorized personnel can modify pricing or access financial data.

- As a Cloud Provider Admin, I want all billing-related administrative actions — pricing plan changes, plan-to-tenant assignments, billing-period configuration, billing-provider changes, and invoice generation — to produce entries in the OSAC audit log (visible through the API, CLI, and UI where audit is surfaced), so that I can satisfy compliance and regulatory audit requirements.

### Cloud Infrastructure Admin

- As a Cloud Infrastructure Admin, I want to install the billing provider connection as part of the OSAC installation — including credentials that are not stored in plaintext — so that billing integration is operational from day one without exposing secrets in configuration files.

- As a Cloud Infrastructure Admin, I want to switch the billing provider (for example, from M360 to RH Cost Management) via installation configuration, so that a provider change does not require a custom rebuild. Configuring the connection is an infrastructure responsibility; defining rates, the billing period, and tenant onboarding is a Cloud Provider Admin responsibility. A switch takes effect from the switch point forward at a billing-period boundary — prior usage is not replayed, and historical records remain with the previous provider.

- As a Cloud Infrastructure Admin, I want to see when billing integration is unhealthy (usage is not flowing to the billing system), so that I can fix it before invoices are wrong.

### Tenant Admin

- As a Tenant Admin, I want to view my organization's accumulated costs for the current and past billing periods, broken down by service type (VMaaS, CaaS) and resource, so that I can manage my organization's cloud spending. The available history follows the billing provider's retention of cost and invoice data.

- As a Tenant Admin, I want to view costs aggregated by Project (including nested Projects), so that I can attribute spending to teams and departments within my organization. This relies on usage and charge records preserving stable Project identifiers and parent-child relationships, captured by OSAC-985 metering.

- As a Tenant Admin, I want to view past invoices and itemized charge breakdowns for my organization, so that I can reconcile charges with my internal budgets and respond to billing inquiries from my users.

### Tenant User

- As a Tenant User, I want to view the estimated cost of the resources I have deployed and the Projects I have access to, so that I understand my consumption footprint without seeing tenant-wide financial data. Estimated cost reflects the charges the billing system calculates for the resource's billable components — metered usage shortly after it occurs (a bounded processing latency on the order of a minute) together with any non-metered component charges — queried on demand rather than pushed as a streamed feed.

- As a Tenant User, I want to view the cost history over time of the resources and Projects I have access to, so that I can spot trends in my own spending.

## Assumptions

- The metering layer (OSAC-985) is operational and collecting usage data for VMaaS and CaaS before billing integration begins.

- The billing provider (M360 or RH Cost Management) is deployed and reachable from the OSAC deployment. OSAC does not manage the billing provider's lifecycle.

- The billing system supports the pricing models required by this PRD (per-unit rate cards, including negative rates for discounts). If a billing provider lacks a capability, that feature is unavailable in that deployment until the provider supports it.

- The billing system processes metering events with a bounded, low latency (on the order of a minute). Tenants querying their estimated costs see charges derived from recently processed usage data.

- Trial and promotional access is modeled as a per-tenant credit balance that offsets charges as usage is rated at normal (non-zero) rates, rather than a separate zero-rate plan or trial mode. Credits are granted in the billing provider's interface (see Out of Scope).

- Billing, cost, and invoice data are stored and retained on the external billing system, governed by its retention policy. Metering and usage data retention is governed by OSAC-985. OSAC does not independently store, mirror, or delete billing or cost data.

- When billing integration is enabled on a deployment with existing tenants, billing accounts are created for those tenants. Pre-existing usage data (generated before billing activation) is not retroactively billed.

- Billing integration can be disabled without affecting resource provisioning or lifecycle operations. When disabled, billing and cost data already recorded on the billing system remains subject to that system's retention policy.

- Billing data (prices, costs, invoices, tenant consumption) is financially sensitive. It is protected by OSAC's existing data protection mechanisms (encryption in transit and at rest).

## Dependencies

- **OSAC-985 — Metering and Usage Tracking:** Provides the usage data pipeline that billing consumes, and defines the set of billable dimensions that must carry rates. Metering must be operational for VMaaS and CaaS before billing can calculate charges.

- **MaaS billing (OSAC-3794) — tracked independently:** MaaS billing depends on MaaS metering and does not gate this MVP. If MaaS metering lands in time, its billable dimensions are priced through the same mechanism defined here.

- **Billing provider deployment:** M360 or RH Cost Management must be deployed and configured independently. OSAC integrates via the billing provider's APIs.

- **OSAC Catalog (OSAC-1531, OSAC-2452):** VMaaS and CaaS catalog items must exist as offerings. Pricing is on the billable components of provisioned resources, not on catalog items. Browse-time catalog price display is OSAC-3793.

- **Resource composition metadata:** Billing for non-metered components requires the provisioning layer to record which billable components (for example, add-on operators, licenses, or fees) are attached to a provisioned resource. Where these components originate from catalog items, this ties into the catalog dependency above.

- **OSAC-998 — Quota Management:** Billing cost data may feed into quota enforcement in a future milestone. This PRD does not implement quota logic but does not preclude it.

- **Documentation:** User-facing documentation for billing management (pricing plan setup, invoice workflows, cost visibility) and API reference for billing endpoints are delivered with the feature.

---

## Provenance

Authored: draft @ prd 0.8.0 - a605aa5, workspace feat/add-osac-metering-documentation @ 514565f
Final: revise @ prd 0.8.0 - 7efcedb, workspace HEAD @ 155acfa

> Context changed between draft and revise.

<!-- ai-workflow-provenance:{"schema_version":1,"provenance_kind":"session","workflow":"prd","workflow_version":"0.8.0","ai_workflows":"7efcedb","source_repo":"155acfa","source_repo_branch":"HEAD","commits_behind_main":0,"commits_ahead_main":1,"main_ref":"main","phases":["draft","revise","revise","revise"],"authoring_modes":["skill"],"context_changed":true,"origin_untracked":false} -->
