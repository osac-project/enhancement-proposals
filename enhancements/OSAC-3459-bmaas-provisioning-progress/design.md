---
title: bmaas-provisioning-progress
authors:
  - mbernard@redhat.com
creation-date: 2026-09-04
last-updated: 2026-09-04
tracking-link:
  - https://redhat.atlassian.net/browse/OSAC-3459
prd:
  - "prd.md"
see-also:
  - "/enhancements/OSAC-1027-compute-instance-status"
  - "/enhancements/OSAC-1604-granular-cluster-status-reporting"
replaces:
  - N/A
superseded-by:
  - N/A
---

# BMaaS Provisioning Progress and Step Visibility

## Summary

This design adds a persisted, ordered, per-phase progress timeline to bare metal
instances, exposed through the fulfillment-service API and rendered as a
read-only PatternFly `ProgressStepper` on the instance detail view. The
`BareMetalInstance` CRD and fulfillment proto gain two embedded, ordered phase
timelines — `provisioning_phases` (four phases) and `deprovisioning_phases`
(three phases) — carrying each phase's state and a single transition timestamp —
the moment the phase became active — from which the UI derives per-phase
durations. Both timelines are retained for the life of the fulfillment instance
record, so an instance under teardown still shows its original provisioning
history alongside the live deprovisioning timeline. The fulfillment reconciler
derives both timelines from the CR, and the DB copy is kept fresh within seconds
by the existing osac-operator feedback→`Signal` path (no new watch). See
[PRD](prd.md) for detailed requirements.

## Motivation

Today a bare metal instance shows only a coarse lifecycle badge (`PROVISIONING`,
`READY`, `FAILED`) plus a raw conditions table in the UI. The fulfillment
reconciler that derives the instance's API status reads only two of the nine
CRD conditions and sets the `PROVISIONED` condition as a binary ratchet with an
empty reason [Codebase: fulfillment-service/internal/controllers/baremetalinstance/baremetalinstance_reconciler_function.go]
— so the largely sequential provisioning signal the operator already tracks
(host allocation, the provisioning job, network handoff, and readiness) is
discarded before it reaches the API. When a deployment stalls or fails, the user
cannot tell which step is running or where it stopped, and the same opacity
applies to deprovisioning.

Three implementation-level facts shape this design. First, bare-metal
provisioning is driven by a single opaque AAP job
(`osac-create-bare-metal-instance`), not by separable metal3/Ironic states — the
metal3 `BareMetalHost` is inventory and power management only and exposes no
observable per-step provisioning signal [Research: loop-back Domain 7]. Hardware
preparation, OS deployment, and configuration therefore all happen inside that
one job and cannot be independently observed; they collapse into a single
**Provisioning** phase. Only Host Allocation, Network Setup, and Ready are
independently observable (via osac-operator conditions/signals). Second, the
DB↔hub freshness path already exists: the osac-operator feedback controller
already watches the hub CRs and rings fulfillment via a `Signal(id)` RPC on
status change, and the fulfillment reconciler already re-reads the CR and updates
the DB within seconds — so no new watch is needed, only an extension of what the
`Signal` fires on and of the reconciler's field mapping [Research: loop-back
Domain 8]. Third, a single cycling status
condition (the shipped VMaaS shape) retains only the *current* sub-step and its
`lastTransitionTime` — it loses the ordered history of prior phases as the reason
advances, so it cannot present the full completed timeline the PRD requires
[PRD: In Scope; Assumptions]. (A single transition timestamp per phase is,
however, sufficient to convey timing — see the design decision below.)

This design closes all three gaps while keeping the cross-service progress
experience consistent with VMaaS (OSAC-1027) and CaaS (OSAC-1604).

### Goals

- Reuse the OSAC status pattern: retain the existing lifecycle `state` and
  `conditions`, and express the current sub-step as a condition reason, so the
  shared status label and conditions table stay consistent across services
  [PRD: In Scope; Locked pattern reuse].
- Represent per-phase state and a single transition timestamp as an embedded,
  ordered timeline field on `BareMetalInstanceStatus` — not a separate CRD or DB
  table — keeping the model consistent with how every OSAC resource carries its
  status, and letting the UI derive each phase's duration from consecutive
  transition timestamps [Research: dedicated-object analysis].
- Persist the completed timeline in the fulfillment DB so it survives CR
  deletion and remains viewable for the life of the fulfillment instance record
  (until the record is archived on finalizer removal), with no new persistence
  subsystem.
- Reuse the existing osac-operator feedback→`Signal` freshness path so status
  reflects backend changes within seconds during and after active phases — no new
  hub-side watch is introduced.
- Introduce a single reusable read-only `ProgressStepper` UI keyed off the new
  timeline field, usable later by VMaaS/CaaS without a model change.

### Non-Goals

- No user-initiated actions on the progress view: no retry, re-provision, or any
  mutating control [PRD: Out of Scope].
- No changes to the metal3/Ironic provisioning automation or AAP playbook logic;
  this design only observes and surfaces existing backend signals
  [PRD: Out of Scope].
- No per-phase log or command output; the timeline carries phase name, state,
  timestamps, and a human-readable message only [PRD: Out of Scope].
- No cross-tenant aggregated list of in-progress instances; users reach
  instances through existing navigation [PRD: Out of Scope].
- No progress model changes for VMaaS or CaaS in this feature, though the new
  field and UI component are designed to be reusable by them [PRD: Out of Scope].

## Proposal

The change spans three components in dependency order:

1. **fulfillment-service proto** gains two `repeated
   BareMetalInstancePhaseProgress` fields on `BareMetalInstanceStatus` —
   `provisioning_phases` and `deprovisioning_phases` — plus two enums:
   `BareMetalInstancePhase` (the seven user-facing phase *values*: four
   provisioning, three deprovisioning) and `BareMetalInstancePhaseState`
   (`PENDING`, `RUNNING`, `SUCCEEDED`, `FAILED`, `SKIPPED`). Each entry carries
   `phase`, `state`, `last_transition_time`, and `message`. A `BareMetalInstance`
   lives exactly one provision→(optional) deprovision cycle — re-provisioning
   creates a new CR — so two fixed-purpose arrays match that lifecycle 1:1, the
   provisioning/deprovisioning direction is structural (no redundant
   `direction`/`sequence` field is needed), and both histories are retained.

2. **bare-metal-fulfillment-operator** adds a matching
   `ProvisioningProgress []PhaseProgress` field to `BareMetalInstanceStatus` and
   populates it during reconciliation by folding its own lifecycle conditions and
   AAP job status into the ordered phase timeline, recording each phase's
   transition timestamp (the moment it became active) itself — the metal3
   `BareMetalHost` exposes no per-step provisioning signal and the AAP
   `JobStatus.Timestamp` is trigger-only, so the operator is the authoritative
   source of every transition timestamp.

