# Test Plan — OSAC-985 Metering and usage tracking

## Overview

- **Design:** [Design](design.md)
- **PRD:** [Requirements](prd.md)
- **Total test cases:** 11

Execution entries identify source assertions on OSAC main. Gap entries describe unresolved tests for
the named work owner. No individual assignee or follow-up ticket is recorded here.

The historical design’s projection and reconciliation scenarios use current Fold, Round and
heartbeat evidence where their observable results match. The deployed restart and source-history
comparison remains unresolved in TC-EL-06. See [Event-log driven
metering](../OSAC-5753-event-log-driven-metering/testplan.md) and [Metering event
contract](../OSAC-6056-metering-event-contract/testplan.md) for shared recovery and replay
boundaries.

## Deployed VMaaS

#### TC-MU-01: A running VM produces typed compute heartbeats

| Priority | Automation |
|---|---|
| critical | automated |

- **Tier:** E2E
- **Owner:** [QE]
- **References:** [PRD — VMaaS acceptance criteria](prd.md#vmaas) and [Design — VM state
  machine](design.md#vmaas-state-machine)
- **Dependencies:** Real deployed fulfillment, hub controllers, Kafka and metering. The Echo adapter
  provides the test readback for published records.
- **Execution:** `tests/e2e/vmaas/sanity/test_metering_billing.py`
- **Evidence:** `test_metering_heartbeat_envelope` ([source](https://github.com/osac-project/osac/blob/2a69f3d27c2341da4dd4fe8965bc7cfadcf90d69/tests/e2e/vmaas/sanity/test_metering_billing.py)).
- **Selector:** `uv run pytest -n 0 tests/e2e/vmaas/sanity/test_metering_billing.py::test_metering_heartbeat_envelope` from `repository root` in osac. Not run for this backfill.

**Preconditions.** Use a metering-enabled VMaaS hub, its default instance type, ready template and a
dedicated test project.

1. Create a VM in the project and wait for RUNNING.
2. Wait up to 180 seconds for a heartbeat with the running type.
3. Check the envelope and wait for a second typed heartbeat.

**Expected results.** At least two typed records arrive. The checked record has the published v1 envelope,
the fixture instance type and project, meter `compute`, unit `second` and positive quantity.

#### TC-MU-02: Stopping a VM ends net compute billing

| Priority | Automation |
|---|---|
| critical | automated |

- **Tier:** E2E
- **Owner:** [QE]
- **References:** [PRD — VMaaS acceptance criteria](prd.md#vmaas) and [Design — VM state
  machine](design.md#vmaas-state-machine)
- **Dependencies:** Real deployed fulfillment, hub controllers, Kafka and metering. The Echo adapter
  provides the test readback for published records.
- **Execution:** `tests/e2e/vmaas/sanity/test_metering_billing.py`
- **Evidence:** `test_metering_stop_ends_billing` ([source](https://github.com/osac-project/osac/blob/2a69f3d27c2341da4dd4fe8965bc7cfadcf90d69/tests/e2e/vmaas/sanity/test_metering_billing.py)).
- **Selector:** `uv run pytest -n 0 tests/e2e/vmaas/sanity/test_metering_billing.py::test_metering_stop_ends_billing` from `repository root` in osac. Not run for this backfill.

**Preconditions.** Provision a RUNNING VM with a typed compute heartbeat in a dedicated test project.

1. Request HALTED and wait for fulfillment to report STOPPED. Capture its state transition time.
2. Allow 90 seconds for the stop to reach metering, then collect final and correcting heartbeats.
3. Observe for another 90 seconds beyond the last interval.

**Expected results.** Net usage beyond the STOPPED stamp is at most one second per dimension in absolute
value. During the 90-second window, absolute net usage beyond the final interval stays at or
below 0.000001 seconds per dimension set.

#### TC-MU-03: Resize and restart split usage by the running instance type

| Priority | Automation |
|---|---|
| critical | automated |

- **Tier:** E2E
- **Owner:** [QE]
- **References:** [PRD — VMaaS acceptance criteria](prd.md#vmaas) and [Design — Billing
  dimensions](design.md#billing-dimensions)
- **Dependencies:** Real deployed fulfillment, hub controllers, Kafka and metering. The Echo adapter
  provides the test readback for published records.
- **Execution:** `tests/e2e/vmaas/sanity/test_metering_billing.py`
- **Evidence:** `test_metering_resize_splits_dimensions` ([source](https://github.com/osac-project/osac/blob/2a69f3d27c2341da4dd4fe8965bc7cfadcf90d69/tests/e2e/vmaas/sanity/test_metering_billing.py)).
- **Selector:** `uv run pytest -n 0 tests/e2e/vmaas/sanity/test_metering_billing.py::test_metering_resize_splits_dimensions` from `repository root` in osac. Not run for this backfill.

**Preconditions.** Run a VM on the default type in the test project. Create a distinct 4-vCPU, 8-GiB
type for the resize and capture initial typed usage.

1. Update the VM’s requested type, observe RestartRequired and restart it.
2. Wait for the VM to return to RUNNING on the new type.
3. Group signed heartbeats for the VM by old and new running type and compare net intervals.

**Expected results.** Both series exist, intervals within each series are contiguous, and the series do not
overlap. The gap fits within the observed restart window. After 90 seconds the old type still has no
net billing past the new start.

#### TC-MU-04: Deleting a VM closes its net compute billing

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** E2E
- **Owner:** [QE]
- **References:** [PRD — VMaaS acceptance criteria](prd.md#vmaas) and [Design — VM
  deletion](design.md#test-plan)
- **Dependencies:** Real deployed fulfillment, hub controllers, Kafka and metering. The Echo adapter
  provides the test readback for published records.
- **Execution:** `tests/e2e/vmaas/sanity/test_metering_billing.py`
- **Evidence:** `test_metering_delete_ends_billing` ([source](https://github.com/osac-project/osac/blob/2a69f3d27c2341da4dd4fe8965bc7cfadcf90d69/tests/e2e/vmaas/sanity/test_metering_billing.py)).
- **Selector:** `uv run pytest -n 0 tests/e2e/vmaas/sanity/test_metering_billing.py::test_metering_delete_ends_billing` from `repository root` in osac. Not run for this backfill.

**Preconditions.** Use a RUNNING VM with a typed heartbeat and a known hub ComputeInstance CR.

1. Delete the VM and capture the recorded deletion time.
2. Collect final and correcting heartbeats and compute net intervals.
3. Observe another 120 seconds beyond the final interval.

**Expected results.** Net intervals are contiguous and bill one second per second. The last reaches the
observed deletion within the one-second stamp tolerance, net usage past the stamp has absolute value
at most one second per dimension. During the 120-second observation, absolute net usage beyond
the final interval stays at or below 0.000001 seconds per dimension set.

## History recovery and contract evolution

#### TC-MU-05: Current Round catch-up restores the same ledger after an injected crash

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Component integration
- **Owner:** [DEV]
- **References:** [Design — Restart recovery](design.md#high-availability-and-restart-recovery) and
  [Design — Restart](design.md#test-plan)
- **Dependencies:** Real Kafka and PostgreSQL test containers and the metering service components
  under test. The harness supplies fulfillment snapshots and omits the fulfillment server and
  billing provider. The crash is injected and the test holds the Fold behind catch-up to isolate
  ledger reconstruction.
- **Execution:** `osac-metering/metering-service/internal/round/round_test.go`
- **Evidence:** `TestCrashMidCatchUpRestoreReplaysSameLedger` ([source](https://github.com/osac-project/osac/blob/2a69f3d27c2341da4dd4fe8965bc7cfadcf90d69/osac-metering/metering-service/internal/round/round_test.go)).
- **Selector:** `go test ./internal/round -run '^(TestCrashMidCatchUpRestoreReplaysSameLedger)$'` from `osac-metering/metering-service` in osac. Not run for this backfill.

**Preconditions.** Use a RUNNING VM with a small-to-large resize at +2m30s. Take a database backup
after the first round and publish three later round groups.

1. Restore the backup and inject a catch-up crash after applying two groups.
2. Replay from the backup again and compare the ledger and progress with uninterrupted catch-up.

**Expected results.** Replayed ledger rows, heartbeat offset and last round time equal the uninterrupted
result. The interrupted intermediate ledger differs.

#### TC-MU-06: Schema loader accepts an optional added field and refuses a removed field

| Priority | Automation |
|---|---|
| medium | automated |

- **Tier:** Unit
- **Owner:** [DEV]
- **References:** [Design — Schema versioning](design.md#schema-versioning) and [PRD — Cross-cutting
  criteria](prd.md#cross-cutting)
- **Dependencies:** In-process fixtures only; no database, broker, deployment, or billing provider.
- **Execution:** `osac-metering/schema/versions_internal_test.go`
- **Evidence:** `TestLoadVersionsAcceptsAVersionThatOnlyAddsAField + TestLoadVersionsRejectsAVersionThatDropsAField` ([source](https://github.com/osac-project/osac/blob/2a69f3d27c2341da4dd4fe8965bc7cfadcf90d69/osac-metering/schema/versions_internal_test.go)).
- **Selector:** `go test . -run '^(TestLoadVersionsAcceptsAVersionThatOnlyAddsAField|TestLoadVersionsRejectsAVersionThatDropsAField)$'` from `osac-metering/schema` in osac. Not run for this backfill.

**Preconditions.** Use the shipped v1 and a synthetic compatible v2 in an in-memory filesystem.

1. Load both versions with optional `provider_region` added to v2.
2. Reload a separate v2 fixture that drops v1’s `rules_revision`.

**Expected results.** The compatible pair loads both versions. The dropped-field fixture reports that
`rules_revision` was dropped.

#### TC-MU-07: A pinned historical reader still reads retained records after upgrade

| Priority | Automation |
|---|---|
| medium | automated |

- **Tier:** Contract
- **Owner:** [DEV]
- **References:** [Design — Schema versioning](design.md#schema-versioning) and [PRD — Cross-cutting
  criteria](prd.md#cross-cutting)
- **Dependencies:** Use real version-pinned schema validation and reader builds plus a retained
  synthetic record. No broker or provider is needed.
- **Gap:** The loader and release guard check add-only schema evolution and file immutability. An
  independent historical-reader readback across a release upgrade is unresolved.

**Preconditions.** Pin an independent reader to a released v1 contract and save its output for a
retained v1 compute heartbeat with quantity 60 seconds. Use the first additive producer version as
the upgrade fixture.

1. Read the original archived record with the pinned reader before and after the upgrade.
2. Use the new reader to decode the same archived record with its declared v1 schema and compare the
   two results.

**Expected results.** Both readers return the same v1 resource, meter, interval and 60-second quantity. The
historical reader’s output stays byte-identical across the upgrade.

## CaaS and MaaS

#### TC-MU-08: Fold and Round meter a cluster and its worker under the READY gate

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Component integration
- **Owner:** [DEV]
- **References:** [PRD — CaaS acceptance criteria](prd.md#caas) and [Design — CaaS state
  machine](design.md#caas-state-machine)
- **Dependencies:** Real Kafka and PostgreSQL test containers and the metering service components
  under test. The harness supplies fulfillment snapshots and omits the fulfillment server and
  billing provider. Relay publishes to the fixture Kafka topic.
- **Execution:** `osac-metering/metering-service/internal/pipeline/pipeline_test.go`
- **Evidence:** `TestClusterWorkersBillUnderTheRootGate` ([source](https://github.com/osac-project/osac/blob/2a69f3d27c2341da4dd4fe8965bc7cfadcf90d69/osac-metering/metering-service/internal/pipeline/pipeline_test.go)).
- **Selector:** `go test ./internal/pipeline -run '^(TestClusterWorkersBillUnderTheRootGate)$'` from `osac-metering/metering-service` in osac. Not run for this backfill.

**Preconditions.** Use cluster `cluster-1`, template `openshift-4-19`, version `4.19.0`, and
`bmi-1`, a medium worker in node set `workers`.

1. Publish cluster PROGRESSING and worker STARTING snapshots at 10:00Z. Run the 10:01 Round and
   drain the outbox.
2. Publish cluster READY effective 10:00:30Z and run the 10:02 Round.

**Expected results.** No heartbeat is emitted during install. After READY, separate control-plane and
worker-allocation heartbeats each bill 120 seconds and carry their fixture dimensions, with the
worker linked to `cluster-1` and node set `workers`.

#### TC-MU-09: A deployed CaaS resize and delete are visible in cluster and worker usage

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** E2E
- **Owner:** [QE]
- **References:** [PRD — CaaS acceptance criteria](prd.md#caas) and [Design — CaaS
  lifecycle](design.md#test-plan)
- **Dependencies:** Real deployed fulfillment, hub controllers, Kafka and metering. The Echo adapter
  provides the test readback for published records. Real CaaS orchestration and the configured host
  provider are required.
- **Gap:** The Kafka/PostgreSQL fixture covers the READY gate and worker dimensions. A deployed CaaS
  lifecycle including scale and final usage readback is unresolved.

**Preconditions.** Use a deployed CaaS hub with metering and one node set on a provisionable
hardware class.

1. Provision a cluster with one worker, wait for READY and read control-plane and worker usage.
2. Scale the node set to two workers, wait for the change to settle, then delete the cluster and
   read the final intervals.

**Expected results.** The two meter families are separately visible and attributable to the same cluster.
The extra worker contributes only after its allocation and net usage stops at the recorded deletion
boundary.

#### TC-MU-10: MaaS ingest resolves the tenant and publishes enriched usage before committing

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Component integration
- **Owner:** [DEV]
- **References:** [PRD — MaaS acceptance criteria](prd.md#maas) and [Design — MaaS
  ingest](design.md#integration-tests)
- **Dependencies:** Requires real source and enriched Kafka topics and the MaaS consumer. Use
  controlled tenant lookup data and inject only the publish failure. No external billing provider.
- **Gap:** Adapter translation starts with already enriched tenant data. Raw ingestion, tenant
  resolution, and commit-after-publish remain unresolved.

**Preconditions.** Provision a synthetic organization `org-1` mapped to tenant `acme` and an input
record for model `granite-8b` with 100 input and 20 output tokens.

1. Produce the inference usage event with `organization_id=org-1` to the raw input.
2. Read from the enriched topic and check source progress after publication.
3. Repeat with one controlled publish failure before success.

**Expected results.** The enriched event names `acme` and the selected model with the source token counts.
The source offset commits after successful publication and stays uncommitted on the failed attempt.

#### TC-MU-11: MaaS ingest permanently rejects a missing or unresolvable organization

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Component integration
- **Owner:** [DEV]
- **References:** [PRD — MaaS acceptance criteria](prd.md#maas) and [Design — MaaS consumer
  validation](design.md#unit-tests)
- **Dependencies:** Requires real Kafka and the MaaS consumer with controlled tenant lookup data. No
  external provider.
- **Gap:** The adapter’s inference-rejection and DLQ tests operate on enriched events. No equivalent
  raw organization-resolution rejection test was identified.

**Preconditions.** Map `org-1` to `acme`. Prepare two otherwise valid usage records, one without
organization ID and one with unmapped `org-unknown`.

1. Consume the two records and capture rejection outcomes.
2. Inspect the enriched topic for both IDs and verify neither is retried as a transient lookup failure.

**Expected results.** Both invalid inputs produce permanent rejection with zero enriched usage records and
no attribution to a default tenant.
