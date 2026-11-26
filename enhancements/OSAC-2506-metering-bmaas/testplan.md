# Test Plan — OSAC-2506 Metering for BMaaS

## Overview

- **Design:** [Design](design.md)
- **PRD:** [Requirements](prd.md)
- **Total test cases:** 9

Execution entries identify source assertions on OSAC main. Gap entries describe unresolved tests for
the named work owner. No individual assignee or follow-up ticket is recorded here.

## Allocation and consumption

#### TC-M-01: A running bare-metal instance bills allocation and consumption

| Priority | Automation |
|---|---|
| critical | automated |

- **Tier:** E2E
- **Owner:** [QE]
- **References:** [PRD — BMaaS acceptance criteria](prd.md#7-acceptance-criteria)
- **Dependencies:** Real deployed fulfillment, hub controllers, Kafka and metering. The Echo adapter
  provides the test readback for published records. Real BMaaS provisioning is required.
- **Execution:** `tests/e2e/bmaas/sanity/test_baremetal_metering.py`
- **Evidence:** `test_baremetal_instance_bills_allocation_and_consumption` ([source](https://github.com/osac-project/osac/blob/2a69f3d27c2341da4dd4fe8965bc7cfadcf90d69/tests/e2e/bmaas/sanity/test_baremetal_metering.py)).
- **Selector:** `uv run pytest -n 0 tests/e2e/bmaas/sanity/test_baremetal_metering.py::test_baremetal_instance_bills_allocation_and_consumption` from `repository root` in osac. Not run for this backfill.

**Preconditions.** An onboarded BMaaS test tenant has a catalog item, disk image, SSH key secret and
known fixture instance type. Create in the default project.

1. Create a BareMetalInstance and wait for RUNNING.
2. Poll for the first and then a second typed heartbeat for each meter, allowing up to 600 seconds
   per wait.

**Expected results.** Both meters report unit `second` and the fixture instance type. The typed heartbeat intervals
for each meter are contiguous with quantity equal to elapsed seconds. The allocation start is no
later than the consumption start.

#### TC-M-02: BMI deletion closes both meters in the deployed journey

| Priority | Automation |
|---|---|
| critical | automated |

- **Tier:** E2E
- **Owner:** [QE]
- **References:** [Design — E2E deletion](design.md#test-plan) and [PRD — BMaaS acceptance
  criteria](prd.md#7-acceptance-criteria)
- **Dependencies:** Real deployed fulfillment, hub controllers, Kafka and metering. The Echo adapter
  provides the test readback for published records. Real BMaaS provisioning is required.
- **Execution:** `tests/e2e/bmaas/sanity/test_baremetal_metering.py`
- **Evidence:** `test_baremetal_instance_bills_allocation_and_consumption` ([source](https://github.com/osac-project/osac/blob/2a69f3d27c2341da4dd4fe8965bc7cfadcf90d69/tests/e2e/bmaas/sanity/test_baremetal_metering.py)).
- **Selector:** `uv run pytest -n 0 tests/e2e/bmaas/sanity/test_baremetal_metering.py::test_baremetal_instance_bills_allocation_and_consumption` from `repository root` in osac. Not run for this backfill.

**Preconditions.** A deployed RUNNING BareMetalInstance has typed allocation and consumption
heartbeats and a resolved hub CR.

1. Delete the instance and capture the recorded deletion time from its CR.
2. Wait for final partial pieces, then recompute net typed intervals for both meters and watch the
   topic for another 180 seconds.

**Expected results.** Each meter bills one second per second in contiguous net intervals through at least
the observed deletion time minus one second. For 180 seconds, absolute net usage past the
final interval stays at or below 0.000001 seconds per dimension set.

#### TC-M-03: A built BMaaS heartbeat conforms to the published schema

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Contract
- **Owner:** [DEV]
- **References:** [Design — BMaaS pipeline contract](design.md#bmaas-pipeline-integration-contract)
- **Dependencies:** In-process fixtures only; no database, broker, deployment, or billing provider.
- **Gap:** The generic producer/schema fixture uses a Cluster. The BMaaS-specific producer-to-schema
  assertion is unresolved.

**Preconditions.** Use a synthetic instance of type `metal-1tb` in tenant `acme` and a 60-second
allocation interval.

1. Build the BMaaS heartbeat with the resource dimension set and encode it.
2. Validate the serialized envelope and payload using the published schema for the emitted version.

**Expected results.** The schema accepts the heartbeat, whose resource, meter, tenant and instance-type
dimension identify this allocation.

#### TC-M-04: The Fold records BMaaS facts from the event log

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Component integration
- **Owner:** [DEV]
- **References:** [Design — BMaaS pipeline contract](design.md#bmaas-pipeline-integration-contract)
- **Dependencies:** Real Kafka and PostgreSQL test containers and the metering service components
  under test. The harness supplies fulfillment snapshots and omits the fulfillment server and
  billing provider.
- **Gap:** The design-history fixture checks VM, Volume and ExternalIP facts. No equivalent Fold
  assertion for BMaaS dimensions was identified.

**Preconditions.** Prepare timestamped BareMetalInstance snapshots for `bmi-1`, tenant `acme`,
project `web`, type `metal-1tb` and catalog item `standard`.

1. Publish PROVISIONING then RUNNING snapshots to the tenant log with times 10:00:00Z and 10:01:00Z.
2. Fold through both Kafka offsets and query the instance history in PostgreSQL.

**Expected results.** The history contains the instance identity, project, catalog and type facts plus the
RUNNING transition at 10:01:00Z.

#### TC-M-05: The heartbeat carries dimensions for both BMaaS meters

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Unit
- **Owner:** [DEV]
- **References:** [Design — BMaaS billing dimensions](design.md#bmaas-billing-dimensions)
- **Dependencies:** In-process fixtures only; no database, broker, deployment, or billing provider.
- **Gap:** The deployed case checks instance type on both meters. A focused builder assertion for
  the full dimension set is unresolved.

**Preconditions.** Use fixed allocation and consumption pieces for `bmi-1`, tenant `acme`, type
`metal-1tb`, catalog `standard`, project `web`.

1. Build and decode a heartbeat for each meter.
2. Compare the meter label and encoded dimension keys and values.

**Expected results.** The two payloads carry their respective meter labels and the same instance type,
catalog, tenant and project values.

#### TC-M-06: The provider bills a retried BMaaS event once

| Priority | Automation |
|---|---|
| medium | automated |

- **Tier:** Contract
- **Owner:** [DEV]
- **References:** [Design — M360 adapter](design.md#m360-adapter) and [PRD — BMaaS acceptance
  criteria](prd.md#7-acceptance-criteria)
- **Dependencies:** Requires the real adapter and M360 test tenant with readback. The heartbeat
  input is synthetic.
- **Gap:** Translation and provider submission evidence do not establish durable per-ID BMaaS
  billing. Provider readback and a replay assertion are unresolved.

**Preconditions.** Use a real test billing tenant with a usage readback mechanism and a unique
synthetic BMaaS allocation heartbeat ID.

1. Send a 60-second allocation record through the adapter.
2. Replay the identical record through a fresh adapter instance and query durable provider usage for
   the ID.

**Expected results.** Provider readback shows one logical record and 60 billed seconds.

## Configuration and ordering

#### TC-M-07: Missing BMaaS instance type fails dimension resolution

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Unit
- **Owner:** [DEV]
- **References:** [Design — BareMetalInstanceType
  resolution](design.md#baremetalinstancetype-resolution) and [Design — configuration
  error](design.md#test-plan)
- **Dependencies:** In-process fixtures only; no database, broker, deployment, or billing provider.
- **Gap:** No equivalent test was identified for the design’s missing-spec-ID failure. Current rule
  evaluation and the older mapper design use different inputs.

**Preconditions.** Start with a RUNNING BMI snapshot and clear `spec.instance_type.id`. Keep its
state time and tenant intact.

1. Resolve billing dimensions for this snapshot.
2. Send the result through the handler with an empty in-memory emission recorder.

**Expected results.** Dimension resolution reports a configuration error. The recorder contains zero
billable events or outbox writes.

#### TC-M-08: Duplicate and stale BMaaS versions leave billing unchanged

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Component integration
- **Owner:** [DEV]
- **References:** [Design — Publication
  idempotency](design.md#projection-and-event-publication-idempotency) and [Design — version
  ordering](design.md#test-plan)
- **Dependencies:** Real Kafka and PostgreSQL test containers and the metering service components
  under test. The harness supplies fulfillment snapshots and omits the fulfillment server and
  billing provider.
- **Gap:** The generic Fold replay test proves fact determinism. The design’s BMI
  fulfillment-version gate and its no-emission result are unresolved in the current event-log
  implementation.

**Preconditions.** Use a BMI history with RUNNING version 12 at 10:01:00Z and an existing allocation
and consumption result.

1. Redeliver version 12.
2. Deliver a stale version 11 STOPPED snapshot with an older transition time, then advance processing.
3. Compare effective history and emitted billing records with the version-12 baseline.

**Expected results.** Current state stays RUNNING and replay adds zero lifecycle or heartbeat records for
either stale or duplicate input.

#### TC-M-09: BMaaS allocation and consumption follow different state intervals

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Unit
- **Owner:** [DEV]
- **References:** [Design — Allocation state
  machine](design.md#bmaas-state-machine--allocation-meter) and [Design — Consumption state
  machine](design.md#bmaas-state-machine--consumption-meter)
- **Dependencies:** In-process fixtures only; no database, broker, deployment, or billing provider.
- **Execution:** `osac-metering/metering-service/internal/usage/engine_test.go`
- **Evidence:** `TestBareMetalAllocationAndConsumption` ([source](https://github.com/osac-project/osac/blob/2a69f3d27c2341da4dd4fe8965bc7cfadcf90d69/osac-metering/metering-service/internal/usage/engine_test.go)).
- **Selector:** `go test ./internal/usage -run '^(TestBareMetalAllocationAndConsumption)$'` from `osac-metering/metering-service` in osac. Not run for this backfill.

**Preconditions.** Use the default rules and fixed history for `bm-1` of instance type `m7a`.

1. Apply STARTING, RUNNING, STOPPED and DELETING at successive minute boundaries after PROVISIONING
   at 10:00Z.
2. Evaluate through 10:05Z and read the two meter pieces.

**Expected results.** Allocation bills 240 seconds from 10:01 to 10:05. Consumption bills 60 seconds from
10:02 to 10:03 and ends at STOPPED.