3. **fulfillment-service reconciler** maps the CR timelines into the proto
   `provisioning_phases` and `deprovisioning_phases` fields (and sets the current
   sub-step reason on the existing `PROVISIONED` condition). Freshness reuses the
   existing osac-operator feedback→`Signal` path: the feedback controller's
   `Signal(id)` trigger is extended to fire when either timeline changes, and the
   reconciler's `syncStatus()` mapping is extended to carry the new fields. No new
   watch or informer is added.

4. **osac-ui** adds a read-only `BareMetalProgressStepper` component to the
   instance detail view, rendering `provisioning_phases` as a vertical
   PatternFly `ProgressStepper`; once `deprovisioning_phases` is populated it
   renders a second teardown stepper below the (now historical) provisioning
   one, so both timelines stay visible. The component auto-refreshes and remains
   available for completed and failed instances (and for released instances
   until their record is archived).

The two timelines are the single authoritative representation of per-phase
progress; the conditions/reason layer is retained only for coarse-status
consistency with other services. Because the fulfillment DB already stores the
instance's proto status as JSON, both timelines persist across CR deletion with
no new storage.

**Design decision — one transition timestamp per phase, not start + end
`[User]`.** This design records a *single* `last_transition_time` per phase — the
moment the phase became active — rather than a separate start and end. Because the
user-facing timeline is strictly sequential and contiguous (overlapping backend
work is collapsed into one ordered sequence, see the phase mapping below), a
phase's end is exactly the next phase's `last_transition_time`, and its duration is
the difference between consecutive transition timestamps. No information is lost
relative to explicit start+end, the UI can still show per-phase durations, and the
shape matches the shipped VMaaS `metav1.Condition` (one `lastTransitionTime` per
transition) more closely. The PRD's In Scope has been reconciled to this contract
(a transition timestamp per phase, duration derived) — this design and the PRD
now agree; there is no deferred PRD change.

**Duration derivation rules (terminal, milestone, failed, and skipped phases).**
A phase's *end* is the next phase's `last_transition_time` when a later phase
exists in the same timeline; a phase's **duration** is `end −
last_transition_time`. The boundary cases are defined explicitly so no phase
requires a duration from a non-existent successor:

- **Terminal resting phase (`Ready`, `SUCCEEDED`).** `Ready` is the resting
  state a running instance settles into; it has no successor and no bounded
  duration. The UI shows its transition time only (no duration). This is the
  intended terminal for a live instance.
- **Point-in-time milestones (`Teardown Initiated`, `Released`).** Single
  transition timestamp, no derived duration, by definition (see the phase
  mapping).
- **`SKIPPED` phases.** Single transition timestamp (the point the phase was
  passed), no derived duration.
- **A `FAILED` phase.** The phase entered `RUNNING` at its `last_transition_time`
  and then failed with no successor phase. Its end is the coarse lifecycle
  condition's `lastTransitionTime` — specifically the `PROVISIONED` condition
  transition that recorded the `FAILED`/terminal state — so a failed phase's
  duration is `PROVISIONED.lastTransitionTime − phase.last_transition_time`
  (time spent before failure). This is the one case where the timeline consumes
  the coarse condition timestamp; every non-terminal phase derives its duration
  purely from the next phase.

### Workflow Description

Actors: **Tenant User**, **Tenant Admin**, and **Cloud Provider Admin** — all
have the same read-only view of an instance they can already see.

Starting state: a bare metal instance has been ordered and its
`BareMetalInstance` CR exists on the hub.

1. The user opens the instance detail page in the console. The page issues a
   `GET /api/fulfillment/v1/baremetal_instances/{id}` and renders
   `status.provisioning_phases` as a vertical stepper: Host Allocation →
   Provisioning → Network Setup → Ready. If `status.deprovisioning_phases` is
   non-empty (the instance is being or has been torn down), a second teardown
   stepper — Teardown Initiated → Cleaning → Released — renders below the
   provisioning one, so both timelines are visible.
2. Each step shows its state (pending, running with a spinner, succeeded, or
   failed) and the time it became active; the UI derives each finished step's
   duration from the next step's transition time (and the running step's elapsed
   time from now), except the terminal `Ready` phase and the milestones, which
   show a transition time only.
3. While the instance is non-terminal, the detail query re-fetches on a bounded
   ~5s polling interval (a per-page interval, not the global ~10s default); the
   operator updates the CR, the osac-operator feedback controller signals
   fulfillment, which re-syncs the DB within seconds, and the next poll shows the
   advanced timeline without any user action.
4. On failure, the failing step renders in the danger variant with a
   phase-specific, human-readable message (for example, "OS installation and
   configuration did not complete; the provisioning job failed."); no raw
   internal error is shown, and no retry control is offered.
5. When provisioning completes, all four provisioning steps show succeeded with
   their derived durations (`Ready` shows only its transition time); the timeline
   remains rendered and, once the instance is terminal, refetching stops.
6. When the user deletes the instance, the deprovisioning stepper appears below
   the retained provisioning history and tracks teardown to Released; polling
   resumes while teardown is in progress.
7. After the instance is released and its CR removed, the detail view continues
   to serve both final persisted timelines from the fulfillment DB until the
   instance record is archived on finalizer removal, after which the public
   `GET` returns 404 as for any released instance (see Persistence and
   retention).

```mermaid
sequenceDiagram
    actor User
    participant UI as osac-ui
    participant API as fulfillment-service API
    participant DB as PostgreSQL
    participant Rec as fulfillment reconciler
    participant FB as osac-operator feedback ctrl
    participant Hub as BareMetalInstance CR (hub)
    participant Op as bare-metal operator

    Op->>Hub: update status (phase advances)
    Hub-->>FB: watch event (status changed)
    FB->>Rec: Signal(id) [existing RPC]
    Rec->>Hub: Get CR (fresh)
    Rec->>Rec: fold CR -> proto provisioning/deprovisioning timelines
    Rec->>DB: write instance status (both phase arrays)
    loop every ~5s while instance non-terminal
        UI->>API: GET baremetal_instances/{id}
        API->>DB: read status
        DB-->>API: provisioning_phases + deprovisioning_phases
        API-->>UI: timelines
        UI->>User: render ProgressStepper(s)
    end
