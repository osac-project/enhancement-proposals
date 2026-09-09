# Testplan — OSAC-3459

## Overview

- **Feature:** OSAC-3459 — BMaaS Provisioning Progress and Step Visibility
- **Total test cases:** 16
- **Requirements covered:** 8 of 8
- **Interface changes covered:** 6 of 6

> The PRD does not use numbered `FR-N`/`NFR-N` IDs. The requirement IDs below are
> derived from the PRD's In Scope items, User Stories, and Out of Scope
> constraints, and match the requirement IDs used in `design.md`:
> FR-1 per-phase display; FR-2 four+three phases mapped to backend signals;
> FR-3 auto-refresh; FR-4 persisted timeline; FR-5 per-phase failure messages;
> NFR-1 ~5s freshness; NFR-2 read-only; NFR-3 pattern-reuse consistency.

## Test Cases

### FR-1: The bare metal instance detail view shows each phase's name, state, and transition timestamp with derived duration (provisioning and deprovisioning)

#### TC-FR1-01: Provisioning timeline renders all four phases with state and timestamps

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-5 | critical | automated |

##### Preconditions

- A bare metal instance is provisioning; its API status carries a
  `provisioning_phases` timeline with the four provisioning phases (and an empty
  `deprovisioning_phases`).

##### Steps

1. Open the instance detail page.
2. Inspect the rendered `ProgressStepper`.

##### Expected Results

- Four ordered steps appear: Host Allocation, Provisioning, Network Setup,
  Ready.
- The running phase shows the `info` variant with a spinner and is marked current;
  completed phases show `success`; not-yet-started phases show `pending`.
- Each started step's description shows the time it became active; each finished
  step also shows a duration derived from the next step's transition time.

#### TC-FR1-02: Deprovisioning timeline renders the three teardown phases

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-5 | high | automated |

##### Preconditions

- A bare metal instance is being deleted; its API status carries the three
  deprovisioning phases in `deprovisioning_phases` (with the four completed
  `provisioning_phases` still retained).

##### Steps

1. Open the detail page of the instance under deletion.
2. Inspect the rendered stepper.

##### Expected Results

- Three ordered steps appear: Teardown Initiated, Cleaning, Released.
- Teardown Initiated and Released render as point-in-time milestones (single
  timestamp, no running spinner); Cleaning shows a running state while active.

#### TC-FR1-03: API returns the provisioning_phases array with populated transition timestamps

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-1 | high | automated |

##### Preconditions

- A bare metal instance has completed Host Allocation and is in Provisioning.

##### Steps

1. Issue `GET /api/fulfillment/v1/baremetal_instances/{id}`.
2. Read `status.provisioning_phases`.

##### Expected Results

- `status.provisioning_phases` contains entries for each phase with `phase` and
  `state` set; `status.deprovisioning_phases` is empty.
- Host Allocation has `state = SUCCEEDED` with a `last_transition_time`; Provisioning
  has `state = RUNNING` with a later `last_transition_time`, so Host Allocation's
  derived end equals Provisioning's `last_transition_time`.
- No `start_time`/`end_time` fields are present on any phase entry (single
  `last_transition_time` per phase).

### FR-2: The workflow presents four provisioning and three deprovisioning phases, each mapped to an authoritative backend signal

#### TC-FR2-01: Operator lifecycle conditions and AAP job status map to the correct phase and state

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-2 | critical | automated |

##### Preconditions

- Operator unit test harness with osac-operator lifecycle-condition and AAP
  job-status fixtures.

##### Steps

1. Drive a fixture through `Allocated` → provision job triggered
   (`osac-create-bare-metal-instance`) → `ProvisionTemplateComplete`.
2. Advance the fixture through `NetworkHandoffComplete`/`IPDiscoveryComplete` →
   `PowerSynced` → phase `Ready`.

##### Expected Results

- On `Allocated`, `ProvisioningProgress` shows Host Allocation `SUCCEEDED` and
  Provisioning `RUNNING`; the single opaque provision job (OS install +
  configuration) is represented by the one Provisioning phase.
- On `ProvisionTemplateComplete`, Provisioning is `SUCCEEDED` and Network Setup
  becomes `RUNNING`; on `PowerSynced`/`Ready`, Network Setup is `SUCCEEDED` and
  Ready becomes/settles `SUCCEEDED`.
- Provisioning's `lastTransitionTime` is the operator-recorded moment the provision
  job was triggered (not the AAP `JobStatus.Timestamp`, which is trigger-only);
  its derived end equals the next phase's (Network Setup) `lastTransitionTime`.

