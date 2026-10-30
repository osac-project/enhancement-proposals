# Request MFA Usage from Brokered OIDC Server

| Field | Value |
|---|---|
| Author(s) | Juan Hernandez |
| Jira | [OSAC-3027](https://redhat.atlassian.net/browse/OSAC-3027) |
| Date | 2026-10-29 |
| Target milestone | 0.5 |

## Problem Statement

Today, OSAC sign-in through a tenant-managed OpenID Connect (OIDC) server does
not request multifactor authentication (MFA). Cloud Provider Admins and Tenant
Admins cannot choose separately for each tenant whether OSAC should request
MFA. Without that choice, a tenant-managed identity provider has no OSAC signal
to use when applying its own MFA policy; it remains responsible for deciding
whether MFA is performed. [User]

## In Scope

- The MFA request setting is configured separately for each tenant and applies
  to that tenant's brokered OIDC sign-ins when enabled. [User]
- The OSAC console lets a Cloud Provider Admin change the setting for each
  tenant and a Tenant Admin change it for their own tenant. The setting
  defaults to disabled for backward compatibility, so existing sign-in
  behavior is preserved until it is enabled. [User] [Clarify: R5.Q1]
- When enabled, OSAC requests generic MFA from the tenant-managed identity
  provider without specifying a particular method or assurance level. If the
  provider does not apply MFA, sign-in follows that provider's own policy. When
  disabled, OSAC sends no MFA request and brokered sign-in behavior remains
  unchanged. [Clarify: R1.Q2, R1.Q3, R3.Q1] [User]
- Tenant Admin guidance explains when OSAC sends the request for their tenant
  and that the tenant-managed identity provider decides whether MFA is
  performed. OSAC does not guarantee or enforce MFA. [Jira: OSAC-3027]
  [Clarify: R1.Q3, R1.Q5] [User]
- A Cloud Infrastructure Admin can verify during a brokered OIDC sign-in that
  OSAC sends the MFA request; per-sign-in evidence is not required. [Jira:
  OSAC-3027] [Clarify: R1.Q5]

## Out of Scope

- Platform-enforced MFA, including blocking sign-in when the identity provider
  does not apply MFA.
- Changes to MFA policy on tenant-managed identity providers.
- A single deployment-wide MFA setting; the request preference is managed
  separately for each tenant. [User]
- Per-sign-in evidence or reporting that claims MFA was performed.
- Automatic session logoff and configurable session timeouts.

## User Stories

### Cloud Provider Admin

- As a Cloud Provider Admin, I want to change the MFA request preference for
  each tenant I administer in the OSAC console, so that I can control whether
  its brokered sign-ins ask its identity provider to apply its MFA policy.
  [User] [Clarify: R5.Q1]

### Cloud Infrastructure Admin

- As a Cloud Infrastructure Admin, I want to verify during a tenant's brokered
  OIDC sign-in that OSAC sends the MFA request when that tenant's setting is
  enabled, so that I can validate the authentication setup. [Jira: OSAC-3027]

### Tenant Admin

- As a Tenant Admin, I want to change the MFA request preference for my tenant
  in the OSAC console, so that I can choose whether OSAC requests generic MFA
  during my tenant's brokered sign-ins. [User] [Clarify: R5.Q1]
- As a Tenant Admin, I want guidance on when OSAC requests MFA and what my
  identity provider decides, so that I can configure my tenant-managed
  provider accordingly. [Jira: OSAC-3027] [Clarify: R1.Q3, R1.Q5]

### Tenant User

- As a Tenant User, I want my sign-in to follow my organization's MFA policy
  when the identity provider honors OSAC's request, so that authentication
  follows my organization's policy. [Jira: OSAC-3027] [Clarify: R1.Q2,
  R1.Q3]

## Dependencies

- **OSAC UI:** The tenant-management workflow must expose the per-tenant setting
  to Cloud Provider Admins and Tenant Admins. [User] [Clarify: R5.Q1]
- [**OSAC-3024 — Red Hat Sovereign Enclave Integration**](https://redhat.atlassian.net/browse/OSAC-3024):
  Jira links OSAC-3027 as depending on this Feature.
- [**OSAC-4387 — Token Lifecycle Hardening**](https://redhat.atlassian.net/browse/OSAC-4387):
  Jira marks OSAC-3027 as blocked by this Epic.
- **Downstream linked work:** [OSAC-3018 — HIPAA Compliance Readiness](https://redhat.atlassian.net/browse/OSAC-3018),
  [OSAC-3019 — NIST SP 800-53 Compliance Readiness](https://redhat.atlassian.net/browse/OSAC-3019), and
  [OSAC-2889 — EU Sovereignty & Compliance Readiness](https://redhat.atlassian.net/browse/OSAC-2889)
  are linked as depending on OSAC-3027.

---

## Provenance

Authored: respond @ prd 0.11.5 - 7b2b8de, workspace main @ 6f3f72851
Phases: draft, revise, respond, respond, respond, respond

<!-- ai-workflow-provenance:{"schema_version":1,"provenance_kind":"session","workflow":"prd","workflow_version":"0.11.5","ai_workflows":"7b2b8de","source_repo":"6f3f72851","source_repo_branch":"main","commits_behind_main":0,"commits_ahead_main":0,"main_ref":"main","phases":["draft","revise","respond","respond","respond","respond"],"authoring_modes":["skill"],"context_changed":false,"origin_untracked":false} -->