```

This diagram shows the freshness path the design reuses — the existing
osac-operator feedback controller → `Signal(id)` → reconciler re-read → DB write
— and the UI polling path. The key takeaway: the operator's CR updates
already reach the DB within seconds via this path; this design only extends what
the `Signal` fires on (both phase timelines) and the reconciler's field mapping.
Total UI-visible freshness has two bounded parts: source-side (CR→DB) is bounded
by the existing feedback path (seconds), and DB→UI is bounded by the UI's
**~5s per-page poll** while the instance is non-terminal (a dedicated
`refetchInterval`, not the global ~10s default). The end-to-end bound the user
sees is therefore the sum of the two — both single-digit seconds — which is what
the PRD's "approximately every 5 seconds" auto-refresh now names as the UI
bound `[User]`. Polling stops once the instance is terminal.

### API Extensions

This enhancement modifies the fulfillment-service `BareMetalInstances` API
surface and the `BareMetalInstance` CRD. It does not add new gRPC services,
webhooks, or aggregated API servers. It does not read or modify resources owned
by other teams (in particular, it does not depend on metal3 CRD internals — the
timeline is derived from osac-operator lifecycle conditions and AAP job status).

The concrete interface changes (referenced by the testplan as IC-N):

- **IC-1 — Proto phase-timeline fields.** Add `repeated
  BareMetalInstancePhaseProgress provisioning_phases` and `repeated
  BareMetalInstancePhaseProgress deprovisioning_phases` to
  `BareMetalInstanceStatus` in both the private and public protos, with new enums
  `BareMetalInstancePhase` and `BareMetalInstancePhaseState`. Regenerated via
  `buf lint && buf generate`. Requirements: FR-1, FR-2.
- **IC-2 — CRD `ProvisioningProgress` field.** Add `ProvisioningProgress
  []PhaseProgress` to `BareMetalInstanceStatus` in the operator, with operator
  logic that populates the ordered timeline from backend signals. Requirements:
  FR-1, FR-2, FR-4.
- **IC-3 — Reconciler timeline sync.** Extend the fulfillment reconciler's
  `syncStatus()` to map the CR timelines into the proto `provisioning_phases` and
  `deprovisioning_phases` fields and set the current-step reason on the
  `PROVISIONED` condition. Requirements: FR-1, FR-4, FR-5.
- **IC-4 — Extend the existing feedback→`Signal` freshness path.** Extend the
  osac-operator feedback controller's `Signal(id)` trigger to fire when either
  phase timeline changes (today it already fires on other status changes), so
  the fulfillment reconciler re-syncs the DB within seconds. No new watch or
  informer is added. Requirements: NFR-1.
- **IC-5 — UI progress stepper.** Add the read-only `BareMetalProgressStepper`
  to the instance detail view, consuming `status.provisioning_phases` and
  `status.deprovisioning_phases`, auto-refreshing, with an `aria-live` region.
  Requirements: FR-1, FR-2, FR-3, FR-4, FR-5, NFR-2.
- **IC-6 — Failure message mapping.** Define the exact human-readable failure
  message the operator/reconciler write into the failing phase's `message` field.
  Only phases that carry a `RUNNING`/`FAILED` state can fail; the point-in-time
  milestones (Teardown Initiated, Released) do not. The mapping is **fixed and
  deterministic**: each failure reason maps to exactly one message string, so a
  consumer or test can assert one expected `message` per reason. There are no
  alternatives and no per-phase choice at runtime — the operator derives the
  reason from the failing condition/job and writes the corresponding message
  verbatim.

  | Phase | Failure reason (from failing condition/job) | Exact `message` on `FAILED` |
  |-------|---------------------------------------------|-----------------------------|
  | Host Allocation | `NoMatchingHosts` (no available host matched the profile) | "No bare metal host matched the requested profile." |
  | Host Allocation | `HostAllocationFailed` (host search/claim error other than no-match) | "Host allocation failed." |
  | Provisioning | `ProvisionJobFailed` (the `osac-create-bare-metal-instance` job failed) | "OS installation and configuration did not complete; the provisioning job failed." |
  | Network Setup | `NetworkAttachmentFailed` | "Network attachment did not complete." |
  | Network Setup | `NetworkHandoffFailed` | "Network handoff (reboot) did not complete." |
  | Network Setup | `IPDiscoveryFailed` | "IP address discovery did not complete." |
  | Ready | `ReadyTimeout` (host did not reach powered-on ready state) | "The instance did not reach its powered-on ready state." |
  | Cleaning | `DeprovisionJobFailed` (the `osac-delete-bare-metal-instance` job failed) | "Teardown did not complete; the deprovisioning job failed." |
  | Cleaning | `NetworkOffboardFailed` | "Network offboarding did not complete." |

  These strings are the complete vocabulary; the operator never copies a raw
  operator/AAP/metal3 error string into `message`, and no other message value is
  emitted. The mapping is covered by IC-6 unit tests that assert the exact string
  for each reason. Requirements: FR-5.

Operational impact: if the operator is down, the timeline stops advancing but
the last-synced state remains served from the DB. If the fulfillment reconciler
is down, the DB is not refreshed; the API serves the last-known timeline and
resumes on restart (the reconciler re-syncs via its existing full-resync path).
If the feedback→`Signal` path is disrupted, the design degrades to the existing
periodic full resync (correctness preserved, freshness reduced) rather than
losing data.

## UX Alignment

The `@temp-api` file `osac-ux/libs/ui-components/src/api/v1/baremetal-instance.ts`
exists but exposes no per-phase progress fields today — the instance type is
imported from generated protobuf types (there is no hand-written `@temp-api`
status type) and its status carries the existing coarse fields (`state`,
`conditions`, and the other current status fields) but no per-phase progress.
This EP introduces the fields the UI will consume; after the backend ships and
`pnpm gen-types` runs (which regenerates the types from the rebuilt protos), the
migration diff should be limited to adding the two timeline fields below. Both
arrays hold the same `BareMetalInstancePhaseProgress` element type; the rows below
use `<timeline>` to stand for either `provisioningPhases` or
`deprovisioningPhases`.

| UI field (`@temp-api` TypeScript) | Proto field (this EP) | Notes / deviation |
|---|---|---|
| `status.provisioningPhases[]` | `status.provisioning_phases[]` | New. The four provisioning phases; camelCase → snake_case |
| `status.deprovisioningPhases[]` | `status.deprovisioning_phases[]` | New. The three deprovisioning phases; empty until teardown begins |
| `status.<timeline>[].phase` | `status.<timeline>[].phase` | New. Enum `BareMetalInstancePhase` (field `phase`, mirroring `IdentityProviderStatus.phase`); UI renders the display label per phase |
| `status.<timeline>[].state` | `status.<timeline>[].state` | New. Enum `BareMetalInstancePhaseState` → PatternFly step variant |
| `status.<timeline>[].lastTransitionTime` | `status.<timeline>[].last_transition_time` | New. camelCase → snake_case. When the phase became active; UI derives duration from the next phase's value |
| `status.<timeline>[].message` | `status.<timeline>[].message` | New. Human-readable failure/status text; empty on success |
| `status.state` | `status.state` | Unchanged; still drives the coarse status label |
| `status.conditions` | `status.conditions` | Unchanged; retained for the shared conditions table |

No known anti-patterns apply: both timelines are status (read-only,
observed-state) fields, not a sub-resource action, string-union storage class,
K8s-internal field, one-time secret, or RHOAI operator field.

### Implementation Details/Notes/Constraints

#### Proto schema

```proto
enum BareMetalInstancePhase {
  BARE_METAL_INSTANCE_PHASE_UNSPECIFIED = 0;
  // Provisioning — Provisioning covers OS install + configuration, which run in
  // a single opaque AAP job and are not independently observable.
  BARE_METAL_INSTANCE_PHASE_HOST_ALLOCATION = 1;
  BARE_METAL_INSTANCE_PHASE_PROVISIONING = 2;
  BARE_METAL_INSTANCE_PHASE_NETWORK_SETUP = 3;
  BARE_METAL_INSTANCE_PHASE_READY = 4;
  // Deprovisioning
  BARE_METAL_INSTANCE_PHASE_TEARDOWN_INITIATED = 5;
  BARE_METAL_INSTANCE_PHASE_CLEANING = 6;
  BARE_METAL_INSTANCE_PHASE_RELEASED = 7;
}

