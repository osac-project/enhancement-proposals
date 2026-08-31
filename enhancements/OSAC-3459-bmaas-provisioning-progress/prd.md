# BMaaS Provisioning Progress and Step Visibility

| Field     | Value |
|-----------|-------|
| Author(s) | Matthieu Bernardin |
| Jira      | https://redhat.atlassian.net/browse/OSAC-3459 |
| Date      | 2026-08-31 |

## Problem Statement

When a bare metal server is ordered through the OSAC UI, the instance enters a "Provisioning" state with no indication of which deployment step is executing, how long it has been running, or where the process has stalled. Users cannot distinguish host allocation from OS imaging from configuration — and a terminal "Failed" badge on error leaves no information to guide self-service troubleshooting. The same gap exists during deprovisioning: teardown progress is equally opaque. Every stalled or slow deployment that cannot be self-diagnosed adds to operator support load and extends time-to-resolution.

## In Scope

- Both provisioning and deprovisioning workflows expose step-level progress: the bare metal instance detail view shows each phase's name, state (pending, running, succeeded, or failed), and start and end timestamps. [Clarify: R2.Q3]
- The provisioning workflow presents five user-visible phases: Host Allocation, Hardware Preparation, OS Deployment, Configuration, and Verification. The deprovisioning workflow presents three phases: Teardown Initiated, Cleaning, and Released. [Clarify: R3.Q3]
- The progress view auto-refreshes approximately every 5 seconds without requiring user action. [Clarify: R1.Q2]
- The step-level timeline persists after provisioning or deprovisioning finishes, giving users access to the full phase history of completed — including failed — instances. [Clarify: R1.Q4]
- The provisioning progress data model is designed for reuse across OSAC services: its structure must accommodate the provisioning semantics of other services (such as VMaaS and CaaS) so that they can adopt the same model without redesign when their progress visibility is implemented. [User]
- Failure descriptions identify the phase that failed and the failure condition in human-readable terms; raw internal system errors and implementation-level details are not surfaced. [User]

## Out of Scope

- User-initiated actions on failure: the progress and failure display is read-only. No retry or re-provision actions are in scope. [Clarify: R1.Q3]
- Automated remediation of failed provisioning steps.
- Changes to the underlying bare metal operator or provisioning automation logic.
- Progress visibility for VMaaS compute instances or CaaS clusters: while the pattern introduced here is intended to generalize across OSAC services, those services are out of scope for this feature. [Clarify: R3.Q1]
- A new cross-tenant aggregated list of in-progress bare metal instances: Cloud Provider Admin reaches individual instances through existing navigation. [Clarify: R2.Q2]
- Component log access per provisioning phase: this feature delivers step-level visibility only — phase name, state, and timestamps. Surfacing log output from the underlying provisioning automation is out of scope. [User]

## User Stories

### Tenant User, Tenant Admin, and Cloud Provider Admin

- As a Tenant User, Tenant Admin, or Cloud Provider Admin, I want to see a step-by-step progress timeline on a bare metal instance's detail page — with each phase's state and start/end timestamps — so that I can tell where the deployment is in the workflow and how long each step has been running.
- As a Tenant User, Tenant Admin, or Cloud Provider Admin, I want to see which provisioning phase failed and a clear description of the failure condition, so that I can understand where the deployment stopped and determine next steps. [User]

  Example failure descriptions, by phase:

  | Phase | Example |
  |---|---|
  | Host Allocation | "No available host matching the requested configuration. All hosts with the required profile are currently allocated." |
  | Hardware Preparation | "Hardware preparation timed out — the host did not complete cleaning within the expected time." |
  | OS Deployment | "OS deployment failed — the operating system image could not be written to the host." |
  | Configuration | "Configuration failed — the host was not reachable for configuration application after imaging." |
  | Verification | "Verification failed — the host did not pass readiness checks within the expected time." |

  Failure descriptions identify the phase and condition without persona-specific action guidance; the appropriate next step varies by user role.
- As a Tenant User, Tenant Admin, or Cloud Provider Admin, I want the progress view to refresh automatically while I am watching, so that I do not have to reload the page to track an active deployment.
- As a Tenant User, Tenant Admin, or Cloud Provider Admin, I want to see the full step-level provisioning history for an instance that has already finished deploying (successfully or with a failure), so that I can review what phases ran and how long each took.
- As a Tenant User, Tenant Admin, or Cloud Provider Admin, I want to see step-by-step deprovisioning progress when a bare metal instance is being deleted, so that I can track teardown to completion.

## Assumptions

- The five provisioning phases (Host Allocation, Hardware Preparation, OS Deployment, Configuration, Verification) and three deprovisioning phases (Teardown Initiated, Cleaning, Released) accurately represent the stages a user can observe during bare metal deployment and teardown. The mapping from backend states to these labels is subject to validation during design; phase names may be adjusted if the backend state model does not align.

## Dependencies

- **OSAC-1604 (Cluster status report, CaaS):** OSAC-1604 is actively working on granular status reporting for CaaS clusters. The design for this feature should coordinate with OSAC-1604 to produce a consistent progress visibility pattern across OSAC services and to avoid divergent approaches that would complicate future cross-service generalization. [Clarify: R3.Q2]

---

## Provenance

Authored: revise @ prd 0.9.0 - a17a43d, workspace main @ ed93971
Phases: draft, revise, revise, revise, revise, revise

<!-- ai-workflow-provenance:{"schema_version":1,"provenance_kind":"session","workflow":"prd","workflow_version":"0.9.0","ai_workflows":"a17a43d","source_repo":"ed93971","source_repo_branch":"main","commits_behind_main":0,"commits_ahead_main":2,"main_ref":"main","phases":["draft","revise","revise","revise","revise","revise"],"authoring_modes":["skill"],"context_changed":false,"origin_untracked":false} -->
