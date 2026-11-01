# Clarification Log — OSAC-7019

## Status

- Rounds completed: 18; round 1 was reconstructed from the existing conversation.
- Open gaps: 1 (Q10 below).
- Exit criteria met: No; the concrete use case and operational limits in Q10
  remain open.
- Draft authorization: The user requested a first PRD draft with open
  questions. Q10 remains explicit rather than inferred.

## Round 1 — Scope and Delivery

### R1.Q1: Does the Feature require UI work?

#### Answer

The user selected: "Yes — include UX and UI design."

#### Impact

The delivery includes the tenant UI and the API already required by the Feature.
Both UX and UI design work are tracked by the bootstrap tasks.

#### Decision (D1)

UI delivery is in scope. API delivery is required by OSAC-7019. CLI delivery
was undecided at this round and is resolved in D28.

---

### R1.Q2: Which milestone is targeted?

#### Answer

The user chose version 0.5 for now, with the option to change it later.
The Feature currently has fix version 0.5.

#### Impact

The first draft targets milestone 0.5.

#### Decision (D2)

Use target milestone 0.5 unless the user revises it.

---

### R1.Q3: Does resume mean a new boot or continuing retained execution?

#### Answer

The user described pause as a freeze and resume as returning to retained RAM.
After reviewing KubeVirt pause/unpause semantics, the user confirmed that
behavior and explicitly requested that the Feature be updated to match it.

#### Impact

The requirements use pause/unpause semantics: guest execution and I/O freeze,
RAM remains allocated, and the same VM instance resumes without rebooting.
The updated Feature is the authoritative source for the current scope.

#### Decision (D3)

Pause retains RAM and execution state in the same VM; resume continues that
execution. This Feature does not implement power-off/start, hibernation, or
memory-capacity reclamation.

---

### R1.Q4: Can the first draft retain unresolved questions?

#### Answer

After being told that network guarantees, lifecycle interactions, failure
handling, permissions, reporting, and overlap with OSAC-1844 remain open, the
user requested: "please go ahead and use the prd skill to get the draft going".

#### Impact

Create a review draft grounded in confirmed behavior. Preserve unanswered
questions and acceptance gaps explicitly. This authorizes local drafting;
it supplies no answers to Q1–Q8 and does not authorize publishing.

#### Decision (D4)

Proceed with a first review draft carrying the remaining decisions as open.

---

## Round 2 — Network identity during pause

### R2.Q1: Should a successful pause/resume retain the VM's IP and MAC?

#### Answer

The user confirmed that the VM's IP and MAC should not change during
pause/resume, including after a long pause.

#### Impact

The PRD requires the same assigned IP and guest MAC before and after a
successful pause/resume of the same VM instance. The design must validate that
the supported network retains the allocation and OSAC preserves and reports
the same VM instance. External sessions may still time out while the guest is
paused. Loss of the VM instance or host remains a separate open question (Q4).

#### Decision (D5)

A successful pause/resume retains the VM's assigned IP and guest MAC, including
across long pauses. Pause/resume does not promise survival of external
connections or sessions.

---

## Round 3 — Repeated requests

### R3.Q1: What if the requested state is already reached?

#### Answer

The user agreed that pausing an already paused VM and resuming an already
running VM should each succeed as a no-op.

#### Impact

The PRD specifies successful, unchanged-state responses for these two cases.
No second lifecycle operation starts. Requests made while an operation is
still in progress, conflicting requests, and invalid source states remain
open under Q2.

#### Decision (D6)

Pause on an already paused VM and resume on an already running VM succeed
without changing VM state or starting another operation.

---

## Round 4 — Requests during transitions

### R4.Q1: What happens when pause and resume requests arrive during a transition?

#### Answer

The user chose the existing Start/Stop reconciliation pattern: the UI does
not offer an opposing action during a transition, while the API accepts the
latest requested state. An active job may finish; OSAC then acts on the
latest desired state rather than executing every intervening request.

#### Impact

