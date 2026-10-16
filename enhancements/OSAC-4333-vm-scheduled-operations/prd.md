# VM Scheduled Operations

**Status:** Draft for review. Proposed policies and open decisions are identified under Assumptions; the PRD is not yet approved.

| Field | Value |
|---|---|
| Author(s) | AI-assisted draft; curated by Codex for Eran Cohen |
| Jira | [OSAC-4333](https://redhat.atlassian.net/browse/OSAC-4333) |
| Date | 2026-10-12 |

## Problem Statement

Tenant teams use virtual machines for planned windows such as business hours, batch jobs, demos, and drills. Today they must start, stop, create, or tear down VMs by hand, or leave them running continuously; the source identifies avoidable cost and capacity waste, missed starts, VMs left running after hours, and operational work that grows with VM count and team handoffs. Schedules would make these operations follow intended usage windows instead of depending on memory and manual coordination. The scheduling service carries no additional charge. Resources continue to be metered and billed under the usual OSAC policies; scheduling an action does not change its billing rules.

## In Scope

- Tenants can create, update, and cancel schedules with cron-like recurrence in UTC only.
- A schedule can start or stop an existing VM, or provision or de-provision a VM.
- The user can select a single VM, project, tags, or owner/user as the target.
- Tenant Admins and Tenant Users can manage schedules within their authority. Tenant Admins can override schedules created by Tenant Users; the proposed meaning of “override” is listed under Assumptions for owner approval.
- A missed or failed scheduled operation produces a UI alert and an email notification. Notification delivery depends on [OSAC-75](https://redhat.atlassian.net/browse/OSAC-75); the recipient policy remains to be confirmed below.
- Scheduling has no service charge. Scheduled resources are metered and billed as usual, with the same billing behavior as the corresponding manual operations.

## Out of Scope

- Cloud Provider Admin and Cloud Infrastructure Admin capabilities are unaffected by this feature.
- **Proposed exclusions for owner confirmation:** clusters, bare metal, autoscaling, time zones other than UTC, and notification channels beyond UI alerts and email. The source gives these as examples for the PRD to refine; this draft does not treat them as approved exclusions.

## User Stories

### Tenant Admin

- As a Tenant Admin, I want to schedule Start and Stop for an existing VM or a selected set of VMs so that my tenant's capacity and cost follow planned usage windows.
- As a Tenant Admin, I want to schedule VM provisioning and de-provisioning for a selected target so that tenant capacity follows planned needs.
- As a Tenant Admin, I want to create, update, and cancel cron-like schedules in UTC, using a single VM, project, tags, or owner/user as the target, so that I can manage those operations across the tenant.
- As a Tenant Admin, I want to override or manage schedules created by Tenant Users so that tenant policy and cost controls remain enforceable.
- As a Tenant Admin, I want a UI alert and email when a scheduled operation is missed or fails so that I can remediate it.

### Tenant User

- As a Tenant User, I want to schedule Start and Stop for VMs I am allowed to operate so that my workloads are available during the windows I need.
- As a Tenant User, I want to schedule provisioning and de-provisioning for VMs I am allowed to operate so that I can align those operations with planned usage.
- As a Tenant User, I want to create, update, and cancel cron-like schedules in UTC, using a single VM, project, tags, or owner/user as the target, so that I can manage allowed VM operations without manual intervention.
- As a Tenant User, I want a UI alert and email when a scheduled operation is missed or fails so that I know when an action did not complete.

## Assumptions

The policy proposals below require review. Notification availability and the billing rules stated above were confirmed by the feature owner; the remaining proposals are defaults for discussion only.

- **Tenant Admin override — proposed:** within their own tenant, an Admin can inspect, edit, or cancel a Tenant User's schedule, including its action, recurrence, and targets. The UI should retain the creator and identify the Admin who made a change. Confirm whether override includes all these controls or only some of them. No cross-tenant authority or diagnostic access is proposed.
- **Delayed authorization — proposed:** check a user's authority when a schedule is created or changed and again before each scheduled operation. If that authority is gone, do not silently use an Admin identity; report the failure in the UI and by email. The owner must decide which identity executes delayed work and what an authorized Admin may take over.
- **Target timing — proposed:** resolve project, tags, and owner/user membership when each occurrence runs, within the schedule's tenant and authorized scope. Confirm whether membership should instead be fixed when the schedule is created or last edited. This choice is especially important for de-provisioning.
- **Provisioning inputs — open:** define the VM information and destination a user supplies to provision a VM, and how the four target selectors apply to newly provisioned VMs. The proposal is to require a VM definition and destination, but neither is an approved input contract.
- **Stop and de-provision effects — open:** scheduled actions follow the existing lifecycle, retention, and billing behavior of the corresponding manual operations. Treat de-provisioning as distinct from reversible Stop and disclose its effects before a user schedules it; the destructive-action confirmation flow still requires owner approval. Resource billing remains governed by the usual policies.
- **Recurrence and failures — open:** define the accepted cron-like expression format and behavior for missed occurrences, retries, overlapping runs, and partial failures across multiple targets. Proposed default: retain the schedule and report each failed occurrence; do not silently retry or replay a backlog of missed operations until those rules are approved.
- **Notification recipients — open:** UI alerts and email remain release requirements, dependent on OSAC-75. Confirm who receives alerts (schedule creator, Tenant Admin, affected Tenant User, or a combination). OSAC does not currently support notifications; this was confirmed by the feature owner on 2026-10-12.

## Dependencies

- UX and UI must be delivered per the bootstrap UX/UI Design gates, and both the PRD and technical Design must be merged for completion.
- **[Notifications — OSAC-75](https://redhat.atlassian.net/browse/OSAC-75):** OSAC has no notification support yet. This feature depends on that capability for scheduled-operation failure alerts in the UI and by email. The notification capability must be available to satisfy the full failure-notification requirement; UI-only delivery does not satisfy it.

---

## Provenance

Committed: commit @ prd 0.11.3 - d9d66a5, workspace main @ 0fe0e4595 (15 behind origin/main)

> Authoring phases not recorded this session (commit-time snapshot only).

<!-- ai-workflow-provenance:{"schema_version":1,"provenance_kind":"commit_only","workflow":"prd","workflow_version":"0.11.3","ai_workflows":"d9d66a5","source_repo":"0fe0e4595","source_repo_branch":"main","commits_behind_main":15,"commits_ahead_main":0,"main_ref":"main","phases":["commit"],"authoring_modes":["skill"],"context_changed":false,"origin_untracked":false} -->
