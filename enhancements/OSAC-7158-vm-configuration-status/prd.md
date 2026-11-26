# Expose VM configuration operation status across UI, API, and CLI

| Field | Value |
|---|---|
| Author(s) | Carlo Lobrano |
| Jira | [OSAC-7158](https://redhat.atlassian.net/browse/OSAC-7158) |
| Date | 2026-11-16 |

## Problem Statement

Tenant Users and Tenant Admins can view a VM's overall state, but VM summaries do not show configuration work separately, and VM details do not provide one predictable place for the operation and its outcome. A VM can remain RUNNING while a configuration change is waiting, applying, being retried, or failed, making it hard to find VMs that need attention. API and CLI users also lack a clear way to monitor or troubleshoot the same status without relying on the UI. Without consistent status across these surfaces, users may not know whether to wait or seek help.

## In Scope

- VM summaries distinguish a VM’s lifecycle state from its configuration status. They show when configuration work is in progress and when it needs attention. A successful change is acknowledged but is no longer shown as outstanding. [Clarify: R1.Q1, R2.Q3]
- VM summaries and VM details communicate configuration status using these intended meanings: waiting to start, in progress, retry scheduled after a failed attempt, failed with no further retry planned, and complete. A configuration change may report only some of these statuses. Show only the statuses it reports; do not infer others. When a configuration change reports that a prerequisite is blocking it, show its status as waiting and explain the reason in plain language. When multiple configuration operations run in parallel, VM details identify each one. [Clarify: R1.Q2, R4.Q2]
- Users can retrieve status for current or most recent configuration operations through collection and individual-VM outputs in the API and CLI. When multiple operations run in parallel, these outputs expose each operation's status and latest outcome, including when a change has been applied. CLI table and `describe` output show a concise summary; JSON and YAML include the full status. The information identifies each operation, its status, a safe, plain-language explanation, and relevant timestamps. Existing access controls continue to apply. This does not change which VMs a user can access. [Clarify: R5.Q1]

## Out of Scope

- VM start, stop, and restart status. These actions belong to [OSAC-7682](https://redhat.atlassian.net/browse/OSAC-7682).
- Implementing new configuration operations, such as adding disks or networks.
- Full operation history, notifications, or a shared way to track all types of VM operations. VM details show only current configuration operations and the most recent configuration result. [Clarify: R6.Q1]
- Changes to retry behavior, including a user action to stop or cancel a retrying operation. [Clarify: R6.Q2]
- Showing provider job IDs, links, logs, or raw errors is out of scope.

## User Stories

### Tenant User

- As a Tenant User, I want to see configuration status in VM summaries and the corresponding operation and outcome in VM details, the API, and the CLI, so I know whether to wait or seek help.

### Tenant Admin

- As a Tenant Admin, I want to scan my organization's VM summaries and access an explanation for each configuration operation through VM details, the API, and the CLI, so I can help users and identify VMs that need attention.

---

## Provenance

Authored: draft @ prd 0.11.5 - 7b2b8de, workspace main @ a818dfe69
Final: manual-edit [manual] @ prd 0.11.5 - 87d14ea, workspace main @ f34109e7b

> Context changed between draft and manual-edit.

<!-- ai-workflow-provenance:{"schema_version":1,"provenance_kind":"session","workflow":"prd","workflow_version":"0.11.5","ai_workflows":"87d14ea","source_repo":"f34109e7b","source_repo_branch":"main","commits_behind_main":0,"commits_ahead_main":0,"main_ref":"main","phases":["draft","revise","draft","revise","revise","revise","revise","manual-edit"],"authoring_modes":["manual","skill"],"context_changed":true,"origin_untracked":false} -->
