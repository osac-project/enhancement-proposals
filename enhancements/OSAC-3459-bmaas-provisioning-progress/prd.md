# BMaaS Provisioning Progress and Step Visibility

| Field     | Value |
|-----------|-------|
| Author(s) | Matthieu Bernardin |
| Jira      | https://redhat.atlassian.net/browse/OSAC-3459 |
| Date      | 2026-08-31 |

## Problem Statement

When a bare metal server is ordered through the OSAC UI, the instance enters a "Provisioning" state with no indication of which deployment step is executing or where the process has stalled. Users cannot distinguish host allocation from OS imaging from configuration — and a terminal "Failed" badge on error leaves no information to guide self-service troubleshooting. Every stalled or slow deployment that cannot be self-diagnosed adds to operator support load and extends time-to-resolution. (The same opacity exists during deprovisioning, but teardown progress is deferred to a follow-up — see Out of Scope — so this feature focuses on provisioning.)

## In Scope

- The provisioning workflow exposes step-level progress: the bare metal instance detail view shows the current provisioning phase's name, its state (pending, running, succeeded, or failed), and a human-readable status message. Progress is derived from the instance's status conditions; the detail view highlights which of the known phases is currently running (earlier phases done, later phases pending). A phase with no work to do (such as network setup for an instance requesting no network attachment) is shown as completed rather than left stuck pending. [Clarify: R2.Q3]
- The provisioning workflow presents four observable phases: Host Allocation, Provisioning, Network Setup, and Ready. (The earlier Hardware Preparation, OS Deployment, Configuration, and Verification steps run inside a single opaque provisioning-automation job and are not independently observable, so they are folded into the Provisioning phase.) [Clarify: R3.Q3]
- While a bare metal instance is actively provisioning, the progress view auto-refreshes on a bounded ~5-second interval without requiring user action, and stops polling once the instance's provisioning has finished — a successfully provisioned instance resting at ready, or an instance whose provisioning failed. Users see backend progress reflected within single-digit seconds without reloading the page. [Clarify: R1.Q2]
- The terminal outcome persists after provisioning finishes: for a completed instance the detail view shows all phases succeeded, and for a failed instance it shows which phase failed and the human-readable failure message. This terminal/failure state remains viewable for the life of the instance record (until a released instance's record is archived). A full ordered per-phase history with per-phase durations is not part of this iteration and is deferred to a follow-up (see Out of Scope). [Clarify: R1.Q4]
- Progress is presented consistently with how CaaS clusters (OSAC-1604) and VMaaS compute instances (OSAC-1027) surface their progress — the same coarse-condition, staged reason/message display — so users get a consistent progress experience across services rather than a BMaaS-specific one. (How this consistency is achieved at the API level is a design concern.) [User]
- Failure descriptions identify the phase that failed and the failure condition in human-readable terms; raw internal system errors and implementation-level details are not surfaced. [User]

## Out of Scope

- Deprovisioning (teardown) progress visibility: surfacing step-level progress while a bare metal instance is being deleted is deferred to a follow-up. Deletion continues to show only the coarse deleting/deleted state in this iteration.
- A durable, ordered per-phase timeline with per-phase transition timestamps and derived durations (and any provisioning event-timeline or log view): this iteration surfaces the current phase and the terminal/failure outcome via the instance's status conditions, not a stored per-phase history. A persisted full history is deferred to a follow-up.
- User-initiated actions on failure: the progress and failure display is read-only. No retry or re-provision actions are in scope. [Clarify: R1.Q3]
- Automated remediation of failed provisioning steps.
- Changes to the underlying bare metal operator or provisioning automation logic.
- Progress visibility for VMaaS compute instances or CaaS clusters: those services are addressed by OSAC-1027 and OSAC-1604 respectively and are out of scope for this feature, which reuses the same pattern for BMaaS. [Clarify: R3.Q1]
- A new cross-tenant aggregated list of in-progress bare metal instances: Cloud Provider Admin reaches individual instances through existing navigation. [Clarify: R2.Q2]
- Component log access per provisioning phase: this feature delivers step-level visibility only — phase name, state, and timestamps. Surfacing log output from the underlying provisioning automation is out of scope. [User]

## User Stories

### Tenant User, Tenant Admin, and Cloud Provider Admin

- As a Tenant User, Tenant Admin, or Cloud Provider Admin, I want to see which provisioning phase is currently running on a bare metal instance's detail page — with earlier phases marked done and later phases pending — so that I can tell where the deployment is in the workflow.
- As a Tenant User, Tenant Admin, or Cloud Provider Admin, I want to see which provisioning phase failed and a clear description of the failure condition, so that I can understand where the deployment stopped and determine next steps. [User]

  Example failure descriptions, by phase:

  | Phase | Example |
  |---|---|
  | Host Allocation | "No bare metal host matched the requested profile." |
  | Provisioning | "OS installation and configuration did not complete; the provisioning job failed." |
  | Network Setup | "Network attachment did not complete." |
  | Ready | "The instance did not reach its powered-on ready state." |

  Failure descriptions identify the phase and condition without persona-specific action guidance; the appropriate next step varies by user role.
- As a Tenant User, Tenant Admin, or Cloud Provider Admin, I want the progress view to refresh automatically while I am watching, so that I do not have to reload the page to track an active deployment.
- As a Tenant User, Tenant Admin, or Cloud Provider Admin, I want an instance that has already finished deploying to show its terminal outcome — all phases succeeded, or which phase failed and why — so that I can review the result of the deployment after it completes.

## Assumptions

- The four provisioning phases (Host Allocation, Provisioning, Network Setup, Ready) are user-facing labels, not backend states, and do not necessarily map one-to-one to underlying provisioning states — a single phase may aggregate several backend steps, and some originally envisioned steps are not distinct observable signals. How each user-visible phase maps to an authoritative backend signal — its start/finish conditions, behavior for phases with no work to do, retried, or overlapping steps — is a design concern resolved in the design document.
- A bare metal instance's terminal/failure state remains viewable after the instance finishes provisioning. How that state stays addressable and how long it is retained are design decisions deferred to the design phase. (A durable, ordered per-phase history is out of scope for this iteration; see Out of Scope.)

## Dependencies

- **OSAC-1604 (Cluster status report, CaaS) and OSAC-1027 (ComputeInstance phase/condition expansion, VMaaS) — references, not blockers:** these establish the OSAC coarse-condition progress pattern this feature reuses — a single progress-bearing condition whose `reason`/`message` carry the furthest-advanced stage, refreshed each reconcile, with a terminal `READY` condition (CaaS's just-merged OSAC-4441 shape). This work is not gated on either: OSAC-1027 is implemented for VMaaS, and OSAC-1604 has landed the pattern for CaaS. The design aligns with OSAC-1604 to keep the cross-service experience consistent, expressing BMaaS provisioning stages through the existing `PROVISIONED` condition rather than a BMaaS-specific timeline. (OSAC-1604's own PRD already scopes BMaaS as a separate feature sharing this pattern.) [Clarify: R3.Q2]

---

## Provenance

Authored: draft @ prd 0.9.0 - a17a43d, workspace main @ ed93971
Final: respond @ prd 0.9.0 - 562b610, workspace main @ 63b090a

> Context changed between draft and respond.

<!-- ai-workflow-provenance:{"schema_version":1,"provenance_kind":"session","workflow":"prd","workflow_version":"0.9.0","ai_workflows":"562b610","source_repo":"63b090a","source_repo_branch":"main","commits_behind_main":0,"commits_ahead_main":6,"main_ref":"main","phases":["draft","revise","revise","revise","revise","revise","respond","respond"],"authoring_modes":["skill"],"context_changed":true,"origin_untracked":false} -->
