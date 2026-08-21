# Billing Integration MVP

| Field       | Value                |
|-------------|----------------------|
| Author(s)   | Moti Asayag          |
| Jira        | [OSAC-3784](https://redhat.atlassian.net/browse/OSAC-3784) |
| Date        | 2026-08-20           |

## Glossary

Terms are aligned with [FOCUS](https://focus.finops.org/) (FinOps Open Cost and Usage Specification) where applicable. The **Source** column marks each entry as FOCUS-defined (used with FOCUS semantics) or OSAC-specific.

| Term | Source | Definition |
|------|--------|------------|
| Billable component | OSAC | Any component of a provisioned resource that has an associated rate (which may be $0), whether or not its usage is metered. Metered billable components are billable dimensions (see below); non-metered billable components — for example, a paid add-on operator, a software license bundled with a resource, or a setup fee — incur cost without a metered quantity. Every billable component of a provisioned resource must have a rate so that no cost-incurring component is silently unbilled. |
| Billable dimension | OSAC | A metered billable component: a metered quantity that incurs cost and must carry a rate — for example, VMaaS instance-type uptime (an instance type encapsulates CPU, memory, and GPU). Defined by the metering design (OSAC-985). |
| Billing account | FOCUS | A container for resources and/or services that are billed together in an invoice. In OSAC, each tenant is associated with exactly one billing account in the billing provider; a single billing account may back multiple tenants (1:N account-to-tenant). |
| Billing currency | FOCUS | The single base currency in which a billing account's charges are denominated. In OSAC, each billing account uses one immutable base currency; billing across multiple currencies is achieved by provisioning separate billing accounts. |
| Billing period | FOCUS | The time window that an organization receives an invoice for, inclusive of the start date and exclusive of the end date. In OSAC, the billing period is configurable by the Cloud Provider Admin (for example, a calendar month or a custom cycle aligned to fiscal or procurement periods); the active billing provider must support the configured period. |
| Billing provider | FOCUS | The external billing system that OSAC integrates with to manage pricing, cost calculation, and invoicing. Maps to the FOCUS concepts of invoice issuer and data generator. In OSAC: Monetize360 (M360) or Red Hat Cost Management (Koku). |
| Billing provider adapter | OSAC | The integration that connects OSAC usage data to a billing provider. Each OSAC deployment configures one active adapter. |
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

- **Billing provider integration** — a pluggable billing provider adapter with one active provider per deployment. Initial providers: Monetize360 (M360) and Red Hat Cost Management (Koku).
- **Billing system as pricing source of truth** — OSAC fetches prices from the active billing provider; prices are not independently maintained in OSAC. Rate changes take effect for future charges going forward. Every billable component of a provisioned resource must have a corresponding rate in the tenant's effective pricing plan (or the default plan) — both metered components (billable dimensions defined by the metering design, OSAC-985) and non-metered components (for example, a paid add-on operator, a software license, or a setup fee attached to the resource). OSAC surfaces billable components that lack a rate so that no cost-incurring component is silently unbilled. Catalog-to-billing-provider synchronization ensures no provisioned resource is unrateable (enriching catalog items with live prices for display is a separate Feature, OSAC-3793).
- **Billable dimension and component registration** — the billable dimensions (metered, defined by OSAC-985) and non-metered billable components (add-on operators, licenses, fees) that OSAC bills for each service are registered in the active billing system as rateable items with rates, so that incoming metered usage and non-metered charges can be matched to a rate and billed. Introducing a new billable dimension or component (a new service, resource type, or add-on) requires it to be registered with a rate before its data is delivered; OSAC surfaces any billable dimension or component that is not yet rateable so no metered data is dropped for lack of a matching rated item. This closes the loop between metering (quantities) and billing (rating).
- **Charges for non-metered components** — a provisioned resource may include billable components whose cost is not derived from metered usage (for example, a paid add-on operator on a CaaS cluster, a software license bundled with a VM image, or a setup fee). OSAC prices these components, presents their rates as part of the provisioned resource's cost, and delivers their charges to the billing system so they appear on the invoice alongside metered usage. The active billing provider must be able to represent non-usage charges; how such charges are delivered is a design concern.
- **Configurable billing period** — the Cloud Provider Admin configures the billing period for the deployment (for example, a calendar month or a custom cycle); the active billing provider must support the configured period.
- **VMaaS and CaaS billing** — billing models and charge calculation for the two services with existing metering (OSAC-985). Billing for other services (MaaS, BMaaS, Storage, Networking) activates via separate Features as their respective metering becomes available (see Out of Scope).
- **Pricing input validation** — pricing data is validated on input: currency codes are restricted to active ISO-4217 codes, and amounts must be well-formed. Negative rates are permitted, to express discounts and credits.
- **Tenant-to-billing-account lifecycle** — creating a tenant in OSAC provisions a corresponding billing account in the billing provider (idempotently, with retry on provider unavailability and no duplicate accounts). A billing account may back multiple tenants (1:N). Deleting a tenant does **not** immediately purge its billing account: past invoices and consumption remain viewable while the provider settles pending charges; account data for a terminated tenant is permanently deleted after a defined retention period to satisfy compliance. An explicit billing cutover boundary defines when usage begins and ceases to accrue.
- **Billing resilience** — billing system unavailability does not block tenant provisioning or resource lifecycle operations. Account creation and usage delivery are retried idempotently when connectivity is restored, with no double-counted usage or duplicate charges.
- **Invoice idempotency** — draft invoice generation is repeat-safe per tenant and billing period: retries or timeouts return or reuse the existing draft rather than creating duplicate drafts, exports, or conflicting revisions.
- **API, CLI, and UI surfaces** — billing capabilities (cost views, invoice listing, pricing plan management, billing-period and provider configuration) are accessible via the fulfillment-service gRPC/REST API, the `osac` CLI, and the OSAC web console. UI implementation may be phased across milestones.
- **Billing RBAC and visibility boundaries** — billing operations require specific authorization, and cost/invoice data is scoped to the tenant's own billing account. Within a tenant: Tenant Admins see tenant-wide cost history and invoices; Tenant Users see only the cost of resources and projects they have access to, and do not see tenant-wide history or invoices. Project membership bounds visibility so financial data is not exposed across unrelated teams.

## Out of Scope

- **Payment processing and gateway integration** — OSAC generates draft invoices; payment collection and PCI compliance are handled externally.
- **Quota enforcement and budget alerts** — tracked separately as OSAC-998.
- **Workload-level metering** — OSAC meters resources it provisions, not workloads running inside tenant clusters.
- **Billing provider UI** — the billing provider's own administration interface; this PRD covers OSAC-side surfaces only. The Out of Scope items in this section refer to OSAC-side capabilities; functionality native to the billing provider (invoicing, tax, payment, refunds) is delegated to it.
- **Per-user cost attribution and user wallets** — the MVP attributes cost at tenant and project scope only. Per-user consumption views and per-user prepaid wallets/credit balances are a known future need (e.g., MOC 2.0 requests) and are tracked separately, not delivered in this MVP.
- **Prepaid and subscription billing models** — the MVP bills tenants on a pay-as-you-go basis (charges accrue into a draft invoice per billing period). Per-tenant prepaid balances and recurring subscription billing models (surfaced in the osac-ux prototype as a billing-model selector) are deferred. Trial access is modeled separately as a credit offset (see Assumptions), not as a prepaid balance.
- **Reseller and affiliate billing** — affiliate/reseller attribution and reseller-specific pricing (the osac-ux prototype's affiliate identifier) are deferred.
- **MaaS billing** — depends on MaaS metering, which is not yet available; tracked independently (OSAC-3794). It does not gate this MVP.
- **Multi-currency billing** — each billing account uses a single immutable base currency. Billing tenants in different currencies is achieved by provisioning separate billing accounts (the hyperscaler pattern); native multi-currency per account, and reseller/multi-region local-currency billing, are deferred.
- **Multi-provider per deployment** — each OSAC deployment configures one billing provider. Per-tenant provider selection is deferred.
- **Historical data replay across a provider switch** — switching the billing provider takes effect from the switch point forward and occurs at a billing-period boundary; OSAC does not replay prior usage into the new provider, and historical records remain with the previous provider.
- **Bulk billing operations** — batch pricing plan assignment, bulk recalculation, and bulk invoice export are deferred.
- **Ad-hoc credits, refunds, and adjustments** — managed within the billing provider's own interface.
- **Billing data residency** — per-tenant billing data residency by region is enforced by the billing provider, not by OSAC.
- **Catalog item pricing enrichment** — enriching catalog items with live prices from the billing system is a separate Feature (OSAC-3793).
- **Billing for services beyond VMaaS and CaaS** — BMaaS (OSAC-3795), Storage (OSAC-3796), and Networking (OSAC-3797) billing activate via separate Features as metering lands. MaaS (OSAC-3794) is covered by the MaaS-billing item above.

## User Stories

### Cloud Provider Admin

- As a Cloud Provider Admin, I want to configure a billing provider adapter for my OSAC deployment, so that usage data flows automatically to my chosen billing system (M360 or RH Cost Management) without custom integration work.

- As a Cloud Provider Admin, I want to configure the billing period for my deployment (for example, a calendar month or a custom cycle), so that billing aligns with my customers' fiscal and procurement cycles rather than being locked to a fixed calendar month.

- As a Cloud Provider Admin, I want to create pricing plans with rate cards that define rates for billable components (for example, a per-unit price for a resource type) — including discounts expressed as negative rates — so that I can set different rates for different tenants based on their service agreements and hardware classes.

- As a Cloud Provider Admin, I want every billable component of a provisioned resource to have a rate — both the metered dimensions defined by the metering design (OSAC-985), for example VMaaS instance types, which encapsulate CPU, memory, and GPU, and non-metered components such as a paid add-on operator or a software license attached to the resource — so that anything that incurs cost is priced whether it was provisioned through the catalog wizard or directly, and nothing goes unbilled. The catalog surfaces these prices, but pricing applies to the resource's billable components, not to the catalog item alone. If a billable component has no rate, OSAC surfaces the gap.

- As a Cloud Provider Admin, I want each service's billable dimensions (from metering) and non-metered billable components to be registered in the billing system with a rate, so that arriving metered usage and non-metered charges can be rated — and I want to be alerted to any billable dimension or component that has no rate, so I can set one before it goes unbilled.

- As a Cloud Provider Admin, I want to assign pricing plans to tenants, so that each tenant's usage is charged according to their agreed terms. A default plan applies to tenants without a specific assignment. When a plan's rates change, affected tenants' future charges reflect the updated rates.

- As a Cloud Provider Admin, I want to view draft invoices per tenant for a billing period showing charges itemized by service and resource type, so that I can review charges before exporting them to my payment system. Regenerating or retrying an invoice for the same tenant and billing period returns the existing draft rather than creating a duplicate.

- As a Cloud Provider Admin, I want billing operations (pricing plan management, billing-period configuration, invoice review) restricted to users with billing-specific permissions, so that only authorized personnel can modify pricing or access financial data.

- As a Cloud Provider Admin, I want all billing-related administrative actions — pricing plan changes, plan-to-tenant assignments, billing-period configuration, provider adapter changes, and invoice generation — to produce entries in the OSAC audit log (visible through the API, CLI, and UI where audit is surfaced), so that I can satisfy compliance and regulatory audit requirements.

### Cloud Infrastructure Admin

- As a Cloud Infrastructure Admin, I want to deploy and configure the billing provider adapter as part of the OSAC installation — including secure credential storage for the billing provider's API — so that billing integration is operational from day one without exposing credentials in plaintext configuration.

- As a Cloud Infrastructure Admin, I want to deploy and switch the billing provider adapter (e.g., from M360 to RH Cost Management) via configuration, so that provider migrations do not require code changes or redeployment of OSAC core services. Configuring the adapter is an infrastructure responsibility (Cloud Infrastructure Admin); defining rates, the billing period, and tenant onboarding to the billing system is a Cloud Provider Admin responsibility. A switch takes effect from the switch point forward at a billing-period boundary — prior usage is not replayed, and historical records remain with the previous provider.

- As a Cloud Infrastructure Admin, I want to monitor the health of the billing integration through standard OSAC observability, so that I can detect and resolve billing pipeline issues before they affect invoice accuracy.

### Tenant Admin

- As a Tenant Admin, I want to view my organization's accumulated costs for the current and past billing periods, broken down by service type (VMaaS, CaaS) and resource, so that I can manage my organization's cloud spending. The available history follows the billing system's retention of cost and invoice data.

- As a Tenant Admin, I want to view costs aggregated by Project (including nested Projects), so that I can attribute spending to teams and departments within my organization. This relies on usage and charge records preserving stable Project identifiers and parent-child relationships, captured by OSAC-985 metering.

- As a Tenant Admin, I want to view past invoices and itemized charge breakdowns for my organization, so that I can reconcile charges with my internal budgets and respond to billing inquiries from my users.

### Tenant User

- As a Tenant User, I want to view the estimated cost of the resources I have deployed and the Projects I have access to, so that I understand my consumption footprint without seeing tenant-wide financial data. Estimated cost reflects the charges the billing system calculates for the resource's billable components — metered usage shortly after it occurs (a bounded processing latency on the order of a minute) together with any non-metered component charges — queried on demand rather than pushed as a streamed feed.

- As a Tenant User, I want to view the cost history over time of the resources and Projects I have access to, so that I can spot trends in my own spending.

## UI / UX

Billing capabilities are surfaced to users in addition to the API and CLI. A UX prototype for billing already exists in `osac-ux` (provider billing screens, tenant and admin usage and cost views, and predicted billing type definitions), so this feature is not greenfield UI. The UI scope below is defined to align with that prototype; the field-level mapping between the prototype's types and the billing API is a design-phase deliverable (the design document's UX Alignment section, per the workspace convention that treats the prototype's types as primary proto-field input).

Billing views and capabilities by persona are in scope and may be phased across milestones (an API/CLI-first milestone is acceptable):

- **Cloud Provider Admin** — a cost overview across tenants; pricing-plan management (create and edit pricing plans and their rate cards, and designate a default plan); managing the rates for each service's billable dimensions and components and seeing which lack a rate; assigning pricing plans and rates to tenants as part of tenant onboarding and thereafter; a per-tenant billing view showing that tenant's charges and draft invoice for a billing period; usage and cost reports; and billing-period configuration.
- **Tenant Admin** — tenant-wide cost views broken down by service and resource, cost aggregated by Project (including nested Projects), and past invoices with itemized charge breakdowns.
- **Tenant User** — estimated cost of the resources they have deployed and the Projects they can access, and cost history over time, without visibility into tenant-wide financial data.

**Reconciliation with the existing prototype.** The prototype's billable-component and price-plan concepts align with this PRD's billable-component, rate-card, and pricing-plan terminology. Two prototype concepts are intentionally **not** in this MVP and must be reconciled during design: a per-tenant billing-model selector offering prepaid and subscription models (the MVP is pay-as-you-go — see Out of Scope), and an affiliate/reseller identifier (reseller and affiliate billing are deferred — see Out of Scope).

## Assumptions

- The metering layer (OSAC-985) is operational and collecting usage data for VMaaS and CaaS before billing integration begins.

- The billing provider (M360 or RH Cost Management) is deployed and reachable from the OSAC deployment. OSAC does not manage the billing provider's lifecycle.

- The billing system supports the pricing models required by this PRD (per-unit rate cards, including negative rates for discounts). If a billing provider lacks a capability, that feature is unavailable in that deployment until the provider supports it.

- Tenant isolation in the billing system aligns with OSAC's tenant model: each OSAC tenant is associated with exactly one billing account, and a billing account may back multiple tenants (1:N). The mapping mechanism is defined during billing provider integration.

- The billing system processes metering events with a bounded, low latency (on the order of a minute). Tenants querying their estimated costs see charges derived from recently processed usage data.

- OSAC deployments are expected to support up to hundreds of tenants with thousands of active resources generating usage data per billing period.

- Each billing account operates with a single, immutable base billing currency. Billing tenants in different currencies is achieved by provisioning separate billing accounts; native multi-currency per account is out of scope for the MVP.

- Trial and promotional access is modeled as a per-tenant credit balance that offsets charges as usage is rated at normal (non-zero) rates, rather than a separate zero-rate plan or trial mode.

- Billing, cost, and invoice data are stored and retained on the external billing system (M360 or RH Cost Management), governed by its retention policy; OSAC does not independently store or retain billing or cost data. Metering and usage data retention is governed by OSAC-985. OSAC does not mirror the billing system's retention window.

- When billing integration is enabled on a deployment with existing tenants, billing accounts are created for those tenants. Pre-existing usage data (generated before billing activation) is not retroactively billed.

- Billing integration can be disabled without affecting resource provisioning or lifecycle operations. When disabled, billing and cost data already recorded on the billing system remains subject to that system's retention policy; OSAC does not delete it.

- Billing data (prices, costs, invoices, tenant consumption) is financially sensitive. It is protected by OSAC's existing data protection mechanisms (encryption in transit and at rest).

## Dependencies

- **OSAC-985 — Metering and Usage Tracking:** Provides the usage data pipeline that billing consumes, and defines the set of billable dimensions that must carry rates. Metering must be operational for VMaaS and CaaS before billing can calculate charges. Usage and metering data retention is governed by OSAC-985; this PRD does not define a separate usage-retention policy.

- **MaaS billing (OSAC-3794) — tracked independently:** Model-as-a-Service metering completes in a later OSAC release, so billing for MaaS consumption depends on that metering being available. MaaS billing is tracked as a separate deliverable and does not gate this MVP; if MaaS metering lands in time, its billable dimensions are priced through the same mechanism defined here.

- **Billing provider deployment:** M360 or RH Cost Management must be deployed and configured independently. OSAC integrates via the billing provider's APIs.

- **OSAC Catalog (OSAC-1531, OSAC-2452):** Catalog items must exist for the services being billed. The billing integration does not create catalog items but relies on their existence for pricing plan configuration.

- **Resource composition metadata:** Billing for non-metered components requires the provisioning layer to record which billable components (for example, add-on operators, licenses, or fees) are attached to a provisioned resource, so their charges can be delivered to the billing system. Where these components originate from catalog items, this ties into the catalog dependency above.

- **OSAC-998 — Quota Management:** Billing cost data may feed into quota enforcement in a future milestone. This PRD does not implement quota logic but does not preclude it.

- **Documentation:** User-facing documentation for billing management (pricing plan setup, invoice workflows, cost visibility) and API reference for billing endpoints are delivered with the feature.

## Appendix: Scope Against the Revenue Lifecycle

A complete cloud revenue (quote-to-cash) lifecycle spans many stages. This appendix situates the MVP against that industry-standard lifecycle to make the scope boundaries explicit and to distinguish what OSAC owns from what it delegates to the billing provider. It is descriptive context, not a commitment to any specific vendor's product taxonomy or roadmap.

| Revenue lifecycle stage | Description | This MVP |
|-------------------------|-------------|----------|
| Offer & catalog definition | Defining the services that can be ordered | Consumed as a dependency (catalog exists); price enrichment is OSAC-3793 |
| Pricing & rate definition | Rate cards, pricing plans, plan-to-tenant assignment for metered and non-metered billable components | **In scope** — authored by the Cloud Provider Admin, with the billing system as source of truth |
| Metering & usage collection | Turning resource consumption into measurable quantities | Consumed as a dependency (OSAC-985); defines the billable dimensions that must carry rates |
| Rating & charging | Applying rates to metered usage and non-metered components to produce charges | **In scope** — performed by the billing provider; OSAC ensures every billable component is rateable |
| Billing & invoicing | Aggregating charges into draft invoices per billing period | **In scope** — draft invoice generation (idempotent) and review; final issuance is the provider's |
| Credits, discounts & adjustments | Trial credits, negative-rate discounts, ad-hoc adjustments | **Partial** — trial credits and negative-rate discounts in scope; ad-hoc refunds/adjustments delegated to the provider |
| Cost visibility & reporting | Presenting cost and consumption to operators and tenants | **In scope** — tenant/project-scoped cost views via API, CLI, UI |
| Taxation | Computing and applying taxes | Delegated to the billing provider |
| Payment & collections | Charging customers and collecting funds | Delegated to the billing provider / external payment systems |
| Dunning & disputes | Overdue handling, chargebacks, dispute resolution | Delegated to the billing provider |
| Revenue recognition & financial reporting | GAAP/IFRS revenue recognition, ledger integration | Delegated to the billing provider / downstream finance systems |
| Quota & budget enforcement | Enforcing spend limits and budget alerts | Out of scope — tracked as OSAC-998 |
| Per-user attribution & wallets | Per-user cost breakdown and prepaid balances | Out of scope — future need (e.g., MOC 2.0), tracked separately |

The MVP deliberately owns the stages that connect OSAC's metering to a billing provider — pricing, ensuring rateability, draft invoicing, and cost visibility — and delegates the downstream financial stages (taxation, payment, revenue recognition) to the billing provider that OSAC integrates with.

---

## Provenance

Authored: draft @ prd 0.8.0 - a605aa5, workspace feat/add-osac-metering-documentation @ 514565f
Final: revise @ prd 0.8.0 - 7efcedb, workspace HEAD @ 155acfa

> Context changed between draft and revise.

<!-- ai-workflow-provenance:{"schema_version":1,"provenance_kind":"session","workflow":"prd","workflow_version":"0.8.0","ai_workflows":"7efcedb","source_repo":"155acfa","source_repo_branch":"HEAD","commits_behind_main":0,"commits_ahead_main":1,"main_ref":"main","phases":["draft","revise","revise"],"authoring_modes":["skill"],"context_changed":true,"origin_untracked":false} -->
