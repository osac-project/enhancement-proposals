# Tenant On-Boarded Status for Minimal Onboarding Requirements

| Field | Value |
|---|---|
| Author(s) | Shirel Bar Lev |
| Jira | [OSAC-3976](https://redhat.atlassian.net/browse/OSAC-3976) |
| Date | 2026-10-29 |
| Target milestone | 0.5 |
| OSAC area | Shared tenant-level status with role-scoped information |

## Problem Statement

Today, after a tenant is created and onboarding runs, there is no consolidated status showing whether the four minimal onboarding requirements are complete. Cloud Provider Admins must inspect subsystems individually to locate failures, while Tenant Admins and Tenant Users cannot tell whether their tenant is ready for use. Without a shared status, administrators spend time finding failed requirements and tenant users lack a clear readiness signal before provisioning resources.

## In Scope

- Show a tenant-level status for networking, storage, encryption keys, and the breakglass account. Show **Failed** if any component failed or is unavailable; otherwise show **In Progress** if at least one component is pending or in progress; show **On-Boarded** only when all four components succeed. [Clarify: R2.Q1, R3.Q1, R5.Q1]
- Make the tenant status visible to all four personas, with role-appropriate detail, through the UI, API, and CLI. Apply the same visibility rules across all three interfaces. [User, Clarify: R2.Q3]
- When a component status changes, update the overall status and role-appropriate views automatically without requiring a manual refresh. [User, Clarify: R4.Q1]
- For administrative component details, show a simple **In Progress** state while a component is progressing; do not show detailed progress. Show **Succeeded** or **Failed** when the component reaches a result. [Clarify: R2.Q5]

## Out of Scope

- Tenant readiness beyond the four minimal onboarding requirements, including monitoring and health-check indicators.
- Multihub onboarding complications.
- Automatic remediation of failed onboarding components.
- User-triggered retries from the onboarding status view.

## User Stories

### Cloud Provider Admin

- As a Cloud Provider Admin, I want to see the full breakdown of each minimal onboarding requirement and the full failure reason for each failed requirement, so I can identify which requirement failed and decide how to address it. [User, Clarify: R1.Q4, R3.Q2]

### Cloud Infrastructure Admin

- As a Cloud Infrastructure Admin, I want the tenant onboarded status to reflect only the minimal onboarding requirements, with per-component status for networking, storage, encryption keys, and the breakglass account, so I can distinguish onboarding failures from broader readiness or monitoring concerns when triaging infrastructure issues. [User, Clarify: R2.Q2, R3.Q2]

### Tenant Admin

- As a Tenant Admin, I want a simple **Not On-Boarded** / **On-Boarded** indicator for my tenant, so I know whether it is ready for use without contacting the Cloud Provider. [Clarify: R5.Q2]

### Tenant User

- As a Tenant User, I want a simple **Not On-Boarded** / **On-Boarded** indicator on my tenant, so I know whether my workspace is ready before I start provisioning resources. [Clarify: R5.Q2]

## Dependencies

- **Networking, storage, encryption keys, and breakglass account onboarding:** Their status outcomes are needed to determine the overall tenant onboarding status.

---

## Provenance

Authored: revise @ prd 0.11.5 - unknown (not a git repository), workspace main @ 0d428d098
Phases: draft, revise

<!-- ai-workflow-provenance:{"schema_version":1,"provenance_kind":"session","workflow":"prd","workflow_version":"0.11.5","ai_workflows":"unknown (not a git repository)","source_repo":"0d428d098","source_repo_branch":"main","commits_behind_main":null,"commits_ahead_main":null,"main_ref":"main","phases":["draft","revise"],"authoring_modes":["skill"],"context_changed":false,"origin_untracked":false} -->
