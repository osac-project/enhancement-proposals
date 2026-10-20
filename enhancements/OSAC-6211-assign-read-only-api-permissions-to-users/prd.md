# Assign read-only API permissions to users

| Field            | Value |
|------------------|-------|
| Author(s)        | Juan Hernandez |
| Jira             | [OSAC-6211](https://redhat.atlassian.net/browse/OSAC-6211) |
| Date             | 2026-10-20 |
| Target milestone | 0.4 |

## Problem Statement

Some OSAC users need to inspect resources without being able to change or
remove them. Permission management needs a clearly defined read-only level
that administrators can assign consistently across OSAC API resources and
the UI. Without it, administrators lack a clear way to grant view-only access
while preventing resource mutations.

## In Scope

- Read-only users can use `Get`, `List`, and `Watch` to view OSAC resources
  they already have access to. All other gRPC methods are denied. Existing
  tenant and resource access controls still apply. [User]
- Authorized administrators can assign the read-only level through the API
  and UI, and user-facing API and UI documentation explains the level.

## Out of Scope

- Configurable per-resource permission combinations or custom action sets.
- Changes to individual resource API lifecycle contracts or operations.

## User Stories

### Cloud Provider Admin

- As a Cloud Provider Admin, I want to assign users read-only API access so
  that they can view authorized OSAC resources without changing them.

### Cloud Infrastructure Admin

- As a Cloud Infrastructure Admin, I want read-only access to infrastructure
  resources within my authorization scope so that I can inspect their state
  without changing them.

### Tenant Admin

- As a Tenant Admin, I want to assign tenant users read-only access to our
  organization's resources so that they can view them without creating,
  changing, or deleting them.

### Tenant User

- As a Tenant User, I want to list and view the OSAC resources I am authorized
  to access without mutation permissions so that I can inspect our environment
  safely.

---

## Provenance

Authored: respond @ prd 0.11.5 - 4164796, workspace main @ 95fbc127c
Phases: draft, respond

<!-- ai-workflow-provenance:{"schema_version":1,"provenance_kind":"session","workflow":"prd","workflow_version":"0.11.5","ai_workflows":"4164796","source_repo":"95fbc127c","source_repo_branch":"main","commits_behind_main":0,"commits_ahead_main":0,"main_ref":"main","phases":["draft","respond"],"authoring_modes":["skill"],"context_changed":false,"origin_untracked":false} -->
