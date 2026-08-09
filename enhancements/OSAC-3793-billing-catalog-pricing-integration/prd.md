# Billing - Catalog Pricing Integration

| Field       | Value                |
|-------------|----------------------|
| Author(s)   | Moti Asayag          |
| Jira        | [OSAC-3793](https://redhat.atlassian.net/browse/OSAC-3793) |
| Date        | 2026-08-09           |

## Problem Statement

Catalog items (ComputeInstanceCatalogItem, ClusterCatalogItem) display no pricing information. Tenants browsing the catalog cannot see what a resource will cost before provisioning it. Without pricing in the catalog, cost-informed decisions require tenants to provision first and check their billing dashboard afterward — or to consult a pricing document outside OSAC. This defeats the purpose of a self-service catalog and increases the risk of unexpected charges.

## In Scope

- **Catalog items display per-unit price** from the tenant's active pricing plan. Prices reflect the tenant's plan-specific rates, not a single base rate.
- **Graceful degradation** — when the billing system is unavailable, catalog items render without pricing rather than failing. Tenants can still browse and provision; they just don't see prices.
- **API, CLI, and UI surfaces** — pricing is visible on catalog items across all three surfaces. The UI shows formatted prices (e.g., "$0.26/hr" for a 4-core, 8 GiB VM).
- **VMaaS and CaaS catalog items** — ComputeInstanceCatalogItem and ClusterCatalogItem. Pricing for BareMetalInstanceCatalogItem follows when BMaaS billing (OSAC-3795) lands.

## Out of Scope

- **Caching pricing data in OSAC's database** — prices are fetched from the billing system; OSAC does not maintain a local pricing cache.
- **Price comparison across templates** — tenants cannot compare prices side-by-side across multiple catalog items in a single view.
- **Pricing for BareMetalInstanceCatalogItem** — follows when BMaaS billing (OSAC-3795) lands and the billing system has BMaaS pricing plans configured.

## User Stories

### Cloud Provider Admin

- As a Cloud Provider Admin, I want catalog items to display the per-unit price from the tenant's assigned pricing plan, so that tenants see accurate, plan-specific pricing when browsing the catalog.

### Tenant Admin / Tenant User

- As a Tenant Admin or Tenant User, I want to see the price of a catalog item (e.g., "$0.26/hr" for a VM template) before provisioning a resource, so that I can make cost-informed decisions.

## Assumptions

- OSAC-3784 (Billing Integration MVP) is operational — the billing provider adapter is deployed, pricing plans with rate cards are configured, and the billing system is the pricing source of truth.

- Catalog items exist for the services being priced. The billing integration does not create catalog items but relies on their existence (OSAC-1531, OSAC-2452).

- The billing system's API supports querying prices by resource type and pricing plan at catalog display time. A short propagation delay after pricing changes in the billing system is acceptable.

## Dependencies

- **OSAC-3784 — Billing Integration MVP:** Provides the billing provider adapter and pricing plan infrastructure. Must be operational before catalog pricing can query the billing system for prices.

- **OSAC Catalog (OSAC-1531, OSAC-2452):** Catalog items must exist for the services being priced.

---

## Provenance

Authored: draft @ prd 0.8.0 - a605aa5, workspace feat/add-osac-metering-documentation @ 514565f (3 behind origin/main)

<!-- ai-workflow-provenance:{"schema_version":1,"provenance_kind":"session","workflow":"prd","workflow_version":"0.8.0","ai_workflows":"a605aa5","source_repo":"514565f","source_repo_branch":"feat/add-osac-metering-documentation","commits_behind_main":3,"commits_ahead_main":0,"main_ref":"main","phases":["draft"],"authoring_modes":["skill"],"context_changed":false,"origin_untracked":false} -->