The PRD requires eventual convergence to the latest accepted pause/resume
request, with no overlapping contradictory VM lifecycle jobs. An intermediate
request need not reach its final state if a later request supersedes it.
Repeated requests for the same pending state do not create duplicate work.
The user expects a desired pause/resume state on ComputeInstance to propagate
to the operator and AAP, analogous to Start/Stop; field and job design belong
in the design document. Interaction with Start/Stop was tracked under Q3.

#### Decision (D7)

For pause/resume requests during a transition, the latest accepted desired
state wins. OSAC serializes contradictory work for the same VM and converges
on that state. The UI disables opposing actions during the transition.

---

## Round 5 — Stop on a paused VM

### R5.Q1: Can a paused VM be stopped, and what happens to its retained state?

#### Answer

The user agreed that Stop is allowed on a paused VM and supersedes its paused
state.

#### Impact

Stopping discards the retained RAM and clears the pause intent. The VM becomes
stopped; a later Start is a new boot rather than a continuation from memory.
The API result for a direct Resume request on a stopped VM is resolved in
R6.Q2. Other lifecycle interactions were tracked under Q3.

#### Decision (D8)

Stop on a paused VM supersedes Pause. It clears the pause intent and retained
execution state. A subsequent Start boots the VM unpaused.

---

### R5.Q2: What if Stop is requested while Pause is still in progress?

#### Answer

The user confirmed that Stop is accepted while Pause is in progress and
supersedes the pending pause request. The latest desired state is Stopped.

#### Impact

OSAC waits for the active pause job to finish before starting a Stop job,
then converges to Stopped. The intermediate pause need not be reported as a
completed user-visible state. The pause intent must be cleared so a later
Start boots unpaused. KubeVirt's pause API waits for the launcher pause call
to return, while observed status may lag; its Halted run strategy stops a
VMI regardless of its current phase. The design must validate this sequence
on the supported KubeVirt version and test Stop during an active pause job.

#### Decision (D9)

Stop during an in-progress Pause is accepted and supersedes Pause. The VM
eventually becomes Stopped; a later Start makes a new, unpaused boot.

---

## Round 6 — Stop during Resume and actions on paused or stopped VMs

### R6.Q1: What if Stop is requested while Resume is still in progress?

#### Answer

The user agreed that Stop supersedes an in-progress Resume, following the
same job ordering as Stop during Pause.

#### Impact

The active job may finish, then OSAC converges to Stopped. Retained RAM is
discarded. A subsequent Start is a new boot.

#### Decision (D10)

Stop during Resume is accepted and supersedes Resume; the final target is
Stopped.

---

### R6.Q2: What should Resume do on a stopped VM?

#### Answer

The user decided that Resume on a stopped VM is invalid because Stop has
discarded its retained execution state.

#### Impact

Resume returns an invalid-state error and does not start a new VM. Start is
the action that boots a stopped VM.

#### Decision (D11)

Resume on a stopped VM is rejected without changing the VM.

---

### R6.Q3: What should Start do on a paused VM?

#### Answer

The user decided that Start on a paused VM succeeds as a no-op: the VM is
already started, and Resume is the action that continues its execution.

#### Impact

The VM remains paused, retained RAM is unchanged, and no new operation
starts. The UI continues to offer Resume for a paused VM, not Start. The
separate case of Start during an in-progress Pause is resolved in R7.Q2.

#### Decision (D12)

Start on an already paused VM succeeds without changing the VM or its pause
intent.

---

## Round 7 — Start and Pause interactions

### R7.Q1: What should Pause do while Start is underway?

#### Answer

The user decided that OSAC should accept Pause while Start is underway. The
VM should finish starting and then pause, without a second user request.

#### Impact

Pause becomes the desired state after a successful Start. OSAC must not
report Paused before the VM reaches that state. If Start fails, Pause cannot
complete; the failure is visible rather than a false Paused state. The
sequencing mechanism belongs in the technical design.

#### Decision (D13)

Pause during Starting is accepted and applied after Start succeeds.

---

### R7.Q2: What should Start do while Pause is underway?

#### Answer

The user agreed that Start succeeds as a no-op while Pause is underway. It
does not cancel the pending Pause or request a return to Running. Resume is
the action that requests continued execution.

#### Impact

The VM still reaches Paused when the pending Pause succeeds. Start does not
launch another operation or change the pause intent. The UI does not offer
Start as a way to cancel Pause.

