# Delegated tenant context for Cloud Provider Admins

| Field | Value |
|-------|-------|
| Author(s) | Daniel Erez |
| Jira | [OSAC-7125](https://redhat.atlassian.net/browse/OSAC-7125) |
| Date | 2026-11-22 |
| Target milestone | 0.6 |

## Problem Statement

Cloud Provider Admins need to support tenants using their own credentials, with
records showing who did what. OSAC does not yet provide an explicit, auditable
tenant-context workflow across API, CLI, and UI. This feature adds that workflow
using existing roles and permissions, without adding new tenant operations.

## In Scope

- **Choose tenant:** Choose which tenant requests apply to through API, CLI, and UI. Clearly show
  the selected tenant in CLI and UI.
- **Grant/revoke access:** Use existing roles and permissions to grant and revoke a Cloud Provider Admin's
  access to specific tenants and actions. Selecting a tenant does not grant access.
- **Enforce permissions:** Allow requests only when the admin's current permissions
  authorize them in the selected tenant, preserving existing project restrictions.
- **Keep identity and audit:** Preserve the Cloud Provider Admin's identity. Record the original admin, target
  tenant, and action in the audit log. Authorized provider staff can see which admin acted.
  Tenants see only that a Cloud Provider Admin acted, even when filtering by actor.
- **Switch correctly:** Ensure tenant data and existing permission checks reflect the selected tenant
  after switching.
- **Test:** Add automated tests for allowed and denied requests, tenant isolation,
  revocation, context switching, and audit attribution. Use existing VMaaS
  operations where needed.
- **Document:** Document how to grant access and use tenant context through API, CLI, and UI.

## Out of Scope

- Acting as a tenant user or using their credentials.
- Accessing tenants or performing actions without explicit permissions.
- Redesigning authorization already covered by OSAC-6936.
- Adding new tenant operations or full service workflows; VMaaS is used only
  where needed to validate the shared foundation.

## User Stories

### Cloud Provider Admin

- As a Cloud Provider Admin, I want to choose which tenant my requests apply to
  through the API, CLI, or UI so that I can support that tenant using my own
  identity and granted permissions.

### Tenant Admin

- As a Tenant Admin, I want Cloud Provider Admins to act in my tenant only with
  explicitly granted permissions so that my tenant's resources stay protected.
- As a Tenant Admin, I want to see which actions a Cloud Provider Admin performed
  in my tenant, without seeing the individual admin's identity, so that I can
  distinguish provider activity from tenant activity.

## Dependencies

Infrastructure can merge before OSAC-6936 and OSAC-63 integration. Tenant-context
access stays disabled until permissions limit what admins can do (OSAC-6936) and
audit records show who acted in which tenant (OSAC-63).

- **[OSAC-6936](https://redhat.atlassian.net/browse/OSAC-6936):** provides the
  tenant-scoped permissions and revocation this feature builds on.
- **[OSAC-3058 design](https://github.com/osac-project/enhancement-proposals/blob/main/enhancements/OSAC-3058-configurable-named-roles/design.md):**
  the accepted authorization model to follow, not an implementation blocker.
- **[OSAC-63](https://redhat.atlassian.net/browse/OSAC-63):** provides audit
  records identifying the admin, tenant, and action. Once tenant-context access is enabled,
  delegated actions may proceed even if audit events cannot be recorded or delivered.
  The full audit feature is not required.
- **[OSAC-6837](https://redhat.atlassian.net/browse/OSAC-6837):** related
  provider-admin sign-in work. Existing supported authentication can be used
  during development; its full IdP configuration workflow is not required.

---

## Provenance

Authored: draft @ prd 0.11.5 - ceab343, workspace codex/OSAC-7873-cel-exists @ 343345bae
Final: revise @ prd 0.11.5 - 760cf64, workspace codex/OSAC-7125-design @ 46531b8c4

> Context changed between draft and revise.

<!-- ai-workflow-provenance:{"schema_version":1,"provenance_kind":"session","workflow":"prd","workflow_version":"0.11.5","ai_workflows":"760cf64","source_repo":"46531b8c4","source_repo_branch":"codex/OSAC-7125-design","commits_behind_main":0,"commits_ahead_main":330,"main_ref":"main","phases":["draft","revise","revise","revise","revise","revise","revise","revise","revise","revise","revise","revise","revise","revise"],"authoring_modes":["skill"],"context_changed":true,"origin_untracked":false} -->
