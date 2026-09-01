# Self-Subject Access Review API

| Field       | Value   |
|-------------|---------|
| Author(s)   | CrystalChun |
| Jira        | https://redhat.atlassian.net/browse/OSAC-2476 |
| Date        | 2026-08-31 |

## Problem Statement

Authenticated users (tenant admins and tenant users) currently have no way to check their permissions on OSAC resources without attempting the actual operation. This creates friction in user workflows: users must attempt actions to discover they lack permission, leading to unexpected errors and poor user experience. For UI and CLI developers, this limitation prevents implementing permission-aware interfaces that could hide unavailable actions, validate workflows before execution, or provide clear permission-based guidance. Without a permission check API, every permission denial is a user-facing failure rather than a proactive workflow decision.

## In Scope

- **SelfSubjectAccessReview-style API** that allows authenticated users to check their own permissions without performing the operation
- **Create-only RPC** that evaluates permission requests inline and returns results immediately (no persistence to database)
- **Request specification** describing the permission check:
  - Resource type (e.g., Cluster, ComputeInstance, VirtualNetwork, Subnet, SecurityGroup)
  - Verb (create, get, update, delete, list)
  - Optional scoping by tenant name and resource name
- **Response status** indicating the authorization result:
  - `allowed` boolean field showing whether the user has permission
  - Optional `denied` and `reason` fields explaining why permission was denied
- **Identity inference** from authentication context — server extracts user identity from the request's JWT token claims (username, organization, realm roles, groups)
- **Comprehensive resource coverage** — support permission checks for all OSAC resource types and standard verbs
- **Access control** — any authenticated user can call the endpoint to check their own permissions
- **Authorization reuse** — leverage existing OPA policy evaluation logic to ensure permission check results match actual authorization decisions
- **Testing** — unit tests covering allowed/denied scenarios across different roles (Admin, Tenant Admin, Client), integration tests verifying behavior across resource types, verbs, and scoping
- **API documentation** describing the new endpoint, request/response schemas, and usage examples

## Out of Scope

- **Checking another user's permissions** (SubjectAccessReview equivalent) — this feature only supports self-subject access review; checking permissions for a different user or service account is explicitly excluded
- **Bulk permission checks** — evaluating multiple permission scenarios in a single request is not supported; each check requires a separate API call
- **Caching or memoization of results** — permission checks evaluate fresh on every request using current authorization state; no result caching mechanism is provided
- **UI integration work** — while this API enables permission-aware UIs, the actual UI changes to consume this API are a separate feature and not included in this work

## User Stories

### Tenant Admin

- As a tenant admin, I want to check whether I have permission to create a VirtualNetwork in my tenant via the UI, CLI, or API, so that the interface can show or hide the "Create Network" action based on my actual permissions
- As a tenant admin, I want to check whether I have permission to manage users in my tenant before navigating to the user management section, so that the UI can prevent navigation to features I cannot use
- As a tenant admin, I want to check whether I have permission to update quota settings for my tenant, so that quota-related controls can be enabled or disabled based on my role

### Tenant User

- As a tenant user, I want to check whether I have permission to create a ComputeInstance in a specific tenant before starting the creation workflow, so that the UI can validate my permissions upfront rather than failing at submission time
- As a tenant user, I want to check whether I have permission to update a specific ComputeInstance (scoped by tenant and resource name) before enabling the edit form, so that I don't invest effort in changes I cannot save
- As a tenant user, I want to check whether I have permission to delete a Subnet in my tenant, so that the CLI can warn me if I lack permission before prompting for confirmation
- As a tenant user, I want to check whether I have permission to list SecurityGroups in a tenant, so that the API client can detect authorization failures before attempting bulk operations

## Assumptions

- The existing OPA authorization policy (`internal/auth/policies/authz.rego`) contains all necessary logic to evaluate permissions for OSAC resources and verbs, and this logic can be invoked programmatically to perform hypothetical "what if" evaluations without side effects
- All role and permission information required to evaluate authorization decisions is available in the JWT token claims (username, organization, realm roles, groups) presented by the authenticated user
- The Kubernetes SelfSubjectAccessReview API pattern (create-only RPC with spec describing the check and status describing the result) is well-understood by the target audience and does not require additional design justification

## Dependencies

N/A

---

## Provenance

Authored: draft @ prd 0.9.0 - a17a43d, workspace main @ ed93971 (dirty)

<!-- ai-workflow-provenance:{"schema_version":1,"provenance_kind":"session","workflow":"prd","workflow_version":"0.9.0","ai_workflows":"a17a43d","source_repo":"ed93971 (dirty)","source_repo_branch":"main","commits_behind_main":0,"commits_ahead_main":0,"main_ref":"main","phases":["draft"],"authoring_modes":["skill"],"context_changed":false,"origin_untracked":false} -->