#### Decision (D14)

Start during Pause succeeds without changing the pending pause intent.

---

### R7.Q3: What should Start do while Resume is underway?

#### Answer

The user agreed that Start during Resume also succeeds as a no-op. The VM is
already started, and Resume remains the operation that continues execution.

#### Impact

Start does not interrupt, restart, or duplicate the pending Resume. The VM
reaches Running if Resume succeeds.

#### Decision (D15)

Start during Resume succeeds without changing the pending resume intent.

---

### R7.Q4: What should Pause do on a stopped VM?

#### Answer

The user agreed that Pause on a stopped VM returns an invalid-state error.
The VM has no running execution or RAM state to retain, and Stop has cleared
any earlier pause intent.

#### Impact

The UI does not offer Pause on a stopped VM. An API request neither starts
the VM nor saves a pause request to apply after a future Start. Pause during
an in-progress Start remains valid under D13.

#### Decision (D16)

Pause on a stopped VM is rejected without changing the VM or its future
Start behavior.

---

## Round 8 — Restart interactions

### R8.Q1: What should Restart do on a paused VM?

#### Answer

The user agreed that Restart on a paused VM is allowed. It starts a new boot
and does not preserve the execution state held in RAM.

#### Impact

Restart discards retained RAM and the VM comes up unpaused. It is distinct
from Resume, which continues the existing execution. Restart during a Pause
or Resume transition is resolved in R8.Q2.

#### Decision (D17)

Restart on a paused VM is accepted and boots the VM unpaused.

---

### R8.Q2: What should Restart do during Pause or Resume?

#### Answer

The user agreed that Restart is accepted during either transition and takes
precedence over the pending Pause or Resume.

#### Impact

The VM starts a new unpaused boot and does not retain the earlier execution
state. The intermediate Paused or Running state need not be reported as
complete. The design must sequence VM operations without contradictory work
running at the same time.

#### Decision (D18)

Restart during Pause or Resume is accepted; the final target is a new,
unpaused boot.

---

### R8.Q3: What should a new Pause request do during Restart?

#### Answer

The user agreed that a new Pause request during Restart is accepted. After
the new boot succeeds, the VM should pause without another user request.

#### Impact

Restart still discards the earlier execution state and any Pause it
superseded. A Pause requested after Restart begins is a new intent for the
new boot. OSAC must report a boot failure rather than claim the VM paused.
This follows the outcome for Pause during Starting in D13.

#### Decision (D19)

A new Pause during Restart is accepted and applied after the new boot
succeeds.

---

### R8.Q4: What should Resume do during Restart?

#### Answer

The user agreed that Resume during Restart returns an invalid-state error.
Restart has discarded the earlier retained execution state, so there is
nothing to resume. The new VM will run after a successful boot.

#### Impact

The request does not interrupt Restart, create another operation, or change
its unpaused target. This differs from a new Pause during Restart (D19),
which is an intent for the new boot.

#### Decision (D20)

Resume during Restart is rejected without changing the pending Restart.

---

## Round 9 — Delete interactions

### R9.Q1: What should Delete do on a paused VM?

#### Answer

The user agreed that Delete is allowed on a paused VM without a prior
Resume.

#### Impact

Successful deletion removes the VM and releases its retained RAM. Existing
deletion rules for attached resources still apply; this decision does not
define a new disk-retention policy. Delete during Pause or Resume is resolved
in R9.Q2.

#### Decision (D21)

Delete on a paused VM is accepted without resuming it first.

---

### R9.Q2: What should Delete do during Pause or Resume?

#### Answer

The user agreed that Delete is accepted during either transition and takes
precedence. The user need not wait for Pause or Resume to finish before
requesting deletion.

#### Impact

Successful deletion removes the VM and releases retained RAM. Pending
pause/resume intent must not recreate the VM after deletion. The design must
sequence or fence in-progress work so this user-visible outcome holds.
The user later confirmed that Delete taking precedence also rejects any new
Pause or Resume request while deletion is underway; neither can change the
delete target.

#### Decision (D22)

Delete during Pause or Resume is accepted; deletion supersedes the pending
transition. Later Pause or Resume requests while deleting return invalid-state
errors.

