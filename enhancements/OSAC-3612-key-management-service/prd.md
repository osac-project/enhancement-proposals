# Key Management Service - Key Lifecycle Management

| Field       | Value   |
|-------------|---------|
| Author(s)   | Dakota Crowder |
| Jira        | [OSAC-3612](https://redhat.atlassian.net/browse/OSAC-3612) |
| Date        | 2026-09-10 |

## Problem Statement

OSAC can store secrets with envelope encryption, but Tenant Admins cannot manage encryption keys as tenant-scoped resources with distinct lifecycle states. Cloud Provider Admins likewise cannot manage provider-owned keys used by platform infrastructure. These administrators therefore lack a consistent way to create, rotate, revoke, destroy, and inspect the keys they administer, while Cloud Infrastructure Admins lack a common product experience for observing key health. Without a consumer-neutral key-management backbone, each consuming service must provide its own key handling and backend integration, leading to duplicated behavior and inconsistent administrative controls.

## In Scope

- A consumer-neutral key-management capability for tenant-owned and provider-owned keys, exposed through the OSAC API and CLI, with create, view, rotate, revoke, and destroy lifecycle operations. [Clarify: R1.Q1, R1.Q5] [User]
- Tenant isolation that restricts Tenant Admins to keys belonging to their tenant without introducing a new restriction on existing Cloud Provider Admin access. [Clarify: R1.Q2] [User]
- Cloud Provider Admin configuration of platform key backends and policies, applied transparently so tenants do not configure or select KMS infrastructure. [Clarify: R2.Q1, R3.Q1]
- Key versions and confirmed lifecycle states, with prior versions retained for existing encrypted data. A lifecycle request reports confirmed success or an actionable failure; after an uncertain outcome, the user can see the last confirmed state and is told that provider verification may be needed. Consumers associate with a stable logical key; successful rotation promotes a new active version without requiring consumers to update that association. [Clarify: R1.Q4] [User: simplify synchronous lifecycle]
- Revocation blocks normal infrastructure encryption, decryption, and new consumer associations across all retained key versions, making associated data inaccessible to consumers while retaining the key material for an explicit authorized recovery process. Unsupported operations return an actionable failure through the API and CLI. Permanent recovery prevention requires key destruction. [Clarify: R2.Q3] [User]
- Consumer-neutral key associations and lifecycle safeguards that can support downstream OSAC services without bringing service-specific integration into this feature. [Clarify: R1.Q3, R1.Q5, R2.Q3] [User]
- End-to-end coverage of the supported API and CLI key-management journeys.

## Out of Scope

- A key-management UI. [Clarify: R1.Q1]
- Direct key lifecycle management by Tenant Users; this feature limits tenant-owned key lifecycle authority to Tenant Admins. [Clarify: R1.Q2] [User]
- Provider-managed shared or default keys made available for tenant consumption. [User]
- Storage-specific Vault KMIP integration and key binding to volumes, file shares, or object buckets; these belong to OSAC-2389. [Jira: OSAC-2389] [Clarify: R1.Q5]
- Automated key-rotation policies.
- Hardware Security Module integration beyond Vault capabilities.
- Tenant configuration or selection of KMS infrastructure, including tenant-specific backend defaults. [Clarify: R3.Q1]
- Client-side encryption, cross-site key replication, and multi-region key management. [Jira: OSAC-2389]

## User Stories

### Cloud Provider Admin

- As a Cloud Provider Admin, I want to create and view provider-owned encryption keys through the API or CLI so that platform infrastructure can use centrally managed keys. [User]
- As a Cloud Provider Admin, I want to rotate, revoke, and safely destroy provider-owned keys with the same visible lifecycle states and safeguards available for tenant-owned keys so that I can manage their complete lifecycle. [User]
- As a Cloud Provider Admin, I want to configure platform key backends so that tenants can manage keys without needing to understand the supporting infrastructure. [Clarify: R2.Q1, R3.Q1]
- As a Cloud Provider Admin, I want to configure platform key policies so that tenant-owned and provider-owned key management follows provider requirements across consuming services. [Clarify: R2.Q1] [User]

### Cloud Infrastructure Admin

- As a Cloud Infrastructure Admin, I want read-only visibility into platform KMS health and availability so that I can identify conditions affecting key lifecycle operations without gaining control over tenant-owned or provider-owned keys. [Clarify: R2.Q2] [User]

### Tenant Admin

- As a Tenant Admin, I want to create tenant-scoped encryption keys through the API or CLI so that my tenant's resources can use centrally managed keys without requiring KMS infrastructure configuration. [Clarify: R1.Q1, R1.Q2, R3.Q1]
- As a Tenant Admin, I want to view each key's lifecycle state and active version so that I can safely manage keys in my tenant. [Clarify: R2.Q4] [User]
- As a Tenant Admin, I want Rotate to report when a new version is confirmed, or tell me when its outcome needs verification, without requiring associated consumers to select or adopt that version. [Clarify: R1.Q4] [User: simplify synchronous lifecycle]
- As a Tenant Admin, I want to revoke a logical key across all retained versions so that associated data becomes inaccessible to normal infrastructure use when a project or resource is decommissioned, while the key material remains available through an explicit authorized recovery process. [Clarify: R2.Q3] [User]
- As a Tenant Admin, I want to destroy a key permanently when it is not in use and receive an actionable rejection when it remains in use so that obsolete key material can be removed without breaking a consumer. [Clarify: R1.Q3, R2.Q3, R3.Q2] [User]
- As a Tenant Admin, I want downstream services to associate with a stable logical key so that key rotation does not require each consumer to select or update a key version. [Clarify: R1.Q5] [User]
- As a Tenant Admin, I want each lifecycle operation to report confirmed success or an actionable failure, and to distinguish the last confirmed key state from an uncertain provider outcome so that I can decide when verification is needed. [Clarify: R3.Q2] [User: simplify synchronous lifecycle]

## Dependencies

- **Secret Management (OSAC-1567):** Provides the Vault-based secret-management foundation on which key lifecycle management builds.
- **Vault:** Provides key storage and lifecycle capabilities used by the platform KMS.
- **Per-Project Encryption Key Management (OSAC-2389):** Depends on this feature's consumer-neutral lifecycle and association capabilities before adding storage-specific KMIP integration and resource binding.
- **Downstream OSAC services:** Consumers depend on a consistent way to associate their resources with managed keys; service-specific integration is outside this feature.

---

## Provenance

Authored: draft @ prd 0.10.1 - a7f4aa1, workspace main @ b9575896d
Final: revise @ prd 0.11.3 - cc0daa6, workspace osac-5618/allow-system-secrets @ 744fd60b5

> Context changed between draft and revise.

<!-- ai-workflow-provenance:{"schema_version":1,"provenance_kind":"session","workflow":"prd","workflow_version":"0.11.3","ai_workflows":"cc0daa6","source_repo":"744fd60b5","source_repo_branch":"osac-5618/allow-system-secrets","commits_behind_main":0,"commits_ahead_main":1,"main_ref":"main","phases":["draft","draft","respond","respond","revise","revise","respond","revise","revise"],"authoring_modes":["skill"],"context_changed":true,"origin_untracked":false} -->
