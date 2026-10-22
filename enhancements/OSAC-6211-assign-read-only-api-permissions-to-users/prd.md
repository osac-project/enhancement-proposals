# Assign read-only API permissions to users

| Field            | Value |
|------------------|-------|
| Author(s)        | Juan Hernandez |
| Jira             | [OSAC-6211](https://redhat.atlassian.net/browse/OSAC-6211) |
| Date             | 2026-10-20 |
| Target milestone | 0.4 |

## Problem Statement

Some OSAC customers need internal or external auditors to inspect what
resources are in their environment and verify their current state. Auditors
need this visibility without being able to create, change, or delete
resources. Today, administrators lack a consistent way to grant this access
across OSAC APIs and the UI, leaving them to choose between denying auditors
visibility and granting access that also allows changes. [User]

## In Scope

- The read-only role allows `Get`, `List`, and `Watch` on resources a user is
  otherwise authorized to see. It grants no other gRPC methods. Existing
  tenant and resource access controls still apply. [User]
- Role grants are always additive. Adding a read-only role does not remove
  permissions granted by another role. For auditors who must not be able to
  change resources, administrators must ensure that no other assigned role
  allows changes. [User]
- Authorized administrators can assign the read-only level through the API
  and UI, and user-facing API and UI documentation explains the level.

## Out of Scope

- Configurable per-resource permission combinations or custom action sets.
- Changes to individual resource API lifecycle contracts or operations.

## User Stories

### Cloud Provider Admin

- As a Cloud Provider Admin, I want to grant auditors read-only access to
  resources in the tenants they oversee so that auditors can review what is
  present and its current state.

### Cloud Infrastructure Admin

- As a Cloud Infrastructure Admin, I want read-only access to infrastructure
  resources within my authorization scope so that I can verify infrastructure
  state during an audit without changing it.

### Tenant Admin

- As a Tenant Admin, I want to grant internal or external auditors read-only
  access to our organization's resources so that they can review what is
  present and its current state.

### Tenant User

- As a Tenant User, I want to list and view the OSAC resources I am authorized
  to access so that I can inspect our environment during an audit without
  changing resources.

---

## Provenance

Authored: draft @ prd 0.11.5 - 4164796, workspace main @ 95fbc127c
Final: respond @ prd 0.11.5 - d1824b1, workspace main @ 95fbc127c

> Context changed between draft and respond.

<!-- ai-workflow-provenance:{"schema_version":1,"provenance_kind":"session","workflow":"prd","workflow_version":"0.11.5","ai_workflows":"d1824b1","source_repo":"95fbc127c","source_repo_branch":"main","commits_behind_main":0,"commits_ahead_main":0,"main_ref":"main","phases":["draft","respond","respond"],"authoring_modes":["skill"],"context_changed":true,"origin_untracked":false} -->
