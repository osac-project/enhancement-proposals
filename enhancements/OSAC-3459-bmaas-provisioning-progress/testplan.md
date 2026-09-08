# Testplan — OSAC-3459

## Overview

- **Feature:** OSAC-3459 — BMaaS Provisioning Progress and Step Visibility
- **Total test cases:** 15
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

- A bare metal instance is provisioning; its API status carries a `phases`
  timeline with the four provisioning phases.

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
  deprovisioning phases.

##### Steps

1. Open the detail page of the instance under deletion.
2. Inspect the rendered stepper.

##### Expected Results

- Three ordered steps appear: Teardown Initiated, Cleaning, Released.
- Teardown Initiated and Released render as point-in-time milestones (single
  timestamp, no running spinner); Cleaning shows a running state while active.

#### TC-FR1-03: API returns the phases array with populated transition timestamps

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-1 | high | automated |

##### Preconditions

- A bare metal instance has completed Host Allocation and is in Provisioning.

##### Steps

1. Issue `GET /api/fulfillment/v1/baremetal_instances/{id}`.
2. Read `status.phases`.

##### Expected Results

- `status.phases` contains entries for each phase with `phase` and `state` set.
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
2. Read `status.phases` from the DB-backed API.

##### Expected Results

- `phases` is ordered Host Allocation, Provisioning, Network Setup, Ready.
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

- An instance that reached `Ready`; API `phases` all `SUCCEEDED`.

##### Steps

1. Open the completed instance's detail page.
2. Inspect the stepper.

##### Expected Results

- All four steps render `success`, each showing its transition time and a
  duration derived from the next step's transition time.
- No running spinner is shown and no step is marked current.

#### TC-FR4-02: Released instance is archived; the timeline is served up to archival, then the public GET 404s

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-3 | critical | automated |

##### Preconditions

- An instance that reached the Released milestone; the operator is about to
  remove the finalizer.

##### Steps

1. Before finalizer removal, issue `GET /api/fulfillment/v1/baremetal_instances/{id}`
   and read `status.phases`.
2. Let the operator remove the finalizer (fulfillment soft-deletes and archives
   the record to `archived_<table>`), then issue the same `GET` again.

##### Expected Results

- Step 1 returns the final deprovisioning timeline (Teardown Initiated, Cleaning
  `SUCCEEDED`, Released), served from the DB independent of the CR. `status.phases`
  contains **only** the three deprovisioning phases — the four provisioning phases
  are intentionally not retained once deprovisioning starts (`phases` is a
  full-replace projection of the CR's current direction, by design).
- Step 2 returns 404: the released record has been archived and there is no
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

1. Drive the instance to a Provisioning failure.
2. Read the failed phase's `message` from the API.

##### Expected Results

- `phases[Provisioning].message` equals the defined text, e.g. "Provisioning
  failed — the host could not be provisioned; contact support if this persists."
- The same message renders in the stepper's failed step description.

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
  API `phases` payload.

### NFR-1: Progress reflects backend state within approximately 5 seconds

#### TC-NFR1-01: A hub CR phases change reaches the API within the freshness window via the feedback→Signal path

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-4 | high | automated |

##### Preconditions

- Fulfillment reconciler and the osac-operator feedback controller running
  against a kind cluster, with an instance whose CR is at Provisioning, at steady
  state (no in-flight proto diff).

##### Steps

1. Record `t0`, then update the `BareMetalInstance` CR `phases` on the hub to
   advance to Network Setup.
2. Poll `GET /api/fulfillment/v1/baremetal_instances/{id}` at a sub-second
   cadence and record `t1` — the first response that reflects Network Setup
   `RUNNING`.

##### Expected Results

- The feedback controller fires `Signal(id)` on the `phases` change, the
  reconciler re-reads the CR and updates the DB, and the API reflects Network
  Setup `RUNNING`. The assertion is **bounded**: `t1 - t0` ≤ the NFR-1 freshness
  deadline (single-digit seconds; ~5s soft target), and the update arrives
  **before** the periodic full-resync interval would fire (i.e. freshness comes
  from the `Signal` path, not the resync fallback) and without any new
  watch/informer. To isolate the `Signal` path, the periodic full-resync
  interval is configured well above the asserted bound for this case.

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
> and CaaS (`ClusterStatus`) carry no phase field, so the `phases` timeline is
> BMaaS-specific and follows the `IdentityProviderStatus.phase` precedent.

#### TC-NFR3-01: Coarse state and conditions are retained alongside the timeline

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-3 | medium | automated |

##### Preconditions

- An active instance in the Network Setup phase.

##### Steps

1. Read `status.state`, `status.conditions`, and `status.phases` from the API.

##### Expected Results

- `status.state` still returns the coarse lifecycle value and
  `status.conditions` still includes the existing condition set (the shared
  conditions table is unaffected).
- The `PROVISIONED` condition `reason` equals `Network Setup`, matching the
  running phase in `status.phases`.

## Gaps

### Requirement Coverage Gaps

All PRD requirements have test cases.

### Interface Change Coverage Gaps

All interface changes are exercised by test cases (IC-1: TC-FR1-03; IC-2:
TC-FR2-01, TC-FR2-03; IC-3: TC-FR2-02, TC-FR4-02, TC-NFR3-01; IC-4: TC-NFR1-01;
IC-5: TC-FR1-01, TC-FR1-02, TC-FR3-01, TC-FR4-01, TC-FR4-03, TC-NFR2-01; IC-6:
TC-FR5-01, TC-FR5-02).

## Summary

| Metric | Count |
|--------|-------|
| Total test cases | 15 |
| Critical | 3 |
| High | 9 |
| Medium | 3 |
| Low | 0 |
| Automated | 15 |
| Manual | 0 |
| Requirements with test cases | 8 / 8 |
| Interface changes with test cases | 6 / 6 |
