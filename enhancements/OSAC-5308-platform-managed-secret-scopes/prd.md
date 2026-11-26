# Platform-managed Secret scopes

| Field | Value |
| --- | --- |
| Author(s) | Haim Tayrie |
| Jira | [OSAC-5308](https://redhat.atlassian.net/browse/OSAC-5308) |
| Date | 2026-11-25 |

## Problem Statement

Cloud Provider Admins need to associate Secrets of any supported type with a tenant and keep them private to the platform. Today, tenant-owned Secrets are visible to tenant users according to their permissions. Keeping a Secret private to the platform requires the global `system` scope. [OSAC-5425](https://redhat.atlassian.net/browse/OSAC-5425)

## In Scope

- Release 0.6 applies a reusable OSAC object scope model to all supported Secret types in Core. Document four scopes and who can create, list, read, update, delete, reference, or resolve Secrets in each. Use the existing Secrets policy, including type-specific restrictions, as the baseline. [Clarify: R1.Q1]
  - **Tenant-managed.** The tenant manages and can see the Secret under its policy.
  - **Shared.** Tenants can use the Secret through permitted resources.
  - **Platform-global.** The Secret is private to the platform, with no individual tenant owner.
  - **Tenant-associated platform-managed.** The Secret is private to the platform and has an explicit tenant owner.
- Cloud Provider Admins can manage protected Secrets across tenants through the web console, `osac` CLI, and private admin API. They can find tenant-associated Secrets by owner. [Clarify: R1.Q5]
- Authorized controllers can create, read, update, and delete tenant-associated protected Secrets. Only explicitly authorized platform services and controllers can resolve protected Secret references. A tenant-associated Secret is used for its owning tenant. [Clarify: R1.Q2]
- In both protected scopes, only authorized platform identities can see Secret metadata and values. A tenant viewing a resource may see that a Secret is configured, with identifying details redacted. [Clarify: R1.Q3]
- Tenant deletion stays pending until OSAC removes all protected Secrets associated with that tenant. [Clarify: R1.Q4]

## Out of Scope

- StorageBackend credential and hub kubeconfig integrations.
- Fine-grained access controls for protected Secrets and new Secret storage backends.

## User Stories

### Cloud Provider Admin

- As a Cloud Provider Admin, I want to manage Secrets for a tenant so that authorized platform services and controllers can use them for that tenant.
- As a Cloud Provider Admin, I want to assign a Secret to a tenant with access limited to the platform so that I can find that tenant’s Secrets during maintenance and offboarding.

### Cloud Infrastructure Admin

- As a Cloud Infrastructure Admin, I want OSAC to use the correct tenant’s Secret so that I can operate infrastructure safely across tenants.

### Tenant Admin / Tenant User

- As a Tenant Admin or Tenant User, I want to use provider-configured resources so that I can run workloads with the provider handling Secrets.

## Dependencies

- Vault stores Secret values. The design selects the Vault layout for the new scope.
- Tenant-aware references support selection and redaction of protected Secret references. [OSAC-5424](https://redhat.atlassian.net/browse/OSAC-5424)

---

## Provenance

Authored: respond @ prd 0.11.5 - 760cf64, workspace main @ f0a8211
Phases: draft, revise, respond, respond

<!-- ai-workflow-provenance:{"schema_version":1,"provenance_kind":"session","workflow":"prd","workflow_version":"0.11.5","ai_workflows":"760cf64","source_repo":"f0a8211","source_repo_branch":"main","commits_behind_main":0,"commits_ahead_main":0,"main_ref":"main","phases":["draft","revise","respond","respond"],"authoring_modes":["skill"],"context_changed":false,"origin_untracked":false} -->
