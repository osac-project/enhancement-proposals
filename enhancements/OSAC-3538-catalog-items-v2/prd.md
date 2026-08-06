# Catalog Items v2 — Field Governance Redesign

| Field       | Value   |
|-------------|---------|
| Author(s)   | Avishay Traeger |
| Jira        | https://redhat.atlassian.net/browse/OSAC-3538 |
| Date        | 2026-08-06 |

## Problem Statement

OSAC catalog items let Cloud Provider Admins create curated offerings by locking some resource fields and exposing others as editable. The current field governance model uses generic field definitions with freeform values, which limits the quality of the admin and tenant experience. Admins cannot express richer field semantics — for example, offering instance type as a curated list of options instead of a freeform string, presenting image as a dropdown selector, or making image mandatory on a catalog item (a catalog item with no image is an unusual offering). The generic model also prevents database-level referential integrity between catalog items and the resources they reference: an image or instance type referenced by a catalog item can be deleted without warning, silently breaking a published offering.

## In Scope

- Catalog items become an overlay on existing resource creation — fields not mentioned in the catalog item behave as if no catalog item exists. [User]
- Spec fields on each catalog item type are strongly-typed proto fields with a per-field behavior (locked or editable with a default). [User]
- Per-field type customization: fields can use richer types than the underlying resource spec (e.g., instance type as an enum with curated options, image as a mandatory field with a reference selector). [User]
- Template parameters are governed separately via a typed map validated against the referenced template's parameter definitions. [User]
- Database-level referential integrity prevents deletion of resources (images, instance types) referenced by catalog items. [User]
- Applies to all three catalog item types: ComputeInstanceCatalogItem, ClusterCatalogItem, and BareMetalInstanceCatalogItem. [User]

## Out of Scope

- Hidden field behavior (admin sets value, tenant cannot see the field) — separate feature; the behavior enum must be extensible to support it.
- Lifecycle management and versioning (draft/active/deprecated/retired states, version pinning) — separate feature; the design must be extensible to support this.
- Multi-resource composition (catalog items that bundle multiple resources with dependency ordering) — will likely use a different mechanism, not catalog items.
- Post-provisioning governance (restricting what a tenant can modify on a resource after provisioning) — separate feature.
- Cost metadata, metering/usage tracking, discoverability metadata (categories, tags) — separate features.
- Budget enforcement, approval workflows — separate features.
- Catalog item override mechanism for tenant admins (OSAC-2539) — separate feature, but this redesign should be override-friendly.

## User Stories

### Cloud Provider Admin

- As a Cloud Provider Admin, I want to create a catalog item by selecting which resource fields are locked vs. editable using a structured form that shows the actual resource fields — not freeform path inputs — so that I cannot accidentally reference invalid fields.

- As a Cloud Provider Admin, I want locked fields to have pre-defined values that are enforced when a tenant provisions from the catalog item, so that I can enforce guardrails (e.g., lock image to a specific version, restrict instance type to approved sizes).

- As a Cloud Provider Admin, I want editable fields to support per-field type customization (e.g., offering a curated list of instance types rather than accepting any string) so that tenants have guardrails without losing flexibility. [User]

- As a Cloud Provider Admin, I want the system to prevent deletion of resources (images, instance types) that are referenced by a catalog item, so that published offerings do not silently break. [User]

- As a Cloud Provider Admin, I want to govern template parameters on a catalog item with the same locked/editable behavior as spec fields, so that I can control which template parameters a tenant can override. [User]

- As a Cloud Provider Admin, I want fields not mentioned in the catalog item to behave normally during provisioning (as if no catalog item exists), so that the catalog item is an overlay rather than a complete contract. [User]

### Tenant Admin

- As a Tenant Admin, I want to create organization-scoped catalog items using the same field governance model as global items, so that I can tailor offerings for my organization.

### Tenant User

- As a Tenant User, I want to see the full resource configuration when provisioning from a catalog item — locked values displayed as read-only, editable values pre-filled with defaults I can change, and ungoverned fields available as normal — so that I understand what I am getting.

## Assumptions

- The existing three per-resource-type catalog item types (ClusterCatalogItem, ComputeInstanceCatalogItem, BareMetalInstanceCatalogItem) are retained. Unifying them into a single CatalogItem type is not in scope for this redesign.
- Template parameters remain simple scalar types (string, bool, int32, int64, float, double, etc.) and do not require governance of nested structures.

## Dependencies

- **UI team (osac-ux):** The UI creation flow and provisioning wizard both require updates to match the new proto structure. The UI lead has accepted the approach and contributed to the proto design.

---

## Provenance

Authored: draft @ prd 0.7.1 - b8b3f86, workspace feat/osac-taxonomy-presentation @ d22bfa1 (4 behind origin/main)

<!-- ai-workflow-provenance:{"schema_version":1,"provenance_kind":"session","workflow":"prd","workflow_version":"0.7.1","ai_workflows":"b8b3f86","source_repo":"d22bfa1","source_repo_branch":"feat/osac-taxonomy-presentation","commits_behind_main":4,"commits_ahead_main":0,"main_ref":"main","phases":["draft"],"authoring_modes":["skill"],"context_changed":false,"origin_untracked":false} -->