enum BareMetalInstancePhaseState {
  BARE_METAL_INSTANCE_PHASE_STATE_UNSPECIFIED = 0;
  BARE_METAL_INSTANCE_PHASE_STATE_PENDING = 1;
  BARE_METAL_INSTANCE_PHASE_STATE_RUNNING = 2;
  BARE_METAL_INSTANCE_PHASE_STATE_SUCCEEDED = 3;
  BARE_METAL_INSTANCE_PHASE_STATE_FAILED = 4;
  BARE_METAL_INSTANCE_PHASE_STATE_SKIPPED = 5;
}

message BareMetalInstancePhaseProgress {
  BareMetalInstancePhase phase = 1;                    // which phase (matches IdentityProviderStatus.phase precedent)
  BareMetalInstancePhaseState state = 2;               // the phase's progress state
  google.protobuf.Timestamp last_transition_time = 3;  // when the phase became active; duration derived from the next phase
  optional string message = 4;                         // human-readable; populated on failure
}

// Added to BareMetalInstanceStatus alongside the existing `state` and `conditions`:
//   repeated BareMetalInstancePhaseProgress provisioning_phases = N;    // the four provisioning phases
//   repeated BareMetalInstancePhaseProgress deprovisioning_phases = N+1; // the three deprovisioning phases (empty until teardown)
```

Two `repeated BareMetalInstancePhaseProgress` fields —
`provisioning_phases` and `deprovisioning_phases` — are added to
`BareMetalInstanceStatus` alongside the existing `state` and `conditions`
[Codebase: fulfillment-service/proto/private/osac/private/v1/baremetal_instance_type.proto].
Each list is ordered by the phase sequence for its direction and is populated
independently. **Both timelines are retained for the life of the instance
record, not replaced:** `provisioning_phases` is populated as the instance is
provisioned and is *never cleared* when deprovisioning begins;
`deprovisioning_phases` starts empty and is populated with the three teardown
phases (Teardown Initiated, Cleaning, Released) only when the instance is being
deleted. An instance under teardown therefore carries both its completed
provisioning history and its live deprovisioning timeline.

**Why two fixed-purpose arrays rather than one array with a `direction`/`sequence`
field:** a `BareMetalInstance` CR lives exactly one provision→(optional)
deprovision cycle — re-provisioning a host produces a *new* CR, never a second
provisioning pass on the same one — so the two directions map 1:1 onto two arrays
and the direction is structural. A single array carrying an explicit
`direction`/`sequence` discriminator would re-encode, as data, information the
field name already conveys, and would force every reader to filter and sort;
two arrays keep each timeline self-describing and ordered. The change is purely
additive to the proto. The **current sub-step** is derivable as the entry whose
`state == RUNNING` in `deprovisioning_phases` if that array is non-empty,
otherwise in `provisioning_phases`; the reconciler also mirrors that phase name
into the `PROVISIONED` condition's `reason` so the coarse label and conditions
table stay consistent with VMaaS [Codebase: osac-operator/api/v1alpha1/conditions.go].

**Naming conventions and precedent (verified against the shipped protos).** The
new identifiers follow the documented OSAC proto conventions
[Codebase: fulfillment-service/docs/API.md:378-397]: CamelCase enum type names,
values prefixed with the full enum-type name in `UPPER_SNAKE_CASE`, and
`_UNSPECIFIED = 0` first. Field names mirror the closest existing precedents: the
`phase` field and `BareMetalInstancePhase` enum follow the only phase precedent in
the tree, `IdentityProviderStatus.phase` / `IdentityProviderPhase`
[Codebase: fulfillment-service/proto/private/osac/private/v1/identity_provider_type.proto];
`last_transition_time` and `optional string message` match the shared condition
shape used by every resource (`ComputeInstanceCondition`, `ClusterCondition`,
`BareMetalInstanceCondition`, each `google.protobuf.Timestamp last_transition_time`
+ `optional string message`) and the K8s `metav1.Condition`. Note the scope of the
"cross-service consistency" claim: **VMaaS (`ComputeInstanceStatus`) and CaaS
(`ClusterStatus`) carry no phase/step/progress field — only a `state` enum plus
`repeated {Type}Condition conditions`** [Codebase: compute_instance_type.proto,
cluster_type.proto]. The consistency this design reuses is therefore (a) those
conventions and (b) the retained coarse `state` + `conditions` layer; the ordered
`provisioning_phases`/`deprovisioning_phases` timelines are themselves a net-new
construct with no VMaaS/CaaS precedent (reinforcing the Alternatives analysis
below).

#### CRD field

```go
// PhaseProgress records one user-facing provisioning or deprovisioning phase.
type PhaseProgress struct {
    Phase              BareMetalInstancePhase `json:"phase"`
    State              PhaseState             `json:"state"`
    LastTransitionTime *metav1.Time           `json:"lastTransitionTime,omitempty"`
    Message            string                 `json:"message,omitempty"`
}
```

Two fields are added to `BareMetalInstanceStatus` —
`ProvisioningProgress []PhaseProgress` and `DeprovisioningProgress []PhaseProgress`
[Codebase: bare-metal-fulfillment-operator/api/v1alpha1/baremetalinstance_types.go].
The operator populates `ProvisioningProgress` during provisioning and
`DeprovisioningProgress` during teardown, and never clears the former when the
latter begins, mirroring the two proto arrays. The operator runs
`make manifests generate` and `make helm-crds` after the type change (enforced by
CI).

#### Phase-to-backend-signal mapping

The operator derives each phase from an authoritative signal and records one
transition timestamp per phase — the moment the phase becomes active. It is set
once when the phase first enters `RUNNING` (or, for a milestone, when the
milestone occurs) and never overwritten (idempotent). Because the sequence is
strictly ordered and contiguous, a non-terminal phase's *end* is the next phase's
transition timestamp, and its duration is the difference between the two; the
terminal resting phase (`Ready`) and the milestones show no duration, and a
failed phase's fail-instant is the coarse lifecycle `PROVISIONED`
condition's transition (see the duration-derivation rules in the Proposal). The
**operator is the authoritative source of
every transition timestamp**: metal3 exposes no observable per-step provisioning
signal, and the AAP `JobStatus.Timestamp` is trigger-only (it records when a job
was launched, not phase boundaries), so the operator records each transition
itself as it drives the lifecycle.

| Phase | Direction | Backend signal | Transition timestamp source |
|---|---|---|---|
| Host Allocation | prov | `Allocated` condition True (operator host search) | Operator records when host search begins. Failure: `NoMatchingHosts` |
| Provisioning | prov | single `osac-create-bare-metal-instance` AAP job → `ProvisionTemplateComplete` (OS install + configuration, one opaque job) | Operator records when the provision job is triggered |
| Network Setup | prov | `NetworkAttachmentsReady` → `NetworkHandoffComplete` → `IPDiscoveryComplete` | Operator records when network attachment begins |
| Ready | prov | `PowerSynced` → instance phase `Ready` (absorbs readiness/verification) | Operator records when the instance reaches `Ready` |
| Teardown Initiated | deprov | `DeletionTimestamp` set / phase `Deleting` | Deletion accepted (milestone) |
| Cleaning | deprov | deprovision AAP job (`DeprovisionTemplateComplete`) + `NetworkOffboardComplete` | Operator records when teardown work begins |
| Released | deprov | **new** operator-recorded milestone, written and then acknowledged (see handshake) before finalizer removal | Release recorded (milestone) |

> **Released uses a reconciler-gated finalizer handshake.** There is no existing
> signal for the terminal "released" instant, so the operator records a Released
> milestone in `DeprovisioningProgress` on the CR. Writing that milestone is
> **not** by itself a durability guarantee — the asynchronous feedback→`Signal`
> path could miss the last update and leave the DB at `Cleaning` when the CR is
> removed. So finalizer removal is gated on a positive acknowledgment that the
> terminal timeline has reached the DB:
>
> 1. The operator writes the `Released` milestone to the CR but **keeps the
>    finalizer**.
> 2. The fulfillment reconciler syncs the final timeline (both arrays, with
>    `Released` `SUCCEEDED`) to the DB, then **acknowledges** by writing the
>    `osac.openshift.io/timeline-persisted` **annotation** back onto the hub CR.
>    This is a coordination annotation (not observed state, so it is an annotation
>    rather than a status field); writing it is the reconciler's only new write to
>    the CR and requires a small RBAC addition — see RBAC / Tenancy.
> 3. Only after the operator observes that acknowledgment on a subsequent
>    reconcile does it remove the finalizer and let the CR be deleted. If the
>    acknowledgment never appears (reconciler down, Signal lost), the operator
>    requeues and the finalizer stays — the instance rests at `Released` in the
>    CR and the DB is brought current by the periodic full-resync backstop
>    before removal. Finalizer removal never proceeds without a confirmed,
>    durably-persisted terminal timeline.
>
> **`Released` semantics:** `Released` is the **host-release milestone** — it
> means the host has been returned to the pool (`BareMetalHost` back to
> `available`, `consumerRef` cleared) and is reusable. It is written (step 1)
> while the finalizer is still held, so `Released` in the timeline reflects only
> that the host is released, not that the CR is gone. **Finalizer removal is a
> separate, later lifecycle step** (step 3), gated on the persistence
> acknowledgment; it is not part of the `Released` phase definition. Because the
> host is already back to `available` when `Released` is written and the finalizer
> is removed only after the terminal timeline is durably persisted, there is no
> window where a "released" host is still pinned *and* no window where the CR is
> deleted with the DB behind. This resolves the former Open Question 1. This is a
> small, in-scope operator + reconciler change — no AAP or metal3 change is
> involved.

The operator monitors two concrete backend sources, both **polled on each
reconcile** (it does not watch either — it re-reads and requeues, default ~30s):

- **metal3 `BareMetalHost` (BMH)** — read on demand for host search
  (`status.provisioning.state == available`, `operationalStatus == OK`, no
  `spec.consumerRef`, NIC inventory present) and for power state
  (`status.poweredOn` vs `spec.online`, reboot annotation).
- **AAP job templates** — launched and polled for `status == "successful"`:
  `osac-create-bare-metal-instance` (the single opaque OS install + config job),
  `osac-move-network-attachment` (network on/off-board), `osac-query-dhcp-lease`
  (IP discovery), and `osac-delete-bare-metal-instance` (deprovision).

The happy-path sequence below shows what each of those sources returns and the
update the operator makes to the `BareMetalInstance` CR in response: mark the
finished phase `SUCCEEDED` and set the next phase `RUNNING`, stamping the new
phase's `last_transition_time`. Each phase corresponds to the operator's own
lifecycle conditions (all of which already exist), not to a distinct operator
phase enum. Only the success path is shown — failure (a phase entering `FAILED`
on its condition/job error) and `SKIPPED` (a phase with no work, e.g. Network
Setup with no attachment) are covered in the behavior notes below and in the
Failure Handling section, not here.

```mermaid
sequenceDiagram
    participant M3 as metal3 BareMetalHost
    participant AAP as AAP job templates
    participant Op as bare-metal operator
    participant CR as BareMetalInstance status

    Op->>M3: list hosts, filter available plus OK plus no consumerRef
    M3-->>Op: candidate host
    Op->>M3: claim host, set consumerRef
    Op->>CR: Allocated True, Host Allocation SUCCEEDED, Provisioning RUNNING

    Op->>AAP: launch osac-create-bare-metal-instance
    AAP-->>Op: job status successful
    Op->>CR: ProvisionTemplateComplete True, Provisioning SUCCEEDED, Network Setup RUNNING

    Op->>AAP: launch osac-move-network-attachment
    AAP-->>Op: job status successful
    Op->>CR: NetworkAttachmentsReady True
    Op->>M3: set reboot annotation, poll poweredOn
    M3-->>Op: poweredOn true
    Op->>CR: NetworkHandoffComplete True
    Op->>AAP: launch osac-query-dhcp-lease
    AAP-->>Op: DHCP lease artifacts
    Op->>CR: IPDiscoveryComplete True, Network Setup SUCCEEDED, Ready RUNNING

    Op->>M3: poll poweredOn vs spec.online
    M3-->>Op: power converged
    Op->>CR: PowerSynced True, Ready SUCCEEDED

    Note over Op,CR: later, DeletionTimestamp set, phase Deleting
    Op->>M3: power host off
    M3-->>Op: poweredOn false
    Op->>CR: NetworkOffboardComplete True, Teardown Initiated milestone, Cleaning RUNNING
    Op->>AAP: launch osac-move-network-attachment offboard then osac-delete-bare-metal-instance
    AAP-->>Op: job status successful
    Op->>CR: DeprovisionTemplateComplete True, Cleaning SUCCEEDED
    Op->>M3: unassign host, clear consumerRef
    M3-->>Op: host returns to available
    Op->>CR: Released milestone (keep finalizer)
    Note over Op,CR: reconciler syncs terminal timeline to DB, then acks on CR
    Op->>CR: observe timeline-persisted ack, remove finalizer (host now reusable)
