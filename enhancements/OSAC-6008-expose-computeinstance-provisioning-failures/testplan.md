# Testplan — OSAC-6011

## Overview

- **Feature:** OSAC-6008 — Expose ComputeInstance provisioning failures during retries
- **Total test cases:** 15
- **Requirements covered:** 7 of 7
- **Interface changes covered:** 3 of 3
- **Execution status:** planned — no case is implemented or executed yet

These cases define the required implementation and QE coverage. They are
planned tests for the design phase; no case has been implemented or executed
yet.

## Test Case Index

| ID | Scenario | IC | Priority |
|----|----------|----|----------|
| TC-FR1-01 | Public API reports retrying during backoff | IC-1 | critical |
| TC-FR1-02 | VM list and details show retrying | IC-2 | high |
| TC-FR1-03 | CLI list and describe show retrying | IC-3 | high |
| TC-FR2-01 | Only the latest failure is retained across attempts | IC-1 | critical |
| TC-FR3-01 | Failure sources map to safe reasons and messages | IC-1 | critical |
| TC-FR3-02 | VM details show actionable failure data | IC-2 | high |
| TC-FR3-03 | CLI describe shows actionable failure data | IC-3 | high |
| TC-FR3-04 | Terminal outcomes map to final failure without changing retry semantics | IC-1 | critical |
| TC-FR4-01 | Public API clears retry and failure on success | IC-1 | critical |
| TC-FR4-02 | VM surfaces clear retry and failure on success | IC-2 | high |
| TC-FR4-03 | CLI surfaces clear retry and failure on success | IC-3 | high |
| TC-FR5-01 | Existing tenant authorization remains enforced | IC-1 | critical |
| TC-NFR1-01 | Deployed CLI status journey is available | IC-3 | high |
| TC-NFR1-02 | Deployed ComputeInstance retry fields converge | IC-1 | high |
| TC-NFR2-01 | Retry engine behavior remains unchanged | — | critical |

## Test Cases

All cases in this plan are in **planned** status. UI and CLI derive retry
from `Provisioned=False` with reason `RetryScheduled` or `RetryRunning`,
not from failure presence or message text. No additional retry condition is
introduced.

Backend/API and CLI cases are delivered with this design. IC-2 UI cases
(TC-FR1-02, TC-FR3-02, TC-FR4-02) are retained as cross-workflow requirements
and belong to the separate UI development path; they are not claimed as
backend/CLI delivery. Browser coverage also belongs to that UI path.

### FR-1: Retry indicator during pending or active retry

##### Shared Preconditions

- A ComputeInstance exists in a tenant/project readable by the test caller.
- Its provision task has failed with an outcome the existing engine retries.

#### TC-FR1-01: Public API reports retrying during backoff

| Interface Change | Tier | Owner | Priority | Automation |
|-----------------|------|-------|----------|------------|
| IC-1 | Component integration | [DEV] VMaaS | critical | automated |

**Command:** `make -C osac-installer test PLATFORM=kind PROFILE=dev NS=osac SUITE=compute-storage`

**Boundary:** Real Fulfillment API, PostgreSQL, installed ComputeInstance
operator, and Kind Kubernetes API. The AAP HTTP job endpoint is a controlled
recording double; no real provider or VM runs.

**Steps:** 1. Create a ComputeInstance whose first provision result is a
retryable failure. → 2. Poll public Get during backoff. → 3. Let the retry
start and poll public Get while that attempt is running.

**Expected:** The response keeps the existing power state, contains
`PROVISIONED=False` with reason `RetryScheduled`, and contains the
latest failure reason, message, attempt, and observation timestamp. When the
retry starts, `PROVISIONED` remains `False`, its reason becomes
`RetryRunning`, and its message is `A provisioning retry is running.` The
previous failure object remains unchanged until the attempt completes.

#### TC-FR1-02: VM list and details show retrying

| Interface Change | Tier | Owner | Priority | Automation |
|-----------------|------|-------|----------|------------|
| IC-2 | Unit | [DEV] VMaaS UI | high | automated |

