# Configurable Named Roles with Separation of Duties

| Field       | Value   |
|-------------|---------|
| Author(s)   | Dakota Crowder |
| Jira        | https://redhat.atlassian.net/browse/OSAC-3058 |
| Date        | 2026-10-23 |
| Milestone   | 0.5 |

## Problem Statement

Providers can already grant users a fixed set of built-in roles — tenant-admin
and tenant-idp-manager — and every authenticated user receives a fixed
self-service allowlist, but the roles themselves are built into the service:
no administrator can create, compose, or change a role at runtime, and adding
one requires a platform redeploy. Compliance-driven deployments need to model
documented personas such as ISSO, Auditor, and System Owner as specific
compositions of granular capabilities, enforce that conflicting roles are
never held by the same person, and show in the audit trail which named role
authorized each action — none of which the fixed role set can express. The
existing Role and RoleBinding APIs are descriptive only; they do not
influence authorization decisions. Without configurable roles, providers in
regulated industries cannot satisfy the documented-roles and
separation-of-duties expectations of NIST 800-171/HIPAA assessments, and the
audit trail cannot attribute actions to roles.

## In Scope

- A granular capability catalog covering OSAC public API resource types,
  organized as the standard operations (get, list, create, update, delete,
  watch) per resource type [Clarify: R1.Q4]
- Named roles composed from catalog capabilities, authored by Cloud Provider
  Admins (platform-scoped) and by Tenant Admins for their own tenant, limited
  to capabilities the authoring admin holds [Clarify: R1.Q1, R3.Q1]
- Provider-composed roles may include administrator-level capabilities, with
  every such grant recorded [Clarify: R2.Q3]
- Role assignments granting users multiple named roles, with grants and
  revocations taking effect on the user's next request [Clarify: R1.Q3, R1.Q5]
- Separation of duties through configurable mutual exclusions, declared at
  platform level and at tenant level, enforced when a role is assigned
  [Clarify: R3.Q2]
- Audit role context on user actions: the named roles the user held and the
  specific role that authorized the action [Clarify: R3.Q5]
- Role management at runtime through the API, the `osac` CLI, and the web
  console, including live edits to roles that users hold and guarded deletion
  of roles with active assignments [Clarify: R2.Q1, R3.Q3]
- Automatic assignment of a seeded default role — equivalent to today's
  self-service allowlist — when a user is onboarded [Clarify: R3.Q4]
- Self-service visibility of the roles a user holds [Clarify: R2.Q1]

## Out of Scope

- How authorization is evaluated internally — the policy-engine mechanism is
  resolved in the design document [Clarify: R2.Q5]
- Complete audit-log integration — the role-context contract is delivered on
  existing activity surfaces, and full integration lands with OSAC-63
  [Clarify: R2.Q4]
- Fine-grained service-account privilege scoping, including deprivileging the
  template-publisher service account — tracked as OSAC-4386, which builds on
  this capability model
- Per-request role context ("acting as") — a user's held roles apply as-is to
  every action
- Role inheritance or nesting — roles are flat compositions of capabilities

## User Stories

### Cloud Provider Admin

- As a Cloud Provider Admin, I want to define named roles as compositions of
  granular capabilities — for example an "ISSO" role combining cluster
  read/write, audit-log read-only, and security-policy read/write — so that I
  can model my organization's compliance personas.
- As a Cloud Provider Admin, I want to compose roles that include
  administrator-level capabilities when my organization needs them, with every
  such grant recorded, so that flexibility does not come at the cost of
  oversight. [Clarify: R2.Q3]
- As a Cloud Provider Admin, I want to declare named roles mutually exclusive
  — for example ISSO and System Owner — so that no user can hold conflicting
  duties. [Clarify: R3.Q2]
- As a Cloud Provider Admin, I want to assign and revoke named roles with the
  change taking effect on the user's next request so that access changes apply
  immediately, without re-login or redeployment. [Clarify: R1.Q5]
- As a Cloud Provider Admin, I want the audit trail to record the named roles
  a user held and the specific role that authorized each action so that I can
  demonstrate role-based access control to auditors. [Clarify: R3.Q5]
- As a Cloud Provider Admin, I want to create, update, and delete named roles
  at runtime from the API, CLI, or console so that role management never
  requires a platform redeploy.

### Tenant Admin

- As a Tenant Admin, I want to author tenant-scoped named roles from the
  capabilities I hold so that I can tailor access for my organization's users
  without provider involvement. [Clarify: R1.Q1, R3.Q1]
- As a Tenant Admin, I want to declare mutual exclusions among my tenant's
  roles so that separation of duties reflects my organization's policies.
  [Clarify: R3.Q2]
- As a Tenant Admin, I want to assign provider-defined and tenant-scoped
  roles to users in my tenant so that each user's access is explicit and
  reviewable. [Clarify: R1.Q1]
- As a Tenant Admin, I want newly onboarded users to receive a default role
  automatically so that they can use self-service resources on day one
  without a manual grant. [Clarify: R3.Q4]

### Tenant User

- As a Tenant User, I want to see which roles I hold and what they permit so
  that I know what I can do without attempting actions to find out.
  [Clarify: R2.Q1]

## Assumptions

- The capability catalog's first deliverable covers user-facing public API
  resource types; capabilities governing internal service-to-service calls
  are not part of this feature.

## Dependencies

- **OSAC-63 — Activity and Audit Log API:** provides the audit trail that
  carries role context. This feature delivers the role-context contract on
  existing activity surfaces; complete integration lands when OSAC-63 ships.
  [Clarify: R2.Q4]
- **Existing Role and RoleBinding data model:** the foundation this feature
  builds on; today it is descriptive only and not wired into authorization
  decisions.
- **OSAC-4386 — Service Account Privilege Scoping:** builds on this feature's
  capability model and is blocked until it lands.
- **OSAC-3018 (HIPAA Compliance Readiness) and OSAC-2889 (EU Sovereignty &
  Compliance Readiness):** compliance outcomes that depend on this feature's
  named roles and audit role context.

---

## Provenance

Committed: commit @ prd 0.11.5 - e2b0d87, workspace prd/OSAC-3058 @ 9c329b8

> Authoring phases not recorded this session (commit-time snapshot only).

<!-- ai-workflow-provenance:{"schema_version":1,"provenance_kind":"commit_only","workflow":"prd","workflow_version":"0.11.5","ai_workflows":"e2b0d87","source_repo":"9c329b8","source_repo_branch":"prd/OSAC-3058","commits_behind_main":0,"commits_ahead_main":0,"main_ref":"main","phases":["commit"],"authoring_modes":["skill"],"context_changed":false,"origin_untracked":false} -->
