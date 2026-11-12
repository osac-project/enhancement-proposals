# Configure an IdP for Cloud Provider Admins

| Field       | Value |
|-------------|-------|
| Author(s)   | CrystalChun |
| Jira        | [OSAC-6837](https://redhat.atlassian.net/browse/OSAC-6837) |
| Date        | 2026-11-05 |
| Target milestone | 0.5 |
| Affected area | OSAC Core platform administration |

## Problem Statement

Cloud Provider Admins currently lack a supported way to configure an external
IdP for provider users. They need to let multiple provider personnel
authenticate while granting each person only the provider capabilities
explicitly assigned to them. Authentication must establish identity without
granting provider-administration access. Provider IdP bootstrap and recovery
must use the existing OSAC-1030 System Organization break-glass account.
[User] [Clarify: R9.Q1]

## In Scope

- Configure OSAC's connection to an IdP through OIDC using the UI, API, or
  CLI. Reuse the existing OSAC-1030 System Organization break-glass account,
  `system-osac-break-glass`, in the System Organization's Keycloak realm. It
  has the `tenant-idp-manager` realm role and is not a regular JIT-provisioned
  system-tenant user. Do not create a separate provider-only account. Use this
  account for provider IdP configuration and recovery, including correcting a
  failed configuration update. The pre-existing user with the
  `cloud-provider-admin` role is the initial provider user. The break-glass
  account can grant and remove provider roles after bootstrap and is not the
  day-to-day provider administrator. [Clarify: R1.Q1, R1.Q2, R6.Q1, R9.Q1,
  R15.Q1, R18.Q1; User: follow-up clarification]
  [Jira: OSAC-1030]
- Validate a new or changed IdP configuration before accepting it. A valid
  configuration becomes the current provider IdP configuration when saved;
  no second enable action is required. If initial validation fails, do not
  save or apply the configuration, and keep `system-osac-break-glass` usable
  to correct and retry. If an update fails validation, preserve the previous
  configuration. Return actionable feedback in either case. [Clarify: R1.Q5,
  R11.Q1, R18.Q1; User]
- Treat Cloud Provider Admin as the provider-user persona; assigned roles
  determine authorization. IdP authentication and JIT user creation alone
  grant no provider permissions. Explicit provider-scope `RoleBinding`
  assignments grant capabilities, including full provider administration
  (`cloud-provider-admin`), provider read-only access
  (`cloud-provider-reader`). The break-glass account can grant and remove
  provider roles after bootstrap. The pre-existing user with
  `cloud-provider-admin` is the initial provider user. Retain the
  OSAC-1030 System Organization identity and role model; this feature does not
  replace it. Provider-scope user `RoleBinding` assignments are authoritative
  and map one-to-one to same-named roles. IdP group or claim membership is not
  an alternate provider-role grant. [User; Clarify: R10.Q1, R14.Q1]
  [Jira: OSAC-1030]
- Give all regular provider IdP users access to the internal `system` tenant,
  including users with no provider-role assignment. System-tenant access
  provides tenant scope for system-tenant items; it does not grant
  `cloud-provider-admin`, `cloud-provider-reader`, IdP-management, or global
  administration capabilities. Grant those provider capabilities only
  through explicit provider-role assignments. [User: follow-up clarification]
- Reuse the tenant break-glass credential Secret flow for
  `system-osac-break-glass`. During system bootstrap, store the temporary
  username and password in a Secret scoped to the internal `system` tenant.
  An authorized platform administrator or controller can retrieve it through
  the existing Secrets Get authorization path; do not rely on a tenant-create
  response or confirmation dialog for this automatically created account.
  The account holder must change the temporary password at first login. If
  credentials are lost or need rotation, an authorized Keycloak administrator
  can reset the password through the Keycloak Admin Console or API; the
  account holder changes the temporary password at the next login. No
  periodic rotation interval is defined by this feature. [Clarify: R13.Q1]
  [Jira: OSAC-1030]
- Redact an identity provider's client secrets from API responses, UI and
  CLI output, errors, and logs. Omitting a secret in an update preserves the
  stored value. Supplying a replacement rotates the secret only when the
  updated configuration validates and is saved; a failed update preserves
  the previous configuration and secret. [User; Clarify: R18.Q1]
- Support sign-in through the configured IdP for regular provider users. Limit
  local username-and-password authentication to
  `system-osac-break-glass` for provider IdP bootstrap and recovery; it is not
  an alternate sign-in path for regular provider users. [Clarify: R12.Q1]
- Provide user-facing documentation for provider IdP configuration and
  sign-in. Identify the recovery account as `system-osac-break-glass` in the
  System Organization's Keycloak realm and describe its credential delivery
  and reset/rotation process. [Jira: OSAC-6837; Clarify: R9.Q1]

## Out of Scope

- Tenant-specific IdP configuration or changes to tenant authentication.
- Enable/disable lifecycle management for a configured provider IdP. This
  belongs to a separate feature. [Clarify: R18.Q1]
- Using internal `system`-tenant access as an implicit provider-role or
  provider-administration grant. [User: follow-up clarification]
- IdP group or claim mapping as a provider authorization mechanism; provider
  access is assigned through explicit provider-scope `RoleBinding` objects.
  [User]
- Authentication protocols other than OIDC. [Jira: OSAC-6837; Clarify: R1.Q2,
  R6.Q1]

## User Stories

### Cloud Provider Admin

- As a Cloud Provider Admin, I want to authenticate through the configured
  provider IdP and access system-tenant items while receiving only explicitly
  assigned provider roles, so that tenant scope and provider privileges stay
  separate. [User: follow-up clarification]
- As a Cloud Provider Admin using the System Organization break-glass account,
  I want to configure or recover the provider IdP and grant or remove provider
  roles after bootstrap so that provider access can be maintained and
  recovered.
  The pre-existing user with `cloud-provider-admin` is the initial provider
  user. [Clarify: R9.Q1; User: follow-up clarification] [Jira: OSAC-1030]
- As a Cloud Provider Admin configuring the IdP, I want invalid updates to
  preserve the previous working configuration and keep client secrets
  private so that a configuration error does not expose credentials or
  prevent recovery. [Clarify: R1.Q5; User]

## Dependencies

- **External IdP:** OSAC connects to the configured IdP through OIDC for
  provider-user sign-in. [Clarify: R1.Q2, R6.Q1]
- **Existing tenant identity behavior:** The provider flow uses JIT identity
  discovery and explicit role assignment. All regular provider users have
  access to the internal `system` tenant for tenant-scoped items, while that
  membership alone grants no provider role or provider-administration
  capability. [User: follow-up clarification]
- **System Organization and API authorization:** Keep the OSAC-1030 System
  Organization model. Provider human-user `RoleBinding` assignments map to
  same-named role. Fulfillment APIs currently
  authorize ordinary JWT users through the shared OPA/Rego policy over realm
  role and group claims; the separate RoleBinding resolver applies to managed
  service accounts. The current policy recognizes `cloud-provider-reader` as
  a reader but does not recognize `cloud-provider-admin` as an admin role.
  This feature must align the shared policy with provider roles and ensure
  provider API components use the same role-to-capability decisions. For
  provider-user requests, the generic `admins` group rule must not bypass
  provider-role assignment. Provider-admin and provider-reader capabilities
  must not be granted solely by IdP authentication, group membership, or
  `system`-tenant membership. [Clarify: R10.Q1; User: follow-up clarification]
  [Jira: OSAC-1030]
- **OSAC-1030 System Organization:** Provides the existing
  `system-osac-break-glass` account and its `tenant-idp-manager` role. This
  feature uses the existing tenant break-glass credential Secret flow for its
  initial credential and recovery process. [Clarify: R9.Q1, R13.Q1, R15.Q1]
  [Jira: OSAC-1030]

---

## Provenance

Authored: revise @ prd 0.11.5 - 70405a6, workspace main @ cb801c5ab
Final: revise @ prd 0.11.5 - cd88680, workspace fix/omit-break-glass-password @ e2f2bbe78

> Context changed between revise and revise.

> This document's phase history does not include an initial /draft — structure was not verified against the template from origin.

<!-- ai-workflow-provenance:{"schema_version":1,"provenance_kind":"session","workflow":"prd","workflow_version":"0.11.5","ai_workflows":"cd88680","source_repo":"e2f2bbe78","source_repo_branch":"fix/omit-break-glass-password","commits_behind_main":0,"commits_ahead_main":1,"main_ref":"main","phases":["revise","revise","revise","revise","revise","revise","revise","revise","revise","revise","revise","revise","revise","revise","revise","revise","revise","revise","revise","revise","revise","revise"],"authoring_modes":["skill"],"context_changed":true,"origin_untracked":true} -->
