# Billing Integration MVP

| Field       | Value                |
|-------------|----------------------|
| Author(s)   | Moti Asayag          |
| Jira        | [OSAC-3784](https://redhat.atlassian.net/browse/OSAC-3784) |
| Date        | 2026-09-06           |

## Glossary

Terms are aligned with [FOCUS](https://focus.finops.org/) (FinOps Open Cost and Usage Specification) v1.4 where applicable. The **Source** column marks each entry as FOCUS-defined (used with FOCUS semantics), OSAC-specific (an OSAC term or alias, which may map to a FOCUS concept), or reference. OSAC-3793 uses this glossary for shared billing terms.

| Term | Source | Definition |
|------|--------|------------|
| Billable component | OSAC | Any component of a provisioned resource that has an associated rate (which may be $0), whether or not its usage is metered. Metered billable components are billable dimensions (see below); non-metered billable components — for example, a paid add-on operator, a software license bundled with a resource, or a setup fee — incur cost without a metered quantity. Every billable component of a provisioned resource must have a rate so that no cost-incurring component is silently unbilled. |
| Billable dimension | OSAC | A metered billable component: a metered quantity that incurs cost and must carry a rate — for example, VMaaS instance-type uptime (an instance type encapsulates CPU, memory, and GPU). Defined by the metering design (OSAC-985). |
| Billing account | FOCUS | A container for resources and/or services that are billed together in an invoice. In OSAC, each tenant is associated with exactly one billing account in the billing provider; a single billing account may back multiple tenants (1:N account-to-tenant). |
| Billing period | FOCUS | The time window that an organization receives an invoice for, inclusive of the start date and exclusive of the end date. Defined in the billing system (for example, a calendar month or a custom cycle aligned to fiscal or procurement periods); OSAC aligns cost views and draft-invoice retrieval to it and attributes usage to the period in which it accrued. |
| Billing provider | OSAC | The external billing system that OSAC integrates with to manage pricing, cost calculation, and invoicing. OSAC alias mapping to the FOCUS concepts of invoice issuer and data generator. In OSAC: Monetize360 (M360) or Red Hat Cost Management (Koku). |
| Charge | FOCUS | A line item representing a cost incurred for resource or service usage within a billing period. Corresponds to a row in a FOCUS cost and usage dataset. May be negative to represent a discount or credit. |
| Credit | FOCUS | A monetary amount granted to a tenant — trial, promotional, or contractual — that offsets charges as usage is rated at normal rates. Tracked by the billing system as a per-tenant credit balance. |
| Draft invoice | OSAC | An invoice for a billing period that has not been finalized or issued. OSAC alias for an invoice in a FOCUS open billing period (FOCUS invoice issue status: not yet issued). Cloud Provider Admins review and export draft invoices before submitting them to external payment systems. |
| Rate | OSAC | The price associated with a billable component, authored and held in the billing system (may be negative to express a discount, or $0). OSAC references whether a rate exists for a billable component but does not author or store the rate itself. |
| Rate card | reference | The billing system's construct for organizing rates (per-tenant, per-account, tiered, or otherwise). Its structure and cardinality — whether one card is shared across tenants or authored per account — are internal to the billing system and outside OSAC's model; OSAC is agnostic to how rates are organized. |
| Resource type | FOCUS | A classification of a billable resource that determines its pricing. In OSAC, resource types correspond to the sizing profile of a provisioned resource (e.g., instance types for VMaaS, host types for CaaS worker nodes). Aligns with the FOCUS ResourceType dimension. |
| Service | FOCUS | An offering that can be purchased from a service provider, which may include multiple types of charges. In OSAC, a catalog item maps to a Service. OSAC services in scope for this MVP: VMaaS and CaaS. |
| Usage | OSAC | Measured consumption of a resource (e.g., instance-type-seconds consumed while a VM was running). Defined in the metering PRD (OSAC-985). |

## Problem Statement

OSAC's metering layer (OSAC-985) captures resource consumption for VMaaS, CaaS, and future services, but no mechanism exists to convert usage data into charges, define pricing for service offerings, or present costs to tenants. Cloud Provider Admins cannot generate invoices or track revenue, Tenant Admins cannot attribute costs to teams or budgets, and Tenant Users have no visibility into their consumption costs. Without billing integration, each sovereign cloud deployment must build its own billing pipeline from scratch, duplicating effort and fragmenting the operational model.

## In Scope

This MVP defines what OSAC owns at the seam between its resource lifecycle and an external billing system. The billing system is the source of truth for pricing, rating, and invoicing; OSAC delivers usage, connects tenants to billing accounts, and displays cost. OSAC does not author, store, or compute rates. Detailed behavior is in the User Stories; this section states boundaries those stories do not already convey.

- **Pricing is on billable components, not catalog items** — for VMaaS the billable component is the instance type, rated as a single unit rather than separate CPU, memory, and storage line items. Resources provisioned outside the catalog are billed the same way. Browse-time catalog price display is OSAC-3793.
- **One provider, two services** — one billing provider per deployment (Monetize360 (M360) or Red Hat Cost Management (Koku)); VMaaS and CaaS only. Other services and providers activate via separate Features (see Out of Scope).
- **API and CLI this milestone** — the OSAC web console is not required to close this MVP. User-facing billing documentation and API reference ship with the Feature. Rate authoring and tenant billing onboarding are documented by the billing system, not OSAC.

## Out of Scope

- **Payment and provider-native finance operations** — payment processing, tax, invoicing administration, credits, refunds, adjustments, and the billing provider's own UI remain external. OSAC only reviews and exports draft invoices.
- **Quota, budget, and alternative billing models** — quota enforcement, budget alerts (OSAC-4220), per-user wallets, prepaid, subscription, reseller, and affiliate billing are deferred.
- **Advanced pricing and rate authoring** — OSAC does not author rates or rate cards; tiered, volume, promotional, and per-tenant pricing are handled in the billing system (OSAC-3792).
- **Additional services** — billing for MaaS (OSAC-3794), BMaaS (OSAC-3795), Storage (OSAC-3796), and Networking (OSAC-3797) is deferred until their metering is available.
- **Additional currencies and regions** — each billing account has one immutable base currency. Multi-currency, regional tax and e-invoicing, and data residency are handled by the billing system (OSAC-3790 and OSAC-3798).
- **Workload metering and bulk operations** — OSAC meters provisioned resources, not workloads inside tenant clusters; bulk recalculation and invoice export are deferred.
- **Provider migration history** — a provider switch takes effect at a billing-period boundary. OSAC does not replay prior usage, transfer historical data, or guarantee a unified pre/post-switch view; historical data remains subject to the previous provider's availability and retention policy.
- **Catalog pricing enrichment and multi-provider deployments** — live catalog pricing (OSAC-3793) and selecting different providers per tenant are deferred.

## User Stories

### Cloud Provider Admin

- As a Cloud Provider Admin, I want tenant usage to be charged in the billing system installed for my deployment (M360 or RH Cost Management), so that I get invoicing and cost calculation without building a custom billing pipeline.

- As a Cloud Provider Admin, I want each tenant associated with a billing account — including several tenants sharing one account — with a single immutable base currency per account, validated as an active ISO-4217 code, so that charges land on the correct invoice.

- As a Cloud Provider Admin, I want every cost, invoice, and export response scoped to the caller's authorized tenant set and filtered to that tenant's own records, so that on a shared billing account (1:N account-to-tenant) no caller ever sees another tenant's charges. A Cloud Provider Admin acts on a target tenant selected from the tenants assigned to them; a tenant member is restricted to their own tenant. This partitioning is required of every supported provider integration; scoping to the shared account alone is not sufficient.

- As a Cloud Provider Admin, I want a deleted tenant's OSAC access revoked immediately while its pending-charge attribution is retained in the billing provider until those charges settle and the provider's retention period expires — at which point only that tenant's records are purged — so that deletion does not lose billable history or affect other tenants. On a shared account, the account is retained until its last tenant is purged, and one tenant's deletion never removes or hides another tenant's invoices or charges. OSAC removes access; the billing provider owns retention and purge (consistent with the Assumptions that OSAC does not delete provider-held data).

- As a Cloud Provider Admin, I want OSAC to prevent a resource type from being offered for provisioning until every one of its billable components has a rate in the billing system — both metered dimensions (OSAC-985; for example VMaaS instance types, which encapsulate CPU, memory, and GPU) and non-metered components such as a paid add-on operator or a software license — and to alert me to any component lacking a rate, so that nothing that incurs cost is provisioned unbilled, whether from the catalog or directly.

- As a Cloud Provider Admin, I want to review a tenant's draft charges for a billing period, itemized by service and resource type — including non-metered component charges — so that I can check them before they are issued. The billing provider's draft invoice is the authoritative billing object and it owns invoice identity, revisions, and amounts; corrections and adjustments are made in the billing provider, not in OSAC. Where a billing account backs a single tenant, OSAC returns that account's draft invoice. Where an account is shared (1:N), OSAC returns a tenant-scoped view derived from the account-level draft invoice — the requesting tenant's charges only — rather than the raw account invoice, so no tenant sees another's charges. Retrieving the same tenant and billing period more than once returns the same view; it does not create a second invoice.

- As a Cloud Provider Admin, I want to export a tenant's charges for a billing period to my payment system, so that I can collect payment outside OSAC. On a shared account the export carries the tenant-scoped view — the requesting tenant's charges only — not the provider's full account invoice, so an export never omits or exposes charges in a way that yields an invalid cross-tenant invoice.

- As a Cloud Provider Admin, I want OSAC-side billing operations — invoice review and export, billing-provider installation and switchover, and access to cost data — restricted to users with billing-specific permissions, so that only authorized personnel can access financial data or change the billing connection.

- As a Cloud Provider Admin, I want the billing-related actions performed through OSAC — billing-provider installation and switchover, tenant-to-billing-account provisioning, and draft-invoice retrieval and export — to produce entries in the OSAC audit log (visible through the API and CLI), so that I can satisfy compliance and regulatory audit requirements. Rate and pricing changes made directly in the billing system are audited by that system, consistent with it remaining the pricing source of truth.

### Cloud Provider Admin / Tenant Admin

- As a Cloud Provider Admin or Tenant Admin, I want resource provisioning and lifecycle operations to continue when the billing system is unreachable, so that a billing outage does not stop tenants from using the cloud. When the billing system recovers, no usage is missing and no charges or accounts are duplicated.

### Cloud Infrastructure Admin

- As a Cloud Infrastructure Admin, I want to install the billing provider connection as part of the OSAC installation — including credentials that are not stored in plaintext — so that billing integration is operational from day one without exposing secrets in configuration files.

- As a Cloud Infrastructure Admin, I want to switch the billing provider (for example, from M360 to RH Cost Management) via installation configuration, so that a provider change is a configuration change, not a code change, rebuild, or reinstall of OSAC. A switch takes effect from the switch point forward at a billing-period boundary — prior usage is not replayed, and historical records remain with the previous provider.

- As a Cloud Infrastructure Admin, I want to see when billing integration is unhealthy (usage is not flowing to the billing system), so that I can fix it before invoices are wrong.

### Tenant Admin

- As a Tenant Admin, I want to view my organization's accumulated costs for the current and past billing periods, broken down by service type (VMaaS, CaaS) and resource, so that I can manage my organization's cloud spending. The available history follows the billing provider's retention of cost and invoice data.

- As a Tenant Admin, I want to view costs aggregated by Project (including nested Projects), so that I can attribute spending to teams and departments within my organization. This relies on usage and charge records preserving stable Project identifiers and parent-child relationships, captured by OSAC-985 metering.

- As a Tenant Admin, I want to view past invoices and itemized charge breakdowns for my organization, so that I can reconcile charges with my internal budgets and respond to billing inquiries from my users.

### Tenant User

- As a Tenant User, I want to view the estimated cost of the resources I have deployed and the Projects I have access to, so that I understand my consumption footprint without seeing tenant-wide financial data. When I open a cost view, it shows the billing system's latest calculated charges — metered usage together with any non-metered component charges — and an "as of" timestamp; usage still being processed is not yet included.

- As a Tenant User, I want to view the cost history over time of the resources and Projects I have access to, so that I can spot trends in my own spending.

## Assumptions

- The metering layer (OSAC-985) is operational and collecting usage data for VMaaS and CaaS before billing integration begins.

- The billing provider (M360 or RH Cost Management) is deployed and reachable from the OSAC deployment. OSAC does not manage the billing provider's lifecycle.

- The billing system supports the pricing OSAC relies on (per-component rates, including negative rates for discounts, and whatever per-tenant rate differentiation the Cloud Provider Admin authors). OSAC is agnostic to how the billing system organizes those rates. If a billing provider lacks a capability, that feature is unavailable in that deployment until the provider supports it. Whether a single rate structure can be shared across billing accounts is a provider-specific detail OSAC does not assume.

- OSAC does not guarantee a fixed end-to-end latency from usage delivery to queryable charge in this MVP. Cost queries return the most recently processed data with an "as of" timestamp; usage still being processed is not yet reflected. This does not hold during provider recovery or backlog drain.

- Trial and promotional access is modeled as a per-tenant credit balance held by the billing provider, which the provider draws down against charges as usage is rated at normal (non-zero) rates, rather than as a separate zero-rate plan or trial mode. Credits are granted and applied in the billing provider's interface (see Out of Scope).

- Billing, cost, and invoice data are stored and retained on the external billing system, governed by its retention policy. Metering and usage data retention is governed by OSAC-985. OSAC does not independently store, mirror, or delete billing or cost data.

- When billing integration is enabled on a deployment with existing tenants, billing accounts are created for those tenants. Pre-existing usage data (generated before billing activation) is not retroactively billed.

- Billing integration can be disabled without affecting resource provisioning or lifecycle operations. When disabled, billing and cost data already recorded on the billing system remains subject to that system's retention policy.

- Billing data (prices, costs, invoices, tenant consumption) is financially sensitive. It is protected by OSAC's existing data protection mechanisms (encryption in transit and at rest).

## Dependencies

- **OSAC-985 — Metering and Usage Tracking:** Provides the usage data pipeline that billing consumes, and defines the set of billable dimensions that must carry rates. Metering must be operational for VMaaS and CaaS before billing can calculate charges.

- **MaaS billing (OSAC-3794) — tracked independently:** MaaS billing depends on MaaS metering and does not gate this MVP. If MaaS metering lands in time, its billable dimensions are priced through the same mechanism defined here.

- **Billing provider deployment:** M360 or RH Cost Management must be deployed and configured independently. OSAC integrates with the billing provider.

- **OSAC Catalog (OSAC-1531, OSAC-2452):** VMaaS and CaaS catalog items must exist as offerings. Pricing is on the billable components of provisioned resources, not on catalog items. Browse-time catalog price display is OSAC-3793.

- **Resource composition metadata:** Billing for non-metered components requires the provisioning workflow to record which billable components are attached to a provisioned resource. Where these components originate from catalog items, this ties into the catalog dependency above.

- **OSAC-4220 — Quota Foundation:** Billing cost data may feed into quota enforcement in a future milestone. This PRD does not implement quota logic but does not preclude it.

---

## Provenance

Authored: draft @ prd 0.8.0 - a605aa5, workspace feat/add-osac-metering-documentation @ 514565f
Final: revise @ prd 0.8.0 - 7efcedb, workspace HEAD @ 155acfa

> Context changed between draft and revise.

<!-- ai-workflow-provenance:{"schema_version":1,"provenance_kind":"session","workflow":"prd","workflow_version":"0.8.0","ai_workflows":"7efcedb","source_repo":"155acfa","source_repo_branch":"HEAD","commits_behind_main":0,"commits_ahead_main":1,"main_ref":"main","phases":["draft","revise","revise","revise"],"authoring_modes":["skill"],"context_changed":true,"origin_untracked":false} -->
