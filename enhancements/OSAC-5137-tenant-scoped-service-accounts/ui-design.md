# UI Design — OSAC-5146

**Story:** OSAC-5146 — UI Design - API for tenant-scoped service accounts backed by Keycloak OIDC clients

**Date:** 2026-11-18

**Feature:** OSAC-7239 (current Jira parent; published planning documents refer to OSAC-5137)

## Summary

Tenant Admins can create, list, view, update supported labels, and delete service accounts. Account details show lifecycle state, role grants, and credential controls. The role picker offers `tenant-automation`, `tenant-idp-manager`, and `tenant-admin`; other roles are not shown. The Credentials card loads the account’s Secret automatically when rendered. The client secret is masked in a password field by default and can be shown. Provisioning and rotation are asynchronous, so the page shows the latest observed state, uses existing request/query timeouts. Longer term, Secret-change events will trigger a fresh credential read. [PRD: In Scope] [User direction: repeated credential retrieval; no custom polling]

Role access is managed with a **Permissions** card on each subject’s details page. Service-account grants stay on service-account details; user grants move to User details. Replace the generic Role Bindings page with a Users list and details flow. Preserve other subjects when changing a shared binding. [User decision: role grant surfaces]

This plan follows the current repository API. It does not use the published design’s direct service-account role field, display name or description, or inline secret response. The UI follows the user’s direction to allow repeated credential reads, while PRD clarification D6 still says one-time disclosure. Reconcile that requirement before publishing. No UX handoff is available, so interaction details follow the existing resource patterns. [Design: IC-1–IC-5] [User direction: current API is primary]

## Component Architecture

This work implements the service-account inventory and adds detail surfaces for account and user role management.

| UI surface | Design decision |
|------------|-----------------|
| Service-account list | Implement the tenant-scoped card/table list. Use `usePermissions` to gate the list, creation, and deletion by their respective API permissions. Link permitted rows to account details. Show name, creation time, lifecycle state, and deletion state. |
| Service-account create | Collect the account name and supported labels. Show the returned lifecycle state; do not expect credentials in the create response. |
| Service-account details | Show account metadata and lifecycle state. Provide label editing, deletion, a **Permissions** card, and a **Credentials** card. Names and server-managed status are not editable. |
| Service-account Permissions card | Show assigned roles and binding state. Offer **Grant role** only when the account is ready and not deleting. The role picker offers the tenant-scoped service-account roles `tenant-automation`, `tenant-idp-manager`, and `tenant-admin`, using each role’s catalog title and description; other roles are not shown. Revoke this account’s reference while preserving any other subjects in a shared binding. Until OSAC-7873 is fixed, load all binding pages and match the account locally; then switch to a CEL subject filter. |
| Users list and details | Replace generic Role Bindings navigation with a tenant-scoped Users list and read-only identity details. Do not add user create, edit, or delete actions. |
| User Permissions card | Show roles assigned to the selected user and offer **Grant role**. Grant or revoke roles only from User details; preserve other subjects in a shared binding. |
| Credentials card | Automatically load the current client ID and secret when the card mounts. Show the secret in a masked password field by default, with a control to reveal it. Keep values transient and clear them on unmount or after rotation is requested; a later mount can fetch them again. |

RoleBindings.List accepts CEL filters, but the current filter implementation cannot match an ID nested inside its repeated user or service-account reference objects. Until OSAC-7873 is fixed, the Permissions cards load all tenant-visible binding pages and select the current subject in the UI; afterward they use a CEL subject filter. RoleBinding pending and failed states remain visible. Public role data does not identify service-account eligibility, so the account grant dialog filters the role catalog to the current tenant-scoped allowlist: `tenant-automation`, `tenant-idp-manager`, and `tenant-admin`; other roles are not shown.

Use these lifecycle responses:

| Result | UI response |
|--------|-------------|
| Account provisioning is pending | Show the pending state; and keep account role grants unavailable until the account is ready. Load credentials as soon as the credential Secret reference exists |
| Provisioning fails | Show the server message and offer manual refresh. |
| Account deletion is pending | Show a deleting state until the resource is removed. |
| RoleBinding is pending or failed | Show its synchronization state and any returned message in the Permissions card. |
| Rotation request is accepted | Use the default polling mechanism to determine when the secret was rotated - by comparing the referenced secret's content |

## Persona-Aware Decomposition

The UI does not infer the signed-in user’s permissions from role names or branch on persona. It uses `usePermissions` to determine which operations the user can perform. The service-account grant picker separately filters role catalog entries by the explicit tenant-scoped allowlist above. “Tenant Admin” describes the PRD’s intended workflow, not a frontend authorization check. Users with the same API permissions see the same controls regardless of their role label.

- Show the service-account list when `ServiceAccounts.List` is allowed; gate creation and deletion with `ServiceAccounts.Create` and `ServiceAccounts.Delete`.
- Gate account details, label updates, rotation, and credential retrieval with their corresponding API permissions.
- Gate Users list/details and role grant/revocation with the relevant Users and RoleBindings permissions.
- Keep the server authoritative; UI permission checks control navigation and action availability.

## Accessibility Implementation

- Label account and user identity fields, role controls, credential actions, and copy buttons.
- Expose loading, permission denial, provisioning failure, deletion, and role synchronization states to assistive technology.
- Load credentials with the card, but mask the client secret in a password field by default. Provide an accessible show/hide control, label the client ID and secret separately, and do not announce the secret value.
- Use keyboard-operable grant dialogs, restore focus to the invoking control when they close, and keep focus stable during manual refresh.
- Associate form errors with the affected field and announce them without unexpectedly moving focus.

## Testing Strategy

Use UI interaction tests with mocked Connect responses. Cover the account and user flows, permission outcomes, and asynchronous states. Backend API tests do not replace browser-level coverage.

