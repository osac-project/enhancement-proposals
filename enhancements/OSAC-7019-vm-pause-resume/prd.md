# VM pause/resume

| Field | Value |
|-------|-------|
| Author(s) | ibengal |
| Jira | [OSAC-7019](https://redhat.atlassian.net/browse/OSAC-7019) |
| Date | 2026-10-30 |
| Target milestone | 0.5 |
| Status | Draft for review |

## Problem Statement

During tenant-coordinated network maintenance, a tenant may need to halt a
VM's guest I/O without discarding the application state held in RAM. OSAC's
current VM lifecycle interface provides Start, Stop, Restart, and Delete, but
no pause/resume action. Stop/Start requires a new boot and loses that state,
so the tenant cannot continue the same workload after maintenance. Pause
provides a temporary, in-place freeze; it does not reclaim capacity or promise
lower charges. [User]

## In Scope

- VMaaS ComputeInstance pause/resume through the tenant UI, API, and CLI.
  Pause freezes guest CPU execution and I/O while retaining host RAM; Resume
  continues the same VM without a new boot. [Clarify: R1.Q3] [User]
- Pause/resume interactions with Start, Stop, Restart, and Delete, including
  overlapping requests and invalid states, as specified in the acceptance
  cases below.
- Automated validation and E2E coverage of UI, API, and CLI journeys, retained
  RAM, resource persistence, failures, and tenant isolation.

## Out of Scope

- Scheduled or automated pause/resume, including a timed resume.
- Suspend-to-disk, hibernation, or preserving RAM after host failure or VM
  replacement.
- Releasing the VM's RAM or resource reservations, changing metering or
  pricing, or promising reduced charges while paused. [User]
- Paused-VM billing display, which belongs to
  [OSAC-1844](https://redhat.atlassian.net/browse/OSAC-1844).
  [Clarify: R17.Q1]
- Adding live migration or cross-cluster VM movement. Pause does not evacuate
  a node or replace a VM reboot required for an upgrade. Q10 covers what
  tenants see if a paused VM encounters node drain, evacuation, or failure.
  [User]
- A new tenant quota dashboard or quota-management capability.
- Admin-specific pause/resume views or permissions beyond existing VM lifecycle
  access.
- Changes to existing lifecycle behavior outside the pause/resume interactions
  above, including Delete during an ordinary Start or Restart.

## User Stories

### Tenant Admin / Tenant User

1. **Pause execution.** As a Tenant Admin or Tenant User, I want to pause a
   running VM during network maintenance so that the guest stops producing
   I/O without discarding my application's in-memory state.

   Acceptance: through the UI, API, or CLI, an authorized user can pause a
   running VM. When the operation succeeds, guest CPU execution and I/O stop,
   while the VM and its RAM remain allocated and the VM is reported as paused.
   [User]

2. **Resume execution.** As a Tenant Admin or Tenant User, I want to resume a
   paused VM after maintenance so that my workload continues without a new
   boot or reconstruction of its in-memory state.

   Acceptance: through the UI, API, or CLI, an authorized user can resume a
   paused VM. An application holding a value only in RAM retains that value
   and continues its computation. The guest has the same boot identity, and
   OSAC continues the same VM instance without replacing it. [User]

3. **Retain the VM's resources.** As a Tenant Admin or Tenant User, I want my
   VM's network identity and storage preserved across pause/resume so that
   clients can reconnect to the same VM after maintenance.

   Acceptance: the VM identity, configuration, attached disks, and previously
   persisted disk contents, assigned IP address, and guest MAC address are
   unchanged after a successful pause/resume, including a long pause.
   Retaining VM memory does not guarantee that external connections or sessions
   remain valid. [Clarify: R2.Q1]

4. **Observe progress and state.** As a Tenant Admin or Tenant User, I want to
   see the progress of my pause/resume request so that I know when I can begin
   maintenance or return the workload to service.

   Acceptance: the UI, API, and CLI distinguish running from paused, show
   progress, and report the observed final state. The UI disables opposing
   pause/resume actions during transitions. The lifecycle outcomes follow
   OSAC's existing Start/Stop behavior rather than KubeVirt's native responses
   to repeated requests: [Clarify: R17.Q2]

   - Pause on Paused, Resume on Running, a repeated pending request, and Start
     on Paused or during Pause/Resume succeed without new work. For overlapping
     Pause/Resume, the latest accepted request determines the final state;
     intermediate states need not complete.
     [Clarify: R3.Q1, R4.Q1, R6.Q3, R7.Q2, R7.Q3]
   - Pause/Resume on Stopped, Failed, or deleting, and Resume during Restart,
     return invalid-state errors. Pause on Stopped saves no future request;
     the UI offers neither action on Stopped or Failed. On Failed, the existing
     reason stays visible. [Clarify: R6.Q2, R7.Q4, R8.Q4, R9.Q2, R10.Q1]
   - Pause during Start/Restart takes effect after a successful boot; a boot
     failure is shown instead of Paused. Stop/Restart on a paused VM or during
     Pause/Resume supersedes those requests and discards RAM. Stop reaches
     Stopped; a later Start or a Restart boots unpaused. [Clarify: R5.Q1,
     R5.Q2, R6.Q1, R7.Q1, R8.Q1, R8.Q2, R8.Q3]
   - Delete on a paused VM or during Pause/Resume is accepted without waiting.
     It supersedes those requests, removes the VM and retained RAM, and cannot
     be undone by a pending Pause, including one accepted during Start/Restart.
     [Clarify: R9.Q1, R9.Q2, R9.Q3]

   If the host is unreachable, Paused is shown only as the last known,
   unverified state. Node drain follows the VM's configured eviction behavior;
   an eviction that replaces the instance without successful live migration
   loses its RAM state. Confirmed loss of that VM instance removes Resume;
   the UI and API report a new boot as Running only after it succeeds, or
   Failed if it does not, and explain that the retained RAM was lost.
   [Clarify: R11.Q1, R19.Q1]

5. **Understand failure.** As a Tenant Admin or Tenant User, I want a failed
   pause/resume request to explain the failure so that I can decide whether
   maintenance can proceed or the workload needs recovery.

   Acceptance: a failed request produces an error associated with the
   requested operation. The reported VM state reflects the observed outcome,
   including whether it is running or paused; the operation error does not
   itself change the reported state to Failed. If the VM is paused, Resume
   remains available.
   [Clarify: R10.Q1]

6. **Protect tenant workloads.** As a Tenant Admin or Tenant User, I want
   pause/resume access restricted to authorized VMs so that another tenant
   cannot interrupt my workload.

   Acceptance: Pause and Resume follow the same VM authorization as Start and
   Stop. The API rejects a request outside the caller's permitted tenant scope
   without changing the VM. The UI offers actions to the same users who can
   use existing VM lifecycle controls. [Clarify: R13.Q1]

7. **Understand retained resources.** As a Tenant Admin or Tenant User, I want
   to understand the resources my paused VM retains so that I can make an
   informed decision about pausing it.

   Acceptance: user, API, and CLI documentation covers actions, permissions,
   states, errors, external-session limitations, and the distinction from
   stop/start and hibernation. It explains that guest CPU execution stops but
   RAM and existing resource reservations remain allocated, and states the
   IP/MAC retention guarantee. Any applicable tenant quota or allocation
   report continues to count those resources; Pause does not increase
   available quota or promise lower charges. [Clarify: R12.Q1] [User]
   Pause has no automatic end time; the tenant initiates Resume.
   [Clarify: R19.Q1]

## Dependencies

- **KubeVirt:** its documented
  [pause/unpause behavior](https://kubevirt.io/user-guide/user_workloads/lifecycle/#pausing-and-unpausing-a-virtual-machine)
  supplies the execution and memory-retention semantics. It reports Paused,
  or Unknown when the host state cannot be obtained. Its native actions can
  reject repeated or premature requests; OSAC must provide the lifecycle
  outcomes above. The design must validate supported VM configurations and
  paused-VM behavior under the configured node eviction strategy.
- **VMaaS networking:** preservation must align with the accepted
  [networking decisions](https://github.com/osac-project/osac/blob/main/docs/agent-context/networking-decisions.md)
  and [VMaaS networking design](https://github.com/osac-project/enhancement-proposals/blob/main/enhancements/OSAC-1435-vmaas-networking/design.md#network-status-and-address-discovery).
  The design must validate the pause-specific IP/MAC guarantee on supported
  networks, including long pauses, and accurate OSAC state reporting.
- **OSAC-UI and OSAC-VMaaS:** UX/UI design and the lifecycle capability must
  agree on actions, progress, errors, and tenant permissions. OSAC-7019 owns
  tenant pause/resume delivery through the UI, API, and CLI;
  [OSAC-1844](https://redhat.atlassian.net/browse/OSAC-1844) owns any
  paused-VM billing display. [Clarify: R17.Q1]
- **Deployment compatibility:** OSAC does not currently support in-place
  platform upgrades. The design must assess compatibility for existing VM
  state and independently deployed components, as required by
  [OSAC's platform scope guidance](https://github.com/osac-project/osac/blob/main/docs/agent-context/osac-dimensions.md#milestone-scoping).

The following question remains open for review.

| ID | Decision needed | Owner | Effect on the draft |
|----|-----------------|-------|---------------------|
| Q10 | With the configured eviction strategy, can a user-paused VM live migrate during node drain while retaining RAM, paused state, and IP/MAC? If migration is unavailable or fails, what state, error, and Resume availability does OSAC show until eviction or instance loss is confirmed? [User] | OSAC-VMaaS and Product | Defines tenant-visible behavior during maintenance after validating KubeVirt support; does not add a migration action or promise RAM preservation after instance loss. |

---

## Provenance

Authored: draft @ prd 0.11.5 - 7e2d081, workspace main @ fa782878f
Final: respond @ prd 0.11.5 - b369da0, workspace main @ fa782878f

> Context changed between draft and respond.

<!-- ai-workflow-provenance:{"schema_version":1,"provenance_kind":"session","workflow":"prd","workflow_version":"0.11.5","ai_workflows":"b369da0","source_repo":"fa782878f","source_repo_branch":"main","commits_behind_main":0,"commits_ahead_main":0,"main_ref":"main","phases":["draft","revise","revise","revise","revise","revise","revise","revise","revise","revise","revise","revise","revise","revise","revise","revise","revise","revise","revise","revise","revise","revise","revise","revise","revise","revise","revise","revise","revise","revise","respond"],"authoring_modes":["skill"],"context_changed":true,"origin_untracked":false} -->
