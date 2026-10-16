# Tenant-Scoped Service Account Management

| Field | Value |
|---|---|
| Author(s) | Daniel Erez |
| Jira | [OSAC-5137](https://redhat.atlassian.net/browse/OSAC-5137) |
| Date | 2026-10-15 |
| Target milestone | 0.4 (tentative; not a Dev Preview requirement) [Clarify: R1.Q1] |

## Problem Statement

OSAC supports human authentication through Keycloak Organizations, but Tenant Admins cannot create and manage tenant-scoped machine identities for automation. CI/CD pipelines that call OSAC APIs therefore lack a supported way to authenticate without a human user's interactive login, making it harder to assign and maintain dedicated permissions. This capability also unblocks the tenant-scoped identities needed by downstream storage workflows.

## In Scope

- Tenant Admins can create, get, list, update, and delete their tenant's service accounts through the Fulfillment API, UI, and scriptable `osac` CLI. Updates are reflected in later get and list results. Through all three surfaces, Tenant Admins can grant and revoke the same tenant-scoped OSAC roles available for tenant users. [Clarify: R1.Q4, R2.Q2]
- A Tenant Admin's service-account list shows only accounts belonging to that tenant; attempts to manage another tenant's account are denied. A token issued to a tenant-owned service account can access only resources in that account's tenant that its assigned roles permit. Requests to another tenant's resources or to resources outside those roles are denied across BMaaS, CaaS, VMaaS, and MaaS; service-specific resource workflows do not change.
- Tenant Admins receive a service account's client ID and initial secret when creating it; the initial secret is disclosed only once. Get, list, and updates that do not regenerate a secret redact it. Through the API, UI, or CLI, Tenant Admins can regenerate its secret; each replacement is shown once, and the previous secret can no longer be used to obtain new tokens. [Clarify: R3.Q1, R3.Q2]
- Tenant Admin documentation explains account and role management and credential rotation through the UI, API, and CLI. Tenant User documentation explains how to use the client ID and secret to obtain a token and call permitted OSAC APIs.

## Out of Scope

- Quotas or limits on the number of service accounts a tenant may create. OSAC-4500 covers the quota foundation for resource dimensions; service-account counts are not included in that proposal and should be considered separately.
- Zero-downtime rotation in which previous and replacement secrets are both valid during a transition period, the previous secret expires automatically at the end of that period, and Tenant Admins can revoke the previous secret early while keeping the replacement active. This behavior is deferred from this Feature.
- Provider-wide service-account inventory and historical audit records for creation, updates, role changes, secret rotation, or deletion.
- Authentication and credential provisioning for OSAC-managed clients that call the Fulfillment Service. OSAC-5342 covers client inventory, token-source correction, and documentation of credential supply; tenant-linked service-account API creation is out of scope there and remains here.
- Direct access to the Keycloak administration console for tenants.
- Automatic credential provisioning or delivery to tenant clusters and CSI workloads; OSAC-1644 covers cross-cluster authentication and TLS trust, while OSAC-4197 tracks tenant-scoped CSI identity and credential delivery.
- Federation of service accounts with external identity providers.
- Fine-grained per-resource authorization beyond the existing OSAC role model.

## User Stories

### Tenant Admin

- As a Tenant Admin, I want to create a service account and obtain its client ID and generated secret, so that automation can call OSAC APIs without using a human user's credentials.
- As a Tenant Admin, I want to list, view, update, and delete my tenant's service accounts, so that I can manage machine identities as automation is introduced, changed, or retired.
- As a Tenant Admin, I want to grant and revoke the tenant-scoped OSAC roles available for tenant users, so that a service account receives only the access needed by its automation.
- As a Tenant Admin, I want to regenerate a service account's client secret so that the previous secret cannot obtain new tokens, allowing me to replace a credential that is no longer safe to use.

### Tenant User

- As a Tenant User, I want to use a service account's client ID and secret to obtain an access token, so that my automation can call permitted OSAC APIs for my tenant without human interactive login.

## Dependencies

- **Keycloak:** Provides OIDC confidential clients and the client credentials flow used by tenant service accounts.
- **OSAC-1644 (related):** Covers cross-cluster authentication and TLS trust, including connectivity and credential provisioning for tenant-cluster clients. Those workflows remain separate from this Feature's tenant-administered service-account lifecycle.
- **OSAC-4197 (downstream):** Depends on OSAC-5137 for tenant-scoped CSI identities and credential delivery, and on OSAC-1644 for cross-cluster connectivity.

---

## Provenance

Authored: revise @ prd 0.11.5 - 1c6e8de, workspace OSAC-6083-metering-keycloak-auth @ 10a284b20
Phases: draft, revise, revise, revise

<!-- ai-workflow-provenance:{"schema_version":1,"provenance_kind":"session","workflow":"prd","workflow_version":"0.11.5","ai_workflows":"1c6e8de","source_repo":"10a284b20","source_repo_branch":"OSAC-6083-metering-keycloak-auth","commits_behind_main":null,"commits_ahead_main":null,"main_ref":"main","phases":["draft","revise","revise","revise"],"authoring_modes":["skill"],"context_changed":false,"origin_untracked":false} -->
