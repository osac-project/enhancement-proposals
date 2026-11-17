# Expose VM configuration operation status across UI, API, and CLI

| Field | Value |
|---|---|
| Author(s) | Carlo Lobrano |
| Jira | [OSAC-7158](https://redhat.atlassian.net/browse/OSAC-7158) |
| Date | 2026-11-16 |

## Problem Statement

Tenant Users and Tenant Admins can view a VM's overall state, but the VM list does not show configuration work separately, and Details does not provide one predictable place for the operation and its outcome. A VM can remain RUNNING while a configuration change is waiting, applying, being retried, or failed, making it hard to find VMs that need attention. API and CLI users also lack a clear way to monitor or troubleshoot the same status without relying on the UI. Without consistent status across these surfaces, users may not know whether to wait or seek help.

## In Scope

- The VM list shows a concise summary of outstanding configuration work separately from the VM's overall state. It shows a positive indication when the requested configuration is applied and does not present completed configuration as outstanding work. A normal VM state such as STOPPED is not shown as a configuration failure. [Clarify: R1.Q1, R2.Q3]
- The VM list and Details communicate whether configuration work is waiting to start, applying, being retried, finally failed, or complete. When available information shows that a prerequisite is blocking work, they show it as waiting and explain the blocker in plain language. During design, verify that the available information can reliably distinguish each status. If it cannot, document what information is missing. Treat that status as unsupported until the team either adds the needed information or accepts the gap as a limitation. [Clarify: R1.Q2, R4.Q2]
- Details provides one consistent place for the current or most recent configuration operation, its status, and a safe explanation. It identifies the operation, e.g. "VM resize", and shows its latest result until another configuration change starts.
- Users can retrieve VM configuration status through API list and get responses and the CLI. The UI uses this API information. CLI table and `describe` output show a concise summary; JSON and YAML include the full status. The information identifies the operation, its status, a safe explanation, and relevant timestamps. [Clarify: R5.Q1]
- Active configuration work has a simple in-progress indicator, without a completion percentage or time estimate. Retry and failure explanations use safe, plain language.
- In the VM list, elapsed time is shown only while configuration is applying and remains accurate after users reconnect. Applied and final failure states show the date and time when the status changed. The timer does not measure the VM's overall state or accumulate across retry waits. [Clarify: R1.Q3, R2.Q1, R3.Q1, R3.Q2]
- The same status and display pattern may be used for other supported configuration changes, such as adding disks or networks.

## Out of Scope

- VM start, stop, and restart status. These actions belong to [OSAC-7682](https://redhat.atlassian.net/browse/OSAC-7682).
- Implementing new configuration operations, such as adding disks or networks.
- Full operation history, notifications, or a shared way to track all types of VM operations. Details shows only the current or most recent configuration operation. [Clarify: R6.Q1]
- Changes to retry behavior, including a user action to stop or cancel a retrying operation. [Clarify: R6.Q2]
- Showing provider job IDs, links, logs, or raw errors is out of scope.

## User Stories

### Tenant User

- As a Tenant User, I want the VM list to show a short configuration status and the same operation and outcome to be available in Details, API, and CLI, so I know whether to wait or seek help.

### Tenant Admin

- As a Tenant Admin, I want to scan my organization's VM list and access the same configuration-operation explanation in Details, API, and CLI, so I can help users and identify VMs that need attention.

---

## Provenance

Authored: draft @ prd 0.11.5 - 7b2b8de, workspace main @ a818dfe69
Final: manual-edit [manual] @ prd 0.11.5 - 87d14ea, workspace main @ f34109e7b

> Context changed between draft and manual-edit.

<!-- ai-workflow-provenance:{"schema_version":1,"provenance_kind":"session","workflow":"prd","workflow_version":"0.11.5","ai_workflows":"87d14ea","source_repo":"f34109e7b","source_repo_branch":"main","commits_behind_main":0,"commits_ahead_main":0,"main_ref":"main","phases":["draft","revise","draft","revise","revise","revise","revise","manual-edit"],"authoring_modes":["manual","skill"],"context_changed":true,"origin_untracked":false} -->
