# VM pause/resume

| Field | Value |
|-------|-------|
| Author(s) | ibengal |
| Jira | [OSAC-7019](https://redhat.atlassian.net/browse/OSAC-7019) |
| Date | 2026-10-30 |
| Target milestone | 0.5 |
| Status | Draft for review |

## Problem Statement

A Tenant Admin or Tenant User investigating a multi-VM application may need to
freeze one member briefly while its peers continue, then resume it from the
same in-memory state. For example, in a test of a stateful service, the tenant
wants to pause one VM, observe the peers' logs and health checks during the
stall, and resume that VM to see how it rejoins. OSAC currently offers Start,
Stop, Restart, and Delete for VMs, but no tenant-authorized Pause/Resume
action; tenants do not have direct KubeVirt access. Stop/Start reboots the VM
and discards volatile state, while isolating its network or stopping one guest
process does not freeze the whole guest. Pause provides that whole-VM freeze
without reclaiming host capacity; metering while paused follows the existing
CAP-11 rules. [User] [Clarify: R20.Q1, R23.Q1]

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
- Releasing the VM's RAM or resource reservations, or changing existing
  metering or pricing rules. Under
  [CAP-11](/enhancements/OSAC-5753-event-log-driven-metering/prd.md), paused
  VMs accrue no compute metering; their storage volumes and public IPs remain
  metered. OSAC-7019 changes none of these rules. Pausing does not reclaim
  host capacity. [Clarify: R20.Q1]
- Paused-VM billing display, which belongs to
  [OSAC-1844](https://redhat.atlassian.net/browse/OSAC-1844).
  [Clarify: R17.Q1]
- Adding live migration or cross-cluster VM movement. Pause does not evacuate
  a node or replace a VM reboot required for an upgrade. [User]
- A new tenant quota dashboard or quota-management capability.
- Admin-specific pause/resume views or permissions beyond existing VM lifecycle
  access.
- Changes to existing lifecycle behavior outside the pause/resume interactions
  above, including Delete during an ordinary Start or Restart.

## User Stories

### Tenant Admin / Tenant User

1. **Pause execution.** As a Tenant Admin or Tenant User, I want to pause a
   running VM briefly while investigating my multi-VM application, such as
   during integration testing, so that I can observe how its peers respond to
   a stalled member without losing that member's in-memory state.
   [Clarify: R23.Q1]

   Acceptance: through the UI, API, or CLI, an authorized user can pause a
   running VM. When the operation succeeds, guest CPU execution and I/O stop,
   while the VM and its RAM remain allocated and the VM is reported as paused.
   [User]

2. **Resume execution.** As a Tenant Admin or Tenant User, I want to resume a
   paused VM after the investigation so that my workload continues without a
   new boot or reconstruction of its in-memory state.

   Acceptance: through the UI, API, or CLI, an authorized user can resume a
   paused VM. An application holding a value only in RAM retains that value
   and continues its computation. The guest has the same boot identity, and
   OSAC continues the same VM instance without replacing it. [User]

3. **Retain the VM's resources.** As a Tenant Admin or Tenant User, I want my
   VM's network identity and storage preserved across pause/resume so that
   clients can reconnect to the same VM when I resume it.

   Acceptance: the VM identity, configuration, attached disks, and previously
   persisted disk contents, assigned IP address, and guest MAC address are
   unchanged after a successful pause/resume, including a long pause.
   Retaining VM memory does not guarantee that external connections or sessions
   remain valid. [Clarify: R2.Q1]

4. **Observe the VM state.** As a Tenant Admin or Tenant User, I want to see
   the VM's current lifecycle state so that I know whether it is running or
   paused.

   Acceptance: the UI, API, and CLI report the observed VM lifecycle state,
   including Running, Paused, Stopped, or Failed. They do not show
   pause/resume progress or a separate status for an individual request. While
   a pause/resume request is pending, they continue to report the last
   observed VM state; they report the new state after it is observed. If a
   newer request supersedes an earlier one, they report the resulting VM state
   without a separate terminal result for the superseded request. The UI
   disables opposing pause/resume actions during transitions. Lifecycle
   outcomes follow OSAC's existing Start/Stop behavior rather than KubeVirt's
   native responses to repeated requests: [Clarify: R17.Q2, R21.Q1]

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

   Node drain follows the VM's configured eviction behavior. After a
   successful live migration of a user-paused VM, it remains Paused with its
   RAM state retained; the tenant must explicitly Resume it. If migration
   cannot proceed or fails while the original instance remains observed as
   Paused, OSAC continues to show Paused and offer Resume without indicating
   that evacuation succeeded. If the host becomes unreachable, Paused is shown
   only as the last known, unverified state. An eviction that replaces the
   instance without successful live migration loses its RAM state. Confirmed
   loss of that VM instance removes Resume; the UI and API report a new boot
   as Running only after it succeeds, or Failed if it does not, and explain
   that the retained RAM was lost. [Clarify: R11.Q1, R19.Q1, R22.Q1]

5. **Understand request rejection.** As a Tenant Admin or Tenant User, I want
   a rejected Pause or Resume request to explain why OSAC could not accept it
   so that I can correct the request or choose another action.

   Acceptance: when OSAC rejects a Pause or Resume request, it returns an
   appropriate request-level error, such as unauthorized access, a missing VM,
   or an invalid lifecycle state. The rejection does not change the observed
   VM state. This requirement does not cover a later execution failure after
   OSAC has accepted the request. [Clarify: R10.Q1] [User]

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
   available quota. Under
   [CAP-11](/enhancements/OSAC-5753-event-log-driven-metering/prd.md),
   compute metering stops while the VM is paused, while storage volumes and
   public IPs remain metered. OSAC-7019 does not change this behavior or
   pricing. [Clarify: R12.Q1, R20.Q1]
   Pause has no automatic end time; the tenant initiates Resume.
   [Clarify: R19.Q1]

## Dependencies

- **KubeVirt:** its documented
  [pause/unpause behavior](https://kubevirt.io/user-guide/user_workloads/lifecycle/#pausing-and-unpausing-a-virtual-machine)
  supplies the execution and memory-retention semantics. It reports Paused,
  or Unknown when the host state cannot be obtained. Its native actions can
  reject repeated or premature requests; OSAC must provide the lifecycle
  outcomes above. KubeVirt's
  [user-paused migration test](https://github.com/kubevirt/kubevirt/blob/v1.9.1/tests/migration/migration.go#L657-L688)
  confirms that a successfully migrated VMI stays paused until explicitly
  unpaused. The design must validate migration eligibility under OSAC's
  supported storage, networking, and eviction configurations.
- **VMaaS networking:** preservation must align with the accepted
  [networking decisions](https://github.com/osac-project/osac/blob/main/docs/agent-context/networking-decisions.md)
  and [VMaaS networking design](https://github.com/osac-project/enhancement-proposals/blob/main/enhancements/OSAC-1435-vmaas-networking/design.md#network-status-and-address-discovery).
  The design must validate the pause-specific IP/MAC guarantee on supported
  networks, including long pauses and successful live migration, and accurate
  OSAC state reporting.
- **OSAC-UI and OSAC-VMaaS:** UX/UI design and the lifecycle capability must
  agree on actions, state reporting, errors, and tenant permissions.
  OSAC-7019 owns tenant pause/resume delivery through the UI, API, and CLI;
  [OSAC-1844](https://redhat.atlassian.net/browse/OSAC-1844) owns any
  paused-VM billing display. [Clarify: R17.Q1]
- **Deployment compatibility:** OSAC does not currently support in-place
  platform upgrades. The design must assess compatibility for existing VM
  state and independently deployed components, as required by
  [OSAC's platform scope guidance](https://github.com/osac-project/osac/blob/main/docs/agent-context/osac-dimensions.md#milestone-scoping).

---

## Provenance

Authored: draft @ prd 0.11.5 - 7e2d081, workspace main @ fa782878f
Final: respond @ prd 0.11.5 - 70405a6, workspace main @ fa782878f

> Context changed between draft and respond.

<!-- ai-workflow-provenance:{"schema_version":1,"provenance_kind":"session","workflow":"prd","workflow_version":"0.11.5","ai_workflows":"70405a6","source_repo":"fa782878f","source_repo_branch":"main","commits_behind_main":0,"commits_ahead_main":0,"main_ref":"main","phases":["draft","revise","revise","revise","revise","revise","revise","revise","revise","revise","revise","revise","revise","revise","revise","revise","revise","revise","revise","revise","revise","revise","revise","revise","revise","revise","revise","revise","revise","revise","respond","respond","respond","respond","respond","respond","respond","respond"],"authoring_modes":["skill"],"context_changed":true,"origin_untracked":false} -->
