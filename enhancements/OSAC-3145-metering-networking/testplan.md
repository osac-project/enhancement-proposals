# Test Plan — OSAC-3145 Metering for Networking

## Overview

- **Design:** [Design](design.md)
- **PRD:** [Requirements](prd.md)
- **Total test cases:** 10

Execution entries identify source assertions on OSAC main. Gap entries describe unresolved tests for
the named work owner. No individual assignee or follow-up ticket is recorded here.

## Deployed allocation and dimensions

#### TC-N-01: ExternalIP attach, detach and reattach bill disjoint dimension sets

| Priority | Automation |
|---|---|
| critical | automated |

- **Tier:** E2E
- **Owner:** [QE]
- **References:** [Design — Usage and correction contract](design.md#usage-and-correction-contract)
  and [PRD — Networking acceptance criteria](prd.md#7-acceptance-criteria)
- **Dependencies:** Real deployed fulfillment, hub controllers, Kafka and metering. The Echo adapter
  provides test readback via `METERING_ADAPTER_URL`. Use the whole ordered suite with real
  Netris networking, KubeVirt, compatible AAP, guest SSH and a routed IPv4 pool.
- **Execution:** `tests/e2e/networking/vmaas/test_vmaas_networking.py`
- **Evidence:** `TestVmaasNetworking::test_12c_external_ip_attach_detach_reattach_billing` ([source](https://github.com/osac-project/osac/blob/2a69f3d27c2341da4dd4fe8965bc7cfadcf90d69/tests/e2e/networking/vmaas/test_vmaas_networking.py)).
- **Selector:** `uv run pytest -n 0 -x tests/e2e/networking/vmaas/test_vmaas_networking.py` from `repository root` in osac. Not run for this backfill.

**Preconditions.** Use an IPv4 pool, a test project, an allocated ExternalIP and two RUNNING
ComputeInstances on the Netris deployment.

1. Read unattached billing, attach to the first VM and wait for READY and settled attribution.
2. Detach, wait for a later unattached heartbeat, then reattach the same IP to the second VM and
   read another attached heartbeat.
3. Reduce the observed heartbeats to net intervals grouped by dimensions.

**Expected results.** The unattached record identifies the IPv4 pool and test project. The parent reports
each VM ID when it settles. The address survives reattachment and the net intervals for attached and
unattached dimensions are disjoint.

#### TC-N-02: NATGateway allocation uses its network and address references

| Priority | Automation |
|---|---|
| critical | automated |

- **Tier:** E2E
- **Owner:** [QE]
- **References:** [Design — Usage and correction contract](design.md#usage-and-correction-contract)
- **Dependencies:** Real deployed fulfillment, hub controllers, Kafka and metering. The Echo adapter
  provides test readback via `METERING_ADAPTER_URL`. Use the whole ordered suite with real
  Netris networking, KubeVirt, compatible AAP, guest SSH and a routed IPv4 pool.
- **Execution:** `tests/e2e/networking/vmaas/test_vmaas_networking.py`
- **Evidence:** `TestVmaasNetworking::test_12d_nat_gateway_billing` ([source](https://github.com/osac-project/osac/blob/2a69f3d27c2341da4dd4fe8965bc7cfadcf90d69/tests/e2e/networking/vmaas/test_vmaas_networking.py)).
- **Selector:** `uv run pytest -n 0 -x tests/e2e/networking/vmaas/test_vmaas_networking.py` from `repository root` in osac. Not run for this backfill.

**Preconditions.** Use network B and the allocated-address pool from the Netris suite. Create the
NATGateway in the tenant default project.

1. Allocate an ExternalIP and create a NATGateway with that IP ID and network B ID.
2. Wait for READY, then collect at least two heartbeats for the gateway.

**Expected results.** The heartbeat shows allocation in `second` with `virtual_network` and `external_ip`
matching the fixture names and no project dimension. Observed intervals are contiguous and quantity
equals seconds.

#### TC-N-09: Networking translation and durable replay work at the M360 boundary

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Contract
- **Owner:** [DEV]
- **References:** [Design — Usage and correction contract](design.md#usage-and-correction-contract)
- **Dependencies:** Requires the real M360 adapter and provider test tenant with readback. The
  source events are synthetic.
- **Gap:** In-process routing covers both resource endpoints and the correction quantity. Provider
  acceptance of the networking dimension payload and durable per-ID readback are unresolved.

**Preconditions.** Use an authorized M360 test tenant with durable record readback and synthetic
ExternalIP and NATGateway records carrying the published dimensions.

1. Submit each record through the adapter.
2. Replay both IDs via a fresh adapter process.
3. Inspect provider records and compare the dimension values with the sent events.

**Expected results.** Each ID has one durable provider record with its own resource references and
dimensions. Replays leave billed quantity unchanged.

## Translation and attachment state

#### TC-N-03: The adapter routes the two networking resource types

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Unit
- **Owner:** [DEV]
- **References:** [Design — Usage and correction contract](design.md#usage-and-correction-contract)
- **Dependencies:** In-process fixtures only; no database, broker, deployment, or billing provider.
- **Execution:** `osac-metering/adapters/m360/translate_test.go`
- **Evidence:** `TestM360Adapter / routes every resource type to its endpoint` ([source](https://github.com/osac-project/osac/blob/2a69f3d27c2341da4dd4fe8965bc7cfadcf90d69/osac-metering/adapters/m360/translate_test.go)).
- **Selector:** `go test ./m360 -run '^(TestM360Adapter)$' -ginkgo.focus='routes every resource type to its endpoint'` from `osac-metering/adapters` in osac. Not run for this backfill.

**Preconditions.** Use the adapter fixture with resource ID `r-1`, allocation meter, quantity
`-30.000000`, and nil dimensions.

1. Translate an ExternalIP heartbeat.
2. Translate a NATGateway heartbeat with the same payload fields.

**Expected results.** ExternalIP routes to `/networking/externalip/event` and NATGateway to
`/networking/natgateway/event`. Both retain `-30.000000` in `usage_quantity`.

#### TC-N-04: Distinct attach and delete timestamps bound exact usage slices

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Component integration
- **Owner:** [DEV]
- **References:** [Design — Attachment
  transaction](design.md#implementation-detailsnotesconstraints) and [Design — Usage and correction
  contract](design.md#usage-and-correction-contract)
- **Dependencies:** Real Kafka and PostgreSQL test containers and the metering service components
  under test. The harness supplies fulfillment snapshots and omits the fulfillment server and
  billing provider.
- **Gap:** The Netris journey verifies disjoint output and observes a settled stamp. Exact slice
  arithmetic against separate durable timestamps under delayed and replayed events is unresolved.

**Preconditions.** Persist an allocated IP from 10:00:00Z, a settled attach at 10:00:10Z, a detach
at 10:00:20Z and an IP delete at 10:00:30Z. Set receipt times later than all four stamps.

1. Publish and fold those snapshots, then advance the round and read net usage by attached dimension.
2. Redeliver the attach and detach before running the next round.

**Expected results.** The unattached slices are [10:00:00, 10:00:10) and [10:00:20, 10:00:30), the attached
slice is [10:00:10, 10:00:20), and replay leaves total usage at 30 seconds.

#### TC-N-05: The attachment target oneof excludes NATGateway

| Priority | Automation |
|---|---|
| medium | automated |

- **Tier:** Unit
- **Owner:** [DEV]
- **References:** [Design — Attachment and gateway API](design.md#api-extensions)
- **Dependencies:** In-process fixtures only; no database, broker, deployment, or billing provider.
- **Gap:** Existing server specs check missing targets, endpoint rules and addresses claimed by NAT.
  No equivalent exact oneof regression test for the excluded target was identified.

**Preconditions.** Use the private attachment spec descriptor and synthetic target references
`vm-1`, `cluster-1`, `bmi-1` and `nat-1`.

1. Enumerate target oneof members.
2. Decode a supported VM target, then try decoding a request with `natGateway` as its target with
   unknown fields rejected.

**Expected results.** The descriptor has only compute, cluster and bare-metal target members. The VM fixture
decodes, and the NATGateway target is rejected.

#### TC-N-06: Failed parent settlement rolls back the READY child write

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Component integration
- **Owner:** [DEV]
- **References:** [Design — Attachment transaction](design.md#implementation-detailsnotesconstraints)
- **Dependencies:** Real PostgreSQL test container and in-process fulfillment servers/DAOs. Suite
  doubles supply tenancy and attribution. The deployed gateway and provider are omitted. The missing
  feedback timestamp supplies the validation failure.
- **Execution:** `fulfillment-service/internal/servers/private_external_ip_attachments_server_test.go`
- **Evidence:** `TestServers / rolls back the child when parent settlement validation fails` ([source](https://github.com/osac-project/osac/blob/2a69f3d27c2341da4dd4fe8965bc7cfadcf90d69/fulfillment-service/internal/servers/private_external_ip_attachments_server_test.go)).
- **Selector:** `go test ./internal/servers -run '^(TestServers)$' -ginkgo.focus='rolls back the child when parent settlement validation fails'` from `fulfillment-service` in osac. Not run for this backfill.

**Preconditions.** Create an ALLOCATED unattached ExternalIP and a PENDING attachment to a RUNNING
ComputeInstance.

1. Within a savepoint, request READY with the `status.state` mask but no settlement timestamp.
2. Reload the child and parent after the failed savepoint.

**Expected results.** Update returns InvalidArgument. The attachment is still PENDING and parent `attached`
stays false.

#### TC-N-07: Attachment Update masks reject unsupported fields

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Component integration
- **Owner:** [DEV]
- **References:** [Design — Attachment and gateway API](design.md#api-extensions) and [Design —
  Attachment transaction](design.md#implementation-detailsnotesconstraints)
- **Dependencies:** Real PostgreSQL test container and in-process fulfillment servers/DAOs. Suite
  doubles supply tenancy and attribution. The deployed gateway and provider are omitted.
- **Execution:** `fulfillment-service/internal/servers/private_external_ip_attachments_server_test.go`
- **Evidence:** `TestServers / rejects an update without an explicit mask + rejects a metadata update of an external IP attachment` ([source](https://github.com/osac-project/osac/blob/2a69f3d27c2341da4dd4fe8965bc7cfadcf90d69/fulfillment-service/internal/servers/private_external_ip_attachments_server_test.go)).
- **Selector:** `go test ./internal/servers -run '^(TestServers)$' -ginkgo.focus='rejects an update without an explicit mask|rejects a metadata update of an external IP attachment'` from `fulfillment-service` in osac. Not run for this backfill.

**Preconditions.** Use a PENDING attachment to a RUNNING VM and an ALLOCATED parent IP.

1. Update the attachment without a mask.
2. Submit a separate attachment Update with mask `metadata.labels` and label `env=test`.

**Expected results.** Both requests return InvalidArgument. The metadata-mask update returns no response object.

#### TC-N-08: Parent output fields cannot be named in an attachment update mask

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Component integration
- **Owner:** [DEV]
- **References:** [Design — Attachment and gateway API](design.md#api-extensions)
- **Dependencies:** Real PostgreSQL test container and in-process fulfillment servers/DAOs. Suite
  doubles supply tenancy and attribution. The deployed gateway and provider are omitted.
- **Gap:** The nil-mask and metadata-mask tests exercise attachment mask validation. The
  parent-output-path matrix is unresolved.

**Preconditions.** Use a stored PENDING attachment with an ALLOCATED parent whose attached flag is
false and whose attribution is unset.

1. Send attachment Update with `status.state` plus `status.attached`, `status.attribution`, or
   `status.attachment_transition_time`, one extra path per request.
2. Reload both objects after each attempt.

**Expected results.** Each unsupported parent path returns InvalidArgument. The child stays PENDING and the
parent flags, attribution and transition stamp stay unchanged.

#### TC-N-10: Every attachment DAO write failure rolls back settlement

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Component integration
- **Owner:** [DEV]
- **References:** [Design — Attachment transaction](design.md#implementation-detailsnotesconstraints)
- **Dependencies:** Real PostgreSQL test container and in-process fulfillment servers/DAOs. Suite
  doubles supply tenancy and attribution. The deployed gateway and provider are omitted. Inject
  failures at the identified DAO step while keeping the transaction and both tables real.
- **Gap:** The existing savepoint test triggers parent validation after an attempted child update.
  Per-step DAO fault injection for both READY and Delete is unresolved.

**Preconditions.** Use an ALLOCATED parent and a fresh child for each READY and Delete case. Capture
both starting rows and their event changes.

1. Inject one failure at each child or parent DAO write during READY and Delete.
2. After each request, reread both rows and inspect the committed event changes.

**Expected results.** Each failure leaves both rows equal to their starting values, with zero committed
event changes from the rejected transition.