---

### R9.Q3: Is general Delete behavior during Start or Restart in scope?

#### Answer

The user considered Delete during Start or Restart reasonable but questioned
whether this Feature should define that existing lifecycle behavior. The
scope decision is to leave general Delete-versus-Start/Restart behavior to
the existing lifecycle contract.

#### Impact

This Feature requires only pause-specific cleanup: if Pause was accepted
during Start or Restart and a later Delete is accepted, pending Pause must
not recreate the VM. The PRD does not redefine whether or how Delete is
accepted during an ordinary Start or Restart with no pause intent.

#### Decision (D23)

General Delete behavior during Start or Restart is outside this PRD. An
accepted Delete clears pending pause intent so the VM remains deleted.

---

## Round 10 — Failed state

### R10.Q1: What should Pause or Resume do when a VM is reported as Failed?

OSAC can report Failed for a provisioning or update error even when the
underlying VM still exists. What should a tenant see and be allowed to do
with Pause and Resume in this state?

#### Answer

The user agreed that Pause and Resume on a VM reported as Failed should
return invalid-state errors. The UI should not offer those actions and
should continue to show the existing failure reason. Once OSAC reports
Running or Paused again, the corresponding action becomes available.
An error from a Pause or Resume operation must not hide the observed VM
state or leave a paused VM incorrectly reported as Failed and unable to
Resume.

#### Impact

The PRD groups Failed with other invalid source states while preserving
the failure explanation. It also requires the reported running or paused
state to reflect the VM after an operation error, so the tenant can take
the action appropriate to that state.

#### Decision (D24)

Pause and Resume on a VM reported as Failed are rejected without changing
the requested state. The UI does not offer them and retains the failure
reason. A Pause or Resume operation error is shown separately from the
observed running or paused state.

---

## Round 11 — Loss of a paused VM instance

### R11.Q1: What should tenants see if the host or VM instance fails while paused?

Retained RAM depends on the existing VM instance. A temporarily unreachable
host does not prove that instance or its memory has been lost. What should
OSAC show when reachability is uncertain or the loss is confirmed?

#### Answer

The user agreed that temporary host unreachability should leave Paused as
the last known state, marked as unverified. Once the paused VM instance is
confirmed lost, OSAC must stop showing Paused and offering Resume. If the VM
boots again, it is Running only after the fresh boot succeeds; otherwise it
is Failed. The user asked what it means to "tell the tenant" that the RAM
state was lost. This means a clear explanation in the VM's UI and API
status, including after a successful fresh boot, so Running is not mistaken
for a successful Resume.

#### Impact

The PRD defines the boundary of retained RAM and the outcomes visible to
the tenant. It requires an explanation in the existing UI and API journey;
the UX and technical designs determine its presentation and representation.

#### Decision (D25)

Temporary host unreachability is shown as an unverified last known Paused
state. Confirmed loss of the paused VM instance ends the Paused state and
the ability to Resume that execution. A fresh boot can reach Running; a
failed recovery reaches Failed. The UI and API explain that the earlier
in-memory state was lost, even when a new boot succeeds.

---

## Round 12 — Quota and allocation reporting

### R12.Q1: Does a paused VM free quota capacity or require a new quota view?

Paused VMs retain RAM and existing resource reservations. The current
checkout does not expose a tenant VM quota dashboard; per-tenant quotas are
described as a future platform capability. What should milestone 0.5 require?

#### Answer

The user agreed that Pause does not release allocated capacity. A paused
VM continues to count toward any applicable quota and allocation report.
Milestone 0.5 does not add a new quota dashboard; documentation explains
that the resources remain allocated.

#### Impact

The PRD requires quota and allocation reporting to remain consistent with
resource retention wherever those surfaces apply. It names a new quota
dashboard and quota-management capability as outside this Feature.

#### Decision (D26)

Pause does not increase available quota. Any applicable quota or allocation
report continues to count the paused VM's reserved resources. This Feature
does not deliver a new quota dashboard or quota-management capability.

---

## Round 13 — Permissions and admin personas

### R13.Q1: Who may Pause or Resume a VM?

