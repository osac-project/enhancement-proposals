# Support Administrator-Only Labels and Annotations

| Field             | Value |
|-------------------|-------|
| Author(s)         | Haim Tayrie <htayrie@redhat.com> |
| Jira              | [OSAC-6204](https://redhat.atlassian.net/browse/OSAC-6204) |
| Date              | 2026-10-11 |
| Affected services | All OSAC services with resources that expose labels or annotations |
| Target milestone  | 0.4 (Tech Preview) |

## Problem Statement

OSAC resources expose labels and annotations without a visibility or ownership boundary between provider-managed metadata and tenant-facing views and writes. Cloud administrators need to use this metadata for provider-side tracking while keeping it hidden from tenants and protected from tenant changes. Without that boundary, provider-side metadata can be exposed to tenants or changed by tenant requests.

## In Scope

- Administrators can view, add, change, and remove reserved-prefix labels and annotations through the privileged API, console, and CLI on every OSAC resource that exposes them, subject to existing access permissions. [Clarify: D8](clarifications.md#decision-d8)
- Tenant-facing API responses and console views omit reserved-prefix labels and annotations.
- Tenant create and update requests that explicitly supply reserved-prefix labels or annotations, or identify a reserved key to remove, fail as a whole with a clear error and apply no ordinary changes. Updates that omit reserved entries preserve them and may apply ordinary changes successfully. [Clarify: D7](clarifications.md#decision-d7)
- Ordinary labels and annotations retain their existing tenant visibility and behavior.
- The reserved prefix and its matching rules are documented; the exact prefix and rules are determined during design.

## Out of Scope

- Changing existing behavior for non-reserved labels and annotations.
- Replacing labels or annotations with resource-specific typed fields.
- Adding in-place upgrade support; OSAC does not currently support in-place upgrades.

## User Stories

### Administrator

- As an Administrator, I want to view, add, change, and remove reserved-prefix labels and annotations on resources I can manage through the privileged API, console, or CLI, so that I can maintain provider-side tracking metadata without exposing it to tenants. [Clarify: D8](clarifications.md#decision-d8)

### Tenant Admin

- As a Tenant Admin, I want tenant-facing responses and console views to hide reserved labels and annotations, explicit requests to change them to fail clearly, and ordinary updates to preserve hidden entries, so that provider-managed metadata stays private and protected. [Clarify: D7](clarifications.md#decision-d7)

### Tenant User

- As a Tenant User, I want ordinary labels and annotations to remain visible and manageable while reserved-prefix metadata stays hidden and protected from my changes, so that I can use OSAC metadata without seeing or changing provider-only information.

---

## Provenance

Authored: draft @ prd 0.11.5 - 6d28c88, workspace main @ f0a8211
Final: revise @ prd 0.11.5 - 1c6e8de, workspace main @ f0a8211

> Context changed between draft and revise.

<!-- ai-workflow-provenance:{"schema_version":1,"provenance_kind":"session","workflow":"prd","workflow_version":"0.11.5","ai_workflows":"1c6e8de","source_repo":"f0a8211","source_repo_branch":"main","commits_behind_main":0,"commits_ahead_main":0,"main_ref":"main","phases":["draft","revise","revise","revise","revise","revise","revise"],"authoring_modes":["skill"],"context_changed":true,"origin_untracked":false} -->
