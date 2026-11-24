# Test Plan — OSAC-3141 Metering for Block Storage

## Overview

- **Design:** [Design](design.md)
- **PRD:** [Requirements](prd.md)
- **Total test cases:** 10

Execution entries identify source assertions on OSAC main. Gap entries describe unresolved tests for
the named work owner. No individual assignee or follow-up ticket is recorded here.

## Volume usage

#### TC-S-01: An available block Volume bills gibibyte-seconds

| Priority | Automation |
|---|---|
| critical | automated |

- **Tier:** E2E
- **Owner:** [QE]
- **References:** [PRD — Storage usage acceptance criteria](prd.md#acceptance-criteria)
- **Dependencies:** Real deployed fulfillment, hub controllers, Kafka and metering. The Echo adapter
  provides the test readback for published records. The deployed local storage backend provisions
  the Volume.
- **Execution:** `tests/e2e/vmaas/sanity/test_volume_metering.py`
- **Evidence:** `test_volume_bills_gibibyte_seconds` ([source](https://github.com/osac-project/osac/blob/2a69f3d27c2341da4dd4fe8965bc7cfadcf90d69/tests/e2e/vmaas/sanity/test_volume_metering.py)).
- **Selector:** `uv run pytest -n 0 tests/e2e/vmaas/sanity/test_volume_metering.py::test_volume_bills_gibibyte_seconds` from `repository root` in osac. Not run for this backfill.

**Preconditions.** On a metering-enabled VMaaS hub use an onboarded tenant, its test project, a node
with the local storage topology, and storage tier `local`.

1. Create a 5 GiB ReadWriteOnce Volume through the private API and wait for AVAILABLE.
2. Read at least two typed capacity heartbeats for the Volume within 300 seconds.

**Expected results.** The API reports size 5 GiB. Heartbeats carry meter `capacity`, unit `gibibyte_second`,
the project and tier `local`. Quantities equal 5 times interval seconds and consecutive intervals
touch.

#### TC-S-02: Volume deletion closes deployed usage

| Priority | Automation |
|---|---|
| critical | automated |

- **Tier:** E2E
- **Owner:** [QE]
- **References:** [Design — Usage boundaries](design.md#usage-and-correction-contract) and [PRD —
  Deletion acceptance criterion](prd.md#acceptance-criteria)
- **Dependencies:** Real deployed fulfillment, hub controllers, Kafka and metering. The Echo adapter
  provides the test readback for published records. The deployed local storage backend handles
  deletion.
- **Execution:** `tests/e2e/vmaas/sanity/test_volume_metering.py`
- **Evidence:** `test_volume_bills_gibibyte_seconds` ([source](https://github.com/osac-project/osac/blob/2a69f3d27c2341da4dd4fe8965bc7cfadcf90d69/tests/e2e/vmaas/sanity/test_volume_metering.py)).
- **Selector:** `uv run pytest -n 0 tests/e2e/vmaas/sanity/test_volume_metering.py::test_volume_bills_gibibyte_seconds` from `repository root` in osac. Not run for this backfill.

**Preconditions.** Use the AVAILABLE 5 GiB local Volume journey and resolve its hub CR before deletion.

1. Delete the Volume through the private API and record the CR deletion stamp.
2. Wait for final pieces and read net typed intervals, then observe another 120 seconds.

**Expected results.** Net intervals bill 5 GiB per second, form a contiguous span reaching at least the
recorded deletion time minus one second. For 120 seconds, absolute net usage past the final
interval stays at or below 0.000001 GiB-seconds per dimension set.

#### TC-S-03: Correction apply and reverse reach the provider once

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Contract
- **Owner:** [DEV]
- **References:** [Design — Correction adjustments](design.md#usage-and-correction-contract)
- **Dependencies:** Requires Kafka, the real correction consumer and billing test tenant with
  readback. Correction records are synthetic.
- **Gap:** Provider correction apply/reverse and partial-failure replay for Volume adjustments
  remain unresolved.

**Preconditions.** Prepare a synthetic 5 GiB Volume correction over a 10-second slice with one
subtract and one add adjustment, and real provider test readback.

1. Submit the correction, interrupt delivery after the first durable adjustment, then retry.
2. Inspect provider records and the consumer offset.

**Expected results.** Exactly one durable record per adjustment key represents subtract 50 and add 50
GiB-seconds under the same correction ID. The offset advances after both adjustments are durable.

#### TC-S-04: Volume capacity multiplies the provisioned GiB by elapsed seconds

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Unit
- **Owner:** [DEV]
- **References:** [Design — Quantity arithmetic](design.md#usage-and-correction-contract)
- **Dependencies:** In-process fixtures only; no database, broker, deployment, or billing provider.
- **Execution:** `osac-metering/metering-service/internal/usage/engine_test.go`
- **Evidence:** `TestVolumeCapacityMultipliesByProvisionedGib` ([source](https://github.com/osac-project/osac/blob/2a69f3d27c2341da4dd4fe8965bc7cfadcf90d69/osac-metering/metering-service/internal/usage/engine_test.go)).
- **Selector:** `go test ./internal/usage -run '^(TestVolumeCapacityMultipliesByProvisionedGib)$'` from `osac-metering/metering-service` in osac. Not run for this backfill.

**Preconditions.** Use the default rules and a 100 GiB BLOCK Volume tagged `gold` with vendor ID
`vend-9`, AVAILABLE at 10:01Z.

1. Evaluate the fixture through 10:04Z, including its DELETING state update.
2. Compare rate, quantity, unit and dimensions.

**Expected results.** The fixture yields the half-open 10:01–10:04 capacity piece with a 100 GiB multiplier and
18,000 GiB-seconds (18,000,000,000 micros), `gibibyte_second` and tier `gold`. The fixture has no deletion
completion record.

#### TC-S-05: Volume registry disable and re-enable exposes the outage gap

| Priority | Automation |
|---|---|
| medium | automated |

- **Tier:** Component integration
- **Owner:** [DEV]
- **References:** [Design — Gate and recovery](design.md#pagination-feature-gate-and-recovery)
- **Dependencies:** Real Kafka and PostgreSQL test containers and the metering service components
  under test. The harness supplies fulfillment snapshots and omits the fulfillment server and
  billing provider. The adapter route needs a real adapter with a recording provider double.
- **Gap:** The design’s per-token runtime reload across loader, heartbeat and adapter is unresolved.

**Preconditions.** Configure active `volume` and `compute_instance` tokens, one active Volume, one
VM and a retained usage record.

1. Reload the registry without `volume` and publish both resource types during a known two-round window.
2. Re-enable `volume`, then compare persisted and published usage before, during and after the window.

**Expected results.** Volume selection and delivery stop while disabled and prior rows remain. VM metering
continues. Volume usage resumes from authoritative state and the disabled interval is visible as
missing.

#### TC-S-08: Deleted Volume history remains readable for the configured retention

| Priority | Automation |
|---|---|
| medium | automated |

- **Tier:** E2E
- **Owner:** [QE]
- **References:** [PRD — Raw and aggregated retention](prd.md#acceptance-criteria)
- **Dependencies:** Requires deployed fulfillment, storage, Kafka and a real historical usage store,
  with a retention-age fixture. No simulated store can establish the retention result.
- **Gap:** The deployed deletion journey checks the final interval and net usage over a 120-second window.
  Historical retention and finalized aggregate readback are unresolved.

**Preconditions.** Use a deployed billable Volume, a readable heartbeat topic, and access to the
configured historical usage store.

1. Record a typed heartbeat ID and billed total, then delete the Volume.
2. Read the ID before raw retention expires and read the same finalized usage period twice within
   aggregate retention.

**Expected results.** Raw usage stays readable for the configured minimum of 7 days and finalized usage is
unchanged across reads through the configured minimum of 13 months.

## Vendor feedback and state eligibility

#### TC-S-06: PostgreSQL accepts initial vendor ID assignment and rejects changes

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Component integration
- **Owner:** [DEV]
- **References:** [Design — Write-once vendor ID](design.md#api-extensions)
- **Dependencies:** Real PostgreSQL and the metering source migration. The suite writes synthetic
  Volume rows directly and omits the Fulfillment API and storage provider.
- **Execution:** `fulfillment-service/internal/database/migrations/128_add_metering_source_contract_test.go`
- **Evidence:** `TestMigrations / volume vendor volume id + volume vendor volume id cleared` ([source](https://github.com/osac-project/osac/blob/2a69f3d27c2341da4dd4fe8965bc7cfadcf90d69/fulfillment-service/internal/database/migrations/128_add_metering_source_contract_test.go#L362)).
- **Selector:** `go test ./internal/database/migrations -run '^(TestMigrations)$' -ginkgo.focus='volume vendor volume id( cleared)?$'` from `fulfillment-service` in osac. Not run for this backfill.

**Preconditions.** Apply migration 128 and use separate `volume-1` fixtures on `tier-1` with a
fixed state timestamp at 2026-01-01 10:00 UTC. The first row is CREATING with no vendor ID. The
other rows are AVAILABLE with `vendor-1`.

1. Set `status.vendor_volume_id` to `vendor-1` on the CREATING row.
2. Replace `vendor-1` with `vendor-2` on one AVAILABLE row.
3. Clear `vendor-1` on a separate AVAILABLE row.

**Expected results.** The initial assignment updates one row. The replacement and clearing fail with
PostgreSQL SQLSTATE `Z0006`.

#### TC-S-07: Volume state and deletion facts determine eligibility

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Unit
- **Owner:** [DEV]
- **References:** [Design — State predicate matrix](design.md#test-plan) and [Design — State
  transitions](design.md#implementation-detailsnotesconstraints)
- **Dependencies:** In-process fixtures only; no database, broker, deployment, or billing provider.
- **Gap:** Current Unit tests cover missing ID, NFS and deletion before AVAILABLE. The shipped
  rules include DELETING and the capacity fixture has no deletion fact. The design’s exact
  deletion-request cutoff and complete FAILED/DELETING/DELETED matrix remain unresolved.

**Preconditions.** Use BLOCK Volume facts with vendor ID `vendor-1`, AVAILABLE at 10:00Z and
distinct state and deletion times. Include a second fixture that fails before any vendor ID is
assigned.

1. Evaluate FAILED before allocation and AVAILABLE to FAILED at 10:01Z.
2. Evaluate AVAILABLE to DELETING with deletion request at 10:01Z, feedback at 10:02Z and DELETED at
   10:03Z.
3. Try to reopen the DELETED fixture.

**Expected results.** Early FAILED yields zero capacity. AVAILABLE to FAILED closes at 10:01Z. Deletion
closes once at 10:01Z. Delayed feedback and DELETED add zero usage, and DELETED cannot reopen.

#### TC-S-09: Available NFS and missing-vendor-ID volumes emit no capacity

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Unit
- **Owner:** [DEV]
- **References:** [Design — Eligibility predicates](design.md#test-plan)
- **Dependencies:** In-process fixtures only; no database, broker, deployment, or billing provider.
- **Execution:** `osac-metering/metering-service/internal/usage/engine_test.go`
- **Evidence:** `TestVolumeWithoutVendorIDOrBlockProtocolBillsNothing` ([source](https://github.com/osac-project/osac/blob/2a69f3d27c2341da4dd4fe8965bc7cfadcf90d69/osac-metering/metering-service/internal/usage/engine_test.go)).
- **Selector:** `go test ./internal/usage -run '^(TestVolumeWithoutVendorIDOrBlockProtocolBillsNothing)$'` from `osac-metering/metering-service` in osac. Not run for this backfill.

**Preconditions.** Use an AVAILABLE 100 GiB Volume from 10:01Z with a valid creation fact.

1. Evaluate the BLOCK fixture without a vendor ID.
2. Evaluate it again as NFS with vendor ID `vend-9`.

**Expected results.** Both evaluations produce zero usage pieces.

#### TC-S-10: Private Volume Update preserves the assigned vendor ID

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Component integration
- **Owner:** [DEV]
- **References:** [Design — Write-once vendor ID](design.md#api-extensions)
- **Dependencies:** Real PostgreSQL and the in-process private Volumes server. The suite can
  supply tenancy and attribution doubles and use a synthetic vendor ID. The storage provider is omitted.
- **Gap:** The migration covers first assignment and rejects changes at the SQL boundary.
  The server suite covers first assignment. Repeating the same ID, rejecting replacement or
  clearing through the private API and reading back the retained value remain unresolved.

**Preconditions.** Persist an AVAILABLE BLOCK Volume with vendor ID `vendor-1`. Use its latest
version for every private update.

1. Resend the same ID with a `status.vendor_volume_id` update mask.
2. Using the same mask, attempt to clear the ID and to change it to `vendor-2` in separate requests.
3. Read the Volume after each attempt.

**Expected results.** The identical resend succeeds. The clear and replacement are rejected, and each
read returns `vendor-1`.
