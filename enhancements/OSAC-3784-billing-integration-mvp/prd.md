# Billing Integration MVP

| Field       | Value                |
|-------------|----------------------|
| Author(s)   | Moti Asayag          |
| Jira        | [OSAC-3784](https://redhat.atlassian.net/browse/OSAC-3784) |
| Date        | 2026-08-23           |

## Glossary

Terms are aligned with [FOCUS](https://focus.finops.org/) (FinOps Open Cost and Usage Specification) v1.4 where applicable. The **Source** column marks each entry as FOCUS-defined (used with FOCUS semantics), OSAC-specific (an OSAC term or alias, which may map to a FOCUS concept), or reference. OSAC-3793 uses this glossary for shared billing terms.

| Term | Source | Definition |
|------|--------|------------|
| Billable component | OSAC | Any component of a provisioned resource that has an associated rate (which may be $0), whether or not its usage is metered. Metered billable components are billable dimensions (see below); non-metered billable components — for example, a paid add-on operator, a software license bundled with a resource, or a setup fee — incur cost without a metered quantity. Every billable component of a provisioned resource must have a rate so that no cost-incurring component is silently unbilled. |
| Billable dimension | OSAC | A metered billable component: a metered quantity that incurs cost and must carry a rate — for example, VMaaS instance-type uptime (an instance type encapsulates CPU, memory, and GPU). Defined by the metering design (OSAC-985). |
| Billing account | FOCUS | A container for resources and/or services that are billed together in an invoice. In OSAC, each tenant is associated with exactly one billing account in the billing provider; a single billing account may back multiple tenants (1:N account-to-tenant). |
| Billing currency | FOCUS | The single base currency in which a billing account's charges are denominated. In OSAC, each billing account uses one immutable base currency; billing across multiple currencies is achieved by provisioning separate billing accounts. |
| Billing period | FOCUS | The time window that an organization receives an invoice for, inclusive of the start date and exclusive of the end date. Defined in the billing system (for example, a calendar month or a custom cycle aligned to fiscal or procurement periods); OSAC aligns cost views and draft-invoice retrieval to it and attributes usage to the period in which it accrued. |
| Billing provider | OSAC | The external billing system that OSAC integrates with to manage pricing, cost calculation, and invoicing. OSAC alias mapping to the FOCUS concepts of invoice issuer and data generator. In OSAC: Monetize360 (M360) or Red Hat Cost Management (Koku). |
| Charge | FOCUS | A line item representing a cost incurred for resource or service usage within a billing period. Corresponds to a row in a FOCUS cost and usage dataset. May be negative to represent a discount or credit. |
| Credit | FOCUS | A monetary amount granted to a tenant — trial, promotional, or contractual — that offsets charges as usage is rated at normal rates. Tracked by the billing system as a per-tenant credit balance. |
| Draft invoice | OSAC | An invoice for a billing period that has not been finalized or issued. OSAC alias for an invoice in a FOCUS open billing period (FOCUS invoice issue status: not yet issued). Cloud Provider Admins review and export draft invoices before submitting them to external payment systems. |
| FOCUS | reference | [FinOps Open Cost and Usage Specification](https://focus.finops.org/) — an open-source specification that defines requirements for billing data. |
| Meter | OSAC | A named aggregation that turns events into a measurable quantity (e.g., total VM uptime grouped by tenant and project). Defined in the metering PRD (OSAC-985). |
| Rate | OSAC | The price associated with a billable component, authored and held in the billing system (may be negative to express a discount, or $0). OSAC references whether a rate exists for a billable component but does not author or store the rate itself. |
| Rate card | reference | The billing system's construct for organizing rates (per-tenant, per-account, tiered, or otherwise). Its structure and cardinality — whether one card is shared across tenants or authored per account — are internal to the billing system and outside OSAC's model; OSAC is agnostic to how rates are organized. |
| Resource type | FOCUS | A classification of a billable resource that determines its pricing. In OSAC, resource types correspond to the sizing profile of a provisioned resource (e.g., instance types for VMaaS, host types for CaaS worker nodes). Aligns with the FOCUS ResourceType dimension. |
| Service | FOCUS | An offering that can be purchased from a service provider, which may include multiple types of charges. In OSAC, a catalog item maps to a Service. OSAC services in scope for this MVP: VMaaS and CaaS. |
| Usage | OSAC | Measured consumption of a resource (e.g., instance-type-seconds consumed while a VM was running). Defined in the metering PRD (OSAC-985). |

## Problem Statement

OSAC's metering layer (OSAC-985) captures resource consumption for VMaaS, CaaS, and future services, but no mechanism exists to convert usage data into charges, define pricing for service offerings, or present costs to tenants. Cloud Provider Admins cannot generate invoices or track revenue, Tenant Admins cannot attribute costs to teams or budgets, and Tenant Users have no visibility into their consumption costs. Without billing integration, each sovereign cloud deployment must build its own billing pipeline from scratch, duplicating effort and fragmenting the operational model.

## In Scope

This MVP defines what OSAC owns at the seam between its own resource lifecycle and an external billing system. The organizing principle is a clean split of responsibility: **the billing system is the source of truth for pricing, rating, and invoicing; OSAC delivers usage and charge triggers, connects tenants to billing accounts, and displays cost.** OSAC does not author, store, or compute rates, and is deliberately thin at this seam — complex billing configuration lives in the billing system. Detailed behavior is captured in the User Stories below; this section states the conceptual boundaries.

- **Billing system as pricing source of truth** — OSAC does not maintain or compute prices. The billing system owns rate authoring, rating, and invoice production; OSAC references whether a billable component has a rate and displays the cost the billing system calculates. Pricing is anchored to the resource's billable components — for VMaaS the billable component is the instance type, rated as a single unit rather than decomposed into separate CPU, memory, and storage line items — not to the catalog item, since resources can be provisioned outside the catalog and are managed independently afterward. Browse-time catalog price display is OSAC-3793.
- **Rate authoring and tenant billing onboarding are external** — defining rates, organizing them (rate cards), and onboarding a tenant's billing terms are performed directly in the billing system by the Cloud Provider Admin, not in OSAC. OSAC is **agnostic to how rates are organized** — whether one rate card is shared across all tenants or authored per account is internal to the billing system and carries no OSAC-side cost or model. OSAC neither provides rate-authoring surfaces nor assumes a particular rate-card cardinality.
- **Rate coverage before availability (publish gate)** — OSAC ensures every billable component of a resource type — both metered dimensions (OSAC-985) and non-metered components — has a rate in the billing system before that resource type is offered for provisioning, and surfaces any component lacking a rate. This prevents cost-incurring resources from being provisioned unbilled, without OSAC holding the rate itself.
- **Charges for non-metered components** — a provisioned resource may include billable components whose cost is not derived from metered usage (for example, a paid add-on operator on a CaaS cluster, a software license bundled with a VM image, or a setup fee). OSAC identifies these components, ensures each is registered as a rateable item in the billing system, and delivers the charge trigger; the billing system holds the rate and produces the charge so it appears on the invoice alongside metered usage. OSAC does not compute the monetary amount.
- **Initial providers and services** — one billing provider per deployment (Monetize360 (M360) or Red Hat Cost Management (Koku)); billing for the two services with existing metering (VMaaS and CaaS, via OSAC-985). Billing for other services and providers activates via separate Features (see Out of Scope).
- **Tenant-to-billing-account lifecycle** — OSAC provisions and links billing accounts as tenants are created and deleted, including 1:N account-to-tenant sharing and cross-tenant isolation on deletion. Each account is provisioned with a single immutable base currency validated as an active ISO-4217 code.
- **Cost visibility with RBAC scoping** — cost views and invoice listings scoped to the tenant's billing account and aligned to the billing period defined in the billing system, with Tenant Admin (tenant-wide) versus Tenant User (own resources/projects) boundaries, so financial data is not exposed across unrelated teams. OSAC attributes usage to the billing period in which it accrued.
- **Billing resilience** — billing system unavailability never blocks tenant provisioning or resource lifecycle operations; on recovery, no usage is lost and no charges or accounts are duplicated.
- **Provider installation and switch as configuration** — installing and switching the billing provider is an installation-configuration action, not a code change or reinstall.
- **API, CLI, and UI surfaces** — the above are accessible via the OSAC API, the `osac` CLI, and the OSAC web console; UI may be API/CLI-first this milestone. Two `osac-ux` prototype concepts are not in this MVP (prepaid/subscription billing-model selector and affiliate identifier — see Out of Scope).

## Out of Scope

- **Payment processing and gateway integration** — OSAC surfaces the billing provider's draft invoices for review and export; payment collection and PCI compliance are handled externally.
- **Quota enforcement and budget alerts** — tracked separately as OSAC-4220 (Quota Foundation).
- **Workload-level metering** — OSAC meters resources it provisions, not workloads running inside tenant clusters.
- **Billing provider UI** — the billing provider's own administration interface; this PRD covers OSAC-side surfaces only. Functionality native to the billing provider (invoicing, tax, payment, refunds) is delegated to it.
- **Trial, promotional, and ad-hoc credits, refunds, and adjustments** — granted and managed in the billing provider's own interface. The billing provider holds any credit balance and applies it against rated charges; OSAC neither grants credits nor computes the offset (see Assumptions), and does not provide a credit-granting UI.
- **Per-user cost attribution and user wallets** — the MVP attributes cost at tenant and project scope only. Per-user consumption views and per-user prepaid wallets are a known future need (e.g., MOC 2.0 requests) and are tracked separately.
- **Prepaid and subscription billing models** — the MVP bills tenants on a pay-as-you-go basis (charges accrue into a draft invoice per billing period). Per-tenant prepaid balances and recurring subscription models (the osac-ux prototype's billing-model selector) are deferred. Per-tenant enforcement policy on billing-system unavailability — for example, blocking provisioning to protect a prepaid balance — is deferred with prepaid wallets; the MVP's resilience guarantee (provisioning is never blocked) applies uniformly to all tenants.
- **Reseller and affiliate billing** — affiliate/reseller attribution and reseller-specific pricing (the osac-ux prototype's affiliate identifier) are deferred.
- **MaaS billing** — depends on MaaS metering, which is not yet available; tracked independently (OSAC-3794). It does not gate this MVP.
- **Multi-currency billing** — each billing account uses a single immutable base currency. Billing tenants in different currencies is achieved by provisioning separate billing accounts; native multi-currency per account, cross-currency handling (OSAC-3790), and reseller/multi-region local-currency billing, are deferred.
- **Multi-provider per deployment** — each OSAC deployment uses one billing provider. Per-tenant provider selection is deferred.
- **Historical data replay across a provider switch** — switching the billing provider takes effect from the switch point forward at a billing-period boundary; OSAC does not replay prior usage into the new provider, and historical records remain with the previous provider.
- **Rate and rate-card authoring** — defining rates, organizing them into rate cards, and onboarding a tenant's billing terms are performed in the billing system, not OSAC. OSAC provides no rate-authoring surface and is agnostic to rate-card structure and cardinality.
- **Advanced and per-tenant pricing models** — tiered, volume, promotional, and other advanced pricing, and per-tenant rate differentiation, are handled in the billing system (OSAC-3792 is closed; this capability is delivered there, not as an OSAC Feature).
- **Region-based billing and data residency** — assigning a tenant a region that determines tax jurisdiction, e-invoicing format, regulatory framework, and per-region data residency is handled in the billing system (OSAC-3798 is closed; delivered there, not as an OSAC Feature). The tenant-to-billing-account model established here must not preclude assigning a region attribute to a tenant later without re-provisioning its billing account.
- **Bulk billing operations** — bulk recalculation and bulk invoice export are deferred.
- **Catalog item pricing enrichment** — enriching catalog items with live prices from the billing system is a separate Feature (OSAC-3793).
- **Billing for services beyond VMaaS and CaaS** — BMaaS (OSAC-3795), Storage (OSAC-3796), and Networking (OSAC-3797) billing activate via separate Features as metering lands. MaaS (OSAC-3794) is covered by the MaaS-billing item above.

## User Stories

### Cloud Provider Admin

- As a Cloud Provider Admin, I want tenant usage to be charged in the billing system installed for my deployment (M360 or RH Cost Management), so that I get invoicing and cost calculation without building a custom billing pipeline.

- As a Cloud Provider Admin, I want to author rates and onboard each tenant's billing terms directly in the billing system rather than in OSAC, so that I use the billing system's full pricing capabilities and OSAC stays thin at the billing seam. This is why rate cards, pricing plans, per-tenant rate differentiation, and the billing period are configured in the billing system and do not appear as OSAC surfaces.

- As a Cloud Provider Admin, I want OSAC to prevent a resource type from being offered for provisioning until every one of its billable components has a rate in the billing system — both metered dimensions (OSAC-985; for example VMaaS instance types, which encapsulate CPU, memory, and GPU) and non-metered components such as a paid add-on operator or a software license — and to alert me to any component lacking a rate, so that nothing that incurs cost is provisioned unbilled, whether from the catalog or directly. Browse-time catalog price display is OSAC-3793.

- As a Cloud Provider Admin, I want to view the billing provider's draft invoice per tenant for a billing period, itemized by service and resource type, so that I can review charges and export them to my payment system. The billing provider owns invoice identity, revisions, and amounts, and any corrections or adjustments are made in the billing provider, not in OSAC; OSAC requests and retrieves the draft, and that request is repeat-safe per (tenant, billing period), returning the existing provider draft on retry rather than creating a duplicate.

- As a Cloud Provider Admin, I want OSAC-side billing operations — invoice review and export, billing-provider installation and switchover, and access to cost data — restricted to users with billing-specific permissions, so that only authorized personnel can access financial data or change the billing connection.

- As a Cloud Provider Admin, I want the billing-related actions performed through OSAC — billing-provider installation and switchover, tenant-to-billing-account provisioning, and draft-invoice retrieval and export — to produce entries in the OSAC audit log (visible through the API, CLI, and UI where audit is surfaced), so that I can satisfy compliance and regulatory audit requirements. Rate and pricing changes made directly in the billing system are audited by that system, consistent with it remaining the pricing source of truth.

### Cloud Infrastructure Admin

- As a Cloud Infrastructure Admin, I want to install the billing provider connection as part of the OSAC installation — including credentials that are not stored in plaintext — so that billing integration is operational from day one without exposing secrets in configuration files.

- As a Cloud Infrastructure Admin, I want to switch the billing provider (for example, from M360 to RH Cost Management) via installation configuration, so that a provider change is a configuration change, not a code change, rebuild, or reinstall of OSAC. Configuring the connection is an infrastructure responsibility; authoring rates, the billing period, and tenant billing terms is done in the billing system by the Cloud Provider Admin. A switch takes effect from the switch point forward at a billing-period boundary — prior usage is not replayed, and historical records remain with the previous provider.

- As a Cloud Infrastructure Admin, I want to see when billing integration is unhealthy (usage is not flowing to the billing system), so that I can fix it before invoices are wrong.

### Tenant Admin

- As a Tenant Admin, I want to view my organization's accumulated costs for the current and past billing periods, broken down by service type (VMaaS, CaaS) and resource, so that I can manage my organization's cloud spending. The available history follows the billing provider's retention of cost and invoice data.

- As a Tenant Admin, I want to view costs aggregated by Project (including nested Projects), so that I can attribute spending to teams and departments within my organization. This relies on usage and charge records preserving stable Project identifiers and parent-child relationships, captured by OSAC-985 metering.

- As a Tenant Admin, I want to view past invoices and itemized charge breakdowns for my organization, so that I can reconcile charges with my internal budgets and respond to billing inquiries from my users.

### Tenant User

- As a Tenant User, I want to view the estimated cost of the resources I have deployed and the Projects I have access to, so that I understand my consumption footprint without seeing tenant-wide financial data. Estimated cost reflects the charges the billing system calculates for the resource's billable components — metered usage together with any non-metered component charges — queried on demand rather than pushed as a streamed feed. Cost views show the most recently processed data with an "as of" timestamp; usage not yet processed by the billing provider is not yet reflected.

- As a Tenant User, I want to view the cost history over time of the resources and Projects I have access to, so that I can spot trends in my own spending.

## Assumptions

- The metering layer (OSAC-985) is operational and collecting usage data for VMaaS and CaaS before billing integration begins.

- The billing provider (M360 or RH Cost Management) is deployed and reachable from the OSAC deployment. OSAC does not manage the billing provider's lifecycle. Behavior when the provider is unreachable is governed by the Billing resilience item in In Scope — provisioning is never blocked, and no usage, charges, or accounts are lost or duplicated on recovery.

- The billing system supports the pricing OSAC relies on (per-component rates, including negative rates for discounts, and whatever per-tenant rate differentiation the Cloud Provider Admin authors). OSAC is agnostic to how the billing system organizes those rates. If a billing provider lacks a capability, that feature is unavailable in that deployment until the provider supports it. Whether a single rate structure can be shared across billing accounts is a provider-specific detail OSAC does not assume.

- Metering-event processing latency — measured from event delivery to the billing provider until the derived charge is queryable — is provider-dependent and typically low (on the order of a minute). OSAC does not guarantee a fixed end-to-end latency in this MVP, and the bound does not hold during provider recovery or backlog drain; cost queries return the most recently processed data with an "as of" timestamp, and usage still being processed is not yet reflected.

- Trial and promotional access is modeled as a per-tenant credit balance held by the billing provider, which the provider draws down against charges as usage is rated at normal (non-zero) rates, rather than as a separate zero-rate plan or trial mode. Credits are granted and applied in the billing provider's interface (see Out of Scope).

- Billing, cost, and invoice data are stored and retained on the external billing system, governed by its retention policy. Metering and usage data retention is governed by OSAC-985. OSAC does not independently store, mirror, or delete billing or cost data.

- When billing integration is enabled on a deployment with existing tenants, billing accounts are created for those tenants. Pre-existing usage data (generated before billing activation) is not retroactively billed.

- Billing integration can be disabled without affecting resource provisioning or lifecycle operations. When disabled, billing and cost data already recorded on the billing system remains subject to that system's retention policy.

- Billing data (prices, costs, invoices, tenant consumption) is financially sensitive. It is protected by OSAC's existing data protection mechanisms (encryption in transit and at rest).

## Dependencies

- **OSAC-985 — Metering and Usage Tracking:** Provides the usage data pipeline that billing consumes, and defines the set of billable dimensions that must carry rates. Metering must be operational for VMaaS and CaaS before billing can calculate charges.

- **MaaS billing (OSAC-3794) — tracked independently:** MaaS billing depends on MaaS metering and does not gate this MVP. If MaaS metering lands in time, its billable dimensions are priced through the same mechanism defined here.

- **Billing provider deployment:** M360 or RH Cost Management must be deployed and configured independently. OSAC integrates via the billing provider's APIs.

- **OSAC Catalog (OSAC-1531, OSAC-2452):** VMaaS and CaaS catalog items must exist as offerings. Pricing is on the billable components of provisioned resources, not on catalog items. Browse-time catalog price display is OSAC-3793.

- **Resource composition metadata:** Billing for non-metered components requires the provisioning layer to record which billable components are attached to a provisioned resource. Where these components originate from catalog items, this ties into the catalog dependency above.

- **OSAC-4220 — Quota Foundation:** Billing cost data may feed into quota enforcement in a future milestone. This PRD does not implement quota logic but does not preclude it.

- **Documentation:** User-facing documentation for billing management (billing-provider installation and switch, tenant-to-billing-account lifecycle, invoice review and export, cost visibility) and API reference for billing endpoints are delivered with the feature. Rate authoring and tenant billing onboarding are documented by the billing system, not OSAC.

---

## Provenance

Authored: draft @ prd 0.8.0 - a605aa5, workspace feat/add-osac-metering-documentation @ 514565f
Final: revise @ prd 0.8.0 - 7efcedb, workspace HEAD @ 155acfa

> Context changed between draft and revise.

<!-- ai-workflow-provenance:{"schema_version":1,"provenance_kind":"session","workflow":"prd","workflow_version":"0.8.0","ai_workflows":"7efcedb","source_repo":"155acfa","source_repo_branch":"HEAD","commits_behind_main":0,"commits_ahead_main":1,"main_ref":"main","phases":["draft","revise","revise","revise"],"authoring_modes":["skill"],"context_changed":true,"origin_untracked":false} -->
