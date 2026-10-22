# VM Scheduled Operations

**Status:** Draft for review.

| Field | Value |
|---|---|
| Author(s) | Eran Cohen, with AI assistance |
| Jira | [OSAC-4333](https://redhat.atlassian.net/browse/OSAC-4333) |
| Date | 2026-10-21 |

## Problem Statement

Tenant teams need VMs for known windows such as business hours, batch jobs, and demos. Starting and stopping them manually leads to missed starts, VMs left running after hours, and repeated operational work. Scheduling power-state changes lets teams plan VM availability without relying on someone remembering each operation.

Scheduling has no service charge. Resource metering and billing follow the usual OSAC policies, as for equivalent manual operations.

## In Scope

- **VMaaS only:** create, view, update, and cancel schedules for Start or Stop of an existing VM. Each schedule identifies one VM and one action. A user can create separate Start and Stop schedules for the same VM.
- **UTC cron:** recurring schedules use five-field, minute-resolution cron expressions in UTC. Invalid expressions are rejected, and users can see the next scheduled occurrence.
- **Scheduled changes:** each occurrence requests the selected power state. The scheduler does not continuously enforce a time window. A manual power-state change remains effective until the next scheduled occurrence. For example, manually stopping a VM after its scheduled Start leaves it stopped until its next scheduled Start.
- **Permissions:** Tenant Users manage their own schedules for VMs they are allowed to operate. Tenant Admins can inspect, edit, or cancel schedules within their tenant. Creating or editing a schedule requires permission for its VM action, and each occurrence checks the schedule owner's current permissions. An Admin edit retains the owner and records who changed the schedule; it does not grant the owner new permissions. Owners can cancel their schedules even after losing permission to operate the VM.
- **Execution results:** users can see the last execution's status and distinguish a pending power-state change from a completed or failed operation. A VM already in the requested state is a successful no-op. A deleted VM or lost permission is reported as a failure.
- **Missed or failed occurrences:** report the failure and leave future occurrences enabled. V1 does not automatically retry failed occurrences or replay missed ones after recovery. An older occurrence must not override a newer scheduled or manual change.
- **Conflicts:** if Start and Stop are due for the same VM at the same time, apply neither and report the conflict to the affected schedule owners.
- **Notifications:** notify the schedule owner of failed or missed occurrences through a UI alert and email. Tenant Admins can inspect execution status for their tenant. Delivery depends on [OSAC-75](https://redhat.atlassian.net/browse/OSAC-75).
- **Reusable scheduling:** schedule management should support future extensions to other resource actions and schedule types without requiring a separate scheduler for each service. Only VM Start/Stop is exposed in this release; the API representation is decided in the technical design.

## Out of Scope

- VM creation, provisioning, deletion, and de-provisioning.
- Resizing, changing instance types, and scaling of any kind, including time-based and usage-based scaling.
- Project, tag, owner/user, or other dynamic target selectors; bulk or multi-VM schedules.
- Other VM field updates, arbitrary API execution, and user-supplied arbitrary patches.
- Scheduling for clusters, bare metal, or other services.
- Rate-based and one-time schedules, non-UTC time zones, and continuous enforcement of power-state windows.
- Configurable retries, catch-up execution, and notification channels beyond UI alerts and email.
- Changes to Cloud Provider Admin or Cloud Infrastructure Admin capabilities.

## User Stories

### Tenant User

- As a Tenant User, I want to create, update, view, and cancel UTC cron schedules for Start or Stop of one existing VM I am allowed to operate, so that it is available during planned usage periods.
- As a Tenant User, I want to see execution results and receive UI and email alerts for failed or missed occurrences, so that I can act when a scheduled change does not complete.

### Tenant Admin

- As a Tenant Admin, I want the same scheduling capabilities for VMs I am allowed to operate and the ability to inspect, edit, or cancel Tenant User schedules within my tenant, so that I can enforce tenant policy and manage operational problems.

## Dependencies

- **[Notifications — OSAC-75](https://redhat.atlassian.net/browse/OSAC-75):** the notification capability is required for UI and email failure alerts. Both channels remain acceptance requirements.
- UX and UI must be delivered through the bootstrap UX/UI Design gates. Completion requires the PRD and technical Design to be merged.

---

## Provenance

Authored: commit @ prd 0.11.3 - d9d66a5, workspace main @ 0fe0e4595 (15 behind origin/main)
Final: respond @ prd 0.11.3 - d9d66a5, workspace main @ c93dba0d7

> Context changed between commit and respond.

> This document's phase history does not include an initial /draft — structure was not verified against the template from origin.

<!-- ai-workflow-provenance:{"schema_version":1,"provenance_kind":"session","workflow":"prd","workflow_version":"0.11.3","ai_workflows":"d9d66a5","source_repo":"c93dba0d7","source_repo_branch":"main","commits_behind_main":0,"commits_ahead_main":0,"main_ref":"main","phases":["commit","respond"],"authoring_modes":["skill"],"context_changed":true,"origin_untracked":true} -->
