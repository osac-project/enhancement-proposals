# Expose ComputeInstance Provisioning Failures During Retries

| Field     | Value |
|-----------|-------|
| Author(s) | Carlo Lobrano |
| Jira      | https://redhat.atlassian.net/browse/OSAC-6008 |
| Date      | 2026-10-06 |

## Problem Statement

When a VMaaS ComputeInstance provisioning attempt fails, the failure is briefly visible in the instance's status. However, after a brief period, the failure status disappears and reverts to a generic waiting state, and the provisioning lifecycle then schedules a retry for the failed job. The result is that users lose visible failure status: the failure occurred and a retry is underway, but the status surface no longer reflects either fact. Users cannot tell whether the instance is simply pending initial provisioning or is recovering from a failed attempt, and they have no failure details to investigate. [Jira: OSAC-6008]

This affects every persona that interacts with ComputeInstance status in VMaaS:

- **Cloud Provider Admin** — supports tenants and identifies affected resources across organizations; loses the ability to spot retry-impacted instances when the status reverts to generic waiting.
- **Cloud Infrastructure Admin** — investigates infrastructure and integration issues; cannot distinguish an ordinary wait from a retry after a failed provisioning attempt when the failure is no longer visible.
- **Tenant Admin** — gives users in their organization an accurate status and seeks support when needed; sees the same generic waiting state whether the instance is on its first attempt or recovering from a failure.
- **Tenant User** — decides whether to wait or ask for help; has no signal that a failure occurred or that provisioning is being retried. [Jira: OSAC-6008]

## In Scope

- When a provisioning attempt fails and a retry is pending or active, the ComputeInstance status clearly distinguishes two retry states: **retry scheduled** (a retry has been queued but the next provisioning job has not started) and **retry running** (the retry provisioning job has started and is executing). This distinction is visible through the UI and CLI. Specific API fields and data flow are deferred to the design document. [Jira: OSAC-6008]
- The status surface retains the most recent provisioning failures up to a bounded limit, providing a limited failure history that users can review alongside the current retry state. When a new failure occurs and the history is at capacity, the oldest entry is replaced (FIFO eviction). The exact cap is deferred to the design document. No "full history" or "all failures" retention is provided. [User]
- Failure information is useful and actionable: each failure entry includes the failure reason and sufficient detail for the user to understand what went wrong and decide on next steps — whether to wait for the retry to succeed, seek support, or investigate further. The goal is to help users make informed decisions, not simply to record that a failure occurred. [Jira: OSAC-6008]
- A user can see a recent failure in the limited history while the current status shows the ComputeInstance as waiting for or running a retry. The prior failure's visibility is not hidden by the current retry state. [Jira: OSAC-6008]
- After provisioning succeeds, the active failure and retry indicators are cleared — the instance is no longer presented as retrying or failed. Earlier failures within the bounded history remain in the limited failure history. This feature addresses provisioning outcome (success after retries), not VM power state or running lifecycle state. [Jira: OSAC-6008]
- Status and diagnostic details respect existing access controls. Role-specific access rules (which personas can see which failure details) are deferred to the design document; the PRD requires only that existing access-control boundaries are honored. [Jira: OSAC-6008]

## Out of Scope

- Changing retry behavior, adding retry limits or timeouts, or classifying errors as transient or permanent. [Jira: OSAC-6008]
- Determining the root cause of each provisioning template failure. [Jira: OSAC-6008]
- VM power state or running lifecycle state after provisioning succeeds — this feature is scoped to provisioning outcome visibility, not ongoing VM operations. [User]

## User Stories

### Cloud Provider Admin

- As a Cloud Provider Admin, I want to see when a tenant's ComputeInstance is retrying after a provisioning failure so that I can support the tenant and identify affected resources. [Jira: OSAC-6008]

### Cloud Infrastructure Admin

- As a Cloud Infrastructure Admin, I want to distinguish an ordinary wait for a VM from a retry after a failed provisioning attempt so that I can investigate infrastructure or integration issues. [Jira: OSAC-6008]

### Tenant Admin

- As a Tenant Admin, I want to see whether my organization's ComputeInstances are retrying after a failed attempt so that I can give users an accurate status and seek support when needed. [Jira: OSAC-6008]

### Tenant User

- As a Tenant User, I want to know when my ComputeInstance is recovering from a failed provisioning attempt so that I can decide whether to wait or ask for help. [Jira: OSAC-6008]

## Dependencies

- **UI and CLI surfaces:** Retry state (retry scheduled / retry running) and the limited failure history must be visible through existing UI and CLI tooling. Which specific views, pages, or CLI commands surface this information is a design concern; the PRD requires that users can access it through the supported status surfaces without needing direct API access. Specific API fields and data flow are deferred to the design document. [User]

## Open Questions

**OQ-1.** Which specific UI views and CLI commands should surface the retry state and failure history?
*Owner: VMaaS / UX team. Impact: In Scope items regarding UI/CLI visibility. API field design is deferred to the design document; this question concerns the user-facing presentation.* [User]

**OQ-2.** Given that the oldest entry is replaced when the bounded failure history is full (FIFO eviction), are there scenarios where the oldest entry should be preserved instead of evicted — for example, a failure still under active investigation — that warrant an exception to the default eviction policy?
*Owner: VMaaS team. Impact: In Scope item on limited failure history.* [User]

**OQ-3.** What specific failure details make the information actionable for each persona — for example, should entries include error codes, timestamps, references to logs or diagnostic resources, or a combination?
*Owner: VMaaS / UX team. Impact: In Scope item on actionable failure information.* [User]
