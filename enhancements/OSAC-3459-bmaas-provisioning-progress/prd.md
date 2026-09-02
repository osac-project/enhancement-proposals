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
- Progress is surfaced using the status-condition pattern OSAC already established for VMaaS compute instances (OSAC-1027) and is adopting for CaaS clusters (OSAC-1604): a lifecycle phase plus status conditions whose reason names the current sub-step. BMaaS-specific phases (host allocation, hardware preparation, and so on) are expressed as BMaaS reason values within that shared shape — they are not imposed on other services. Reusing the established pattern keeps the progress experience consistent across services without inventing a BMaaS-specific model. [User]
- Failure descriptions identify the phase that failed and the failure condition in human-readable terms; raw internal system errors and implementation-level details are not surfaced. [User]

## Out of Scope

- User-initiated actions on failure: the progress and failure display is read-only. No retry or re-provision actions are in scope. [Clarify: R1.Q3]
- Automated remediation of failed provisioning steps.
- Changes to the underlying bare metal operator or provisioning automation logic.
- Progress visibility for VMaaS compute instances or CaaS clusters: those services are addressed by OSAC-1027 and OSAC-1604 respectively and are out of scope for this feature, which reuses the same pattern for BMaaS. [Clarify: R3.Q1]
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

- The five provisioning phases (Host Allocation, Hardware Preparation, OS Deployment, Configuration, Verification) and three deprovisioning phases (Teardown Initiated, Cleaning, Released) are user-facing labels, not backend states. They do not map one-to-one to the metal3 BareMetalHost state machine: OS Deployment corresponds to metal3 `provisioning`; Hardware Preparation aggregates metal3 `registering`/`inspecting`/`preparing`/`cleaning`; and Configuration and Verification are OSAC-level steps that occur after metal3 reaches `provisioned`. The design must map each user-visible phase to an authoritative backend signal and define its start/finish conditions, timestamp durability, and behavior for skipped or retried steps; phases that do not correspond to a distinct, observable backend signal (for example, Verification) may be renamed, merged, or dropped during design.
- A bare metal instance's step-level timeline remains viewable after the instance finishes provisioning or is released. How a released instance's history stays addressable, how long it is retained, and which roles can view it are design decisions deferred to the design phase.

## Dependencies

- **OSAC-1027 (ComputeInstance phase/condition expansion, VMaaS) and OSAC-1604 (Cluster status report, CaaS):** together these establish the OSAC status-condition progress pattern — a lifecycle phase plus orthogonal conditions with a reason vocabulary. OSAC-1027 is implemented for VMaaS; OSAC-1604 adapts it for CaaS and is in progress. This feature adopts that same pattern for BMaaS rather than introducing a new one; the design should align with OSAC-1604 to keep the cross-service experience consistent. (OSAC-1604's own PRD already scopes BMaaS as a separate feature sharing this pattern.) [Clarify: R3.Q2]

---

## Provenance

Authored: draft @ prd 0.9.0 - a17a43d, workspace main @ ed93971
Final: respond @ prd 0.9.0 - a17a43d, workspace main @ 63b090a

> Context changed between draft and respond.

<!-- ai-workflow-provenance:{"schema_version":1,"provenance_kind":"session","workflow":"prd","workflow_version":"0.9.0","ai_workflows":"a17a43d","source_repo":"63b090a","source_repo_branch":"main","commits_behind_main":0,"commits_ahead_main":6,"main_ref":"main","phases":["draft","revise","revise","revise","revise","revise","respond"],"authoring_modes":["skill"],"context_changed":true,"origin_untracked":false} -->