Should Pause and Resume follow Start and Stop authorization for the same VM,
or require distinct permissions or administrator controls?

#### Answer

The user decided to follow Start and Stop exactly. Tenant Admins and Tenant
Users receive Pause and Resume for VMs in their permitted tenant scope.
Cloud Provider Admin and Cloud Infrastructure Admin access remains governed
by existing VM lifecycle permissions; milestone 0.5 adds no admin-specific
controls or visibility.

#### Impact

The PRD combines Tenant Admin and Tenant User stories because their pause
and resume outcomes are the same. It requires identical authorization for
Pause/Resume and Start/Stop, including API tenant isolation and UI access.
It removes the unresolved admin-persona placeholder.

#### Decision (D27)

Pause and Resume use the same authorization and tenant boundary as Start
and Stop on a VM. This Feature adds no separate pause/resume permission or
admin-specific view or control.

---

## Round 14 — CLI scope

### R14.Q1: Does milestone 0.5 require dedicated Pause/Resume CLI commands?

The Feature specifies UI and API delivery. The current OSAC CLI has no
dedicated Start, Stop, or Restart commands. Should this Feature add
Pause/Resume commands in 0.5?

#### Answer

The user agreed that milestone 0.5 does not require dedicated OSAC CLI
Pause/Resume commands. The API remains available for automation.

#### Impact

The PRD explicitly names dedicated CLI commands as outside 0.5 scope and
keeps UI and API delivery as acceptance requirements.

#### Decision (D28)

Milestone 0.5 delivers Pause/Resume through the UI and API. Dedicated OSAC
CLI Pause/Resume commands are not part of this Feature.

---

## Round 15 — KubeVirt lifecycle alignment

### R15.Q1: Should OSAC mirror KubeVirt's native pause/unpause behavior?

#### Answer

After reviewing KubeVirt's VM API, the user asked to keep the earlier OSAC
lifecycle decisions concise in the PRD and explicitly reopen whether OSAC
should mirror KubeVirt instead. No choice between those behaviors was made.

#### Impact (resolved by D32)

