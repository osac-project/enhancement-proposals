# Add Standardized display_name and description Fields to Resource Metadata

| Field       | Value   |
|-------------|---------|
| Author(s)   | Udi Shkalim |
| Jira        | https://redhat.atlassian.net/browse/OSAC-2921 |
| Date        | 2026-07-21 |
| Last updated | 2026-08-14 |

## Problem Statement

OSAC resources use `metadata.name` as the primary human-visible identifier, but this field is constrained to DNS-label format (lowercase alphanumeric and hyphens, max 63 characters), making it unsuitable as a user-friendly label. Some resource types (Project, Role, NetworkClass, catalog items, templates) work around this with per-resource `title` and `description` fields, while most resources (ComputeInstance, VirtualNetwork, Subnet, PublicIP, BlockVolume) have no friendly name at all. This inconsistency forces repeated per-resource-type discussions about whether to add display fields and produces an uneven user experience across VMs, virtual networks, public IPs, and other resources.

## In Scope

- Consistent, user-friendly resource naming across all OSAC resource types, all personas, and all client interfaces (API, CLI, Web UI) `[PR review: mhrivnak]`
- Two new shared Metadata fields: `display_name` (optional, max 63 characters) and `description` (optional, max 256 characters, **Markdown**); clients that display it MUST render Markdown with sanitization — both mutable, clearable, and not required to be unique `[Clarify: R2.Q1, R3.Q1, R4.Q4, PR review: sk-ilya]`
- Reconciliation of existing per-resource `title`/`description` fields — removed from all 12 resource types that currently have them: Project, Role, IdentityProvider, InstanceType (description only), ClusterTemplate, ComputeInstanceTemplate, BareMetalInstanceTemplate, NetworkClass, HostType, ComputeInstanceCatalogItem, BareMetalInstanceCatalogItem, ClusterCatalogItem `[Clarify: R1.Q1, PR review: sk-ilya, ygalblum]`
- Filtering and sorting by `display_name` `[Clarify: R2.Q2]`

## Out of Scope

- Resource identity — `metadata.name` remains the unique identifier `[PR review: mhrivnak]`
- Display behavior (how clients present `display_name` vs `metadata.name`) — deferred to UX and design phase `[PR review: mhrivnak, ygalblum]`
- Template parameter `title`/`description` fields within ComputeInstanceTemplate, BareMetalInstanceTemplate, and ClusterTemplate — only resource-level fields are affected `[Clarify: R1.Q3]`
- Full multi-locale / i18n Metadata in this feature — single canonical `display_name` / `description` only; localized maps deferred `[osac#263]`

## User Stories

### Cloud Provider Admin

- As a Cloud Provider Admin, I want resources across all tenant organizations to show a consistent, human-readable `display_name` and Markdown `description` so that I can quickly identify and audit resources when reviewing or supporting tenants, regardless of resource type.
- As a Cloud Provider Admin, I want to filter and sort resource lists by `display_name` so that I can find resources across tenants using natural-language terms. `[Clarify: R2.Q2, PR review: mhrivnak]`

### Cloud Infrastructure Admin

- As a Cloud Infrastructure Admin, I want platform-defined resources I manage (NetworkClass, HostType, catalog items, templates) to use the same `metadata.display_name` and `metadata.description` fields as all other resources, so that naming conventions are consistent across platform and tenant resources. `[PR review: sk-ilya, ygalblum]`

### Tenant Admin

- As a Tenant Admin, I want all resource types I manage (VMs, virtual networks, public IPs, security groups, etc.) to support a friendly `display_name` and Markdown `description` so that I can give resources a natural-language name and description that are not constrained to DNS-label format. `[PR review: mhrivnak]`
- As a Tenant Admin, I want to update or clear `display_name` and `description` on existing resources so that I can correct labels or remove outdated descriptions as resources evolve. `[Clarify: R3.Q1]`

### Tenant User

- As a Tenant User, I want to give my resources a friendly `display_name` (up to 63 characters) and Markdown `description` when creating them so that I can identify and organize them more easily than relying on the constrained `metadata.name` field. `[Clarify: R2.Q1]`

## Dependencies

- **fulfillment-service proto and server changes:** Must land before UI and E2E test changes, since both depend on the updated Metadata definition and API behavior.

---

## Provenance

Authored: draft @ prd 0.5.0 - 92734a2, workspace main @ aac0f8e
Final: respond @ prd 0.7.1 - b8b3f86 (dirty), workspace main @ b4cbc82 (dirty)
Revised: 2026-08-14 — clients MUST sanitize Markdown `description` when rendering

> Context changed between draft and respond.

<!-- ai-workflow-provenance:{"schema_version":1,"provenance_kind":"session","workflow":"prd","workflow_version":"0.7.1","ai_workflows":"b8b3f86 (dirty)","source_repo":"b4cbc82 (dirty)","source_repo_branch":"main","commits_behind_main":0,"commits_ahead_main":0,"main_ref":"main","phases":["draft","revise","respond","respond","respond","respond"],"authoring_modes":["skill"],"context_changed":true,"origin_untracked":false} -->
