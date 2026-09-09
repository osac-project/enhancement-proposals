# Testplan — OSAC-3459

## Overview

- **Feature:** OSAC-3459 — BMaaS Provisioning Progress and Step Visibility
- **Total test cases:** 15
- **Requirements covered:** 8 of 8
- **Interface changes covered:** 6 of 6

> The PRD does not use numbered `FR-N`/`NFR-N` IDs. The requirement IDs below are
> derived from the PRD's In Scope items, User Stories, and Out of Scope
> constraints, and match the requirement IDs used in `design.md`:
> FR-1 current-stage display; FR-2 provisioning stages mapped to backend signals;
> FR-3 auto-refresh; FR-4 terminal/failure state persisted for the life of the
> record; FR-5 per-stage failure messages; NFR-1 ~5s freshness; NFR-2 read-only;
> NFR-3 pattern-reuse consistency.
>
> This iteration surfaces **provisioning progress only** via staged
> `reason`/`message` on the existing `PROVISIONED` condition plus a terminal
> `READY` (no new proto/CRD fields). Deprovisioning progress and a durable ordered
> per-phase timeline with durations are deferred (see design "Deferred /
> Follow-up work"), so there are no timeline-array, deprovisioning, or
> finalizer-handshake test cases.

## Test Cases

### FR-1: The bare metal instance detail view shows the current provisioning stage and a human-readable message, computed from the instance conditions

#### TC-FR1-01: Progress stepper renders the four steps derived from the PROVISIONED reason

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-4 | critical | automated |

##### Preconditions

- A bare metal instance is provisioning; its API status has `PROVISIONED`
  `status = False` with `reason = Provisioning` and a curated `message`, and
  `READY` not yet `True`.

##### Steps

1. Open the instance detail page.
2. Inspect the rendered `ProgressStepper`.

##### Expected Results

- Four ordered steps appear: Host Allocation, Provisioning, Network Setup, Ready.
- Host Allocation shows the `success` variant; Provisioning shows `info` with a
  spinner and is marked current; Network Setup and Ready show `pending`.
- The current (Provisioning) step's description shows the curated `message` from
  the `PROVISIONED` condition; no per-step duration is shown.

#### TC-FR1-02: API returns PROVISIONED with the stage reason and curated message; READY terminal

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-1 | high | automated |

##### Preconditions

- A bare metal instance has completed Host Allocation and is in the Provisioning
  stage.

##### Steps

1. Issue `GET /api/fulfillment/v1/baremetal_instances/{id}`.
2. Read `status.conditions`.

##### Expected Results

- The `PROVISIONED` condition has `status = False`, `reason = Provisioning`, and a
  non-empty curated `message` (not raw error text).
- The `READY` condition is not `True`.
- No new phase/timeline fields are present on the status (the change is carried
  entirely on existing condition `reason`/`message`).

### FR-2: The provisioning workflow presents four stages, each derived from an authoritative operator condition, order-independently

#### TC-FR2-01: Operator lifecycle conditions map to the correct furthest-advanced stage

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-2 | critical | automated |

##### Preconditions

- Fulfillment reconciler unit test harness with `BareMetalInstance` CR fixtures
  carrying operator lifecycle conditions in varying orders.

##### Steps

1. Build a fixture with `Allocated = True` and `ProvisionTemplateComplete` not
   set, with the conditions listed in a non-sequential order.
2. Run `syncStatus()`.
3. Advance the fixture to `ProvisionTemplateComplete = True`, network conditions
   not yet True, and re-run.

##### Expected Results

- After step 2, `PROVISIONED.reason = Provisioning` — the furthest-advanced True
  condition selects the stage regardless of condition ordering in the CR.
- After step 3, `PROVISIONED.reason = NetworkSetup`.
- In both cases `PROVISIONED.message` is the curated string for that stage and
  `PROVISIONED.status = False`.

#### TC-FR2-02: PROVISIONED flips True at provisioning completion and READY True at readiness

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-2 | critical | automated |

##### Preconditions

- A CR fixture with all provisioning/network conditions True but the instance not
  yet powered-on ready, and a second fixture that is additionally available/ready.

##### Steps

1. Run `syncStatus()` on the all-provisioned-but-not-ready fixture.
2. Run `syncStatus()` on the ready fixture.

##### Expected Results

- After step 1, `PROVISIONED.status = True` with `reason = Provisioned` and its
  terminal `message`; `READY` is not `True`.
- After step 2, `READY.status = True` with `reason = Ready` and its terminal
  `message`.

#### TC-FR2-03: A stage with no work does not leave the instance stuck

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-2 | medium | automated |

##### Preconditions

- A CR fixture for an instance that requests no network attachment, driven to
  provisioning completion (network conditions satisfied trivially).

##### Steps

1. Run `syncStatus()` through to completion.
2. Inspect the derived stage progression.

##### Expected Results

- The derivation advances past Network Setup (it is treated as satisfied) rather
  than lingering on `reason = NetworkSetup`; `PROVISIONED` reaches `True`.
- The UI renders the Network Setup step as `success`, not stuck `pending`.

#### TC-FR2-04: The CR→stage derivation is exhaustive over the operator condition constants, so a CR-condition change breaks a test rather than the proto

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-6 | high | automated |

##### Preconditions

- The bare-metal-fulfillment-operator `api/v1alpha1` package, which exports the
  `HostCondition*` constants and the pure `DeriveProvisioningProgress` derivation
  used by the fulfillment reconciler. This is an operator-package unit test (it
  guards the contract at the source, next to the constants), not a
  fulfillment-service test.

##### Steps

1. Enumerate the exported `HostCondition*` condition-type constants in the package
   (via the package's declared list of known conditions that the test asserts
   against the exported constants — see expected results).
2. For each constant, assert `DeriveProvisioningProgress` classifies it — it either
   selects a provisioning stage, marks provisioning complete / ready, maps to a
   failure classification, or appears in the derivation's explicit
   "intentionally not surfaced" list.
3. Feed the derivation a synthetic, unknown condition type and a fixture missing a
   previously-mapped condition, and observe the classification result.

##### Expected Results

- Every exported `HostCondition*` constant is classified (mapped or explicitly
  not-surfaced); no constant is left unhandled. The set of constants the test
  iterates is derived from the exported constants themselves, so **adding** a new
  `HostCondition*` without classifying it fails this test.
- **Renaming or removing** a `HostCondition*` that the derivation references fails
  to compile or fails this test (the constant the derivation names no longer
  exists / no longer matches), surfacing the CR→proto coupling as a build/test
  failure in the operator repo — not as a silently wrong or empty proto `reason`
  observed later by the fulfillment reconciler.
- The synthetic unknown condition is ignored (does not select a stage) and its
  presence is flagged as unclassified by the exhaustiveness assertion, confirming
  the guard fires for an unrecognised condition.

### FR-3: The progress view auto-refreshes approximately every 5 seconds without user action

#### TC-FR3-01: Detail view advances the stage on refetch without user interaction

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-4 | high | automated |

##### Preconditions

- An active instance rendered on the detail page; the mock API advances
  `PROVISIONED.reason` from `Provisioning` to `NetworkSetup` between fetches.

##### Steps

1. Render the detail page and let the query refetch (no user action).
2. Observe the stepper after the refetch resolves.

##### Expected Results

- Without any click or reload, the Provisioning step transitions to `success` and
  Network Setup becomes the current running step.
- The `aria-live="polite"` region announces the new current step.

### FR-4: The terminal or failure state (which stage the instance reached or failed at, and its message) persists for the life of the fulfillment instance record

> Re-scoped for this iteration: the single coarse condition persists the
> terminal/failure `reason`/`message`, not a full ordered per-phase history with
> durations. The durable timeline is a deferred follow-up.

#### TC-FR4-01: Completed instance persists terminal conditions and renders all steps succeeded

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-1 | high | automated |

##### Preconditions

- An instance that reached readiness: API `PROVISIONED = True` (`reason
  Provisioned`) and `READY = True` (`reason Ready`).

##### Steps

1. Open the completed instance's detail page and inspect the stepper.
2. Issue `GET /api/fulfillment/v1/baremetal_instances/{id}` and read
   `status.conditions`.

##### Expected Results

- All four steps render `success`; no running spinner and no step marked current;
  no per-step duration is asserted (none is shown this iteration).
- The API returns `PROVISIONED = True` and `READY = True` with their terminal
  reasons/messages, served from the DB.

#### TC-FR4-02: Failed instance persists the failing condition, then archives to 404

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-1 | high | automated |

##### Preconditions

- An instance whose Provisioning stage failed: `PROVISIONED = False`,
  `reason = ProvisionJobFailed`, with the IC-5 curated `message`.

##### Steps

1. Issue `GET /api/fulfillment/v1/baremetal_instances/{id}` and read
   `status.conditions`.
2. Let fulfillment soft-delete and archive the record to `archived_<table>` (on
   finalizer removal), then issue the same `GET` again.

##### Expected Results

- Step 1: the response retains the failing `PROVISIONED` condition
  (`False`, `reason = ProvisionJobFailed`, curated `message`) served from the DB
  independent of the CR, so the failure remains viewable after completion.
- Step 2: returns 404 — the released record has been archived and there is no
  archive-read path, so FR-4 is bounded to the life of the live record (matching
  VMaaS/CaaS).

### FR-5: Failure descriptions identify the stage and condition in human-readable terms; no raw internal errors are surfaced

#### TC-FR5-01: Failed stage shows its defined human-readable message

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-5 | high | automated |

##### Preconditions

- Reconciler test harness; a Provisioning failure is injected via
  `ProvisionJobFailed` (the `osac-create-bare-metal-instance` job fails).

##### Steps

1. Run `syncStatus()` on the failed fixture.
2. Read the `PROVISIONED` condition `message` from the API.

##### Expected Results

- `PROVISIONED.message` equals the exact IC-5 string for `ProvisionJobFailed`:
  "OS installation and configuration did not complete; the provisioning job
  failed." (byte-for-byte; the mapping is fixed and deterministic — one message
  per reason).
