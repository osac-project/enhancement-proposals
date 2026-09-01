# Self-Subject Access Review API

| Field       | Value   |
|-------------|---------|
| Author(s)   | CrystalChun |
| Jira        | https://redhat.atlassian.net/browse/OSAC-2476 |
| Date        | 2026-08-31 |

## Problem Statement

Authenticated users (tenant admins and tenant users) currently have no way to check their permissions on OSAC resources without attempting the actual operation. This creates friction in user workflows: users must attempt actions to discover they lack permission, leading to unexpected errors and poor user experience. For UI and CLI developers, this limitation prevents implementing permission-aware interfaces that could hide unavailable actions, validate workflows before execution, or provide clear permission-based guidance. Without a permission check API, every permission denial is a user-facing failure rather than a proactive workflow decision.

## In Scope

- **Permission check API** that allows authenticated users to check their own permissions on OSAC resources without performing the actual operation
- **Request specification** describing the hypothetical operation to check:
  - Resource type (e.g., Cluster, ComputeInstance, VirtualNetwork, Subnet, SecurityGroup, User, Tenant)
  - Verb (create, get, update, delete, list)
  - Optional tenant name and resource name to scope the hypothetical operation (the authenticated user's identity is always determined from the request's authentication context, never from request fields)
- **Response** indicating whether the authenticated user would be authorized:
  - `allowed` boolean field showing whether the permission check passed
  - Optional `reason` field providing explanation when permission is denied
- **Advisory results** — permission check results reflect authorization state at check time; the actual operation must independently re-evaluate authorization since permissions and resource state may change between the check and the operation
- **Authorization consistency** — permission check results must match the authorization decision that would be made for the same user attempting the same operation (same resource type, verb, tenant, and resource name) at the time of the check
- **User identity determination** — the API determines the authenticated user's identity, tenants, and roles automatically from authentication context (no separate identity parameters)
- **Comprehensive resource coverage** — support permission checks for all OSAC resource types and standard verbs (note: user management and quota scenarios referenced in user stories translate to permission checks on underlying resource operations like creating/updating User or Tenant resources)
- **Access control** — any authenticated user can call the endpoint to check their own permissions
- **Validation** — tests must demonstrate that permission check results match actual authorization outcomes for allowed and denied scenarios across different roles (Admin, Tenant Admin, Client) and resource types
- **API documentation** describing the endpoint, request/response schemas, usage examples, and the advisory nature of results

## Out of Scope

- **Checking another user's permissions** (SubjectAccessReview equivalent) — this feature only supports self-subject access review; checking permissions for a different user or service account is explicitly excluded
- **Bulk permission checks** — evaluating multiple permission scenarios in a single request is not supported; each check requires a separate API call
- **Caching or memoization of results** — permission checks evaluate fresh on every request using current authorization state; no result caching mechanism is provided
- **UI integration work** — while this API enables permission-aware UIs, the actual UI changes to consume this API are a separate feature and not included in this work

## User Stories

### Tenant Admin

- As a tenant admin, I want to check whether I have permission to perform management operations (create VirtualNetwork, manage users via User resource operations, update Tenant quota settings) before attempting them via the UI, CLI, or API, so that interfaces can show or hide actions based on my actual permissions and prevent navigation to features I cannot use

### Tenant User

- As a tenant user, I want to check whether I have permission to create, update, or delete infrastructure resources (ComputeInstance, Subnet, SecurityGroup) in a specific tenant before starting the workflow, so that the UI and CLI can validate permissions upfront and warn me before I invest effort in changes I cannot save
- As a tenant user, I want to check resource-scoped permissions (update or delete operations on a specific resource by name) before enabling edit or delete actions, so that I know whether I can modify a particular resource before attempting the operation

## Assumptions

- The Kubernetes SelfSubjectAccessReview API pattern (request specifying the operation to check, response with allowed/denied result) is well-understood by the target audience and does not require additional design justification

## Dependencies

This feature depends on internal fulfillment-service components (authentication, authorization policy evaluation) but has no external team or service dependencies

---

## Provenance

Authored: draft @ prd 0.9.0 - a17a43d, workspace main @ ed93971 (dirty)
Final: revise @ prd 0.9.0 - a17a43d, workspace main @ 3c61513

> Context changed between draft and revise.

<!-- ai-workflow-provenance:{"schema_version":1,"provenance_kind":"session","workflow":"prd","workflow_version":"0.9.0","ai_workflows":"a17a43d","source_repo":"3c61513","source_repo_branch":"main","commits_behind_main":0,"commits_ahead_main":0,"main_ref":"main","phases":["draft","revise"],"authoring_modes":["skill"],"context_changed":true,"origin_untracked":false} -->
