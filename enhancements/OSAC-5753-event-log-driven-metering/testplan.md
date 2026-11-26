# Test Plan — OSAC-5753 Event-log driven metering

## Overview

- **Design:** [Design](design.md)
- **PRD:** [Requirements](prd.md)
- **Total test cases:** 8

Execution entries identify source assertions on OSAC main. Gap entries describe unresolved tests for
the named work owner. No individual assignee or follow-up ticket is recorded here.

## Fold, rounds and recovery

#### TC-EL-01: Fold writes the design example history

| Priority | Automation |
|---|---|
| critical | automated |

- **Tier:** Component integration
- **Owner:** [DEV]
- **References:** [Design — Fold and history](design.md#the-fold) and [Design — IC-1, IC-2 and
  IC-5](design.md#interface-changes)
- **Dependencies:** Real Kafka and PostgreSQL test containers and the metering service components
  under test. The harness supplies fulfillment snapshots and omits the fulfillment server and
  billing provider.
- **Execution:** `osac-metering/metering-service/internal/fold/fold_test.go`
- **Evidence:** `TestFoldWritesTheDesignExampleHistory` ([source](https://github.com/osac-project/osac/blob/2a69f3d27c2341da4dd4fe8965bc7cfadcf90d69/osac-metering/metering-service/internal/fold/fold_test.go)).
- **Selector:** `go test ./internal/fold -run '^(TestFoldWritesTheDesignExampleHistory)$'` from `osac-metering/metering-service` in osac. Not run for this backfill.

**Preconditions.** Use the recorded fixture at 10:00 UTC with VM `vm-7`, Volume `vol-1`, ExternalIP
`ip-1` and one untracked event.

1. Publish the eight snapshots to the tenant topic, and wait for Fold to reach the final offset.
2. Read and compare all stored fact rows to the fixture timeline.

**Expected results.** History records the VM as RUNNING at +40 seconds, resized to large at +30 minutes and
STOPPED at +60 minutes. It also records Volume AVAILABLE at +2 minutes and the allocated IP facts.
The untracked resource adds no resource history.

#### TC-EL-02: A late Fold resize makes the next Round publish exact signed corrections

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Component integration
- **Owner:** [DEV]
- **References:** [Design — Fold and history](design.md#the-fold) and [Design — Heartbeat
  rounds](design.md#heartbeat-rounds)
- **Dependencies:** Real Kafka and PostgreSQL test containers and the metering service components
  under test. The harness supplies fulfillment snapshots and omits the fulfillment server and
  billing provider. Relay publishes through the fixture Kafka broker.
- **Execution:** `osac-metering/metering-service/internal/round/round_test.go`
- **Evidence:** `TestLateResizeSendsPositiveAndNegativeCorrections` ([source](https://github.com/osac-project/osac/blob/2a69f3d27c2341da4dd4fe8965bc7cfadcf90d69/osac-metering/metering-service/internal/round/round_test.go)).
- **Selector:** `go test ./internal/round -run '^(TestLateResizeSendsPositiveAndNegativeCorrections)$'` from `osac-metering/metering-service` in osac. Not run for this backfill.

**Preconditions.** Use a RUNNING VM of type small from 10:00Z. Run the first three one-minute rounds
and relay their heartbeats.

1. Publish a large-type update received at 10:03:10Z with effective time 10:02:30Z.
2. Fold through the update, run the 10:04 Round and drain the outbox.
3. Read the topic’s signed interval list.

**Expected results.** The topic has the three original 60-second records plus +90 seconds from 10:02:30 to
10:04 and −30 seconds from 10:02:30 to 10:03. The five signed quantities sum to 240 seconds.

#### TC-EL-04: Rebuilding across a crash counts a resent heartbeat once

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Component integration
- **Owner:** [DEV]
- **References:** [Design — Recovery](design.md#recovery) and [Design — Determinism and
  recovery](design.md#test-plan)
- **Dependencies:** Real Kafka and PostgreSQL test containers and the metering service components
  under test. The harness supplies fulfillment snapshots and omits the fulfillment server and
  billing provider. The crash is injected and earlier topic records are delivered by the fixture.
  The total is from the metering topic.
- **Execution:** `osac-metering/metering-service/internal/round/round_test.go`
- **Evidence:** `TestRebuildCountsAResentCopyOnceAcrossACrash` ([source](https://github.com/osac-project/osac/blob/2a69f3d27c2341da4dd4fe8965bc7cfadcf90d69/osac-metering/metering-service/internal/round/round_test.go)).
- **Selector:** `go test ./internal/round -run '^(TestRebuildCountsAResentCopyOnceAcrossACrash)$'` from `osac-metering/metering-service` in osac. Not run for this backfill.

**Preconditions.** Use a RUNNING VM from 10:00Z and a PostgreSQL backup before the first round.
Prepare the first two one-minute heartbeat rows.

1. Write heartbeat rows in order first, second, first again.
2. Restore the backup, inject a catch-up crash after two groups, then resume and let the third round
   publish.

**Expected results.** The crash returns the expected simulated-crash error. The resumed pipeline’s topic
total is 180,000,000 micros when counted by unique heartbeat ID.

#### TC-EL-07: Fold replay preserves resource facts across restarts, repeats and shuffles

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Component integration
- **Owner:** [DEV]
- **References:** [Design — Fold and history](design.md#the-fold) and [Design — Determinism and
  idempotency](design.md#test-plan)
- **Dependencies:** Real Kafka and PostgreSQL test containers and the metering service components
  under test. The harness supplies fulfillment snapshots and omits the fulfillment server and
  billing provider.
- **Execution:** `osac-metering/metering-service/internal/fold/fold_test.go`
- **Evidence:** `TestFoldIsDeterministic` ([source](https://github.com/osac-project/osac/blob/2a69f3d27c2341da4dd4fe8965bc7cfadcf90d69/osac-metering/metering-service/internal/fold/fold_test.go)).
- **Selector:** `go test ./internal/fold -run '^(TestFoldIsDeterministic)$'` from `osac-metering/metering-service` in osac. Not run for this backfill.

**Preconditions.** Use the recorded example log and a clean tenant/store for each variant.

1. Fold the original log in one pass.
2. Fold the same input with restart injection, with every event repeated, and with deterministic
   shuffling.
3. Compare sorted resource history for each variant against the baseline.

**Expected results.** Each variant yields the same resource rows as the single pass. Tenant billing-identity
rows are outside this comparison because log order affects their timestamp.

## Published events and consumer boundary

#### TC-EL-03: The deployed pipeline publishes a positive typed VM heartbeat

| Priority | Automation |
|---|---|
| critical | automated |

- **Tier:** E2E
- **Owner:** [QE]
- **References:** [Design — Published heartbeats](design.md#heartbeats) and [Design —
  IC-3](design.md#interface-changes)
- **Dependencies:** Real deployed fulfillment, hub controllers, Kafka and metering. The Echo adapter
  provides the test readback for published records.
- **Execution:** `tests/e2e/vmaas/sanity/test_metering_billing.py`
- **Evidence:** `test_metering_heartbeat_envelope` ([source](https://github.com/osac-project/osac/blob/2a69f3d27c2341da4dd4fe8965bc7cfadcf90d69/tests/e2e/vmaas/sanity/test_metering_billing.py)).
- **Selector:** `uv run pytest -n 0 tests/e2e/vmaas/sanity/test_metering_billing.py::test_metering_heartbeat_envelope` from `repository root` in osac. Not run for this backfill.

**Preconditions.** Use a deployed metering-enabled VMaaS hub, its default instance type and a
dedicated project.

1. Create a VM, wait for RUNNING, then collect a heartbeat with the running type within 180 seconds.
2. Verify the envelope and wait for a second typed heartbeat.

**Expected results.** The heartbeat is a valid v1 envelope with meter `compute`, unit `second`, the fixture
type and project, and positive quantity. A second typed event arrives.

#### TC-EL-05: The heartbeat producer emits a conformance fixture accepted by the schema

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Contract
- **Owner:** [DEV]
- **References:** [Design — Heartbeat payload](design.md#heartbeats) and [Design —
  IC-3](design.md#interface-changes)
- **Dependencies:** In-process fixtures only; no database, broker, deployment, or billing provider.
  The producer and JSON Schema compiler are real.
- **Execution:** `osac-metering/metering-service/tools/contract/contract_test.go`
- **Evidence:** `TestContract / accepts a real heartbeat and refuses a version it has not published` ([source](https://github.com/osac-project/osac/blob/2a69f3d27c2341da4dd4fe8965bc7cfadcf90d69/osac-metering/metering-service/tools/contract/contract_test.go)).
- **Selector:** `go test ./tools/contract -run '^(TestContract)$' -ginkgo.focus='accepts a real heartbeat and refuses a version it has not published'` from `osac-metering/metering-service` in osac. Not run for this backfill.

**Preconditions.** Build the contract suite’s `cluster-1` control-plane heartbeat in tenant `acme`,
ending at 10:00Z, with 60 seconds of quantity.

1. Compile the generated published schema and validate the serialized heartbeat.
2. Compare the schema envelope attributes with the emitted attributes.

**Expected results.** Validation succeeds and the attribute names match the published version exactly.

#### TC-EL-06: The deployed heartbeat sum reconciles against full source history after restart

| Priority | Automation |
|---|---|
| critical | automated |

- **Tier:** E2E
- **Owner:** [QE]
- **References:** [Design — Recovery](design.md#recovery) and [Design — Full-log reconciliation and
  chaos](design.md#test-plan)
- **Dependencies:** Real deployed fulfillment, hub controllers, Kafka and metering. The Echo adapter
  provides the test readback for published records. Restart the actual metering pod and read both
  Kafka topics.
- **Gap:** The deployed envelope test asserts a positive typed heartbeat. Component rebuild tests
  assert fixture recovery. Deployed source-history reconciliation through restart remains
  unresolved.

**Preconditions.** Use a dedicated metering-enabled hub, a test tenant and the ability to export its
source log and heartbeat topic. Pick one VM with a known start, resize and stop across the restart
window.

1. Record initial offsets and restart metering during the VM sequence.
2. After catch-up, compute expected usage independently from the full source log and rules.
3. Sum the published quantities by dimensions and compare logical heartbeat IDs across restart.

**Expected results.** For every metered dimension tuple the topic total equals the full-log result,
including final partial intervals and signed corrections. Each logical heartbeat ID contributes
once.

#### TC-EL-08: A replayed DLQ heartbeat appears once in provider usage

| Priority | Automation |
|---|---|
| critical | automated |

- **Tier:** E2E
- **Owner:** [QE]
- **References:** [Design — Provider delivery](design.md#delivery-to-the-billing-provider) and
  [Design — DLQ replay and graduation](design.md#test-plan)
- **Dependencies:** Requires deployed Kafka, metering, real adapter and the real test billing
  provider with usage readback. The rejection is a controlled test condition for the synthetic
  record.
- **Gap:** Adapter tests exercise delivery decisions using doubles and the real-provider contract
  asserts synchronous submission. Deployed DLQ replay plus durable provider readback is unresolved.

**Preconditions.** Use a deployed test tenant, real adapter, provider test tenant with durable
readback, and a unique 60-second heartbeat ID.

1. Force a supported transient provider rejection or outage until the heartbeat is recorded in the
   tenant DLQ.
2. Restore delivery and replay the record with its original ID. Repeat the replay after an adapter
   restart.
3. Compare DLQ evidence, input IDs and provider usage readback.

**Expected results.** The DLQ contains the original ID and replay reaches the provider. After recovery
readback holds one logical record with 60 seconds for that ID, with no duplicated charge after the
second replay.