The prior decisions remained provisional until D32 resolved Q9. KubeVirt
reports Paused but has no desired pause state for an existing VM; native
pause/unpause calls can reject repeated or premature requests. This follows the
KubeVirt v1.9.1 [VM API types](https://github.com/kubevirt/kubevirt/blob/v1.9.1/staging/src/kubevirt.io/api/core/v1/types.go)
and [pause/unpause handlers](https://github.com/kubevirt/kubevirt/blob/v1.9.1/pkg/virt-api/rest/lifecycle.go#L260).

---

## Round 16 — In-place pause purpose and CLI scope

### R16.Q1: Should milestone 0.5 include Pause/Resume CLI commands?

#### Answer

After the reviewer questioned the CLI exclusion, the user agreed to add the
commands. This explicitly supersedes D28.

#### Impact

The PRD includes CLI actions, documentation, and validation alongside the UI
and API, and removes CLI delivery from Out of Scope.

#### Decision (D29)

Milestone 0.5 includes OSAC CLI Pause/Resume commands.

---

### R16.Q2: Is the goal in-place KubeVirt pause or disk-backed hibernation?

#### Answer

After comparing KubeVirt pause, memory dumps, and VM snapshots, the user chose
KubeVirt-style pause: temporarily freeze guest execution while retaining host
RAM and the same VM instance. The user explicitly ruled out cost saving as the
purpose. A concrete tenant workflow and expected duration were not supplied.

#### Impact

The PRD names in-place freeze and continuation as the purpose, makes retained
RAM and resource reservations explicit, and excludes hibernation, capacity
reclamation, and any promise of reduced charges. The reviewer's use-case,
duration, and maintenance questions remain open as Q10.

#### Decision (D30)

Pause stops guest CPU execution and I/O without saving RAM to disk or
releasing the VM's host memory and reservations. Resume continues the same
instance without a new boot; this Feature does not seek cost savings.

---

## Round 17 — Review proposals for ownership and lifecycle behavior

### R17.Q1: How should OSAC-7019 and OSAC-1844 divide the work (Q8)?

#### Answer

The user accepted LinskId's PR #450 proposal: OSAC-7019 owns tenant
pause/resume lifecycle delivery through the UI, API, and CLI. OSAC-1844 owns
paused-VM billing display. Neither Feature's split implies a pricing or
metering change in OSAC-7019. Paused reservations continue to count against
tenant quota and allocation. The current OSAC-1844 description also claims
pause/resume UI delivery, so the Jira issues still need to reflect this split.

#### Impact

The PRD assigns lifecycle UI and billing display to different Features and
removes Q8 from the open questions. No billing amount or discount is inferred.

#### Decision (D31)

OSAC-7019 owns pause/resume UI, API, and CLI lifecycle behavior. OSAC-1844
owns paused-VM billing display. OSAC-7019 does not change pricing or metering.

---

### R17.Q2: Should OSAC expose KubeVirt's native pause/unpause errors (Q9)?

#### Answer

The user accepted LinskId's proposal to keep the previously agreed OSAC
Start/Stop-aligned outcomes. Repeated requests are no-ops, and the latest
accepted Pause/Resume request determines the final state during transitions.
Invalid-state cases remain as recorded in earlier rounds. KubeVirt supplies
the freeze and retained-RAM behavior; the design must bridge its imperative
pause/unpause API to the OSAC outcomes.

#### Impact

The lifecycle acceptance cases are no longer provisional. The PRD removes
Q9 while keeping the previously agreed cases intact.

#### Decision (D32)

OSAC exposes its agreed lifecycle outcomes, including repeat-request no-ops
and latest-accepted Pause/Resume wins. It does not expose native KubeVirt
reject-on-repeat behavior to tenants.

---

## Round 18 — Paused VM during node maintenance

### R18.Q1: Does excluding live migration settle paused-VM evacuation behavior?

#### Answer

No. The user asked to make Q10 explicit about whether a paused VM can migrate
during node drain or evacuation, whether RAM, paused state, and IP/MAC survive,
and what OSAC reports if migration cannot preserve them or the node fails.
This does not establish that KubeVirt or OSAC supports migration of a paused
VM; those behaviors still need validation.

#### Impact

The PRD continues to exclude adding live migration, but Q10 now names the
tenant-visible outcomes that must be decided for platform maintenance and
eviction. Existing acceptance for confirmed loss of the VM instance remains.

#### Decision (D33)

Do not add a migration capability to this Feature. Before finalizing the PRD,
validate and define paused-VM behavior during node drain, evacuation, eviction,
and node failure, including state and Resume availability.

---

## Remaining Gaps

| ID | Question | Owner | Impact |
|---|---|---|---|
| Q10 | Which tenant workflow needs an in-place freeze, and for how long? During node drain or evacuation, can a paused VM migrate while retaining RAM, paused state, and IP/MAC? If migration is unavailable or eviction replaces the VM instance, how do the host-loss rules apply, and what state, error, and Resume availability does OSAC show during the transition? | OSAC-VMaaS and Product | Defines the use case and tenant-visible maintenance behavior after validating KubeVirt support. |

Q3 is resolved by D21–D23: pause-specific deletion behavior is defined,
while general Delete behavior during Start or Restart remains outside scope.

These owners follow the Feature's owning team and the bootstrap UI/UX teams;
no individual assignees are inferred. Q10 remains in the draft. Q2, Q4, Q5,
Q6, and Q7 are resolved by D24–D28; D29 supersedes D28's CLI exclusion;
D31 and D32 resolve Q8 and Q9.

## Evidence and Interpretation Boundaries

- The Feature description and KubeVirt documentation support retained RAM
  during an ordinary pause/resume. They do not establish recovery of RAM
  after the underlying instance is lost.
- The accepted VMaaS networking design already commits to retaining the guest
  address across restarts and live migration. D5 extends the requirement to
  successful pause/resume; the design must validate the manager behavior.
- OSAC-1844 currently describes pause/resume UI as well as billing display.
  D31 assigns lifecycle UI to OSAC-7019 and billing display to OSAC-1844;
  the Jira issue descriptions still need alignment.
- Existing Start/Stop/Restart client code provides the current
  lifecycle-interface baseline. No live-cluster behavior was verified.