#### TC-FR2-02: Phases appear in the defined provisioning order in the API

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-3 | high | automated |

##### Preconditions

- A `BareMetalInstance` CR with a populated `ProvisioningProgress` timeline.

##### Steps

1. Reconcile the instance in the fulfillment reconciler.
2. Read `status.provisioning_phases` from the DB-backed API.

##### Expected Results

- `provisioning_phases` is ordered Host Allocation, Provisioning, Network Setup,
  Ready.
- The `PROVISIONED` condition `reason` equals the name of the phase whose
  `state == RUNNING`.

#### TC-FR2-03: An inapplicable phase is marked SKIPPED, not stuck PENDING

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-2 | medium | automated |

##### Preconditions

- An instance that requests no network attachment, so Network Setup has no work
  to do.

##### Steps

1. Reconcile the instance through to `Ready`.
2. Inspect the Network Setup phase entry.

##### Expected Results

- Network Setup has `state = SKIPPED` with a single `lastTransitionTime` and no
  derived duration; the stepper still shows every phase in order.
- Provisioning reflects the AAP provision-job outcome (`SUCCEEDED` on job
  success), with its `lastTransitionTime` recorded by the operator (not the
  trigger-only AAP `JobStatus.Timestamp`).

### FR-3: The progress view auto-refreshes approximately every 5 seconds without user action

#### TC-FR3-01: Detail view advances the timeline on refetch without user interaction

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-5 | high | automated |

##### Preconditions

- An active instance rendered on the detail page; the mock API advances the
  running phase from Provisioning to Network Setup between fetches.

##### Steps

1. Render the detail page and let the query refetch (no user action).
2. Observe the stepper after the refetch resolves.

##### Expected Results

- Without any click or reload, Provisioning transitions to `success` and
  Network Setup becomes the current running step.
- The `aria-live="polite"` region announces the new current step.

### FR-4: The step-level timeline persists after provisioning or deprovisioning finishes, for the life of the fulfillment instance record (failed instances included; released instances until the record is archived on finalizer removal)

#### TC-FR4-01: Completed instance shows all phases succeeded with durations

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-5 | high | automated |

##### Preconditions

- An instance that reached `Ready`; API `provisioning_phases` all `SUCCEEDED`.

##### Steps

1. Open the completed instance's detail page.
2. Inspect the stepper.

##### Expected Results

- All four steps render `success`.
- Host Allocation, Provisioning, and Network Setup each show their transition
  time and a duration derived from the next step's transition time.
- The terminal `Ready` step shows its transition time only and **no** derived
  duration (there is no subsequent phase to derive an end from) — the assertion
  must not expect a duration on `Ready`.
- No running spinner is shown and no step is marked current.

#### TC-FR4-02: Released holds the finalizer until the terminal timeline is persisted (both arrays retained), then archives

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-3 | critical | automated |

##### Preconditions

- An instance that completed provisioning (four `provisioning_phases`
  `SUCCEEDED`) and then reached the Released milestone; the reconciler-gated
  finalizer handshake is under test.

##### Steps

1. When the operator writes the Released milestone, **block the reconciler's
   terminal DB commit** so persistence has not yet happened. Assert the
   `BareMetalInstance` finalizer is **still present** and no
   `osac.openshift.io/timeline-persisted` annotation is set yet. Issue
   `GET /api/fulfillment/v1/baremetal_instances/{id}` and confirm the DB still
   serves the **pre-persistence** deprovisioning state (Cleaning, no `Released`
   entry) — the terminal timeline has not reached the DB.
2. While the commit is still blocked, assert **neither** the `timeline-persisted`
   acknowledgment **nor** finalizer removal has occurred.
3. Unblock the reconciler: let it durably commit the terminal timeline to the DB
   and write the `osac.openshift.io/timeline-persisted` annotation back onto the
   CR. Now issue the same `GET` and read both `status.provisioning_phases` and
   `status.deprovisioning_phases`.
4. Assert the operator observes the acknowledgment and only then removes the
   finalizer.
5. Let fulfillment soft-delete and archive the record to `archived_<table>`, then
   issue the same `GET` again.

##### Expected Results

- Step 1: the finalizer is retained and the API still returns the pre-`Released`
  deprovisioning state — the operator does not remove the finalizer, and the DB
  does not expose the terminal timeline, before the reconciler acknowledges
  persistence.
- Step 2: with the commit blocked, no `timeline-persisted` annotation is written
  and the finalizer is not removed — the handshake does not advance without a
  durable commit.
