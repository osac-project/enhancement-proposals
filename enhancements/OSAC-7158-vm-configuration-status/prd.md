# Show VM configuration progress and failures in the list and Details

| Field | Value |
|---|---|
| Author(s) | Carlo Lobrano |
| Jira | [OSAC-7158](https://redhat.atlassian.net/browse/OSAC-7158) |
| Date | 2026-11-12 |
| Service | VMaaS |
| Target milestone | 0.5 |

## 1. Problem Statement

Users can open a VM's Details, but they cannot scan the VM list for configuration work because it shows only the VM's overall state. A VM can remain RUNNING while configuration is waiting, being applied, scheduled to retry, or failed. The list cannot identify VMs that need attention, and Details needs a consistent place to show which operation is current or most recent and whether it completed. Without that information, users may not know whether to wait or seek help.

## 2. In Scope

- Each VM row shows a concise configuration summary separately from the VM's overall state, including when it remains RUNNING. A normal VM state such as STOPPED is not shown as a configuration failure.
- Each row shows a positive indication when the requested configuration is applied. Completed configuration is no longer presented as outstanding work. [Clarify: R1.Q1, R2.Q3]
- The list and Details communicate whether configuration work is waiting to start, underway, being retried after a failed attempt, finally failed, or complete. When a prerequisite blocks work, the list and Details show it as waiting and explain the blocker in plain language when available information supports it. Unsupported distinctions are documented with what is needed to show them and are not claimed as covered unless supported or explicitly accepted as a limitation. [Clarify: R1.Q2, R3.Q3, R4.Q2]
- Details provides one consistent place for the current or most recent configuration operation, its status, and a safe explanation. It identifies the operation, including VM resize or external-IP attachment, and shows its latest result until another configuration change starts.
- Active work has a simple in-progress indicator. It does not show a completion percentage or an estimate of how long completion will take. Retry and failure explanations use safe, plain language.
- In the list, show elapsed time only while configuration is being applied and keep it accurate after users reconnect. When configuration is applied or has finally failed, show when that state changed. Do not show elapsed time for the VM's overall state or accumulate it across retry waits. [Clarify: R1.Q3, R2.Q1, R3.Q1, R3.Q2]
- Existing access controls continue to apply. This feature does not change which VMs a user can access.

## 3. Out of Scope

- VM start, stop, and restart status. These actions belong to [OSAC-7682](https://redhat.atlassian.net/browse/OSAC-7682).
- Implementing new configuration operations, such as adding disks or networks. They may use this status and display pattern when supported in the future.
- Full operation history, notifications, or changes to retry behavior.
- Provider job IDs, links, logs, or raw errors.
- CLI output for configuration status. [Clarify: R1.Q4]

## 4. User Stories

### Tenant User

As a Tenant User, I want to see a short configuration status for my VMs in the list and understand the operation and its outcome in Details, so I know whether to wait or seek help.

### Tenant Admin

As a Tenant Admin, I want to scan my organization's VM list for configuration work and see a clear explanation in Details, so I can help users and identify VMs that need attention.

## 5. Dependencies

- The VM list and Details may need configuration-status data from the public API. [Clarify: R1.Q4]

---

## Provenance

Authored: draft @ prd 0.11.5 - 7b2b8de, workspace main @ a818dfe69
Final: revise @ prd 0.11.5 - 87d14ea, workspace main @ 045780b38

> Context changed between draft and revise.

<!-- ai-workflow-provenance:{"schema_version":1,"provenance_kind":"session","workflow":"prd","workflow_version":"0.11.5","ai_workflows":"87d14ea","source_repo":"045780b38","source_repo_branch":"main","commits_behind_main":0,"commits_ahead_main":0,"main_ref":"main","phases":["draft","revise"],"authoring_modes":["skill"],"context_changed":true,"origin_untracked":false} -->