- The same message renders verbatim in the stepper's failed step description.

#### TC-FR5-02: Raw internal error text is not surfaced in the conditions

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-5 | medium | automated |

##### Preconditions

- A stage failure whose underlying backend error contains an internal stack trace
  or raw AAP/backend error string.

##### Steps

1. Inject the backend failure with a raw internal error.
2. Read the `PROVISIONED` condition `reason` and `message`.

##### Expected Results

- `message` contains only the stage-specific human-readable text from the fixed
  vocabulary.
- The raw backend error string does not appear in `reason`, `message`, or anywhere
  in the API `status.conditions` payload.

### NFR-1: Progress reflects backend state within approximately 5 seconds

#### TC-NFR1-01: A hub CR condition change reaches the API within the freshness window via the feedback→Signal path

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-3 | high | automated |

##### Preconditions

- Fulfillment reconciler and the osac-operator feedback controller running against
  a kind cluster, at steady state (no in-flight proto diff), for an instance whose
  CR is at the Provisioning stage.

##### Steps

1. Record `t0`, then update the `BareMetalInstance` CR on the hub so the operator
   conditions advance the derived stage from Provisioning to Network Setup.
2. Poll `GET /api/fulfillment/v1/baremetal_instances/{id}` at a sub-second cadence
   and record `t1` — the first response with `PROVISIONED.reason = NetworkSetup`.