- Step 3: after the commit and acknowledgment, the response retains **both**
  timelines — the four completed `provisioning_phases` (all `SUCCEEDED`) **and**
  the three `deprovisioning_phases` (Teardown Initiated, Cleaning `SUCCEEDED`,
  Released `SUCCEEDED`) — served from the DB independent of the CR, and this is
  observable **before** finalizer removal. The provisioning history is retained
  through teardown, not discarded.
- Step 4: only after the `timeline-persisted` acknowledgment is observed does the
  operator remove the finalizer (host returned to the pool: `available`,
  `consumerRef` cleared, reusable).
- Step 5: returns 404 — the released record has been archived and there is no
  archive-read path, so FR-4 is bounded to the life of the live record
  (matching VMaaS/CaaS).

#### TC-FR4-03: Failed instance retains the full timeline with the failed phase

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-5 | high | automated |

##### Preconditions

- An instance whose Provisioning phase failed; downstream phases never started.

##### Steps

1. Open the failed instance's detail page.
2. Inspect the stepper.

##### Expected Results

- Host Allocation shows `success`; Provisioning shows `danger`; Network Setup and
  Ready remain `pending`.
- The Provisioning step shows its transition time and the failure message.

### FR-5: Failure descriptions identify the phase and condition in human-readable terms; no raw internal errors are surfaced

#### TC-FR5-01: Failed phase shows its defined human-readable message

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-6 | high | automated |

##### Preconditions

- Operator/reconciler test harness; a Provisioning failure is injected.

##### Steps

1. Drive the instance to a Provisioning failure via `ProvisionJobFailed` (the
   `osac-create-bare-metal-instance` job fails).
2. Read the failed phase's `message` from the API.

##### Expected Results

- `provisioning_phases[Provisioning].message` equals the exact IC-6 string for
  `ProvisionJobFailed`: "OS installation and configuration did not complete; the
  provisioning job failed." (byte-for-byte; the mapping is fixed and
  deterministic — one message per reason).
- The same message renders verbatim in the stepper's failed step description.

#### TC-FR5-02: Raw internal error text is not surfaced in the timeline

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-6 | medium | automated |

##### Preconditions

- A phase failure whose underlying backend error contains an internal stack
  trace or raw AAP/backend error string.

##### Steps

1. Inject the backend failure with a raw internal error.
2. Read the failed phase's `message`.

##### Expected Results

- `message` contains only the phase-specific human-readable text.
- The raw backend error string does not appear in `message` or anywhere in the
  API `provisioning_phases`/`deprovisioning_phases` payload.

### NFR-1: Progress reflects backend state within approximately 5 seconds

#### TC-NFR1-01: A hub CR phases change reaches the API within the freshness window via the feedback→Signal path (both timeline fields)

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-4 | high | automated |

This case is **parameterized over both timeline fields** — IC-4 extends the
feedback `Signal` trigger to fire on a change to **either** array, so both must be
proven, not just the provisioning one.

##### Preconditions

- Fulfillment reconciler and the osac-operator feedback controller running
  against a kind cluster, at steady state (no in-flight proto diff), for each
  variant:
  - **Variant A (provisioning):** an instance whose CR is at Provisioning.
  - **Variant B (deprovisioning):** an instance under teardown whose CR is at
    Cleaning (`deprovisioning_phases` non-empty).

##### Steps

For each variant:

1. Record `t0`, then update the `BareMetalInstance` CR on the hub:
   - **Variant A:** advance `ProvisioningProgress` to Network Setup.
   - **Variant B:** advance `DeprovisioningProgress` from Cleaning to the
     `Released` milestone.
2. Poll `GET /api/fulfillment/v1/baremetal_instances/{id}` at a sub-second
   cadence and record `t1` — the first response that reflects the new state
   (Variant A: Network Setup `RUNNING`; Variant B: `Released` in
   `deprovisioning_phases`).

##### Expected Results

- In **both** variants the feedback controller fires `Signal(id)` on the changed
  timeline field (`ProvisioningProgress` for A, `DeprovisioningProgress` for B),
  the reconciler re-reads the CR and updates the DB, and the API reflects the new
  state. The assertion is **bounded**: `t1 - t0` ≤ the NFR-1 freshness deadline
  (single-digit seconds; ~5s soft target), and the update arrives **before** the
  periodic full-resync interval would fire (i.e. freshness comes from the
  `Signal` path, not the resync fallback) and without any new watch/informer. To
  isolate the `Signal` path, the periodic full-resync interval is configured well
  above the asserted bound for both variants.
- Variant B proves a `DeprovisioningProgress` change propagates within the same
  bound as a `ProvisioningProgress` change, so teardown freshness is not left
  unverified.

