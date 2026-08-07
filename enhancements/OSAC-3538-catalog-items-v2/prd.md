# Catalog Items v2 — Field Governance Redesign

| Field       | Value   |
|-------------|---------|
| Author(s)   | Avishay Traeger |
| Jira        | https://redhat.atlassian.net/browse/OSAC-3538 |
| Date        | 2026-08-06 |

## Problem Statement

OSAC catalog items let Cloud Provider Admins create curated offerings by locking some resource fields and exposing others as editable. The current field governance model uses generic field definitions with freeform values, which limits the quality of the admin and tenant experience. Admins cannot express richer field semantics — for example, offering instance type as a curated list of options instead of a freeform string, presenting image as a dropdown selector, or making image mandatory on a catalog item (a catalog item with no image is an unusual offering). The generic model also prevents the system from enforcing referential integrity between catalog items and the resources they reference: an image or instance type referenced by a catalog item can be deleted without warning, silently breaking a published offering.

## In Scope

- Catalog items become an overlay on existing resource creation — fields not mentioned in the catalog item behave as if no catalog item exists.
- Spec fields on each catalog item type are structured, typed fields with a per-field behavior (locked or editable with a default).
- Image is mandatory and always locked on a catalog item — tenants cannot change the image during provisioning. The catalog item owner can update the image (e.g., to bump versions for CVE fixes).
- Per-field type customization: fields can use richer types than the underlying resource spec (e.g., instance type as an enum with curated options, image as a mandatory reference selector).
- Template parameters are governed with the same locked/editable behavior as spec fields, validated against the referenced template's parameter definitions.
- The system prevents deletion of resources (images, instance types) referenced by catalog items. Deletion blocking is the immediate behavior; a deprecation/obsolescence model may replace or complement this when the lifecycle feature (see Out of Scope) is implemented.
- Cloud Provider Admins can assign catalog items to specific tenants and control visibility via publish/unpublish.
- Applies to all three catalog item types: ComputeInstanceCatalogItem, ClusterCatalogItem, and BareMetalInstanceCatalogItem.

## Out of Scope

- Hidden field behavior (admin sets value, tenant cannot see the field) — separate feature; the behavior model must be extensible to support it.
- Lifecycle management and versioning (draft/active/deprecated/retired states, version pinning) — separate feature; the design must be extensible to support this.
- Multi-resource composition (catalog items that bundle multiple resources with dependency ordering) — will likely use a different mechanism, not catalog items.
- Post-provisioning governance (restricting what a tenant can modify on a resource after provisioning) — separate feature.
- Cost metadata, metering/usage tracking, discoverability metadata (categories, tags) — separate features. Note: billing requirements may constrain which fields must be locked; those constraints will be captured in the design when the billing feature is specified.
- Budget enforcement, approval workflows — separate features.
- Catalog item override mechanism for tenant admins (OSAC-2539) — separate feature, but this redesign should be override-friendly.
- Tenant-provided images (bring-your-own-image workflow) — covered by a [separate proposal](https://github.com/osac-project/enhancement-proposals/pull/145); this PRD assumes tenants can reference both provider-supplied and tenant-provided images in catalog items.

## User Stories

### Cloud Provider Admin

- As a Cloud Provider Admin, I want to create a catalog item by selecting which resource fields are locked vs. editable using a structured form that shows the actual resource fields — not freeform path inputs — so that I cannot accidentally reference invalid fields.

- As a Cloud Provider Admin, I want every catalog item to require an image that is locked during provisioning, so that each catalog item represents a concrete offering (e.g., "RHEL 10 Small VM") and tenants cannot change the image when provisioning.

- As a Cloud Provider Admin, I want to update the image on an existing catalog item (e.g., to apply CVE fixes) without recreating it, so that I can maintain offerings over time.

- As a Cloud Provider Admin, I want editable fields to support per-field type customization (e.g., offering a curated list of instance types rather than accepting any string) so that tenants have guardrails without losing flexibility.

- As a Cloud Provider Admin, I want the system to prevent deletion of resources (images, instance types) that are referenced by a catalog item, so that published offerings do not silently break.

- As a Cloud Provider Admin, I want to govern template parameters on a catalog item with the same locked/editable behavior as spec fields, so that I can control which template parameters a tenant can override.

- As a Cloud Provider Admin, I want fields not mentioned in the catalog item to behave normally during provisioning (as if no catalog item exists), so that the catalog item is an overlay rather than a complete contract.

- As a Cloud Provider Admin, I want to assign a catalog item to a specific tenant and control its visibility via publish/unpublish, so that I can target offerings to the right audience.

### Tenant Admin

- As a Tenant Admin, I want to create organization-scoped catalog items using the same field governance model as global items, so that I can tailor offerings for my organization.

### Tenant User

- As a Tenant User, I want to see the full resource configuration when provisioning from a catalog item — locked values displayed as read-only, editable values pre-filled with defaults I can change, and ungoverned fields available as normal — so that I understand what I am getting.

## Assumptions

- The existing three per-resource-type catalog item types (ClusterCatalogItem, ComputeInstanceCatalogItem, BareMetalInstanceCatalogItem) are retained. Unifying them into a single CatalogItem type is not in scope for this redesign.
- Template parameters remain simple scalar types (string, bool, int32, int64, float, double, etc.) and do not require governance of nested structures.
- A catalog item reference remains mandatory for resource creation (existing behavior, unchanged by this feature).
- OSAC is pre-GA; no migration of existing catalog items or API compatibility layer is required. Existing catalog items using the old field_definitions model will be recreated.

## Dependencies

- **UI team (osac-ux):** The UI creation flow and provisioning wizard both require updates to match the new API structure. The UI lead has accepted the approach and contributed to the design.

---

## Provenance

Authored: respond @ prd 0.7.1 - b8b3f86, workspace feat/osac-taxonomy-presentation @ d22bfa1 (4 behind origin/main)
Phases: draft, respond

<!-- ai-workflow-provenance:{"schema_version":1,"provenance_kind":"session","workflow":"prd","workflow_version":"0.7.1","ai_workflows":"b8b3f86","source_repo":"d22bfa1","source_repo_branch":"feat/osac-taxonomy-presentation","commits_behind_main":4,"commits_ahead_main":0,"main_ref":"main","phases":["draft","respond"],"authoring_modes":["skill"],"context_changed":false,"origin_untracked":false} -->