##### Expected Results

- The feedback controller fires `Signal(id)` on the condition change, the
  reconciler re-reads the CR and updates the DB, and the API reflects the new
  stage. The assertion is **bounded**: `t1 - t0` ≤ the NFR-1 freshness deadline
  (single-digit seconds; ~5s soft target), and the update arrives **before** the
  periodic full-resync interval would fire (freshness comes from the `Signal`
  path, not the resync fallback) and without any new watch/informer. To isolate
  the `Signal` path, the periodic full-resync interval is configured well above
  the asserted bound.

#### TC-NFR1-02: The detail view reflects an API stage change within the bounded UI poll interval and stops at terminal

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-4 | high | automated |

##### Preconditions

- The instance detail page is rendered for a **non-terminal** instance; the mock
  API returns `PROVISIONED.reason = Provisioning`. Fake timers control the query
  `refetchInterval`.

##### Steps

1. Render the detail page and let the initial fetch settle on the Provisioning
   stage.
2. Update the mock API to return `PROVISIONED.reason = NetworkSetup`, then advance
   fake timers by the dedicated ~5s `refetchInterval` (no user interaction).
3. Inspect the stepper.
4. Drive the instance to a resting terminal state (`PROVISIONED = True`,
   `READY = True`), let one more interval elapse, then update the mock API again
   and advance timers.

