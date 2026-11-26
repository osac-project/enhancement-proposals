# Test Plan — OSAC-983 Reliable event distribution

## Overview

- **Public requirements:** [design.md](design.md), [prd.md](prd.md)
- **Total test cases:** 10

Execution identifies matching assertions on OSAC main. Gaps describe remaining coverage for
the named work owner. No individual assignee or follow-up ticket is recorded here.

## Test cases

#### TC-EV-01: Database triggers deliver Project create, signal, update and delete events

| Priority | Automation |
|---|---|
| critical | automated |

- **Tier:** Component integration
- **Owner:** [DEV]
- **References:** [design.md, lines 1174-1178](https://github.com/osac-project/enhancement-proposals/blob/84a28b6b9865f71684304e9fd1e1665835807bfc/enhancements/OSAC-983-reliable-event-distribution/design.md#L1174-L1178)
- **Dependencies:** Real PostgreSQL trigger, Kafka test broker and in-process publisher; synthetic tenant/Project; no fulfillment endpoint.
- **Execution:** `fulfillment-service/internal/servers/event_publisher_test.go`
- **Evidence:** `Publishes trigger-written insert, signal, update, and delete events` ([source](https://github.com/osac-project/osac/blob/b778b3abffc55bad57edcd5e82d37b82a1280c90/fulfillment-service/internal/servers/event_publisher_test.go#L1666)).
- **Selector:** `ginkgo run --timeout 10m --focus='Publishes trigger-written insert, signal, update, and delete events' internal/servers` from `fulfillment-service`. Source reviewed, test not run.

**Preconditions.** Use a synthetic tenant and project p-1 titled Acme.

1. Create, mark a signal, change the title to Updated and remove the fixture project through the suite database operations.
2. Read the corresponding Kafka records and pending-row count.

**Expected results.** The expected Project events arrive with their IDs, tenant and titles in order, and pending rows drain. Canonical main stages records in changes.

#### TC-EV-02: An uncommitted lower row is published before a committed higher row once visible

| Priority | Automation |
|---|---|
| critical | automated |

- **Tier:** Component integration
- **Owner:** [DEV]
- **References:** [design.md, lines 1179-1181](https://github.com/osac-project/enhancement-proposals/blob/84a28b6b9865f71684304e9fd1e1665835807bfc/enhancements/OSAC-983-reliable-event-distribution/design.md#L1179-L1181)
- **Dependencies:** Real PostgreSQL transactions and Kafka, in-process publisher; no deployed client or production data.
- **Execution:** `fulfillment-service/internal/servers/event_publisher_test.go`
- **Evidence:** `Does not claim a row from an open transaction ahead of a committed higher ID` ([source](https://github.com/osac-project/osac/blob/b778b3abffc55bad57edcd5e82d37b82a1280c90/fulfillment-service/internal/servers/event_publisher_test.go#L1396)).
- **Selector:** `ginkgo run --timeout 10m --focus='Does not claim a row from an open transaction ahead of a committed higher ID' internal/servers` from `fulfillment-service`. Source reviewed, test not run.

**Preconditions.** Stage the suite's earlier synthetic change in an open transaction and commit a later one.

1. Observe no topic for one second, then commit the earlier transaction and read both records.
2. Compare arrival order and pending-row count.

**Expected results.** The earlier row is published first, the later row follows and no pending rows remain. Broker acknowledgment is treated separately.

#### TC-EV-03: A publisher interruption before row deletion causes one replay

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Component integration
- **Owner:** [DEV]
- **References:** [design.md, lines 1182-1184](https://github.com/osac-project/enhancement-proposals/blob/84a28b6b9865f71684304e9fd1e1665835807bfc/enhancements/OSAC-983-reliable-event-distribution/design.md#L1182-L1184)
- **Dependencies:** Real PostgreSQL and Kafka testcontainers; in-process publisher and simulated interruption in its callback.
- **Execution:** `fulfillment-service/internal/servers/event_publisher_test.go`
- **Evidence:** `Re-publishes the same row when the process crashes before delete` ([source](https://github.com/osac-project/osac/blob/b778b3abffc55bad57edcd5e82d37b82a1280c90/fulfillment-service/internal/servers/event_publisher_test.go#L1448)).
- **Selector:** `ginkgo run --timeout 10m --focus='Re-publishes the same row when the process crashes before delete' internal/servers` from `fulfillment-service`. Source reviewed, test not run.

**Preconditions.** Insert the synthetic change for obj-1 and use the callback fixture that stops processing before delete.

1. Observe the first record and retained row.
2. Restart the publisher and collect both records.

**Expected results.** Both carry the same object key and current main's change-row event ID. The row drains after retry. Read-time IDs and consumer handling are separate cases.

#### TC-EV-04: The publisher uses the tenant name verbatim in its topic

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Component integration
- **Owner:** [DEV]
- **References:** [design.md, lines 1185-1188](https://github.com/osac-project/enhancement-proposals/blob/84a28b6b9865f71684304e9fd1e1665835807bfc/enhancements/OSAC-983-reliable-event-distribution/design.md#L1185-L1188)
- **Dependencies:** Real Kafka and PostgreSQL with synthetic DNS-label tenants; in-process publisher.
- **Gap:** Canonical tests cover two tenant topics and configured prefix. No named exact test was found for the design's full boundary-label matrix.

**Preconditions.** Prepare a 63-character lowercase tenant, a digit-bounded tenant and a hyphenated tenant.

1. Publish one synthetic event for each.
2. Compare the topic names and their received IDs.

**Expected results.** Every topic is osac.events. followed by the tenant name verbatim, and receives only its fixture event.

#### TC-EV-05: Event IDs identify Kafka records at read time

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Contract
- **Owner:** [DEV]
- **References:** [design.md, lines 1189-1194](https://github.com/osac-project/enhancement-proposals/blob/84a28b6b9865f71684304e9fd1e1665835807bfc/enhancements/OSAC-983-reliable-event-distribution/design.md#L1189-L1194)
- **Dependencies:** Real event bridge and recording Kafka fixture; synthetic topics and offsets; no external client or database cursor lookup.
- **Gap:** Current publisher tests assert IDs from change rows. No exact offset-derived read-time bridge ID assertion was found on canonical main.

**Preconditions.** Provide a fixed record and a second record at another offset in the same synthetic topic.

1. Read the first record twice, then read the second.
2. Compare the emitted IDs and their associated positions.

**Expected results.** The same record gives the same ID each time and the other offset has a distinct ID.

#### TC-EV-06: The publisher retains a row until the broker acknowledges it

| Priority | Automation |
|---|---|
| critical | automated |

- **Tier:** Component integration
- **Owner:** [DEV]
- **References:** [design.md, lines 1179-1181](https://github.com/osac-project/enhancement-proposals/blob/84a28b6b9865f71684304e9fd1e1665835807bfc/enhancements/OSAC-983-reliable-event-distribution/design.md#L1179-L1181)
- **Dependencies:** Real PostgreSQL and publisher; controlled Kafka protocol endpoint can withhold an acknowledgment.
- **Gap:** Canonical cases separately test broker metadata timeout and callback failure. No exact assertion verified that withholds produce acknowledgment and observes the row before and after success.

**Preconditions.** Stage one fixture row and delay the broker fixture's publish acknowledgment.

1. Observe the pending row while the request waits.
2. Acknowledge the publish and read the row again.

**Expected results.** The row is retained while acknowledgment is absent and removed only after success.

#### TC-EV-07: Replay is harmless to every in-scope consumer

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Component integration
- **Owner:** [DEV]
- **References:** [design.md, lines 1179-1184](https://github.com/osac-project/enhancement-proposals/blob/84a28b6b9865f71684304e9fd1e1665835807bfc/enhancements/OSAC-983-reliable-event-distribution/design.md#L1179-L1184)
- **Dependencies:** Real isolated event delivery and recorded consumer handlers; synthetic records and object state; no external provider.
- **Gap:** Publisher replay proves duplicate delivery, not the consumers' behavior. No shared source assertion found for controller state convergence and a stream consumer accepting duplicates; metering adoption is outside the proposal.

**Preconditions.** Create a synthetic object and two equivalent events at different offsets.

1. Deliver both to the controller fixture and observe reconciled state.
2. Read both via the stream consumer and compare their logical object identity.

**Expected results.** The controller converges once to the current desired state. The stream client can receive both records without treating either as a new object.

#### TC-EV-08: Replay returns only authorized retained events

| Priority | Automation |
|---|---|
| critical | automated |

- **Tier:** Component integration
- **Owner:** [DEV]
- **References:** [design.md, lines 1212-1237](https://github.com/osac-project/enhancement-proposals/blob/84a28b6b9865f71684304e9fd1e1665835807bfc/enhancements/OSAC-983-reliable-event-distribution/design.md#L1212-L1237)
- **Dependencies:** Real test Kafka, PostgreSQL and fulfillment stream in Kind; two isolated tenants and supported cursor fixtures.
- **Gap:** Canonical live visibility tests were found. Cursor resume and retention remain unresolved. The design's integration section says commit order, while the earlier section and existing publisher spec use serial order after the earlier row becomes visible; a single ordering contract needs clarification before crediting resume order.

**Preconditions.** Start an authorized disposable subscriber and create fixture events before and after disconnection in two tenants.

1. Resume using the subscriber's supported cursor and inspect events.
2. Independently check handling of standard invalid and expired cursor fixtures.

**Expected results.** The subscriber receives all authorized retained records and no unrelated records. Invalid fixtures return InvalidArgument and expired fixtures return FailedPrecondition. Replay ordering remains unresolved pending agreement on the public requirement.

#### TC-EV-09: A consumer group discovers new topics and resumes per-topic offsets

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Component integration
- **Owner:** [DEV]
- **References:** [design.md, lines 1221-1232](https://github.com/osac-project/enhancement-proposals/blob/84a28b6b9865f71684304e9fd1e1665835807bfc/enhancements/OSAC-983-reliable-event-distribution/design.md#L1221-L1232)
- **Dependencies:** Real disposable Kafka and fulfillment stream, synthetic group and tenant topics; external consumers omitted.
- **Gap:** The canonical publisher suite verifies topic creation. The subscriber discovery, committed-offset recovery and group reassignment assertions are unresolved in canonical event suites.

**Preconditions.** Use two test group members, two fixture tenants and bounded Kafka metadata refresh.

1. Add a tenant topic after subscribe, consume and commit offsets, then restart one member.
2. Compare delivered sets and resumed positions.

**Expected results.** New topic records arrive, assignments are disjoint before restart, and the surviving group's per-topic resume has no missed events.

#### TC-EV-10: A deployed controller resumes without re-listing after restart

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** E2E
- **Owner:** [QE]
- **References:** [design.md, lines 1242-1246](https://github.com/osac-project/enhancement-proposals/blob/84a28b6b9865f71684304e9fd1e1665835807bfc/enhancements/OSAC-983-reliable-event-distribution/design.md#L1242-L1246)
- **Dependencies:** Real disposable deployed controller, fulfillment and Kafka group state; synthetic updates and captured API counters.
- **Gap:** No deployed controller restart selector with group-offset and no-full-relist assertions found in canonical E2E sources.

**Preconditions.** Create an isolated controller and observe its committed position for one fixture tenant.

1. Restart it while a new fixture update is pending.
2. Check controller convergence and full-list request counts.

**Expected results.** It applies the pending update from the committed position without a full re-list.
