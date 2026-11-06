# Keep VM Details Available During Deletion

| Field | Value |
|-------|-------|
| Author(s) | Carlo Lobrano |
| Jira | [OSAC-7096](https://redhat.atlassian.net/browse/OSAC-7096) |
| Date | 2026-11-02 |
| Service | VMaaS |
| Target milestone | 0.5 |

## Problem Statement

Tenant Admins and Tenant Users can request VM deletion, but the VM list prevents them from opening its details while deletion is in progress. This blocks inspection of the VM's available information and investigation of deletion failures. Users need access to those details while the VM still exists, with disappearance from the UI confirming completed deletion.

## In Scope

- A VM remains listed while deletion is in progress, including when deletion encounters a failure. Its name continues to link to its details until removal is confirmed. Existing tenant access controls continue to determine which VMs each user can inspect.
- During deletion and after a deletion failure, the details view shows the VM's identity and existing configuration information when available. Potentially stale values, such as displayed IP addresses, are marked **last known**. Missing values are marked **unavailable**. [Clarify: R1.Q1]
- The details view clearly indicates that deletion is in progress. OSAC provides safe deletion-failure information to authorized tenant users. This includes a plain-language cause when safely available. Otherwise, OSAC explains that deletion could not finish and the reason is unavailable. [Clarify: R1.Q3]
- During deletion and after a deletion failure, the VM's configuration, power, and networking controls remain disabled. [Clarify: R1.Q2]
- Authorized users may attempt a console connection during deletion and after a deletion failure. If the console accepts the connection, they can use it. OSAC warns that deletion may interrupt the session. Console access does not delay or cancel cleanup. [Clarify: R1.Q2] [User]
- Once removal is confirmed, the VM disappears from the list and its details are no longer displayed. An open details view returns to the VM list.

## Out of Scope

- Retaining or displaying deleted VMs or their deletion results.
- Operation history and notifications.
- New controls for canceling or retrying deletion.
- Exposing provider job IDs, links, logs, or raw errors.

## User Stories

### Tenant Admin / Tenant User

- As a Tenant Admin or Tenant User, I want to open the details of a VM I have permission to view while deletion is in progress or has failed, so that I can inspect its available identity and configuration information.
- As a Tenant Admin or Tenant User, I want to use an available VM console during deletion or after a deletion failure, subject to my existing console permissions, so that I can investigate the VM. [User]
- As a Tenant Admin or Tenant User, I want to see the VM's deletion status and a safe explanation of any deletion failure, so that I can understand whether deletion is progressing or needs attention.

---

## Provenance

Authored: revise @ prd 0.11.5 - 7b2b8de, workspace main @ 60d787561
Phases: draft, revise, revise, revise

<!-- ai-workflow-provenance:{"schema_version":1,"provenance_kind":"session","workflow":"prd","workflow_version":"0.11.5","ai_workflows":"7b2b8de","source_repo":"60d787561","source_repo_branch":"main","commits_behind_main":0,"commits_ahead_main":0,"main_ref":"main","phases":["draft","revise","revise","revise"],"authoring_modes":["skill"],"context_changed":false,"origin_untracked":false} -->
