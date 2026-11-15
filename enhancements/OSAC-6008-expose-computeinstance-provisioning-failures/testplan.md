# Testplan — OSAC-6011

## Overview

- **Feature:** OSAC-6008 — Expose ComputeInstance provisioning failures during retries
- **Total test cases:** 15
- **Requirements covered:** 7 of 7
- **Interface changes covered:** 3 of 3

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
| TC-NFR1-02 | Deployed UI status journey is available | IC-2 | high |
| TC-NFR2-01 | Retry engine behavior remains unchanged | — | critical |

## Test Cases

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
retryable failure. → 2. Poll public Get until the engine records `Retrying`.

**Expected:** The response keeps the existing power state, contains
`PROVISIONED=False` with reason `ProvisioningRetry`, contains
`PROVISIONING_RETRY=True` with reason `RetryScheduled`, and contains the
latest failure reason, message, attempt, and observation timestamp.

#### TC-FR1-02: VM list and details show retrying

| Interface Change | Tier | Owner | Priority | Automation |
|-----------------|------|-------|----------|------------|
| IC-2 | Unit | [DEV] VMaaS UI | high | automated |

**Command:** `pnpm test -- VmTable VmDetails` from `osac-ui/`

**Boundary:** React Testing Library with generated types and rendered
components. No browser, network, operator, or API server runs.

**Steps:** 1. Render the VM list with a retrying instance. → 2. Open the
details view for the same object.

**Expected:** The list Status cell shows the existing power-state label plus a
secondary `Retrying` label, and the details header and Overview section show
the same retry indicator.

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

##### Expected Results

- `last_provisioning_failure.attempt` is `2`.
- The message is `quota exhausted`.
- No failure array or prior attempt 1 value exists.
- `PROVISIONING_RETRY` remains `True`.

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
| Valid `osac_error` | `ProviderReported` | Exact parsed `osac_error.message` |
| Successful job with malformed or unexpected `osac_result` | `ResultRejected` | `OSAC could not accept the provisioning result.` |
| Failed job with missing or malformed `osac_error` | `InvalidResult` | `The provisioning provider returned an invalid or incomplete result.` |
| Timeout | `TimedOut` | `The provisioning attempt timed out.` |
| Lost job | `JobLost` | `The provisioning job was lost before its result could be read.` |
| Job not started | `JobNotStarted` | `The provisioning job did not start.` |
| AAP infrastructure error | `ProviderError` | `The provisioning provider reported an infrastructure error.` |

No produced message contains an AAP job ID, task name, manager name, log,
traceback, or next-retry timestamp.

#### TC-FR3-02: VM details show actionable failure data

| Interface Change | Tier | Owner | Priority | Automation |
|-----------------|------|-------|----------|------------|
| IC-2 | Unit | [DEV] VMaaS UI | high | automated |

**Command:** `pnpm test -- VmTable VmDetails` from `osac-ui/`

**Boundary:** React Testing Library with generated types. No browser or
network boundary runs.

**Steps:** 1. Render VM details with a failure value. → 2. Read the
Provisioning row and list tooltip.

**Expected:** Both surfaces show the localized reason label, exact safe
message, `Attempt 2`, and the formatted observation timestamp.

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
- The controller sets `ProvisioningRetry=False` with reason
  `RetryNotScheduled`.
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

**Steps:** 1. Fail the first provision attempt retryably. → 2. Let the retry
attempt succeed. → 3. Poll public Get until provisioning completes.

**Expected:** `PROVISIONED=True`, `PROVISIONING_RETRY=False` with reason
`AsExpected`, and `last_provisioning_failure` is absent rather than an empty
message.

#### TC-FR4-02: VM surfaces clear retry and failure on success

| Interface Change | Tier | Owner | Priority | Automation |
|-----------------|------|-------|----------|------------|
| IC-2 | Unit | [DEV] VMaaS UI | high | automated |

**Command:** `pnpm test -- VmTable VmDetails` from `osac-ui/`

**Boundary:** React Testing Library with generated types. No browser or
network boundary runs.

**Steps:** 1. Render a retrying instance. → 2. Re-render the same components
with the success response.

**Expected:** The secondary `Retrying` label, failure tooltip, and
Provisioning failure rows are absent; the existing power-state label remains.

#### TC-FR4-03: CLI surfaces clear retry and failure on success

| Interface Change | Tier | Owner | Priority | Automation |
|-----------------|------|-------|----------|------------|
| IC-3 | Unit | [DEV] Fulfillment | high | automated |

**Command:** `go test ./internal/cmd/cli/describe/computeinstance ./internal/rendering` from `fulfillment-service/`

**Boundary:** Real CLI renderer and generated types with a stubbed transport.
No deployed API or operator runs.

**Steps:** 1. Render a retrying instance. → 2. Render the success response.

**Expected:** List shows `PROVISIONING` and `LAST FAILURE` as `-`; describe
omits the retry and all failure rows.

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

#### TC-NFR1-02: Deployed UI status journey is available

| Interface Change | Tier | Owner | Priority | Automation |
|-----------------|------|-------|----------|------------|
| IC-2 | E2E | [QE] VMaaS | high | automated |

**Command:** `OSAC_UI_BASE_URL=<deployed-ui-url> pnpm --filter @osac/playwright run playwright --project=vmaas-provisioning-status`

**Boundary:** Real browser, deployed UI, Fulfillment API, database, operator,
and AAP test job. No CLI boundary runs.

**Steps:** 1. Open the VM list during retry. → 2. Open the instance details. →
3. Wait for success and revisit both views.

**Expected:** The list and details show the secondary `Retrying` indicator and
safe failure details during retry, then omit both after success while the
power-state label remains.

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

All PRD requirements have test cases.

### Interface Change Coverage Gaps

All interface changes are exercised by test cases.

### Execution and Ownership Gaps

- No case is implemented or executed in this design-only phase. The owning
  [DEV] and [QE] stories must add and run them.
- UI cases require explicit authorization to advance the selected API
  baseline and run `pnpm gen-types`.
- Reviewers must confirm whether the two deployed [QE] cases remain in this
  feature or are consolidated with OSAC-6578; if moved, update this plan and
  link the owning Jira issue.

## Summary

| Metric | Count |
|--------|-------|
| Total test cases | 15 |
| Critical | 7 |
| High | 8 |
| Medium | 0 |
| Low | 0 |
| Automated | 14 |
| Manual | 0 |
| Requirements with test cases | 7 / 7 |
| Interface changes with test cases | 3 / 3 |