**Command:** `pnpm test -- VmTable VmDetails` from `osac-ui/`

**Boundary:** React Testing Library with generated types and rendered
components. No browser, network, operator, or API server runs.

**Steps:** 1. Render the VM list with a retrying instance. → 2. Open the
details view for the same object.

**Expected:** Supported UI status surfaces expose that provisioning is
retrying without changing the power state. Copy, placement, and visual
assertions follow the separate UX specification when available.

#### TC-FR1-03: CLI list and describe show retrying

| Interface Change | Tier | Owner | Priority | Automation |
|-----------------|------|-------|----------|------------|
| IC-3 | Unit | [DEV] Fulfillment | high | automated |

**Command:** `go test ./internal/cmd/cli/describe/computeinstance ./internal/rendering` from `fulfillment-service/`

**Boundary:** Real CLI and table/describe renderers with generated protobuf
types and a stubbed gRPC transport. No deployed service or operator runs.

**Steps:** 1. Render `osac get computeinstances` with a retrying instance. →
2. Render `osac describe computeinstance` for the same object.

**Expected:** The list has `PROVISIONING` equal to `Retrying`; describe shows
`Provisioning: Retrying`.

### FR-2: Latest failure retained while retry is pending or running

#### TC-FR2-01: Only the latest failure is retained across attempts

| Interface Change | Tier | Owner | Priority | Automation |
|-----------------|------|-------|----------|------------|
| IC-1 | Envtest | [DEV] VMaaS | critical | automated |

**Command:** `make -C osac-operator test`

**Boundary:** Real Kubernetes API server, etcd, loaded CRDs, and in-process
controller. AAP is in memory and the Fulfillment gRPC client is a test double.

##### Steps

1. Fail provision attempt 1 with `backend busy`.
2. Advance the clock and fail attempt 2 with `quota exhausted`.
3. Read the ComputeInstance CR and the private object produced by the
   feedback mapper.
4. In the same lifecycle, let the engine persist attempt 2's failure but
   force the controller's following status update to conflict. Recreate the
   reconciler/engine from persisted state and reconcile during backoff.
5. Launch attempt 3 while forcing its controller projection to conflict;
   recreate the engine and reconcile while attempt 3 is still running.
6. Let attempt 3 succeed; after the engine stores success, force the public
   failure-clearing CR status update to conflict. Recreate the reconciler
   and engine and reconcile again with infrastructure still becoming ready.
7. Exercise legacy fixtures with no `lastFailure`: a `Retrying` entry and
   running entries with attempt 1 and attempt 3. Include attempt 3 from a
   configuration rerun and a cancelled-job relaunch. Recreate the engine
   between observations; also launch the snapshot-free `Retrying` fixture.
8. Let a legacy fixture fail retryably after upgrade, then launch its next
   attempt after backoff.

##### Expected Results

- `last_provisioning_failure.attempt` is `2`.
- The message is `Provisioning failed.`; neither provider-supplied message
  appears in public status. The attempt and observation time identify the
  newer failure even when both public messages are identical.
- No failure array or prior attempt 1 value exists.
- `PROVISIONED=False` with reason `RetryScheduled` during backoff and
  `RetryRunning` after launch of attempt 3.
- `status.jobs[provision].lastFailure` preserves attempt 2's reason, fixed
  message, attempt number, and original observation time across both
  conflicts and restarts. The later public projection matches exactly,
  even when the job's current attempt is 3. No AAP failure re-fetch or
  operational-message parsing is needed.
- After success and the failed clearing write, the next reconcile removes
  stale public failure data from the persisted successful job state; no
  failure checkpoint or retry reason remains. Infrastructure progress is
  still `Provisioned=False/WaitingForVM` or `ProvisioningStorage`.
- The legacy `Retrying` fixture reports `RetryScheduled` with absent public
  failure data. Snapshot-free running fixtures retain existing infrastructure
  progress status, with no `RetryRunning` inference from attempt count or
  earlier in-memory observations. No historical observation time is invented.
- A newly observed legacy-fixture failure creates the checkpoint and public
  failure; its subsequent running retry reports `RetryRunning` and retains
  that original failed-attempt number and observation time across restart.

