# Test Plan — OSAC-6056 Metering event contract

## Overview

- **Design:** [Design](design.md)
- **PRD:** [Requirements](prd.md)
- **Total test cases:** 8

Execution entries identify source assertions on OSAC main. Gap entries describe unresolved tests for
the named work owner. No individual assignee or follow-up ticket is recorded here.

## Published schema and versioning

#### TC-EC-01: Generated reference and schema match the committed contract

| Priority | Automation |
|---|---|
| critical | automated |

- **Tier:** Contract
- **Owner:** [DEV]
- **References:** [Design — Generated reference](design.md#the-generated-reference) and [Design —
  Criterion 19](design.md#test-plan)
- **Dependencies:** In-process fixtures only; no database, broker, deployment, or billing provider.
  The generator and committed inputs are real.
- **Execution:** `osac-metering/metering-service/tools/contract/contract_test.go`
- **Evidence:** `TestContract / matches the committed files, so CI fails on a stale reference` ([source](https://github.com/osac-project/osac/blob/2a69f3d27c2341da4dd4fe8965bc7cfadcf90d69/osac-metering/metering-service/tools/contract/contract_test.go)).
- **Selector:** `go test ./tools/contract -run '^(TestContract)$' -ginkgo.focus='matches the committed files, so CI fails on a stale reference'` from `osac-metering/metering-service` in osac. Not run for this backfill.

**Preconditions.** Use the public OSAC source tree with committed generated reference and schema and
its current rule revision.

1. Load the contract inputs.
2. Run the contract freshness check against the checkout.

**Expected results.** The generator reports no stale reference or checkable schema and the check succeeds.

#### TC-EC-02: The checkable schema accepts the produced v1 heartbeat and rejects v99

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Contract
- **Owner:** [DEV]
- **References:** [Design — Schemas never change](design.md#schemas-never-change) and [Design —
  Version and producer conformance](design.md#test-plan)
- **Dependencies:** In-process fixtures only; no database, broker, deployment, or billing provider.
  Uses the actual builder and JSON Schema compiler.
- **Execution:** `osac-metering/metering-service/tools/contract/contract_test.go`
- **Evidence:** `TestContract / accepts a real heartbeat and refuses a version it has not published` ([source](https://github.com/osac-project/osac/blob/2a69f3d27c2341da4dd4fe8965bc7cfadcf90d69/osac-metering/metering-service/tools/contract/contract_test.go)).
- **Selector:** `go test ./tools/contract -run '^(TestContract)$' -ginkgo.focus='accepts a real heartbeat and refuses a version it has not published'` from `osac-metering/metering-service` in osac. Not run for this backfill.

**Preconditions.** Use the real heartbeat builder and the `cluster-1` fixture with meter
`control_plane`, quantity 60 seconds and tenant `acme`.

1. Compile the generated schema and validate the serialized heartbeat.
2. Change its event type to `osac.resource.heartbeat.v99` and validate again.

**Expected results.** The original heartbeat validates and its envelope matches the published attribute set.
The unpublished version fails validation.

#### TC-EC-05: An additive version passes the release guard and an edited published schema fails

| Priority | Automation |
|---|---|
| critical | automated |

- **Tier:** Contract
- **Owner:** [DEV]
- **References:** [Design — Schemas never change](design.md#schemas-never-change) and [Design —
  Criteria 6 and 7](design.md#test-plan)
- **Dependencies:** The Git fixture, Bash and release-tag guard are real. The fixture supplies the
  tag and v2 file in an offline checkout.
- **Execution:** `osac-metering/metering-service/tools/contract/tag_gate_internal_test.go`
- **Evidence:** `TestTagGateAllowsANewVersionAndRejectsAnEditedOne` ([source](https://github.com/osac-project/osac/blob/2a69f3d27c2341da4dd4fe8965bc7cfadcf90d69/osac-metering/metering-service/tools/contract/tag_gate_internal_test.go)).
- **Selector:** `go test ./tools/contract -run '^(TestTagGateAllowsANewVersionAndRejectsAnEditedOne)$'` from `osac-metering/metering-service` in osac. Not run for this backfill.

**Preconditions.** Git and Bash are available. The suite uses a temporary Git checkout with its own
release tag containing v1.

1. Run the release-tag guard on the tagged baseline.
2. Add the synthetic v2 file and manifest entry and rerun.
3. Append one newline to the published v1 file and rerun.

**Expected results.** The baseline and additive file pass the tag guard. Editing the tagged v1 fails and
names the changed path. The guard checks byte-level immutability for tagged versions.

#### TC-EC-06: Replay decoding uses the version named by a retained record

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Unit
- **Owner:** [DEV]
- **References:** [Design — Schemas never change](design.md#schemas-never-change) and [Design —
  Criterion 8](design.md#test-plan)
- **Dependencies:** In-process fixtures only; no database, broker, deployment, or billing provider.
- **Execution:** `osac-metering/metering-service/internal/round/catchup_internal_test.go`
- **Evidence:** `TestDecodeHeartbeatReplaysARecordWithItsNamedVersion` ([source](https://github.com/osac-project/osac/blob/2a69f3d27c2341da4dd4fe8965bc7cfadcf90d69/osac-metering/metering-service/internal/round/catchup_internal_test.go)).
- **Selector:** `go test ./internal/round -run '^(TestDecodeHeartbeatReplaysARecordWithItsNamedVersion)$'` from `osac-metering/metering-service` in osac. Not run for this backfill.

**Preconditions.** Use the replay decoder, shipped v1 and a 60-second heartbeat written at
2026-11-02 10:00Z. Construct a synthetic v2 effective one hour later.

1. Decode the original v1 record.
2. Decode separate copies missing `rules_revision`, carrying v99, and carrying v2 before its
   effective time.

**Expected results.** The original restores its ledger key, round time and 60,000,000 micros. Every negative
copy is rejected with its corresponding missing-field, unknown-version or pre-effective-date error.

#### TC-EC-07: Kafka replay across two schema versions reconstructs the same usage

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Component integration
- **Owner:** [DEV]
- **References:** [Design — Schemas never change](design.md#schemas-never-change) and [Design —
  Criteria 8 and 21](design.md#test-plan)
- **Dependencies:** Real Kafka and PostgreSQL test containers and the metering service components
  under test. The harness supplies fulfillment snapshots and omits the fulfillment server and
  billing provider.
- **Gap:** Version selection and decoding tests plus single-version pipeline recovery exist.
  Two-version Kafka replay and ledger equality remain unresolved.

**Preconditions.** Use Kafka, PostgreSQL, retained v1 data and a supported later additive schema in
a test fixture with a known effective time. Prepare 60 seconds under each version for one ledger
key.

1. Write one heartbeat per version at its valid write time.
2. Restore a backup before those records and replay both through the normal Round catch-up.
3. Compare the restored ledger to the uninterrupted ledger.

**Expected results.** Both versions remain readable and contribute once. The reconstructed total is 120
seconds at the same key, with the same progress as the baseline.

## Deployed consumer and reader access

#### TC-EC-03: An independent reader computes a billable total using the public contract

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** E2E
- **Owner:** [QE]
- **References:** [Design — Worked example](design.md#the-worked-example) and [Design — Criterion
  18](design.md#test-plan)
- **Dependencies:** Use real deployed Kafka, metering records and reader ACLs. No billing provider
  is required.
- **Gap:** Local reading-rule tests do not run the example against deployed Kafka. This external
  reader journey is unresolved.

**Preconditions.** Use a dev hub with reader access and known 60-second positive and 20-second
negative usage records for the same resource, meter, component and dimensions.

1. Discover the tenant heartbeat topic, read both messages as the external reader, and validate by
   their named version.
2. Sum signed quantities with the worked example and inspect its output.

**Expected results.** The example reports 40 seconds for the expected dimension key, reads only the
heartbeat topic and stores no credentials.

#### TC-EC-04: A deployed heartbeat names its published v1 version

| Priority | Automation |
|---|---|
| medium | automated |

- **Tier:** E2E
- **Owner:** [QE]
- **References:** [Design — Version and producer conformance](design.md#test-plan)
- **Dependencies:** Real deployed fulfillment, hub controllers, Kafka and metering. The Echo adapter
  provides the test readback for published records.
- **Execution:** `tests/e2e/vmaas/sanity/test_metering_billing.py`
- **Evidence:** `test_metering_heartbeat_envelope` ([source](https://github.com/osac-project/osac/blob/2a69f3d27c2341da4dd4fe8965bc7cfadcf90d69/tests/e2e/vmaas/sanity/test_metering_billing.py)).
- **Selector:** `uv run pytest -n 0 tests/e2e/vmaas/sanity/test_metering_billing.py::test_metering_heartbeat_envelope` from `repository root` in osac. Not run for this backfill.

**Preconditions.** Use a deployed VMaaS hub with metering, a ready VM template and dedicated project.

1. Create a VM and wait for RUNNING.
2. Read its typed compute heartbeat within 180 seconds and validate the envelope.

**Expected results.** The CloudEvent type equals `osac.resource.heartbeat.v1` and the shared verifier
accepts the v1 envelope.

#### TC-EC-08: One reader credential follows all tenant heartbeat topics

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** E2E
- **Owner:** [QE]
- **References:** [Design — Reading access](design.md#reading-access) and [Design — Criteria 11 and
  12](design.md#test-plan)
- **Dependencies:** Requires real deployed Kafka ACLs, onboarding, metering and a reader client. No
  billing provider is required.
- **Gap:** Chart rendering asserts configured ACLs. Live multi-tenant reads, onboarding and
  revocation timing against the broker remain unresolved.

**Preconditions.** Deploy Kafka and OSAC with two test tenants and one read-only reader entry with
no tenant list. Prepare a third tenant to onboard.

1. Discover both heartbeat topics by prefix and consume with the same credential and assigned group.
2. Onboard the third tenant and read its heartbeat topic without changing the reader entry.
3. Remove the entry and measure the next fetch on each topic.

**Expected results.** The same credential reads all three topics. Revocation causes the next running fetch
to fail within 60 seconds across the three topics without OSAC pod restarts.
