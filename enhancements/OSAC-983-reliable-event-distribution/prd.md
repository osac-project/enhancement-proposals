# Reliable Event Distribution

| Field            | Value                                          |
|------------------|------------------------------------------------|
| Author(s)        | Juan Hernandez                                 |
| Jira             | https://redhat.atlassian.net/browse/OSAC-983   |
| Date             | 2026-08-21                                     |
| Target Milestone | 0.3                                            |

## Problem Statement

Clients of the fulfillment-service can already subscribe to resource-change
events through the gRPC events API (the `Watch` method), but delivery is
unreliable: a consumer receives only the events emitted while it is actively
connected. Any event produced while a consumer is disconnected — during a
restart, redeploy, or network interruption — is lost, with no way to catch up.
OSAC's own event consumers work around this by periodically re-scanning all
resources, which is expensive and still leaves gaps between scans
[Clarify: R2.Q1]. Reliability-sensitive initiatives — notifications, audit
logging, and compliance pipelines — cannot be built on a source that silently
drops events. Until delivery is reliable, every consumer must choose between
polling and accepting missed events.

## In Scope

- Reliable delivery of the existing event set through the `Watch` API, so a
  consumer receives the events it missed while disconnected once it reconnects
  and resumes from its last position (at-least-once delivery)
  [Clarify: R1.Q1, R2.Q3].
- An opt-in resume position ("offset") and consumer-group identifier on the
  `Watch` request: supplying a group causes each event to be delivered to
  exactly one instance of that group; omitting it delivers every event to
  every instance [Clarify: R2.Q2] [User].
- Broadcast delivery as the default mode, with load-balanced delivery across a
  consumer group available as an opt-in [User].
- Tenant isolation preserved end-to-end in the reliable delivery path — a
  consumer receives only events for the organization(s) it is authorized to
  see [Jira: OSAC-983].
- Migration of the fulfillment-service controllers — the internal consumers
  that subscribe to events as the backbone of their work — onto the reliable
  delivery path as the first adopters, with no regression in resource
  consistency [Clarify: R2.Q1, R2.Q4] [User].

## Out of Scope

- Migrating other event consumers (for example, the cost-management subsystem)
  onto the reliable delivery path — they can adopt it later through the same
  API without further changes to it [Clarify: R2.Q1].
- Adding, changing, or reformatting events; this feature delivers the events
  exactly as the `Watch` API emits them today, in their current format
  [Clarify: R1.Q3] [User].
- A tenant-facing event query or history API [Jira: OSAC-983].
- Notification delivery (email, webhook) and audit-log storage or query,
  delivered by OSAC-75 and OSAC-63 respectively [Jira: OSAC-983].
- Prometheus alerting rules [Jira: OSAC-983, comment by @Crystal Chun].
- Selection of the specific messaging technology, which is a design-phase
  decision [Clarify: R1.Q2].

## User Stories

### Cloud Provider Admin / Tenant Admin / Tenant User

These personas consume the events API through the public API, and the
reliability capabilities below are identical for all of them, so they share the
following stories. The fulfillment-service's own controllers consume the same
capabilities through the internal API — they are the first adopters and the
primary internal consumer (see In Scope) [User].

- As a Cloud Provider Admin, Tenant Admin, or Tenant User, I want to receive
  the resource-change events my consumer missed while it was disconnected, once
  it reconnects and resumes from its last position, so that I can build
  integrations that never silently drop events without having to poll the API.
- As a Cloud Provider Admin, Tenant Admin, or Tenant User, I want to run
  several instances of an event consumer as a group where each event is
  delivered to only one instance, so that I can scale out event processing
  without handling every event multiple times.
- As a Cloud Provider Admin, Tenant Admin, or Tenant User, I want my existing
  event subscriptions to keep behaving exactly as they do today when I do not
  opt into the new options, so that adopting the reliability features is
  optional and does not force me to change working integrations.

## Dependencies

- **Notifications API (OSAC-75):** Depends on this work for a reliable event
  source to trigger email and webhook delivery.
- **Activity and Audit Log API (OSAC-63):** Depends on this work for durable,
  ordered events to build an immutable audit trail.
- **Breakfix Structured Event API / NCP BFX02 (OSAC-3128):** Depends on
  reliable event delivery for structured breakfix events.
- **MOC compliance logging:** Depends on reliable event delivery for
  HIPAA/NIST audit pipelines.
- **Cost-management subsystem:** Depends on this work to eventually receive
  every event without loss; it adopts the reliable path through the same API
  in a separate effort [Clarify: R2.Q1].

---

## Provenance

Authored: revise @ prd 0.8.0 - 7efcedb, workspace main @ 6e8f396
Phases: draft, revise, revise, revise

<!-- ai-workflow-provenance:{"schema_version":1,"provenance_kind":"session","workflow":"prd","workflow_version":"0.8.0","ai_workflows":"7efcedb","source_repo":"6e8f396","source_repo_branch":"main","commits_behind_main":0,"commits_ahead_main":0,"main_ref":"main","phases":["draft","revise","revise","revise"],"authoring_modes":["skill"],"context_changed":false,"origin_untracked":false} -->