### FR-3: Actionable and safe failure details

#### TC-FR3-01: Failure sources map to safe reasons and messages

| Interface Change | Tier | Owner | Priority | Automation |
|-----------------|------|-------|----------|------------|
| IC-1 | Unit | [DEV] VMaaS | critical | automated |

**Command:** `make -C osac-operator test`

**Boundary:** Real engine and controller code with the in-memory AAP double.
No real AAP, provider, Kubernetes API, or Fulfillment service runs.

**Steps:** 1. Run the table-driven failure-source cases. → 2. Inspect the
controller-produced failure value.

##### Expected Results

| Failure source | Reason | Message |
|---|---|---|
| Valid `osac_error` | `ProviderReported` | `Provisioning failed.` |
| Successful job with malformed or unexpected `osac_result` | `ResultRejected` | `Internal error` |
| Failed job with missing or malformed `osac_error` | `InvalidResult` | `Internal error` |
| Timeout | `TimedOut` | `The provisioning attempt timed out.` |
| Lost job | `JobLost` | `Internal error` |
| Job not started | `JobNotStarted` | `Internal error` |
| AAP infrastructure error | `ProviderError` | `Internal error` |

Include valid `osac_error` messages containing a sentinel credential, AAP
job ID, task/manager name, log, traceback, and next-retry timestamp. Each
still maps to `Provisioning failed.`; no sentinel or supplied text appears
in public status, including the condition message.

#### TC-FR3-02: VM details show actionable failure data

| Interface Change | Tier | Owner | Priority | Automation |
|-----------------|------|-------|----------|------------|
| IC-2 | Unit | [DEV] VMaaS UI | high | automated |

**Command:** `pnpm test -- VmTable VmDetails` from `osac-ui/`

**Boundary:** React Testing Library with generated types. No browser or
network boundary runs.

**Steps:** 1. Supply a ComputeInstance with a latest-failure value to the UI
consumer. → 2. Verify the failure data available to its status surfaces.

**Expected:** The UI consumer retains the failure reason, exact tenant-safe
message, failed attempt number, and observation timestamp. Presentation
assertions are deferred to the separate UX specification.

#### TC-FR3-03: CLI describe shows actionable failure data

| Interface Change | Tier | Owner | Priority | Automation |
|-----------------|------|-------|----------|------------|
| IC-3 | Unit | [DEV] Fulfillment | high | automated |

**Command:** `go test ./internal/cmd/cli/describe/computeinstance ./internal/rendering` from `fulfillment-service/`

**Boundary:** Real CLI renderer and generated types with a stubbed transport.
No deployed API or operator runs.

**Steps:** 1. Describe a ComputeInstance with a failure value.

**Expected:** Output contains the reason label, exact safe message,
`Last Provisioning Failure Attempt: 2`, and an RFC 3339 observation timestamp.

#### TC-FR3-04: Terminal outcomes map to final failure without changing retry semantics

| Interface Change | Tier | Owner | Priority | Automation |
|-----------------|------|-------|----------|------------|
| IC-1 | Unit | [DEV] VMaaS | critical | automated |

**Command:** `make -C osac-operator test`

**Boundary:** Real engine, controller, and no-output acceptance code with the
in-memory AAP double. No real AAP, provider, Kubernetes API, or Fulfillment
service runs.

##### Steps

1. Return a valid `osac_error` with `retryable=false`.
2. Return a failed AAP job with a missing `osac_error`.
3. Return a failed AAP job with a malformed `osac_error`.
4. Return a successful AAP job with a malformed or unexpected `osac_result`.

##### Expected Results

- Each case leaves `NetworkJobStatus.State` as `Failed`.
- The controller sets `Provisioned=False` with reason `ProvisioningFailed`.
- No retry reason or additional retry condition is present.
- `last_provisioning_failure` is populated with the matching safe reason and
  message.
- No case schedules a retry or changes the existing engine's retry decision.

### FR-4: Clear indicators and failure after success

#### TC-FR4-01: Public API clears retry and failure on success

