# Billing - Catalog Pricing Integration

| Field       | Value                |
|-------------|----------------------|
| Author(s)   | Moti Asayag          |
| Jira        | [OSAC-3793](https://redhat.atlassian.net/browse/OSAC-3793) |
| Date        | 2026-08-09           |

## Problem Statement

Catalog items (ComputeInstanceCatalogItem, ClusterCatalogItem, BareMetalInstanceCatalogItem) display no pricing information. Tenants browsing the catalog cannot see what a resource will cost before provisioning it. Without pricing in the catalog, cost-informed decisions require tenants to provision first and check their billing dashboard afterward — or to consult a pricing document outside OSAC. This defeats the purpose of a self-service catalog and increases the risk of unexpected charges.

## In Scope

- **Assigned catalog items display per-unit price** from the tenant's active pricing plan. Pricing is shown only for catalog items assigned/available to the requesting user's context (tenant/project). Prices reflect the tenant's plan-specific rates, not a single base rate.
- **Graceful degradation** — when the billing system is unavailable, catalog items render without pricing rather than failing. Tenants can still browse and provision; they just don't see prices.
- **API, CLI, and UI surfaces** — pricing is visible on catalog items across all three surfaces. The UI shows formatted prices (e.g., "$0.26/hr" for a 4-core, 8 GiB VM).
- **All catalog item types** — ComputeInstanceCatalogItem, ClusterCatalogItem, and BareMetalInstanceCatalogItem.
- **Visibility alignment with catalog assignment** — pricing follows the same hierarchical visibility model as catalog items (global → tenant → project).

## Out of Scope

- **Caching pricing data in OSAC's database** — prices are fetched from the billing system; OSAC does not maintain a local pricing cache.
- **Price comparison across templates** — tenants cannot compare prices side-by-side across multiple catalog items in a single view.
- **Field governance for pricing fields** — pricing information is always visible (not locked/hidden) when available. Advanced field governance behaviors for pricing follow in a separate feature.

## User Stories

### Cloud Provider Admin

- As a Cloud Provider Admin, I want catalog items to display the per-unit price from the tenant's assigned pricing plan, so that tenants see accurate, plan-specific pricing when browsing the catalog.

### Tenant Admin / Tenant User

- As a Tenant Admin or Tenant User, I want to see the price of a catalog item available to my context (e.g., "$0.26/hr" for a VM template) before provisioning a resource, so that I can make cost-informed decisions about approved offerings.

## Assumptions

- OSAC-3784 (Billing Integration MVP) is operational — the billing provider adapter is deployed, pricing plans with rate cards are configured, and the billing system is the pricing source of truth.

- OSAC-3538 (Catalog Items v2) is operational — catalog items use the new structured field model, and the legacy field_definitions approach has been replaced. This PRD assumes the v2 field governance model throughout.

- OSAC-2474 (Catalog Item Assignment) is operational — the hierarchical assignment model (global → tenant → project) determines catalog item visibility, and pricing respects this same visibility model.

- Catalog items exist for the services being priced. The billing integration does not create catalog items but relies on their existence and assignment.

- The billing system's API supports querying prices by resource type and pricing plan at catalog display time. A short propagation delay after pricing changes in the billing system is acceptable.

## Dependencies

- **OSAC-2474 — Catalog Item Assignment to Tenants and Projects:** Provides the hierarchical catalog item assignment model. Must be operational before pricing can respect catalog item visibility rules.

- **OSAC-3538 — Catalog Items v2 Field Governance Redesign:** Provides the new structured field model for catalog items. Must be operational before pricing can be integrated with the catalog item schema.

- **OSAC-3784 — Billing Integration MVP:** Provides the billing provider adapter and pricing plan infrastructure. Must be operational before catalog pricing can query the billing system for prices.

- **OSAC Catalog (OSAC-1531, OSAC-2452):** Catalog items must exist for the services being priced.

## Open Questions

Questions for reviewers to resolve during PR review. Once answered, the resolution will be incorporated into the relevant section above and the entry removed.

### 1. Implementation sequencing with OSAC-2474

- **Owner:** Product team, Engineering team
- **Impact:** Dependencies, delivery timeline
- **Question:** Should catalog pricing respect assignment visibility from day one, or should it initially work independently and be aligned later? This affects whether OSAC-2474 is a hard blocker or parallel development is possible.

---

## Provenance

Authored: draft @ prd 0.8.0 - a605aa5, workspace feat/add-osac-metering-documentation @ 514565f (3 behind origin/main)
Final: revise @ prd 0.8.0 - a605aa5, workspace HEAD @ a2c2e18 (dirty)

> Context changed between draft and revise.

<!-- ai-workflow-provenance:{"schema_version":1,"provenance_kind":"session","workflow":"prd","workflow_version":"0.8.0","ai_workflows":"a605aa5","source_repo":"a2c2e18 (dirty)","source_repo_branch":"HEAD","commits_behind_main":0,"commits_ahead_main":1,"main_ref":"main","phases":["draft","revise","revise"],"authoring_modes":["skill"],"context_changed":true,"origin_untracked":false} -->
