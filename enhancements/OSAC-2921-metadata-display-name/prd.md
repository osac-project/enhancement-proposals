# Add Standardized display_name and description Fields to Resource Metadata

| Field       | Value   |
|-------------|---------|
| Author(s)   | Udi Shkalim |
| Jira        | https://redhat.atlassian.net/browse/OSAC-2921 |
| Date        | 2026-07-21 |

## Problem Statement

OSAC resources use `metadata.name` as the primary human-visible identifier, but this field is constrained to DNS-label format (lowercase alphanumeric and hyphens, max 63 characters), making it unsuitable as a user-friendly label. Some resource types (Project, Role, NetworkClass, catalog items, templates) work around this with per-resource `title` and `description` fields, while most resources (ComputeInstance, VirtualNetwork, Subnet, PublicIP, BlockVolume) have no friendly name at all. This inconsistency forces repeated per-resource-type discussions about whether to add display fields and produces an uneven user experience across VMs, virtual networks, public IPs, and other resources.

## In Scope

- `display_name` (optional string, max 63 characters) and `description` (optional string, max 256 characters) added to the shared Metadata, automatically inherited by every resource type `[Clarify: R2.Q1, R4.Q4]`
- Removal of existing `title` and `description` fields from the spec of spec-based resources: Project, Role, IdentityProvider, and InstanceType (description only) `[Clarify: R1.Q1, R4.Q2, R5.Q2]`
- Both fields are optional, mutable after creation, and clearable `[Clarify: R3.Q1]`
- Users can filter and sort resource lists by `display_name` across UI, CLI, and API `[Clarify: R2.Q2]`
- UI displays `display_name` in place of `metadata.name` when set; falls back to `metadata.name` when `display_name` is not set — this applies uniformly across list views, detail pages, breadcrumbs, and search results `[Clarify: R4.Q1, R5.Q1]`
- E2E test coverage for create, update, and clear of `display_name` and `description` across representative resource types
- Documentation updated to describe the new fields and fallback behavior

## Out of Scope

- Making `display_name` or `description` required for any resource type
- Renaming or removing existing `metadata.name` semantics
- Enforcing uniqueness constraints on `display_name`
- Template parameter `title`/`description` fields within ComputeInstanceTemplate, BaremetalInstanceTemplate, and ClusterTemplate — only resource-level fields are affected `[Clarify: R1.Q3]`
- Flat-shape, platform-defined resources that already have top-level `title`/`description` fields: ClusterTemplate, ComputeInstanceTemplate, BareMetalInstanceTemplate, NetworkClass, HostType, ComputeInstanceCatalogItem, BareMetalInstanceCatalogItem, and ClusterCatalogItem — these keep their existing fields unchanged `[Clarify: R4.Q2, R5.Q2]`

## User Stories

### Cloud Provider Admin

- As a Cloud Provider Admin, I want resources across all tenant organizations to show a consistent, human-readable `display_name` and `description` so that I can quickly identify and audit resources when reviewing or supporting tenants, regardless of resource type.
- As a Cloud Provider Admin, I want to filter and sort resource lists by `display_name` so that I can locate specific resources across tenants without memorizing DNS-label names. `[Clarify: R2.Q2]`

### Tenant Admin

- As a Tenant Admin, I want all resource types I manage (VMs, virtual networks, public IPs, security groups, etc.) to support a friendly `display_name` and `description` so that I can label and document resources meaningfully instead of being limited by `metadata.name` restrictions.
- As a Tenant Admin, I want to update or clear `display_name` and `description` on existing resources so that I can correct labels or remove outdated descriptions as resources evolve. `[Clarify: R3.Q1]`

### Tenant User

- As a Tenant User, I want to give my resources a friendly `display_name` (up to 63 characters) and `description` when creating them so that I can identify and organize them more easily than relying on the constrained `metadata.name` field. `[Clarify: R2.Q1]`
- As a Tenant User, I want list views to show `display_name` when set and fall back to `metadata.name` when it is not, so that I always see the most useful identifier regardless of whether a display name was provided.

## Dependencies

- **fulfillment-service proto and server changes:** Must land before UI and E2E test changes, since both depend on the updated Metadata definition and API behavior.

---

## Provenance

Authored: revise @ prd 0.5.0 - 92734a2, workspace main @ aac0f8e
Phases: draft, revise

<!-- ai-workflow-provenance:{"schema_version":1,"provenance_kind":"session","workflow":"prd","workflow_version":"0.5.0","ai_workflows":"92734a2","source_repo":"aac0f8e","source_repo_branch":"main","commits_behind_main":0,"commits_ahead_main":0,"main_ref":"main","phases":["draft","revise"],"authoring_modes":["skill"],"context_changed":false} -->
