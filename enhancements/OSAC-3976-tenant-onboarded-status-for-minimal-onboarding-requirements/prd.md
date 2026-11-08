# Tenant On-Boarded Status for Minimal Onboarding Requirements

| Field | Value |
|---|---|
| Author(s) | Shirel Bar Lev |
| Jira | [OSAC-3976](https://redhat.atlassian.net/browse/OSAC-3976) |
| Date | 2026-11-06 |
| Target milestone | 0.5 |
| OSAC area | Shared tenant-level status with role-scoped information |

## Problem Statement

Today, after a tenant is created and onboarding runs, there is no consolidated status showing whether the four minimal onboarding requirements are complete. Cloud Provider Admins must inspect subsystems individually to locate failures, while Tenant Admins and Tenant Users cannot tell whether their tenant is ready for use. Without a shared status, administrators spend time finding failed requirements and tenant users lack a clear readiness signal before provisioning resources.

## In Scope

- For `cloud-provider-admin`, show a detailed tenant onboarding status for networking, workload storage, Secret Storage, and the breakglass account. Show **Failed** if any component failed or is unavailable; otherwise show **In Progress** if at least one component is pending or in progress; show **On-Boarded** only when all four components succeed. Secret Storage covers completion of initial storage setup for tenant credentials. Breakglass completion requires the account to exist and its credentials to be saved securely. [Clarify: R2.Q1, R3.Q1, R5.Q1, D13, D14]
- Restrict the detailed onboarding status, component breakdown, and failure reasons to `cloud-provider-admin`. For their own tenant, `tenant-admin` and `tenant-user` see only **On-Boarded** or **Not On-Boarded**; they do not see component states, progress, or failure reasons. Apply these visibility rules consistently through the UI, API, and CLI. [User, Clarify: R2.Q3, D12, D15, D16]
- When a component status changes, update the overall status and role-appropriate views automatically without requiring a manual refresh. [User, Clarify: R4.Q1]
- For `cloud-provider-admin` component details, show a simple **In Progress** state while a component is progressing; do not show detailed progress. Show **Succeeded** or **Failed** when the component reaches a result. [Clarify: R2.Q5]

## Out of Scope

- Tenant readiness beyond the four minimal onboarding requirements, including monitoring and health-check indicators.
- Encryption-key provisioning and key lifecycle management. [User scope update; Clarify: D13]
- Multihub onboarding complications.
- Automatic remediation of failed onboarding components.
- User-triggered retries from the onboarding status view.

## User Stories

### Cloud Provider Admin (`cloud-provider-admin`)

- As a Cloud Provider Admin, I want to see the full breakdown of each minimal onboarding requirement and the full failure reason for each failed requirement, so I can identify which requirement failed and decide how to address it. [User, Clarify: R1.Q4, R3.Q2, D16]

### Tenant Admin (`tenant-admin`)

- As a Tenant Admin, I want a simple **Not On-Boarded** / **On-Boarded** indicator for my tenant, so I know whether it is ready for use without contacting the Cloud Provider. [Clarify: R5.Q2, D16]

### Tenant User (`tenant-user`)

- As a Tenant User, I want a simple **Not On-Boarded** / **On-Boarded** indicator on my tenant, so I know whether my workspace is ready before I start provisioning resources. [Clarify: R5.Q2, D16]

## Dependencies

- **Networking, workload storage, Secret Storage, and breakglass account onboarding:** Their status outcomes are needed to determine the overall tenant onboarding status.

---

## Provenance

Authored: revise @ prd 0.11.5 - unknown (not a git repository), workspace main @ 0d428d098
Final: revise @ prd 0.11.5 - unknown (shared workflow recipes unavailable), workspace main @ 0d54f8b27
Phases: draft, revise

<!-- ai-workflow-provenance:{"schema_version":1,"provenance_kind":"session","workflow":"prd","workflow_version":"0.11.5","ai_workflows":"unknown (shared workflow recipes unavailable)","source_repo":"0d54f8b27","source_repo_branch":"main","commits_behind_main":null,"commits_ahead_main":null,"main_ref":"main","phases":["draft","revise"],"authoring_modes":["skill"],"context_changed":true,"origin_untracked":false} -->