#### TC-NFR1-02: The detail view reflects an API timeline change within the bounded UI poll interval

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-5 | high | automated |

##### Preconditions

- The instance detail page is rendered for a **non-terminal** instance; the mock
  API returns Provisioning `RUNNING`. Fake timers control the query
  `refetchInterval`.

##### Steps

1. Render the detail page and let the initial fetch settle on Provisioning
   `RUNNING`.
2. Update the mock API to return Network Setup `RUNNING`, then advance fake
   timers by the dedicated ~5s `refetchInterval` (no user interaction).
3. Inspect the stepper.
4. Drive the instance to a resting terminal state (`Ready` `SUCCEEDED`,
   `deprovisioning_phases` empty), let one more interval elapse, then update the
   mock API again and advance timers.
5. Simulate deletion: update the mock API so `deprovisioning_phases` is now
   non-empty (Teardown Initiated milestone, Cleaning `RUNNING`) while the four
   `provisioning_phases` remain `SUCCEEDED`, and trigger a single refetch
   (query invalidation, as the delete mutation would cause).
6. Advance fake timers by another ~5s interval, then update the mock API to
   advance Cleaning → Released and advance timers again.

##### Expected Results

- After step 2's single ~5s interval, the stepper reflects Network Setup
  `RUNNING` without any click or reload — the DB→UI leg is bounded to the
  dedicated per-page ~5s poll, not the global ~10s default. This complements
  TC-NFR1-01, which measures the CR→API (DB) leg; together they bound
  end-to-end freshness.
- After step 4, while the instance is at a resting `Ready` with no teardown the
  query **stops refetching**: the later mock-API change is not picked up,
  confirming polling halts when the current timeline is terminal.
- After step 5, once `deprovisioning_phases` becomes non-empty the query
  **resumes** its ~5s cadence — the historical `Ready` `SUCCEEDED` does not
  suppress teardown polling — and the second stepper renders the teardown
  timeline.
- After step 6, the teardown advance to `Released` is reflected within one ~5s
  interval; once `Released` `SUCCEEDED` is the terminal deprovisioning state the
  query stops refetching again.

### NFR-2: The progress and failure display is read-only

#### TC-NFR2-01: The progress view exposes no retry or re-provision control

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-5 | high | automated |

##### Preconditions

- A failed instance rendered on the detail page.

##### Steps

1. Open the failed instance's detail page.
2. Query the stepper region for interactive controls.

##### Expected Results

- No retry, re-provision, or other mutating button/link is present in the
  progress region.
- The steps expose no click/select behavior (display-only stepper).

### NFR-3: Progress reuses the OSAC status-condition pattern for cross-service consistency

> "Reuse" here means the shared proto conventions (condition-shape field names —
> `last_transition_time`, optional `message` — and the coarse `state` + `conditions`
> layer), not a shared phase/timeline construct: VMaaS (`ComputeInstanceStatus`)
> and CaaS (`ClusterStatus`) carry no phase field, so the phase timelines
> (`provisioning_phases`/`deprovisioning_phases`) are BMaaS-specific and follow
> the `IdentityProviderStatus.phase` precedent.

#### TC-NFR3-01: Coarse state and conditions are retained alongside the timeline

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-3 | medium | automated |

##### Preconditions

- An active instance in the Network Setup phase.

##### Steps

1. Read `status.state`, `status.conditions`, and `status.provisioning_phases`
   from the API.

##### Expected Results

- `status.state` still returns the coarse lifecycle value and
  `status.conditions` still includes the existing condition set (the shared
  conditions table is unaffected).
- The `PROVISIONED` condition `reason` equals `Network Setup`, matching the
  running phase in `status.provisioning_phases`.

## Gaps

### Requirement Coverage Gaps

All PRD requirements have test cases.

### Interface Change Coverage Gaps

All interface changes are exercised by test cases (IC-1: TC-FR1-03; IC-2:
TC-FR2-01, TC-FR2-03; IC-3: TC-FR2-02, TC-FR4-02, TC-NFR3-01; IC-4: TC-NFR1-01;
IC-5: TC-FR1-01, TC-FR1-02, TC-FR3-01, TC-FR4-01, TC-FR4-03, TC-NFR1-02,
TC-NFR2-01; IC-6: TC-FR5-01, TC-FR5-02).

## Summary

| Metric | Count |
|--------|-------|
| Total test cases | 16 |
| Critical | 3 |
| High | 10 |
| Medium | 3 |
| Low | 0 |
| Automated | 16 |
| Manual | 0 |
| Requirements with test cases | 8 / 8 |
| Interface changes with test cases | 6 / 6 |
