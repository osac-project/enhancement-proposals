# BMaaS Provisioning Progress and Step Visibility

| Field     | Value |
|-----------|-------|
| Author(s) | Matthieu Bernardin |
| Jira      | https://redhat.atlassian.net/browse/OSAC-3459 |
| Date      | 2026-08-31 |

## Problem Statement

When a bare metal server is ordered through the OSAC UI, the instance enters a "Provisioning" state with no indication of which deployment step is executing, how long it has been running, or where the process has stalled. Users cannot distinguish host allocation from OS imaging from configuration — and a terminal "Failed" badge on error leaves no information to guide self-service troubleshooting. The same gap exists during deprovisioning: teardown progress is equally opaque. Every stalled or slow deployment that cannot be self-diagnosed adds to operator support load and extends time-to-resolution.

## In Scope

- Both provisioning and deprovisioning workflows expose step-level progress: the bare metal instance detail view shows each phase's name, state (pending, running, succeeded, failed, or skipped — a phase with no work to do, such as network setup for an instance requesting no network attachment, is marked skipped rather than left pending), and a single transition timestamp (the moment the phase became active); per-phase duration is derived from the next phase's transition timestamp rather than stored as a separate start/end pair. The final resting phase and the point-in-time milestones carry a transition timestamp with no derived duration. [Clarify: R2.Q3]
- The provisioning workflow presents four observable phases: Host Allocation, Provisioning, Network Setup, and Ready. (The earlier Hardware Preparation, OS Deployment, Configuration, and Verification steps run inside a single opaque provisioning-automation job and are not independently observable, so they are folded into the Provisioning phase.) The deprovisioning workflow presents three phases: Teardown Initiated, Cleaning, and Released. [Clarify: R3.Q3]
- While a bare metal instance is actively provisioning or deprovisioning, the progress view auto-refreshes on a bounded ~5-second interval without requiring user action, and stops polling once the instance reaches a terminal state (ready, failed, or released). Users see backend progress reflected within single-digit seconds without reloading the page. [Clarify: R1.Q2]
- The step-level timeline persists after provisioning finishes, giving users access to the full phase history of completed — including failed — instances. When deprovisioning begins, the completed provisioning history is retained alongside the new deprovisioning timeline: the two are surfaced as separate provisioning and deprovisioning histories, so users can review both the original deployment and the teardown of the same instance. Both histories persist for the life of the instance record. [Clarify: R1.Q4]
- Progress is presented consistently with how VMaaS compute instances (OSAC-1027) and CaaS clusters (OSAC-1604) surface their progress — the same phase-and-sub-step display — so users get a consistent progress experience across services rather than a BMaaS-specific one. (How this consistency is achieved at the API level is a design concern.) [User]
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

- As a Tenant User, Tenant Admin, or Cloud Provider Admin, I want to see a step-by-step progress timeline on a bare metal instance's detail page — with each phase's state and transition timestamp (from which its duration is derived) — so that I can tell where the deployment is in the workflow and how long each step has been running.
- As a Tenant User, Tenant Admin, or Cloud Provider Admin, I want to see which provisioning phase failed and a clear description of the failure condition, so that I can understand where the deployment stopped and determine next steps. [User]

  Example failure descriptions, by phase:

  | Phase | Example |
  |---|---|
  | Host Allocation | "No bare metal host matched the requested profile; contact support if this persists." |
  | Provisioning | "OS installation and configuration did not complete; the provisioning job failed." |
  | Network Setup | "Network attachment did not complete." |
  | Ready | "The instance did not reach its powered-on ready state." |

  Failure descriptions identify the phase and condition without persona-specific action guidance; the appropriate next step varies by user role.
- As a Tenant User, Tenant Admin, or Cloud Provider Admin, I want the progress view to refresh automatically while I am watching, so that I do not have to reload the page to track an active deployment.
- As a Tenant User, Tenant Admin, or Cloud Provider Admin, I want to see the full step-level provisioning history for an instance that has already finished deploying (successfully or with a failure), so that I can review what phases ran and how long each took.
- As a Tenant User, Tenant Admin, or Cloud Provider Admin, I want to see step-by-step deprovisioning progress when a bare metal instance is being deleted, so that I can track teardown to completion.

## Assumptions

- The four provisioning phases (Host Allocation, Provisioning, Network Setup, Ready) and three deprovisioning phases (Teardown Initiated, Cleaning, Released) are user-facing labels, not backend states, and do not necessarily map one-to-one to underlying provisioning states — a single phase may aggregate several backend steps, and some originally envisioned steps are not distinct observable signals. How each user-visible phase maps to an authoritative backend signal — its start/finish conditions, timestamp durability, behavior for skipped, retried, or overlapping steps, and whether it is a point-in-time milestone or a phase with a running state — is a design concern resolved in the design document.
- A bare metal instance's step-level timeline remains viewable after the instance finishes provisioning or is released. How a released instance's history stays addressable, how long it is retained, and which roles can view it are design decisions deferred to the design phase.

## Dependencies

- **OSAC-1027 (ComputeInstance phase/condition expansion, VMaaS) and OSAC-1604 (Cluster status report, CaaS) — references, not blockers:** these establish the OSAC status-condition progress pattern — a lifecycle phase plus orthogonal conditions with a reason vocabulary — that this feature reuses. This work is not gated on either: OSAC-1027 is already implemented for VMaaS, and OSAC-1604 (adapting the pattern for CaaS) can proceed in parallel. The design should align with OSAC-1604 to keep the cross-service experience consistent. (OSAC-1604's own PRD already scopes BMaaS as a separate feature sharing this pattern.) [Clarify: R3.Q2]

---

## Provenance

Authored: draft @ prd 0.9.0 - a17a43d, workspace main @ ed93971
Final: respond @ prd 0.9.0 - 562b610, workspace main @ 63b090a

> Context changed between draft and respond.

<!-- ai-workflow-provenance:{"schema_version":1,"provenance_kind":"session","workflow":"prd","workflow_version":"0.9.0","ai_workflows":"562b610","source_repo":"63b090a","source_repo_branch":"main","commits_behind_main":0,"commits_ahead_main":6,"main_ref":"main","phases":["draft","revise","revise","revise","revise","revise","respond","respond"],"authoring_modes":["skill"],"context_changed":true,"origin_untracked":false} -->