| Interface Change | Tier | Owner | Priority | Automation |
|-----------------|------|-------|----------|------------|
| IC-1 | Component integration | [DEV] VMaaS | critical | automated |

**Command:** `make -C osac-installer test PLATFORM=kind PROFILE=dev NS=osac SUITE=compute-storage`

**Boundary:** Real Fulfillment API, PostgreSQL, installed operator, and Kind
Kubernetes API. AAP is a controlled recording double; no real provider or VM
runs.

##### Steps

1. Fail the first provision attempt retryably and observe its public failure.
2. Let the retry job succeed while the VM is absent. Poll public Get.
3. Introduce a VM whose storage is still provisioning and poll again.
4. Allow the existing infrastructure-readiness check to pass and poll again.

##### Expected Results

- Job success clears `last_provisioning_failure` (absent, not an empty object)
  and removes the retry reason; the job's internal checkpoint is also absent.
- With no VM, `PROVISIONED=False/WaitingForVM`; while storage is provisioning,
  `PROVISIONED=False/ProvisioningStorage`. Neither state reports retry.
- Only when infrastructure is ready does the condition become
  `PROVISIONED=True/InfrastructureReady`.

#### TC-FR4-02: VM surfaces clear retry and failure on success

| Interface Change | Tier | Owner | Priority | Automation |
|-----------------|------|-------|----------|------------|
| IC-2 | Unit | [DEV] VMaaS UI | high | automated |

**Command:** `pnpm test -- VmTable VmDetails` from `osac-ui/`

**Boundary:** React Testing Library with generated types. No browser or
network boundary runs.

**Steps:** 1. Render a retrying instance. → 2. Re-render the same components
with the success response.

**Expected:** The UI consumer reflects no retry reason and an absent latest
failure after job success, even if `Provisioned` remains `False` while
infrastructure is becoming ready. Power-state semantics are preserved. Presentation assertions
follow the separate UX specification.

#### TC-FR4-03: CLI surfaces clear retry and failure on success

| Interface Change | Tier | Owner | Priority | Automation |
|-----------------|------|-------|----------|------------|
| IC-3 | Unit | [DEV] Fulfillment | high | automated |

**Command:** `go test ./internal/cmd/cli/describe/computeinstance ./internal/rendering` from `fulfillment-service/`

**Boundary:** Real CLI renderer and generated types with a stubbed transport.
No deployed API or operator runs.

**Steps:** 1. Render a retrying instance. → 2. Render the success response.

**Expected:** List shows `PROVISIONING` and `LAST FAILURE` as `-`; describe
omits the retry and all failure rows, including a successful-job response
that still has `Provisioned=False/WaitingForVM` or `ProvisioningStorage`.

### FR-5: Existing access-control boundaries

#### TC-FR5-01: Existing tenant authorization remains enforced

| Interface Change | Tier | Owner | Priority | Automation |
|-----------------|------|-------|----------|------------|
| IC-1 | Component integration | [DEV] Fulfillment | critical | automated |

**Command:** `make -C osac-installer test PLATFORM=kind PROFILE=dev NS=osac SUITE=fulfillment`

**Boundary:** Deployed Fulfillment API, PostgreSQL, and identity/authorization
path. No operator, AAP, provider, or UI runs.

##### Steps

1. Store a retrying ComputeInstance in project A.
2. Call public Get and List as an authorized Tenant User from project A.
3. Call public Get and List as a user who has no access to project A.

##### Expected Results

- The authorized caller receives the retry condition and failure field.
- The unauthorized caller receives the existing permission-denied error.
- No cross-tenant response contains the instance, condition, or failure field.

### NFR-1: Supported UI and CLI status surfaces

#### TC-NFR1-01: Deployed CLI status journey is available

| Interface Change | Tier | Owner | Priority | Automation |
|-----------------|------|-------|----------|------------|
| IC-3 | E2E | [QE] VMaaS | high | automated |

**Command:** `uv run pytest -n 0 tests/e2e/vmaas/regression/provisioning/test_compute_instance_retry_status.py`