##### Expected Results

- After step 2's single ~5s interval, the stepper reflects Network Setup running
  without any click or reload — the DB→UI leg is bounded to the dedicated per-page
  ~5s poll, not the global ~10s default. This complements TC-NFR1-01, which
  measures the CR→API (DB) leg; together they bound end-to-end freshness.
- After step 4, once the instance is terminal (`READY = True`) the query **stops
  refetching**: the later mock-API change is not picked up, confirming polling
  halts at a terminal state.

### NFR-2: The progress and failure display is read-only

#### TC-NFR2-01: The progress view exposes no retry or re-provision control

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-4 | high | automated |

##### Preconditions

- A failed instance rendered on the detail page.

##### Steps

1. Open the failed instance's detail page.
2. Query the stepper region for interactive controls.

##### Expected Results

- No retry, re-provision, or other mutating button/link is present in the progress
  region.
- The steps expose no click/select behavior (display-only stepper).

### NFR-3: Progress reuses the OSAC coarse-condition staged reason/message pattern for cross-service consistency

> "Reuse" here means the same shape CaaS adopted in OSAC-4441 (PR #646): a single
> coarse progress condition whose `reason`/`message` carry the furthest-advanced
> stage, refreshed each reconcile, with a terminal `READY`. No new
> phase/timeline construct is introduced.

#### TC-NFR3-01: Coarse state and conditions are retained; PROVISIONED reason equals the current stage

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-2 | medium | automated |

##### Preconditions

- An active instance in the Network Setup stage.

##### Steps

1. Read `status.state` and `status.conditions` from the API.

##### Expected Results

- `status.state` still returns the coarse lifecycle value and `status.conditions`
  still includes the existing condition set (the shared conditions table is
  unaffected).
- The `PROVISIONED` condition `reason` equals `NetworkSetup`, matching the current
  provisioning stage — the same coarse-condition staged-reason shape CaaS uses.

## Gaps

### Requirement Coverage Gaps

All PRD requirements in scope for this iteration have test cases. Deprovisioning
progress and the durable ordered per-phase timeline are deferred (out of scope
here) and are intentionally not covered.

### Interface Change Coverage Gaps

All interface changes are exercised by test cases (IC-1: TC-FR1-02, TC-FR4-01,
TC-FR4-02; IC-2: TC-FR2-01, TC-FR2-02, TC-FR2-03, TC-NFR3-01; IC-3: TC-NFR1-01;
IC-4: TC-FR1-01, TC-FR3-01, TC-NFR1-02, TC-NFR2-01; IC-5: TC-FR5-01, TC-FR5-02;
IC-6: TC-FR2-04).

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
