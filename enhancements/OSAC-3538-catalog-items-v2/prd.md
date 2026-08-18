# Catalog Items v2 — Field Governance Redesign

| Field       | Value   |
|-------------|---------|
| Author(s)   | Avishay Traeger |
| Jira        | https://redhat.atlassian.net/browse/OSAC-3538 |
| Date        | 2026-08-06 |

## Problem Statement

OSAC catalog items let Cloud Provider Admins create curated offerings by locking some resource fields and exposing others as editable. The current field governance model uses generic field definitions with freeform values, which limits the quality of the admin and tenant experience. Admins cannot express richer field semantics — for example, presenting an image as a typed reference selector rather than a freeform string. The generic model also prevents the system from enforcing referential integrity between catalog items and the resources they reference: an image or instance type referenced by a catalog item can be deleted without warning, silently breaking a published offering.

## In Scope

- Catalog Items act as an overlay on resource creation. When a Catalog Item is used, its defaults and field governance are applied during creation: locked fields use the Catalog Item value; editable fields use the tenant-provided value when present, otherwise the Catalog Item default if one is defined; and fields not governed by the Catalog Item follow normal resource creation semantics. After creation, the Catalog Item is not consulted for reconciliation or Day-2 governance, and the resulting resource follows its normal independent lifecycle.
- When a resource is created from a Catalog Item, all information required for the resulting resource to operate independently must be resolved as part of creation.
- Spec fields on each Catalog Item type are structured, typed fields that use the same value type as the corresponding resource spec field, with per-field behavior (locked or editable with an optional default), replacing the current freeform-path, generic-value model. Only the subset of spec fields relevant to catalog governance are exposed — fields like network attachments are not governable through catalog items. The design will enumerate the exact fields per resource type. Template parameters are governed via a key-value map.
- The catalog item owner may update governed field values and behaviors, subject to field-specific rules. Changes affect only future provisioning.
- Template parameters are governed with the same locked/editable behavior as spec fields, validated against the referenced template's parameter definitions.
- The system prevents deletion of resources (images, instance types) referenced by catalog items. Deletion blocking is the immediate behavior; a deprecation/obsolescence model may replace or complement this when the lifecycle feature (see Out of Scope) is implemented.
- Cloud Provider Admins can assign catalog items to specific tenants and control visibility via publish/unpublish.
- Applies to all three catalog item types: ComputeInstanceCatalogItem, ClusterCatalogItem, and BareMetalInstanceCatalogItem.

## Out of Scope

- Constraints on editable fields (allowed values, min/max ranges) — separate feature; the behavior model must be extensible to support composable constraints alongside locked/editable.
- Hidden field behavior (admin sets value, tenant cannot see the field) — separate feature; the behavior model must be extensible to support it.
- Lifecycle management and versioning (draft/active/deprecated/retired states, version pinning) — separate feature; the design must be extensible to support this.
- Multi-resource composition (catalog items that bundle multiple resources with dependency ordering) — will likely use a different mechanism, not catalog items.
- Cost metadata, metering/usage tracking, discoverability metadata (categories, tags) — separate features. Note: billing requirements may constrain which fields must be locked; those constraints will be captured in the design when the billing feature is specified.
- Budget enforcement, approval workflows — separate features.
- Catalog item override mechanism for tenant admins (OSAC-2539) — separate feature, but this redesign should be override-friendly.
- Tenant-provided images (bring-your-own-image workflow) — covered by a [separate proposal](https://github.com/osac-project/enhancement-proposals/pull/145); this PRD assumes tenants can reference both provider-supplied and tenant-provided images in catalog items.
- Day-2 Catalog Item governance and catalog-aware resource lifecycle management.

## User Stories

### Cloud Provider Admin

- As a Cloud Provider Admin, I want to create a catalog item by selecting which resource fields are locked vs. editable using a structured form that shows the actual resource fields — not freeform path inputs — so that I cannot accidentally reference invalid fields.

- As a Cloud Provider Admin, I want to lock any governed field on a catalog item — for example the image, or the instance type — so that I can publish a concrete offering (e.g., "RHEL 10 Small VM", or a "small" vs. "large" sizing my organization defines) where tenants cannot change the fields I have fixed.

- As a Cloud Provider Admin, I want to update a governed field value on an existing catalog item — for example the image, to apply CVE fixes — without recreating it, so that I can maintain offerings over time. Changes only affect new provisioning.

- As a Cloud Provider Admin, I want editable fields to use typed inputs rather than freeform strings, so that tenants have guardrails without losing flexibility.

- As a Cloud Provider Admin, I want the system to prevent deletion of resources (images, instance types) that are referenced by a catalog item, so that published offerings do not silently break.

- As a Cloud Provider Admin, I want to govern template parameters on a catalog item with the same locked/editable behavior as spec fields, so that I can control which template parameters a tenant can override.

- As a Cloud Provider Admin, I want to define Catalog Items that prescribe input for only some fields, while allowing the remaining fields to retain their original behavior, so that I can affect only the fields I care about without having to redefine behavior for other fields.

- As a Cloud Provider Admin, I want to assign a catalog item to a specific tenant and control its visibility via publish/unpublish, so that I can target offerings to the right audience.

### Tenant Admin

- As a Tenant Admin, I want to create, update, publish, unpublish, and delete organization-scoped catalog items using the same field governance model as global items, so that I can tailor provisioning offerings for my organization.

### Tenant User

- As a Tenant User, I want to see the full resource configuration when provisioning from a catalog item — locked values displayed as read-only, editable values pre-filled with defaults I can change, and ungoverned fields available as normal — so that I understand what I am getting.

## Assumptions

- The existing three per-resource-type catalog item types (ClusterCatalogItem, ComputeInstanceCatalogItem, BareMetalInstanceCatalogItem) are retained. Unifying them into a single CatalogItem type is not in scope for this redesign.
- Template parameters remain simple scalar types (string, bool, int32, int64, float, double, etc.) and do not require governance of nested structures.
- Resources can be created through the API with or without a Catalog Item. The initial UI provisioning flow remains Catalog Item-based.
- OSAC is pre-GA; no migration of existing catalog items or API compatibility layer is required. Existing catalog items using the old field_definitions model will be recreated.

## Dependencies

- **UI team (osac-ux):** The UI creation flow and provisioning wizard both require updates to match the new API structure. The UI lead has accepted the approach and contributed to the design.

---

## Provenance

Authored: draft @ prd 0.7.1 - b8b3f86, workspace feat/osac-taxonomy-presentation @ d22bfa1 (4 behind origin/main)
Final: respond @ prd 0.8.0 - 7efcedb, workspace feat/osac-taxonomy-presentation @ d22bfa1 (61 behind origin/main)

> Context changed between draft and respond.

<!-- ai-workflow-provenance:{"schema_version":1,"provenance_kind":"session","workflow":"prd","workflow_version":"0.8.0","ai_workflows":"7efcedb","source_repo":"d22bfa1","source_repo_branch":"feat/osac-taxonomy-presentation","commits_behind_main":61,"commits_ahead_main":0,"main_ref":"main","phases":["draft","respond","respond","respond","respond","respond"],"authoring_modes":["skill"],"context_changed":true,"origin_untracked":false} -->
