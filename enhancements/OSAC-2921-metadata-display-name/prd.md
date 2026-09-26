# Add Standardized display_name and description Fields to Resource Metadata

| Field       | Value   |
|-------------|---------|
| Author(s)   | Udi Shkalim |
| Jira        | https://redhat.atlassian.net/browse/OSAC-2921 |
| Date        | 2026-09-24 |

## Problem Statement

OSAC resources use `metadata.name` as the primary human-visible identifier, but this field is constrained to DNS-label format (lowercase alphanumeric and hyphens, max 63 characters), making it unsuitable as a user-friendly label. Some resource types (Project, Role, NetworkClass, catalog items, templates) work around this with per-resource `title` and `description` fields, while most resources (ComputeInstance, VirtualNetwork, Subnet, PublicIP, BlockVolume) have no friendly name at all. This inconsistency forces repeated per-resource-type discussions about whether to add display fields and produces an uneven user experience across VMs, virtual networks, public IPs, and other resources.

## In Scope

- Consistent, user-friendly resource naming across all OSAC resource types, all personas, and all client interfaces (API, CLI, Web UI) `[PR review: mhrivnak]`
- Two new shared Metadata fields: `display_name` (optional, max 63 characters) and `description` (optional, max 256 characters) — values can be changed or cleared on resource types that support metadata editing, and are not required to be unique. For networking resources governed by OSAC-1433, the values are set at creation and cannot be changed or cleared later. `[Clarify: R2.Q1, R3.Q1, R4.Q4, PR review: sk-ilya; User; OSAC-1433]`
- Reconciliation of existing per-resource `title`/`description` fields — removed from all 12 resource types that currently have them: Project, Role, IdentityProvider, InstanceType (description only), ClusterTemplate, ComputeInstanceTemplate, BareMetalInstanceTemplate, NetworkClass, HostType, ComputeInstanceCatalogItem, BareMetalInstanceCatalogItem, ClusterCatalogItem `[Clarify: R1.Q1, PR review: sk-ilya, ygalblum]`
- Filtering and sorting by `display_name` `[Clarify: R2.Q2]`

## Out of Scope

- Resource identity — `metadata.name` remains the unique identifier `[PR review: mhrivnak]`
- Display behavior (how clients present `display_name` vs `metadata.name`) — deferred to UX and design phase `[PR review: mhrivnak, ygalblum]`
- Template parameter `title`/`description` fields within ComputeInstanceTemplate, BareMetalInstanceTemplate, and ClusterTemplate — only resource-level fields are affected `[Clarify: R1.Q3]`

## User Stories

### Cloud Provider Admin

- As a Cloud Provider Admin, I want resources across all tenant organizations to show a consistent, human-readable `display_name` and `description` so that I can quickly identify and audit resources when reviewing or supporting tenants, regardless of resource type.
- As a Cloud Provider Admin, I want to filter and sort resource lists by `display_name` so that I can find resources across tenants using natural-language terms. `[Clarify: R2.Q2, PR review: mhrivnak]`

### Cloud Infrastructure Admin

- As a Cloud Infrastructure Admin, I want platform-defined resources I manage (NetworkClass, HostType, catalog items, templates) to use the same `metadata.display_name` and `metadata.description` fields as all other resources, so that naming conventions are consistent across platform and tenant resources. `[PR review: sk-ilya, ygalblum]`

### Tenant Admin

- As a Tenant Admin, I want all resource types I manage (VMs, virtual networks, public IPs, NetworkACLs, etc.) to support a friendly `display_name` and `description` so that I can give resources a natural-language name and description that are not constrained to DNS-label format. `[PR review: mhrivnak]`
- As a Tenant Admin, I want to update or clear `display_name` and `description` on existing resources whose metadata supports editing so that I can correct labels or remove outdated descriptions as resources evolve. Networking resources governed by OSAC-1433, including NetworkACLs and Subnets, remain create-time-only. `[Clarify: R3.Q1; User; OSAC-1433]`

### Tenant User

- As a Tenant User, I want to give my resources a friendly `display_name` (up to 63 characters) and `description` when creating them so that I can identify and organize them more easily than relying on the constrained `metadata.name` field. `[Clarify: R2.Q1]`

## Dependencies

- **fulfillment-service proto and server changes:** Must land before UI and E2E test changes, since both depend on the updated Metadata definition and API behavior.

---

## Provenance

Authored: revise @ prd 0.11.3 - cc0daa6, workspace main @ 06d340f90 (43 behind origin/main)

> This document's phase history does not include an initial /draft — structure was not verified against the template from origin.

<!-- ai-workflow-provenance:{"schema_version":1,"provenance_kind":"session","workflow":"prd","workflow_version":"0.11.3","ai_workflows":"cc0daa6","source_repo":"06d340f90","source_repo_branch":"main","commits_behind_main":43,"commits_ahead_main":0,"main_ref":"main","phases":["revise"],"authoring_modes":["skill"],"context_changed":false,"origin_untracked":true} -->