**Boundary:** Real Fulfillment API and database, operator, AAP, KubeVirt,
and CLI against a deployed environment. The AAP playbook is a controlled
real job that returns a retryable `osac_error` once and succeeds on the next
attempt; it does not prove every provider failure mode.

**Steps:** 1. Create the ComputeInstance. → 2. Observe CLI list and describe
during retry. → 3. Wait for the second attempt to succeed and observe again.

**Expected:** During retry, list and describe show `Retrying` and the safe
failure details; after success, both surfaces show no retry or failure.

#### TC-NFR1-02: Deployed ComputeInstance retry fields converge

| Interface Change | Tier | Owner | Priority | Automation |
|-----------------|------|-------|----------|------------|
| IC-1 | E2E | [QE] VMaaS | high | automated |

**Command:** Proposed case in `tests/e2e/vmaas/regression/provisioning/test_compute_instance_retry_status.py`, run with `uv run pytest -n 0 tests/e2e/vmaas/regression/provisioning/test_compute_instance_retry_status.py`.

**Boundary:** Real Fulfillment API, database, operator, AAP, and KubeVirt.
A controlled real AAP job fails once with a retryable `osac_error` and then
succeeds. No browser or UI boundary is exercised.

**Steps:** Create a ComputeInstance using the fail-once provisioning fixture
and observe its public status through retry and eventual success.

**Expected:** During backoff, the ComputeInstance contains
`PROVISIONED=False` with reason `RetryScheduled`, and a populated
`last_provisioning_failure` with the expected reason, safe message, failed
attempt number, and observation timestamp. While the retry runs, the reason
becomes `RetryRunning` and the previous failure is retained. After success,
no retry reason remains and `last_provisioning_failure` is absent. If the VM
or storage is not ready yet, `PROVISIONED` remains `False` with the existing
progress reason; it becomes `True/InfrastructureReady` only after the
readiness check passes. Power-state semantics are unchanged.

### NFR-2: Retry behavior remains unchanged

#### TC-NFR2-01: Retry engine behavior remains unchanged

| Interface Change | Tier | Owner | Priority | Automation |
|-----------------|------|-------|----------|------------|
| — | Unit | [DEV] VMaaS | critical | automated |

**Command:** `make -C osac-operator test`

**Boundary:** Real engine and existing retry tests with the in-memory AAP
double. No Kubernetes API, Fulfillment service, or deployed provider runs.

**Steps:** 1. Run the existing retry classification, backoff, and attempt
tests after the status change.

**Expected:** `NetworkJobStatus.State` remains `Retrying`, the attempt count
and backoff intervals match the existing values, and the operational
`NetworkJobStatus.Message` format is unchanged.

## Gaps

### Requirement Coverage Gaps

All PRD requirements map to cases, but NFR-1 UI presentation coverage is
provisional until the separate UX specification is available. API assertions
do not prove the deployed UI journey.

### Interface Change Coverage Gaps

All interface changes map to planned cases. IC-2 UI cases specify the data
behavior only; their concrete presentation assertions require the separate
UX specification.

### Execution and Ownership Gaps

- No case is implemented or executed in this design-only phase. The owning
  [DEV] and [QE] stories must add and run them.
- IC-2 UI cases and browser coverage belong to the separate UI development
  path, which owns its UX specification, API type baseline, and generated
  types. No API case is claimed as browser coverage. A dedicated UI tracking
  issue has not been identified; cross-workflow tracking remains unresolved.
- CLI implementation and both deployed CLI/API cases (TC-NFR1-01 and
  TC-NFR1-02) stay with this design, owned by [QE] VMaaS for deployed journeys;
  they are not consolidated into [OSAC-6578](https://redhat.atlassian.net/browse/OSAC-6578).

## Summary

| Metric | Count |
|--------|-------|
| Total test cases | 15 |
| Critical | 7 |
| High | 8 |
| Medium | 0 |
| Low | 0 |
| Automated | 15 |
| Manual | 0 |
| Requirements with test cases | 7 / 7 |
| Interface changes with test cases | 3 / 3 |
