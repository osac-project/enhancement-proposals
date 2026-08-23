# Billing - Catalog Pricing Integration

| Field       | Value                |
|-------------|----------------------|
| Author(s)   | Moti Asayag          |
| Jira        | [OSAC-3793](https://redhat.atlassian.net/browse/OSAC-3793) |
| Date        | 2026-08-23           |

## Problem Statement

VMaaS and CaaS catalog items (ComputeInstanceCatalogItem, ClusterCatalogItem) display no pricing information. A catalog item maps to a service whose provisioned resource is composed of billable components — the metered resource type (for example, a VMaaS instance type) plus any non-metered components such as a paid add-on operator, a bundled software license, or a setup fee. Tenants browsing the catalog cannot see what any of these will cost before provisioning. Without pricing at browse time, cost-informed decisions require tenants to provision first and check their billing dashboard afterward — or to consult a pricing document outside OSAC. This defeats the purpose of a self-service catalog and increases the risk of unexpected charges.

## In Scope

- **Display-time price enrichment of VMaaS and CaaS catalog items** — when a ComputeInstanceCatalogItem or ClusterCatalogItem is displayed, it is enriched with the price of the billable components of the resource it would provision, resolved against the requesting tenant's effective pricing plan (or the default plan when the tenant has no specific assignment). Prices always reflect the billing system's current rates, subject to the same bounded processing latency as OSAC-3784.
- **Metered and non-metered billable components are both priced** — the display shows the metered per-unit rate for the item's resource type (for example, "$0.26/hr" for a Small instance type) and itemizes any non-metered billable component charges attached to the resource (for example, a paid add-on operator, a bundled license, or a one-time setup fee), so the tenant sees the full cost picture rather than the usage rate alone. Amounts are shown in the billing account's base currency; the dollar figures here are illustrative.
- **Graceful degradation on transient unavailability** — when the billing system is unreachable, catalog items render without pricing rather than failing. Tenants can still browse and provision; they just don't see prices. This covers transient outages and is not a substitute for rate coverage: a billable component that has no rate is a coverage gap OSAC-3784 requires be surfaced to the Cloud Provider Admin, not a silent steady state.
- **API, CLI, and UI surfaces** — enriched pricing is available on catalog items across all three surfaces. The UI shows formatted prices, including the per-unit rate and any itemized non-metered charges.
- **Visibility alignment with catalog assignment** — pricing follows the same hierarchical visibility model as catalog items (global → tenant → project) and is shown only for items the requesting user can browse. List prices are tenant-scoped: the same for every project and user in the tenant. A list price is not incurred-cost visibility; OSAC-3784 scopes actual charges by project membership.
- **Cloud Provider Admin preview is tenant-contextual** — when a Cloud Provider Admin previews catalog prices, the amounts are the list prices that tenant would see (that tenant's effective plan). This verifies tenant-facing display; it is not a second, provider-specific price list.

## Out of Scope

- **Independently maintained catalog prices** — catalog items do not carry a price that an admin edits in OSAC independently of the billing system. The amounts shown always come from billing rates.
- **Price comparison across templates** — tenants cannot compare prices side-by-side across multiple catalog items in a single view.
- **Total-cost projection** — the display shows per-unit rates and itemized non-metered charges for a catalog item; it does not project total spend for a configured or running resource over time. Estimated cost of deployed resources is OSAC-3784's Tenant User cost view.
- **Multi-perspective / context-driven pricing** — the catalog does not expose the provider's cost basis or margin, nor a separate per-end-user price. Cloud Provider Admin preview uses the selected tenant's plan (see In Scope), not a second price list. Per-user cost attribution remains Out of Scope in OSAC-3784.
- **Field governance for pricing fields** — pricing information is always visible (not locked/hidden) when available. Advanced field governance behaviors for pricing follow in a separate feature.
- **BMaaS catalog pricing** — price enrichment of BareMetalInstanceCatalogItem is [OSAC-3795](https://redhat.atlassian.net/browse/OSAC-3795).
- **MaaS catalog pricing** — price enrichment of MaasCatalogItem (including per-token prices) is [OSAC-3794](https://redhat.atlassian.net/browse/OSAC-3794).
- **Non-catalog billable resources** — this feature does not show list prices for resources that are not catalog items (for example standalone instance types, storage, or ExternalIPs). Incurred-cost views and rate-card management for those remain OSAC-3784.

## User Stories

### Cloud Provider Admin

- As a Cloud Provider Admin, I want to preview the list price a given tenant would see for an approved VMaaS or CaaS catalog item, so that I can confirm plan-specific rates before tenants provision.

### Tenant Admin / Tenant User

- As a Tenant Admin or Tenant User, I want to see the price of a VMaaS or CaaS catalog item available to my context before provisioning — the per-unit rate (e.g., "$0.26/hr" for a Small instance type) together with any non-metered charges such as an add-on or setup fee — so that I can make cost-informed decisions about approved offerings.

## Assumptions

- The billing system can return current rates for a catalog offering's billable components at browse time. A short delay after a pricing change is acceptable (bounded processing latency, consistent with OSAC-3784).
- VMaaS and CaaS catalog offerings have rates in the tenant's effective (or default) plan. Missing rates are a coverage gap OSAC-3784 surfaces to the Cloud Provider Admin; this feature only omits the affected component's price on the catalog display.

## Dependencies

- **OSAC-2474 — Catalog Item Assignment to Tenants and Projects:** Provides the hierarchical catalog item assignment model. Must be operational before pricing can follow catalog item visibility.

- **OSAC-3538 — Catalog Items v2 Field Governance Redesign:** Provides the v2 field model for catalog items. Must be operational before this feature can show billing rates on catalog items without an independently maintained catalog price.

- **OSAC-3784 — Billing Integration MVP:** Provides pricing plans, rate cards keyed to billable components, and the billing system as pricing source of truth. OSAC-3784 delegates catalog price enrichment for display to this feature. Must be operational before catalog items can show prices. Shared billing terms follow OSAC-3784's glossary (billable component, billable dimension, rate card, pricing plan, resource type, service).

- **OSAC Catalog (OSAC-1531, OSAC-2452):** VMaaS and CaaS catalog items (ComputeInstanceCatalogItem, ClusterCatalogItem) must exist for the services being priced.

---

## Provenance

Authored: draft @ prd 0.8.0 - a605aa5, workspace feat/add-osac-metering-documentation @ 514565f (3 behind origin/main)
Final: revise @ prd 0.8.0 - 7efcedb, workspace HEAD @ 155acfa

> Context changed between draft and revise.

<!-- ai-workflow-provenance:{"schema_version":1,"provenance_kind":"session","workflow":"prd","workflow_version":"0.8.0","ai_workflows":"7efcedb","source_repo":"155acfa","source_repo_branch":"HEAD","commits_behind_main":0,"commits_ahead_main":1,"main_ref":"main","phases":["draft","revise","revise","revise","respond","revise"],"authoring_modes":["skill"],"context_changed":true,"origin_untracked":false} -->
