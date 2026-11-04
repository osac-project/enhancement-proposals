# Show VM configuration work at a glance in the VM list

| Field | Value |
|---|---|
| Author(s) | Carlo Lobrano |
| Jira | [OSAC-7158](https://redhat.atlassian.net/browse/OSAC-7158) |
| Date | 2026-11-04 |
| Service | VMaaS |
| Target milestone | 0.5 |

## 1. Problem Statement

VM details let users inspect configuration work one VM at a time, while the VM list shows only each VM's overall state. A VM can remain RUNNING while a configuration change is applying or has failed, so users cannot identify delayed or failed configuration work by scanning the list. Tenant Users and Tenant Admins cannot quickly find VMs in their organization that need attention, and Cloud Provider Admins cannot scan the VMs they are allowed to see across tenants to decide where support is needed.

## 2. In Scope

- Each VM row shows its configuration state separately from its overall VM state, including when the VM remains RUNNING.
- The list shows a positive indication whenever a VM's requested configuration is applied. [Clarify: R1.Q1, R2.Q3]
- Rows distinguish configuration work waiting to start, being applied, scheduled to retry after a failed attempt, and finally failed. A prerequisite that blocks work is shown as waiting with the reason. When another attempt will occur after a failure, the row makes that retry intent clear. [Clarify: R1.Q2, R3.Q3]
- Active configuration work has a simple in-progress indicator. It does not show a completion percentage or estimate how long completion will take.
- Retry and failure text gives a safe explanation in plain language.
- Show elapsed time only while configuration is being applied, and keep it accurate after users reconnect. For configuration that is applied or has finally failed, show the date and time that state changed. Do not show elapsed time for the VM's overall state, such as RUNNING. [Clarify: R1.Q3, R2.Q1, R3.Q1, R3.Q2]

## 3. Out of Scope

- Full operation history and notifications.
- Changes to retry behavior.
- Provider job IDs, links, logs, or raw errors.
- CLI output for configuration status. [Clarify: R1.Q4]

## 4. User Stories

### Tenant User

As a Tenant User, I want to see each of my VMs' configuration state in the VM list so that I know which VM to inspect.

### Tenant Admin

As a Tenant Admin, I want to scan my organization's VM list and see which VMs have applied configuration and which have work waiting, applying, scheduled to retry, or failed so that I can focus on those needing attention.

### Cloud Provider Admin

As a Cloud Provider Admin, I want to scan the VMs I am allowed to see across tenants and identify outstanding configuration work or failures so that I can choose which VM needs support.

## 5. Dependencies

- The VM list may need configuration-status data from the public API to show each VM's state. Specific data needs are for design. [Clarify: R1.Q4]

---

## Provenance

Authored: draft @ prd 0.11.5 - 7b2b8de, workspace main @ a818dfe69

<!-- ai-workflow-provenance:{"schema_version":1,"provenance_kind":"session","workflow":"prd","workflow_version":"0.11.5","ai_workflows":"7b2b8de","source_repo":"a818dfe69","source_repo_branch":"main","commits_behind_main":0,"commits_ahead_main":0,"main_ref":"main","phases":["draft"],"authoring_modes":["skill"],"context_changed":false,"origin_untracked":false} -->