| Scenario | Setup and action | Expected result |
|----------|------------------|-----------------|
| Service-account lifecycle | Create an account, inspect its pending and ready states, edit labels, and delete it. | Only supported fields are submitted; no credentials are expected from Create; deletion remains visible while cleanup is pending. |
| Service-account role management | Open the grant dialog for a ready account, inspect the available roles, grant and revoke a role, including a binding shared with another subject. Try granting while the account is not ready. | The picker offers only `tenant-automation`, `tenant-idp-manager`, and `tenant-admin` with catalog titles and descriptions; other roles are not shown. Granting is disabled until the account is ready; only this account’s reference is removed; other subjects remain. Binding synchronization state is shown. |
| Users and user role management | Open the Users list and a User detail; grant and revoke a role from the user’s Permissions card. | Identity fields are shown; role changes are scoped to that user; generic Role Bindings navigation and editing are absent. |
| Credentials and rotation | Mount the card, toggle secret visibility, request rotation, and later receive a Secret-change event. | Mounting loads credentials; toggling visibility does not call the API; the secret starts masked; values stay out of shared cache and storage. Clear the old value after rotation is accepted. In the short term, later reads may still be stale; in the event-driven flow, the event triggers a fresh read without polling. |
| Binding lookup and permissions | Return more than one page of tenant bindings and a mix of subjects; deny ServiceAccounts.List, Create, and Delete checks; compare users with different role labels but identical permission results. | The UI loads all pages and preserves unrelated binding subjects. Denied list/create/delete actions are unavailable, and users with the same permissions see the same controls regardless of role label. |

No UI implementation or browser-test owner has been identified under the parent epic. Assign those owners before treating the proposed coverage as scheduled work.

## Acceptance Criteria Mapping

OSAC-5146 has no issue-level acceptance criteria. The table maps the PRD outcomes, published design, and user decisions to observable behavior.

| Source | Observable result | Verification |
|--------|-------------------|--------------|
| PRD: Tenant Admin scope | A Tenant Admin can create, list, view, update supported labels, and delete service accounts in the active tenant. | Account lifecycle interaction checks and permission-denied cases. |
| Design: IC-1, IC-2 | Account details show lifecycle state and provide credential retrieval and rotation actions. | Pending, ready, failed, repeated retrieval, and rotation-request checks. |
| User decision: Permissions card on service-account details | A Tenant Admin grants or revokes `tenant-automation`, `tenant-idp-manager`, or `tenant-admin` from account details, with no direct role field on the account. Other roles are not shown in this tenant flow. | Check the role picker’s choices and catalog descriptions, readiness gating, and shared-binding behavior. |
| User decision: Users details for user grants | The former generic Role Bindings surface becomes Users list/details, and user grants are managed on the selected User detail. | Navigation and user role grant/revoke checks. |
| PRD: credential-use scope | Credential consumers use issued credentials for token requests; the design adds no separate management workflow for that task. | Confirm credential-use guidance is separate from the management UI; control visibility follows API permissions, not role labels. |
| User decision: repeated retrieval and no custom polling | Credentials load when the card mounts and can be fetched again later. Longer term, Secret-change events trigger a fresh read; no polling loop or custom timeout is added. | Mount, repeated-read, and event-triggered refresh checks. |
| PRD: tenant isolation | Lists, details, and mutations remain scoped to the active tenant and authorized operations. | Permission-denied and tenant-isolation checks at the UI/API boundary. |

## API Findings

The current API supports the main account, user, role, binding, credential, and permission flows through its public services. Users list/details are available to the UI through Connect. The current account model has no direct role field, display name, or description; access is represented by RoleBindings, and credentials are read from a separate Secret. [Current API] [Design: IC-1–IC-5]

Current API limitations remain. Although RoleBindings.List accepts CEL filters, the current implementation does not support matching an ID nested inside the repeated user or service-account reference objects. This is tracked by OSAC-7873: until it is fixed, both Permissions cards load all pages and filter locally; afterward they switch to CEL filtering (medium; filtering-d78032bc73e6). Public role data has no service-account eligibility field, so the UI must mirror the backend allowlist: tenant-scoped account grants support `tenant-automation`, `tenant-idp-manager`, and `tenant-admin`; all other roles are excluded from the picker (medium; field-7191a4e2afad). Rotation is asynchronous, updates the existing Secret, and exposes no public completion state; an immediate read may still return the old value (high; state-1a064f851d74)

The published design and PRD do not fully match the current contract. The design describes direct service-account roles, optional display metadata, and inline credential responses; those shapes are unavailable. The PRD’s one-time credential disclosure conflicts with the user’s direction and the API’s repeatable credential read. Users list/detail REST annotations are also not registered on the REST gateway, but the current UI uses the registered Connect service. Reconcile the PRD disclosure policy before publishing.

---

## Provenance

Authored: plan @ ui-design 0.1.0 - cd88680, workspace sa_list_page @ 0acc57bc1 (dirty)
Final: revise @ ui-design 0.1.0 - cd88680, workspace bugfix/OSAC-7675-catalog-launch-routes-main @ 838b5cad2

> Context changed between plan and revise.

<!-- ai-workflow-provenance:{"schema_version":1,"provenance_kind":"session","workflow":"ui-design","workflow_version":"0.1.0","ai_workflows":"cd88680","source_repo":"838b5cad2","source_repo_branch":"bugfix/OSAC-7675-catalog-launch-routes-main","commits_behind_main":0,"commits_ahead_main":115,"main_ref":"main","phases":["plan","review-api","review-api","review-api","review-api","revise","revise","revise","revise","revise","revise","revise","revise","revise","revise","revise","revise","revise"],"authoring_modes":["skill"],"context_changed":true,"origin_untracked":false} -->
