# VM Scheduled Operations

**Status:** Draft for review.

| Field | Value |
|---|---|
| Author(s) | Eran Cohen, with AI assistance |
| Jira | [OSAC-4333](https://redhat.atlassian.net/browse/OSAC-4333) |
| Date | 2026-10-26 |

## Problem Statement

Tenant teams need VMs for known windows such as business hours, batch jobs, and demos. Starting and stopping them manually leads to missed starts, VMs left running after hours, and repeated operational work. Scheduling power-state changes lets teams plan VM availability without relying on someone remembering each operation.

Scheduling has no service charge. Resource metering and billing follow the usual OSAC policies, as for equivalent manual operations.

## In Scope

- **VMaaS only:** Create, view, update, and cancel schedules for Start or Stop of an existing VM. The underlying scheduling framework is generic, but V1 restricts exposed operations strictly to declarative power state changes (patching `run_strategy`). Exposing other fields requires extensive testing coverage and knowledge about what is actually supported, so additional operations are deferred to future features. Each schedule identifies one VM and one action. A user can create separate Start and Stop schedules for the same VM.
- **Timezones:** Recurring schedules use minute-resolution cron expressions. Users can specify an IANA timezone (e.g., `America/New_York`), which handles DST shifts automatically (skipping nonexistent times, executing once on repeated times). Use the first occurrence when a local time repeats. Execution timestamps and underlying execution/audit records remain in UTC; schedule definitions retain the selected IANA timezone. Invalid expressions and timezone names are rejected, and users can see the next scheduled occurrence.
- **Scheduled changes:** each occurrence requests the selected power state. The scheduler does not continuously enforce a time window. A manual power-state change remains effective until the next scheduled occurrence. For example, manually stopping a VM after its scheduled Start leaves it stopped until its next scheduled Start.
- **Permissions:** Tenant Users manage their own schedules. Creating or editing a schedule requires the acting user's permission for its VM action. Tenant Admins can inspect and cancel any schedule within their tenant without the schedule owner's VM-action permission. An Admin edit requires the Admin's own VM-action permission, regardless of the owner's current permission. Every occurrence checks the schedule owner's current permissions. An Admin edit retains the owner and records who changed the schedule; it does not transfer execution authority or grant the owner new permissions. Owners can cancel their schedules even after losing permission to operate the VM.
- **Execution results:** users can view occurrence status and its reason through the UI or API. `PENDING` means an execution attempt or an accepted VM transition is in progress. `SUCCESS` means the requested power state was observed; a VM already in that state is a successful no-op. `FAILED` means an attempted operation could not complete, including permission denial, a deleted target, an update/transition error, or a documented completion timeout. `MISSED` means the occurrence was skipped without an execution attempt, with its reason shown. Tenant Admins can inspect execution status within their tenant. Active push notifications, including UI alerts, and emails are deferred to V2 as a fast follow; V1 is not blocked on OSAC-75.
- **Missed or failed occurrences:** an occurrence may begin execution only during its scheduled UTC minute. If it has not started before the next UTC minute begins, record `MISSED` with an expired-deadline reason. After downtime, expired occurrences are recorded as `MISSED` and are not replayed. The deadline governs starting an attempt, not completion of an accepted VM transition, which can remain `PENDING` afterward. Record attempted operations that cannot complete as `FAILED`. Both outcomes leave future occurrences enabled; V1 does not automatically retry failed occurrences or replay missed ones.
- **Conflicts and ordering:** if opposite actions for the same VM are due in the same scheduled UTC minute, skip both and record `MISSED` with a conflict reason. Check this at execution time before applying either action; V1 does not evaluate future cron intersections at schedule creation or update. Adjacent-minute actions are allowed with no minimum separation. Apply their desired-state changes in scheduled-time order without waiting for the previous VM transition to finish. An unstarted older occurrence is skipped as `MISSED` if its minute has expired or a newer scheduled or manual power-state change has superseded it. For example, an unstarted 10:00 occurrence is `MISSED` once 10:01 begins; only the 10:01 occurrence remains eligible. If an attempted occurrence is superseded while still `PENDING`, record `FAILED` with a superseded reason. No delayed older request may overwrite newer power-state intent.
- **Reusable scheduling:** the underlying framework schedules generic JSON patches, with V1 exposing only the `run_strategy` power-state changes described above. Scheduled changes use the normal resource authorization and reconciliation path. V1 does not introduce dedicated imperative power-management APIs or restrict unrelated manual VM updates. The detailed patch representation and safe field allowlist are specified in the technical design.

## Out of Scope

- VM creation and deletion are explicitly excluded from V1. While the scheduler architecture is generic, these operations carry different safety semantics and require separate testing coverage that will be evaluated in future iterations. Creation/provisioning is excluded due to API complexity, and deletion/de-provisioning is deferred to keep this increment focused on power states.
- Resizing, changing instance types, and scaling of any kind, including time-based and usage-based scaling.
- Project, tag, owner/user, or other dynamic target selectors; bulk or multi-VM schedules.
- Scheduling updates to VM fields other than `run_strategy`, arbitrary API execution, and user-supplied patches beyond the V1 allowlist.
- Scheduling for clusters, bare metal, or other services.
- Rate-based and one-time schedules, and continuous enforcement of power-state windows.
- Configurable retries and catch-up execution.
- Active push notifications, UI alerts, and email notifications; these are deferred to V2. Viewing execution status in the UI/API remains in V1.
- Changes to Cloud Provider Admin or Cloud Infrastructure Admin capabilities.

## User Stories

### Tenant User

- As a Tenant User, I want to create, update, view, and cancel cron schedules in my chosen IANA timezone for Start or Stop of one existing VM I am allowed to operate, so that planned usage stays aligned with local time across DST changes.
- As a Tenant User, I want to see successful, failed, and missed occurrences in the UI or API, so that I can investigate when a scheduled change does not complete.

### Tenant Admin

- As a Tenant Admin, I want the same scheduling capabilities for VMs I am allowed to operate and the ability to inspect, edit, or cancel Tenant User schedules within my tenant, so that I can enforce tenant policy and manage operational problems.

## Dependencies

- **[Technical design — OSAC-4337](https://redhat.atlassian.net/browse/OSAC-4337):** the design must specify the scheduled-update handoff, execution authorization, stale-update protection, reconciliation/status mapping, and completion timeout that satisfy the user-visible rules above.
- UX and UI must be delivered through the bootstrap UX/UI Design gates. Completion requires the PRD and technical Design to be merged.

---

## Provenance

Authored: commit @ prd 0.11.3 - d9d66a5, workspace main @ 0fe0e4595 (15 behind origin/main)
Final: respond @ prd 0.11.3 - d9d66a5, workspace main @ a6d3626e5

> Context changed between commit and respond.

> This document's phase history does not include an initial /draft — structure was not verified against the template from origin.

<!-- ai-workflow-provenance:{"schema_version":1,"provenance_kind":"session","workflow":"prd","workflow_version":"0.11.3","ai_workflows":"d9d66a5","source_repo":"a6d3626e5","source_repo_branch":"main","commits_behind_main":0,"commits_ahead_main":0,"main_ref":"main","phases":["commit","respond","revise","respond"],"authoring_modes":["skill"],"context_changed":true,"origin_untracked":true} -->