```

The four provisioning phases run before the instance is live; the three
deprovisioning phases begin only when the instance is deleted, so an instance
that is never deleted simply rests at `Ready`. The operator records every
transition timestamp itself as it observes these sources — metal3 exposes no
per-step provisioning signal beyond the coarse BMH state, and the AAP
`JobStatus.Timestamp` is trigger-only (records launch, not phase boundaries) —
which is also why the terminal `Released` instant needs the small
operator-recorded milestone and reconciler-gated handshake called out above (no
existing BMH state or AAP job marks it). Once the operator writes these
`ProvisioningProgress`/`DeprovisioningProgress` changes to the CR, they reach the
DB and API within seconds via the existing feedback→`Signal` path shown in the
Workflow Description sequence diagram.

Behavior for the cases the PRD asks the design to define [PRD: Assumptions]:

- **Milestone vs. running:** Host Allocation is short but has a running state
  while searching; Teardown Initiated and Released are point-in-time milestones
  (a single transition timestamp, no derived duration); the remaining phases have
  a running state.
- **Skipped:** a phase with no work to do (for example, Network Setup when the
  instance requests no network attachment) is emitted with `state = SKIPPED` and
  the transition timestamp of the point it was passed, so the timeline is always
  complete and the stepper shows every phase in order.
- **Retried:** retries within a phase (the AAP job) do not reset the phase's
  transition timestamp and do not add entries; the phase stays `RUNNING` until it
  reaches a terminal state. Sub-retry detail is not surfaced (no log access, per
  Non-Goals).
- **Overlapping / collapsed:** where backend work overlaps or is not separately
  observable (OS install and configuration both run inside the single provision
  job), it is attributed to the single user-facing phase that represents it
  (**Provisioning**); the user always sees a strictly ordered sequence.

#### Reconciler and freshness

The fulfillment reconciler's `syncStatus()` folds `ProvisioningProgress` and
`DeprovisioningProgress` into the proto `provisioning_phases` and
`deprovisioning_phases` fields and sets the `PROVISIONED` condition reason to the
current running phase, replacing today's empty-reason ratchet
[Codebase: fulfillment-service/internal/controllers/baremetalinstance/baremetalinstance_reconciler_function.go].
When it syncs a terminal `Released` timeline, it also writes the
`timeline-persisted` acknowledgment back to the CR that gates finalizer removal
(see the Released handshake above).

Freshness reuses the existing feedback path rather than adding a new watch. The
osac-operator already runs a feedback controller that watches the hub
`BareMetalInstance` CRs and rings fulfillment via a `Signal(id)` RPC when their
status changes; that signal triggers the fulfillment reconciler to re-read the CR
and update the DB within seconds [Research: loop-back Domain 8]. This design only
(a) extends the feedback controller's `Signal` trigger so it also fires when
either phase timeline changes, and (b) extends the reconciler's `syncStatus()` to
map the new fields [Codebase: fulfillment-service/internal/controllers/reconciler.go].
No new informer, watch, or polling loop is introduced. The existing periodic full
resync is retained as a correctness backstop (and, per the Released handshake, is
the fallback that guarantees the terminal timeline reaches the DB before finalizer
removal even if a `Signal` is lost).

#### Persistence and retention

Both timelines persist automatically: the fulfillment DB stores the instance's
proto status as JSON, so once the reconciler writes the final timelines they
survive CR deletion and are served read-only for completed and failed instances,
and for released instances **for the life of the fulfillment instance record**.
Retention is tied to that record, mirroring VMaaS and CaaS `[User]` — the
timelines are a bounded per-instance snapshot (at most seven phase entries total,
four provisioning + three deprovisioning) embedded in status, not an unbounded
audit log. On release the operator removes the CR's finalizer;
fulfillment then soft-deletes the record and archives it to `archived_<table>`,
after which the public `GET` returns 404 (there is no archive-read path)
[Research: loop-back Domain 9]. FR-4 is therefore scoped to the life of the live
record: the persisted timeline is viewable after provisioning/deprovisioning
finishes and up until the released record is archived — matching how every other
status field, and VMaaS/CaaS, behave. This is consistent with how OSAC embeds
status rather than maintaining separate history objects
[Research: dedicated-object analysis]; no dedicated retention subsystem is
introduced.

#### UI

`BareMetalProgressStepper` (osac-ui) renders `status.provisioning_phases` as a
vertical PatternFly `ProgressStepper`, and — when `status.deprovisioning_phases`
is non-empty — a second `ProgressStepper` for the teardown timeline below it, so
the provisioning history stays visible during and after teardown [Research:
PatternFly]. State → variant mapping: `PENDING` → `pending`; `RUNNING` → `info`
with a spinner icon and `isCurrent`; `SUCCEEDED` → `success`; `FAILED` →
`danger`; `SKIPPED` → `default` (muted). Each step's `description` shows the time
the phase became active and, for phases that have one, its derived duration
(from the next step's transition time, or for the running step elapsed from now);
the terminal `Ready` phase and the milestones show a transition time only, and a
failed step shows `message`. The component is read-only (no actions) and pairs the
steppers with a visually hidden `aria-live="polite"` region restating the current
step so poll-driven updates are announced. It uses the `useBareMetalInstance`
query with a **dedicated ~5s `refetchInterval` while the instance is non-terminal**
(a per-page override of the global ~10s default), so the DB→UI leg of freshness is
bounded to ~5s rather than ~10s, and **stops refetching once the instance is
terminal** [Codebase: osac-ui/apps/app-frontend/src/main.tsx]. The same component
renders the persisted timelines for finished instances.

The terminal predicate is evaluated against the **currently active** timeline, not
against any historical phase, so a resting `Ready` does not suppress teardown
updates:

- If `deprovisioning_phases` is **empty** (no teardown), the instance is terminal
  iff the last provisioning phase is terminal — `Ready` `SUCCEEDED`, or a
  provisioning phase in `FAILED`. Polling stops.
- If `deprovisioning_phases` is **non-empty** (teardown in progress or done), the
  instance is terminal iff the deprovisioning timeline is terminal — `Released`
  `SUCCEEDED`, or a deprovisioning phase in `FAILED`. While teardown is still
  running, the instance is **non-terminal even though provisioning ended at
  `Ready` `SUCCEEDED`**, so a historical `Ready` never stops polling once
  deprovisioning has begun — the query resumes its ~5s cadence for the teardown
  timeline.

### Security Considerations

This feature inherits the existing security model without changes. Both phase
timelines are observed state exposed through the same read path and authorization
as the rest of `BareMetalInstanceStatus`; a caller who can `GET` the instance can
see its timelines, and no new mutating surface is added (the view is read-only per
Non-Goals). Input validation is limited to enum-constrained fields and
operator-generated timestamps; no user input reaches the timeline. The
human-readable failure messages are drawn from a fixed operator-defined
vocabulary and deliberately exclude raw internal errors [PRD: In Scope], which
also avoids leaking implementation detail across the tenant boundary.

### Failure Handling and Recovery

- **A provisioning phase fails.** The operator sets that phase `FAILED` with a
  phase-specific message and stops advancing; the reconciler syncs it; the UI
  renders the danger variant. Downstream phases remain `PENDING`. Recovery is
  out of scope (read-only) — the user deletes and re-orders.
- **Operator down mid-phase.** The CR stops advancing; the DB serves the last
  timeline. On restart the operator resumes reconciliation and continues
  recording transition timestamps; timestamps already set are not overwritten.
- **Fulfillment reconciler restarts mid-reconcile.** The status write is
  idempotent (full timeline replace); on restart the reconciler re-syncs via its
  existing full-resync path, converging the DB to the current CR.
- **Feedback→`Signal` path disrupted.** Freshness degrades to the existing
  periodic full resync; timelines are still eventually consistent and no data is
  lost.
- **CR deleted before final sync (release).** This cannot silently lose the
  terminal state: the reconciler-gated finalizer handshake (see the Released
  note) holds the finalizer until the reconciler has durably persisted the
  terminal timeline to the DB and acknowledged on the CR. If the acknowledgment
  is delayed (Signal lost, reconciler down), the operator requeues and the
  periodic full-resync backstop brings the DB current before the finalizer is
  removed — the CR is never deleted with the DB left at `Cleaning`.
- **A phase has no work to do.** Where a phase is inapplicable (for example,
  Network Setup when the instance requests no network attachment), the operator
  emits it as `SKIPPED` rather than leaving it stuck `PENDING`.

### RBAC / Tenancy

No tenancy changes are required. Both phase-timeline fields
(`provisioning_phases` and `deprovisioning_phases`) are added to an existing
tenant-scoped resource and served through the same authorization path;
visibility follows the instance's existing tenant scoping. No new
resources are introduced, so no new `osac.openshift.io/tenant` or
`osac.openshift.io/owner-reference` metadata is needed — the existing annotations
on `BareMetalInstance` are unaffected [Codebase: bare-metal-fulfillment-operator/api/v1alpha1/baremetalinstance_types.go].

One small RBAC addition is required: the Released handshake has the fulfillment
reconciler write the `osac.openshift.io/timeline-persisted` acknowledgment
annotation back onto the hub `BareMetalInstance`. Today the reconciler reads CRs
and writes only to the DB, so it must be granted `patch` on `baremetalinstances`
(the object, for its metadata/annotations) on the hub to record that
acknowledgment. This is the only new permission; it grants no additional read
visibility and does not affect tenant scoping. The operator already has the read
permission it needs to observe the annotation on a subsequent reconcile.

### Observability and Monitoring

No new Prometheus metrics or alerts are introduced. The operator continues to
emit Kubernetes events on phase transitions via existing condition-change event
recording; the new timeline is observable through the API and CR status. Existing
monitoring mechanisms apply. A per-phase "stalled" metric (e.g. a gauge for time
spent in the current `RUNNING` phase, to alert on phases exceeding an expected
duration) is a natural follow-up but is out of scope for this design — the
`last_transition_time` per phase already makes such a metric derivable later
without a schema change.

### Risks and Mitigations

- **Extra `Signal` volume on the fulfillment reconciler.** Firing the existing
  feedback `Signal` on timeline changes (either array) adds signal events.
  Mitigation: the signal is ID-only ("ring the bell, fulfillment pulls") and
  coalesces to a single per-instance re-sync; the periodic full resync remains
  the backstop, and no new watch is added.
- **Timeline vs. conditions divergence.** Maintaining both phase timelines and
  the condition reason risks inconsistency. Mitigation: the reconciler derives
  the reason from the current-phase timeline (the running entry in
  `deprovisioning_phases` if non-empty, else `provisioning_phases`) in one place,
  so they cannot drift.
- **Phase-mapping drift as the operator lifecycle evolves.** The mapping depends
  on osac-operator lifecycle conditions and AAP job status, not metal3 state
  strings. Mitigation: the mapping lives in one operator function with unit tests
  over condition/job-status fixtures.
- **Refresh cost.** While an instance is non-terminal the detail view polls with
  a dedicated ~5s `refetchInterval` (a per-page override of the global ~10s
  default) and stops at terminal, so per-page cost is bounded to a single-instance
  GET on an open detail page; end-to-end UI freshness is the CR→DB latency
  (seconds, via feedback→`Signal`) plus the ~5s poll `[User]`.

### Drawbacks

The design adds a second representation of progress (two phase timelines
alongside conditions), which is more API surface than a pure single-cycling
condition. It is justified because a single cycling condition retains only the
*current* sub-step and loses the ordered history of prior phases as the reason
advances — whereas the PRD requires the full completed timeline to remain
viewable. (Timing is *not* the reason for the extra surface: one transition
timestamp per phase already conveys start, end, and duration for a sequential
timeline — see the design decision in the Proposal.) The conditions layer is
retained only for coarse-status consistency. The design adds no new freshness
integration path — it reuses the existing osac-operator feedback→`Signal` path,
extending only what it fires on. This cost is proportionate to the requirement
and reused by future services.

## Alternatives (Not Implemented)

- **Single cycling condition only (the shipped VMaaS shape).** Express phases
  purely as reasons on one `PROVISIONED` condition. Pros: minimal API surface,
  identical to VMaaS. Cons: a single condition retains only the current reason
  and its `lastTransitionTime`, so it loses the ordered history of prior phases
  as the reason advances — failing the PRD's persisted, viewable-after-completion
  timeline requirement [PRD: In Scope; Assumptions]. (Timing alone would be fine
  — one transition timestamp per phase suffices — but history retention is the
  gap.) Rejected.
- **One metav1.Condition per phase.** Model each phase as its own condition type.
  Pros: familiar shape; one `lastTransitionTime` per condition is, as this design
  concludes, enough to convey timing. Cons: conditions are a semantically
  unordered set, so seven lifecycle-coupled condition types bloat the shared
  conditions table, provide no explicit ordering or `SKIPPED` semantics, and
  break coarse-status consistency with other services. Rejected in favor of the
  ordered timeline; the reason layer already covers current-step consistency.
- **Dedicated progress CRD or DB history table.** A separate resource/table for
  the timeline. Pros: unbounded retention, append-only writes. Cons: no OSAC
  precedent (every resource embeds status; OSAC-1604 rejected a separate
  stream), new CRD/proto/RPC + DB migration + second fetch path, and breaks the
  cross-service consistency goal — disproportionate for a bounded timeline of at
  most seven phase entries (four provisioning + three deprovisioning)
  [Research: dedicated-object analysis]. Rejected: retention is tied to
  the life of the instance record, mirroring VMaaS/CaaS `[User]`, so no unbounded
  durable audit is required.
- **CaaS orthogonal-conditions model (OSAC-1604).** Multiple independent
  condition types (control-plane / workers). Pros: consistent with CaaS. Cons:
  that model exists because clusters have parallel health axes; BMaaS
  provisioning is a linear sequence, so orthogonal conditions add complexity with
  no benefit [Research: VMaaS/CaaS]. Rejected.
- **Shortened global reconciler `SyncInterval`, or a new hub-side watch, for
  freshness.** Lower the BM reconciler's full-resync interval to ~5s, or add a
  new informer on `BareMetalInstance` CRs. Pros: the interval knob is simple;
  a watch is targeted. Cons: both are unnecessary — the osac-operator feedback
  controller already Signals fulfillment on CR status change and delivers
  seconds-level freshness today [Research: loop-back Domain 8]; a shortened
  global resync also scales poorly. Rejected: this design extends the existing
  `Signal` path instead, and keeps the periodic full resync as the backstop.

## Open Questions

None. The former open question — the exact "Released" ordering guarantee — is
resolved by the reconciler-gated finalizer handshake (see the Released note in
the Proposal): `Released` is the host-release milestone (host returned to the
pool — `available`, `consumerRef` cleared, reusable). Finalizer removal is a
separate, later step, performed only after the reconciler has durably persisted
the terminal timeline to the DB and acknowledged it on the CR with the
`osac.openshift.io/timeline-persisted` annotation, with the periodic full-resync
backstop guaranteeing convergence if the acknowledgment is delayed.

## Test Plan

**Note:** *Section not required until targeted at a release.* Concrete scenarios,
mapped to the requirement/interface-change matrix, are enumerated in
`testplan.md`.

### Unit Tests

- Phase-mapping function: each osac-operator lifecycle-condition / AAP job-status
  fixture maps to the correct phase and state; the per-phase
  `last_transition_time` is set once and not overwritten on subsequent reconciles.
- Skipped/retried/collapsed handling: a no-op Network Setup yields `SKIPPED`;
  an AAP provision-job retry keeps Provisioning `RUNNING` with a stable
  `last_transition_time`.
- Reconciler `syncStatus()`: the CR timelines fold into the proto
  `provisioning_phases` and `deprovisioning_phases` arrays; the `PROVISIONED`
  condition reason equals the current running phase (the running entry in
  `deprovisioning_phases` if non-empty, else `provisioning_phases`).
- Failure vocabulary: each phase failure produces its defined human-readable
  message and no raw error text.

### Integration Tests

- envtest: driving a `BareMetalInstance` CR through Host Allocation →
  Provisioning → Network Setup → Ready produces a monotonically advancing
  `provisioning_phases` timeline; deletion appends the three deprovisioning
  phases through Released to `deprovisioning_phases` while `provisioning_phases`
  is retained unchanged.
- Feedback→`Signal` path: a CR status/timeline change triggers a DB sync within
  seconds (fulfillment reconciler against a kind cluster).
- Persistence: after the Released handshake and CR deletion, the API still
  serves both retained timelines up to record archival.

### E2E Tests

- pytest (`tests/e2e/`): order a bare metal instance and assert the API exposes
  the four provisioning phases with timestamps; delete it and assert the three
  deprovisioning phases through Released.
- osac-ui (Vitest + RTL / Cypress): the detail view renders the stepper with
  correct variants for pending/running/succeeded/failed, shows a failure message
  on a failed phase, exposes no retry control, and updates on refetch.

## Graduation Criteria

Graduation criteria will be finalized when targeting a release; the measurable
gates per stage are:

- **Dev Preview:** `provisioning_phases` is populated end-to-end for the happy
  path; phase-mapping unit tests cover every osac-operator condition / AAP
  job-status fixture; the UI stepper renders the four provisioning phases against
  a kind cluster.
- **Tech Preview:** all testplan cases pass (FR-1…FR-5, NFR-1…NFR-3), including
  the failure (FR-5/IC-6), released-archival (TC-FR4-02), and freshness
  (TC-NFR1-01) scenarios; NFR-1 freshness is verified to meet single-digit
  seconds via the feedback→`Signal` path in e2e; no regression in the coarse
  `state`/`conditions` layer.
- **GA:** the feature has run in a production-representative deployment across at
  least one full provisioning and one full deprovisioning cycle without timeline
  divergence from the CR, and the failure-message vocabulary has been reviewed
  with support.

**Documentation.** User-facing change is limited to the instance detail view;
the new stepper needs a short help/legend entry (phase meanings, state colors).
The only API-surface documentation change is the two new phase-timeline fields
(`provisioning_phases`, `deprovisioning_phases`) in the generated proto/API
reference — no new endpoints. No runbook change beyond the
Troubleshooting notes above.

## Upgrade / Downgrade Strategy

This adds optional fields to an existing CRD and proto message. On upgrade,
existing instances have empty `provisioning_phases`/`deprovisioning_phases`
lists until their next reconcile populates them; the UI renders nothing (or the
coarse label) when both are empty, so there is no hard dependency on the new
fields. Downgrade is safe: the
new status fields are ignored by older readers and can be dropped without data
loss because the timeline is derived state, re-derivable from the CR on the next
reconcile.

## Version Skew Strategy

The operator writes `ProvisioningProgress`/`DeprovisioningProgress` to the CR; an
older fulfillment reconciler that does not read them simply omits the timeline
fields from the API (existing behavior). A newer reconciler reading a CR written
by an older operator sees empty timelines and serves the coarse status. The
`provisioning_phases`/`deprovisioning_phases` proto fields are additive and
optional, so fulfillment-service and osac-operator tolerate skew in either
direction. No CRD version migration is required (fields added within
`v1alpha1`).

## Support Procedures

- **Detection:** a stalled timeline (a phase stuck `RUNNING` past expected
  duration) indicates a backend stall; for the Provisioning phase, correlate with
  operator logs and the `osac-create-bare-metal-instance` AAP job status (metal3
  `BareMetalHost` shows only power/inventory state). A timeline that never updates
  in the UI while the CR advances indicates a feedback-path or reconciler problem
  — check the fulfillment reconciler logs and `Signal`/DB-sync events.
- **Disabling:** the feature has no feature gate; to suppress the UI, the stepper
  component can be hidden without backend changes. The backend fields are inert
  if unread. Disabling has no effect on provisioning itself (observation only).
- **Recovery:** restarting the fulfillment reconciler re-syncs CRs via its
  existing full-resync path and reconverges the DB; consistency is maintained
  because both timelines are a full-replace derived projection of the CR's
  `ProvisioningProgress`/`DeprovisioningProgress` status.

## Infrastructure Needed

None. Existing repositories, CI, and test infrastructure (envtest, kind, pytest
e2e) cover the change.

---

## Provenance

Authored: respond @ design 0.9.0 - 562b610, workspace main @ d27d7951b
Phases: draft, revise, revise, revise, revise, revise, revise, revise, respond, respond, respond

<!-- ai-workflow-provenance:{"schema_version":1,"provenance_kind":"session","workflow":"design","workflow_version":"0.9.0","ai_workflows":"562b610","source_repo":"d27d7951b","source_repo_branch":"main","commits_behind_main":0,"commits_ahead_main":0,"main_ref":"main","phases":["draft","revise","research","revise","revise","revise","revise","revise","revise","respond","respond","respond"],"authoring_modes":["skill"],"context_changed":false,"origin_untracked":false} -->
