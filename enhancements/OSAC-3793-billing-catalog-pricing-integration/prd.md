# Billing - Catalog Pricing Integration

| Field       | Value                |
|-------------|----------------------|
| Author(s)   | Moti Asayag          |
| Jira        | [OSAC-3793](https://redhat.atlassian.net/browse/OSAC-3793) |
| Date        | 2026-08-20           |

## Problem Statement

Catalog items (ComputeInstanceCatalogItem, ClusterCatalogItem, BareMetalInstanceCatalogItem) display no pricing information. A catalog item maps to a service whose provisioned resource is composed of billable components — the metered resource type (for example, a VMaaS instance type) plus any non-metered components such as a paid add-on operator, a bundled software license, or a setup fee. Tenants browsing the catalog cannot see what any of these will cost before provisioning. Without pricing at browse time, cost-informed decisions require tenants to provision first and check their billing dashboard afterward — or to consult a pricing document outside OSAC. This defeats the purpose of a self-service catalog and increases the risk of unexpected charges.

## In Scope

- **Display-time price enrichment of catalog items** — when a catalog item is displayed, OSAC enriches it with the price of the billable components of the resource it would provision, resolved against the requesting tenant's effective pricing plan (or the default plan when the tenant has no specific assignment). Pricing is presented only for catalog items assigned/available to the requesting user's context (tenant/project) and reflects that tenant's plan-specific rate cards, not a single base rate. Prices are read live from the billing system at display time; they are not stored on the catalog item.
- **Metered and non-metered billable components are both priced** — the display shows the metered per-unit rate for the item's resource type (for example, "$0.26/hr" for a Small instance type) and itemizes any non-metered billable component charges attached to the resource (for example, a paid add-on operator, a bundled license, or a one-time setup fee), so the tenant sees the full cost picture rather than the usage rate alone. Amounts are shown in the billing account's base currency; the dollar figures here are illustrative.
- **Graceful degradation on transient unavailability** — when the billing system is unreachable, catalog items render without pricing rather than failing. Tenants can still browse and provision; they just don't see prices. This covers transient outages and is not a substitute for rate coverage: a billable component that has no rate is a coverage gap OSAC-3784 requires be surfaced to the Cloud Provider Admin, not a silent steady state. This feature degrades gracefully as a fallback but does not treat a missing rate as normal.
- **API, CLI, and UI surfaces** — enriched pricing is available on catalog items across all three surfaces. The UI shows formatted prices, including the per-unit rate and any itemized non-metered charges.
- **All catalog item types** — ComputeInstanceCatalogItem, ClusterCatalogItem, and BareMetalInstanceCatalogItem.
- **Visibility alignment with catalog assignment** — pricing follows the same hierarchical visibility model as catalog items (global → tenant → project). A catalog list price (a plan rate) is distinct from incurred-cost visibility: showing a user the rate for an offering they can browse is not the same as exposing another project's actual charges, which OSAC-3784 scopes by project membership.

## Out of Scope

- **Caching pricing data in OSAC's database** — prices are fetched live from the billing system; OSAC does not maintain a local pricing cache, and catalog items carry no cost metadata.
- **Price comparison across templates** — tenants cannot compare prices side-by-side across multiple catalog items in a single view.
- **Total-cost projection** — the display shows per-unit rates and itemized non-metered charges for a catalog item; it does not project total spend for a configured or running resource over time. Estimated cost of deployed resources is OSAC-3784's Tenant User cost view.
- **Multi-perspective / context-driven pricing** — the catalog shows a single price per context: the requesting tenant's plan-specific rate. It does not expose the provider's own cost basis or margin, nor a separate per-end-user price. Different tenants may see different prices because they hold different pricing plans, but within a context there is one price. Per-user cost attribution is Out of Scope in OSAC-3784.
- **Field governance for pricing fields** — pricing information is always visible (not locked/hidden) when available. Advanced field governance behaviors for pricing follow in a separate feature.

## User Stories

### Cloud Provider Admin

- As a Cloud Provider Admin, I want catalog items to display the price of their billable components — the metered per-unit rate for the resource type and any non-metered component charges — drawn from the tenant's effective pricing plan, so that tenants see accurate, plan-specific pricing for approved offerings when browsing the catalog.

### Tenant Admin / Tenant User

- As a Tenant Admin or Tenant User, I want to see the price of a catalog item available to my context before provisioning — the per-unit rate (e.g., "$0.26/hr" for a Small instance type) together with any non-metered charges such as an add-on or setup fee — so that I can make cost-informed decisions about approved offerings.

## Assumptions

- OSAC-3784 (Billing Integration MVP) is operational — the billing provider adapter is deployed, pricing plans with rate cards keyed to billable components are configured (with a default plan for unassigned tenants), and the billing system is the pricing source of truth. OSAC-3784 explicitly delegates catalog price enrichment for display to this feature. This PRD uses OSAC-3784's glossary for shared billing terms (billable component, billable dimension, rate card, pricing plan, resource type, service).

- OSAC-3538 (Catalog Items v2) is operational — catalog items use the new structured field model, and the legacy field_definitions approach has been replaced. This PRD assumes the v2 field governance model throughout. Consistent with that day-1 governance model, the catalog carries no cost metadata; price is resolved from billing at display time.

- OSAC-2474 (Catalog Item Assignment) is operational — the hierarchical assignment model (global → tenant → project) determines catalog item visibility, and pricing respects this same visibility model.

- Catalog list prices are tenant-scoped: rate cards are resolved from the tenant's effective pricing plan and are the same for all projects and users within the tenant. This concerns list prices shown at browse time, not incurred-cost visibility, which OSAC-3784 scopes by project membership.

- The billing system has configured rates for the billable components of resources available through catalog items. Per OSAC-3784's no-gaps contract, missing rates are surfaced to the Cloud Provider Admin; where a rate is nonetheless unavailable at display time, the affected component renders without a price (graceful degradation).

- Catalog items exist for the services being priced. This feature does not create catalog items but relies on their existence and assignment.

- The billing system's API supports querying prices for a resource type's billable components by pricing plan at catalog display time. A short propagation delay after pricing changes in the billing system is acceptable (a bounded processing latency, consistent with OSAC-3784).

## Dependencies

- **OSAC-2474 — Catalog Item Assignment to Tenants and Projects:** Provides the hierarchical catalog item assignment model. Must be operational before pricing can respect catalog item visibility rules.

- **OSAC-3538 — Catalog Items v2 Field Governance Redesign:** Provides the new structured field model for catalog items and establishes that the catalog carries no cost metadata (price is resolved from billing at display time). Must be operational before pricing can be integrated with the catalog item schema.

- **OSAC-3784 — Billing Integration MVP:** Provides the billing provider adapter, pricing plans, and rate cards keyed to billable components, and is the pricing source of truth. OSAC-3784 delegates catalog price enrichment for display to this feature (reciprocal scope handshake). Must be operational before catalog pricing can query the billing system for prices.

- **OSAC Catalog (OSAC-1531, OSAC-2452):** Catalog items must exist for the services being priced.

---

## Provenance

Authored: draft @ prd 0.8.0 - a605aa5, workspace feat/add-osac-metering-documentation @ 514565f (3 behind origin/main)
Final: respond @ prd 0.8.0 - 7efcedb, workspace HEAD @ 155acfa

> Context changed between draft and respond.

<!-- ai-workflow-provenance:{"schema_version":1,"provenance_kind":"session","workflow":"prd","workflow_version":"0.8.0","ai_workflows":"7efcedb","source_repo":"155acfa","source_repo_branch":"HEAD","commits_behind_main":0,"commits_ahead_main":1,"main_ref":"main","phases":["draft","revise","revise","revise","respond"],"authoring_modes":["skill"],"context_changed":true,"origin_untracked":false} -->
