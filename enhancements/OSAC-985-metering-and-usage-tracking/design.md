---
title: event-log-driven-metering
authors:
  - ovishlit@redhat.com
creation-date: 2026-09-30
last-updated: 2026-10-01
tracking-link:
  - https://redhat.atlassian.net/browse/OSAC-985
prd:
  - "prd.md"
see-also:
  - "/enhancements/OSAC-983-reliable-event-distribution"
  - "/enhancements/OSAC-2506-metering-bmaas"
  - "/enhancements/OSAC-3141-metering-storage"
  - "/enhancements/OSAC-3145-metering-networking"
---

# Metering on the OSAC event log

## Summary

For greenfield deployments, consume tenant `osac.events.*` topics directly from the first tenant onward. A deterministic fold turns each tenant's events into billable intervals; every 60 seconds a heartbeat round sends the signed difference between what should be billed and what was already billed to `osac.metering.heartbeat.<tenant>`, and M360 applies rates. Every metering table can be rebuilt from Kafka, so a database restore never bills an interval twice. See [PRD](prd.md) for detailed requirements.

## Motivation

The Watch consumer and periodic List reconciler both write meter state, creating competing observations, consistency races, and conflicting corrections by design. The event log becomes the source for resuming the projection after consumer outages or upgrades, instead of asking a reconciler to repair it. [Codebase: `osac-metering/metering-service/`; `fulfillment-service/internal/servers/event_publisher.go`]

Billing must also survive loss of the metering database without double billing or gaps [PRD: CAP-15, CAP-16, D-2]. M360 is append-only and deduplicates only repeated event IDs, so a heartbeat it has received can never be replaced or merged. A database restored from a backup does not know which heartbeats were sent after the backup was taken; resuming from its stored offset alone would re-send that time range under new IDs, and M360 would bill it twice. Two properties prevent this: the fold is deterministic, so replaying events rebuilds exactly the same state, and the record of what was emitted is rebuilt from the heartbeat topic before any new heartbeat is sent. [User]

### Goals

- Consume protobuf event snapshots directly from Kafka and deduplicate by the existing stable `Event.id`. [User]
- Define billable meters as projection predicates. The generic fold opens, closes, and splits intervals; it contains no state-transition tables. [User]
- Make the fold deterministic: the same events and meter definitions always produce the same state. [User]
- Survive restarts, upgrades, and database restores without double billing or gaps. [User]
- Publish signed interval quantities to one v1 heartbeat topic per tenant. M360 deduplicates persistent event IDs and owns pricing. [User]
- Preserve all current fulfillment meter types and their resource-local billing dimensions.
- Cover every metered resource type with one pipeline. This design intentionally includes the BMaaS, storage, and networking meters that PRD 985 defers, supersedes the per-resource designs (OSAC-2506, OSAC-3141, OSAC-3145) where they differ, and keeps events and heartbeats indefinitely instead of CAP-7's configurable retention. [User]

### Non-Goals

- Existing-deployment cutover, user-facing usage views, hierarchy rollups, pricing, invoices, quota enforcement, MaaS, and vendor-fed bandwidth; this pipeline emits billing intervals only.

MaaS remains metered as it is today, as a completely separate case from this pipeline.

## Proposal

One metering consumer folds full fulfillment snapshots into PostgreSQL using data-defined billability predicates, and heartbeat rounds send each tenant's signed usage to its own heartbeat topic. PostgreSQL stores its position in every topic it reads or writes.

### Workflow Description

1. Deploy fulfillment capture and the metering consumer before onboarding the first tenant or creating billable resources.
2. Tenant onboarding creates `osac.events.<tenant>`, `osac.metering.heartbeat.<tenant>`, and `osac.metering.dlq.<tenant>` together before committing Tenant creation, through whatever mechanism OSAC-983 settles on (an open question there). Each topic has one partition and keeps every record indefinitely: `retention.ms=-1`, `retention.bytes=-1`, and `cleanup.policy=delete`, so it is never compacted. Metering discovers tenants from `osac.events.*` topic metadata and starts a new tenant at offset 0 of both topics. It never creates topics, does not use Watch, and does not consume shared/system topics.
3. Each event is applied in a PostgreSQL transaction that also records its offset in `applied_offsets`. The consumer always resumes after `applied_offsets`; Kafka group offsets are committed afterwards for lag monitoring only.
4. Every 60 seconds, a heartbeat round sends each tenant's signed usage to its heartbeat topic. The M360 adapter discovers `osac.metering.heartbeat.*` topics exactly as metering discovers event topics, from topic metadata and starting each new topic at offset 0, and forwards heartbeats to M360, which applies rates.

On every start, metering runs the recovery steps (see Recovery) before its first heartbeat round.

### API Extensions

No public API or UI changes. Metering reads private protobuf `Event` records directly. `changes.id` already supplies stable `Event.id`. The source Event has no extra schema marker; protobuf field meanings remain immutable and wire compatibility is checked in CI.

### Implementation Details/Notes/Constraints

#### Meter definitions

Each revision of the meter definitions is its own ConfigMap, `osac-metering-rules-<NNNN>`, with `immutable: true`, so Kubernetes rejects edits; changing rules means adding a revision and rolling out metering, which loads revisions at startup. A revision holds the definitions, the `effective_at` from which it governs usage, and the fold version that interprets it. A change to how the fold interprets events ships as new code plus a new revision; usage before that revision's `effective_at` keeps the old logic, so an upgrade never re-bills history. Metering records each revision it uses in `rule_revisions` and refuses to start, with a notification, if a used revision (recorded there or stamped on a heartbeat) is missing or changed, or if a new revision's `effective_at` is in the past. A ValidatingAdmissionPolicy, installed with metering, denies deleting revisions (Kubernetes 1.30+). Only cluster administrators can create revision ConfigMaps; metering can only read them.

A definition names the resource type, meter and component keys, unit, multiplier, dimensions, and `billable_when`. A meter's unit never changes across revisions; a different unit requires a new meter name. Definitions cannot use transition tables, raw SQL, clock reads, or data from other objects, and may read only allowlisted snapshot fields, because dimensions leave OSAC in heartbeats.

- `billable_when` lists the billable states. It may also require fields that never change once the resource is billable, and use two history rules evaluated from `state_changes`: a *continue-only* state keeps an open meter open but never opens one, and `once: <state>` bills nothing until the resource first reaches that state, then also bills its earlier billable time.
- The allowlist names, for each billing field that can change after creation, the snapshot field holding its change time; all other billing fields are fixed at creation.
- Initial definitions, carrying the dimensions today's mappers emit. `FAILED` is never billable. Every meter carries the dimensions `deployment` (the installation's `METERING_DEPLOYMENT_ID`, required at startup and never changed), tenant, project, catalog, template, and meter type, plus the resource-specific ones below. Meters and units: ComputeInstance `compute` (`second`); ClusterOrder `control_plane` (`second`) and `worker` (`node_second`); BareMetalInstance `allocation` and `consumption` (`second`); Volume `capacity` (`gibibyte_second`); ExternalIP and NATGateway `allocation` (`second`).
  - ComputeInstance: `RUNNING`. Dimensions `status.instance_type`, which changes at `status.instance_type_transition_time`, `image_ref`, and `boot_disk_size_gib`.
  - ClusterOrder: `PROGRESSING|READY` with `once: READY`, so a cluster that fails or is deleted before it is ever ready bills nothing. Independent control-plane and per-node-set worker meters; worker meters multiply by the node set's `size`, which changes at its `size_transition_time`. Dimensions `cluster_template` and the release image, plus `host_type` and `node_set` per node set.
  - BareMetalInstance: allocation `STARTING|RUNNING|STOPPING|STOPPED` with `DELETING` continue-only, so a host deleted before provisioning completes or after failing bills nothing; consumption `RUNNING`. Dimension `bm_instance_type`. System-topic worker BMIs are not consumed.
  - Volume: `AVAILABLE`, only when `protocol` is BLOCK and a vendor volume ID is set. Multiplier `status.provisioned_size_gib` (GiB-seconds), the capacity the array committed, as today; it is fixed once set because the API rejects size changes. Dimension `storage_tier`.
  - ExternalIP: `ALLOCATED`. Dimensions `pool`, `ip_family`, the settled attribution (`attribution_type`, `attribution_id`, `attribution_endpoint`), and `attached`, which changes at `attachment_transition_time`.
  - NATGateway: `READY`. Dimensions `virtual_network` and `external_ip`.

#### Deterministic fold

The fold is the only code that interprets source events. It applies each tenant's events in offset order:

```
foldEvent(event):                                # one PostgreSQL transaction
  r = resources[event.resource] or a new row     # last applied version (0 when new), deleted_at, condition fields
  if event.id not in processed_events and event.metadata.version >= r.last_version:
    if the state changed:    insert state_changes(resource, version, state, changed_at = state_transition_time)
    if allowlisted fields changed: insert dimension_changes(resource, version, fields, changed_at = each field's change-time field)
    if OBJECT_DELETED:       r.deleted_at = Event.timestamp
    r.last_version = event.metadata.version; r.fields = condition fields; insert processed_events(event.id)
  applied_offsets[tenant] = event.offset         # advances for skipped events too
```

`foldEvent` records facts only, every allowlisted field whatever the current rules use, so it never depends on a revision. `shouldBeBilled(meter, upTo)` reads only these rows and the meter definitions. It walks the history revision by revision and interprets each period with the fold version that revision pins (`interpret[revision.fold_version]`); fold versions are never removed from the metering code, and a revision naming a missing one makes metering refuse to start, with a notification. A meter is billable while `billable_when` holds over the resource's state history; its intervals start no earlier than `metadata.creation_timestamp`, split at state, dimension, and revision boundaries and at every UTC midnight, and end at deletion or, if still open, at `upTo`. Field conditions read the values kept in `resources`. `metadata.deletion_timestamp` is never a boundary. Durations are exact, as today: integer microseconds, with quantity `multiplier × duration` as a fixed-point decimal. A run, a span during which a meter is continuously billable, that lasts under one second is not billed (CAP-4).

The fold reads no wall clock, no other tenant's data, and nothing outside its tables and the meter definitions, so the same events always produce the same rows, whether applied in one pass, across restarts, or after a restore. A repeated or older event changes nothing.

#### Heartbeat rounds

Every 60 seconds, each tenant runs one round in one PostgreSQL transaction. `heartbeatTime` is the current minute on PostgreSQL's clock, so a pod's clock never matters; if that clock moves backwards, rounds wait until it passes `last_heartbeat`. If PostgreSQL's clock and the pod's clock differ by more than five minutes, the round is skipped with a notification, so a forward jump never bills ahead. The transaction locks the tenant's `last_heartbeat` row, so overlapping pods serialize and only one round per heartbeat time commits:

```
heartbeatRound(tenant, heartbeatTime):           # heartbeatTime = 10:01:00, 10:02:00, ...
  for each meter that is open or changed since the previous round:
    should  = shouldBeBilled(meter, upTo = heartbeatTime)
    already = billed_intervals(meter)
    for each piece of (should − already):        # e.g. +60s 10:02→10:03, or −30s 10:02:30→10:03
      add a heartbeat to the outbox
    billed_intervals(meter) = should
  last_heartbeat[tenant] = heartbeatTime         # must increase; enforced in PostgreSQL
```

`billed_intervals` is what metering has emitted, net of corrections: one row per tenant, meter key (resource, meter, component, dimensions), and `from`, holding `to` and the multiplier; a key's rows never overlap. `should − already` compares the two multipliers on every sub-interval and, wherever they differ, emits a piece with quantity `(should − already) × duration`. Only heartbeat rounds change it, so it always equals the sum of all heartbeats emitted, and a late event needs no special handling: the next round sends the difference. Splitting at UTC midnight keeps every piece within one day, because M360 dates each event with one timestamp: a piece spanning midnight at month end would bill entirely to one month. Sixty seconds bounds how stale a tenant's running total can be; each heartbeat becomes one M360 rated transaction, so a longer interval trades freshness for volume.

A heartbeat (`osac.resource.heartbeat.v1`) is self-contained: tenant, resource, meter, component, dimensions, `from`, `to`, signed quantity, `heartbeat_time`, the `last_applied_offset` it saw, and the rules revision and hash it used, so it traces to the events and rules that produced it. It uses the existing `schema.Usage` shape: `semantics=interval`, `from` inclusive and `to` exclusive in UTC, a signed fixed-point `quantity` as text in the meter's unit, and `precision=microsecond`; consumers add heartbeats up and never replace them. Its CloudEvent `time` is `from`. Its ID is a hash of tenant, resource, meter, component, dimensions, `from`, `to`, and `heartbeat_time`, without the quantity. Because `heartbeat_time` strictly increases per tenant, two different rounds never share an ID; if one round is ever computed twice, the copies share IDs and M360 drops the second. The relay sends outbox rows in order until Kafka acknowledges, then deletes them and advances the tenant's `heartbeat_positions` in one transaction. The M360 adapter forwards each heartbeat with its ID. If M360 rejects one, the adapter moves it to the tenant's DLQ and keeps going. A notification stays active while the DLQ holds anything; once the cause is fixed, the operator replays it by resetting the adapter's offset on that tenant's topic to the DLQ record's `original-offset` header, and M360 drops the heartbeats it already has. The DLQ is mandatory: the adapter refuses to start without one.

#### Recovery

Billing integrity is non-negotiable: losing the metering database must never cause double billing or lost usage. That is why every table can be rebuilt from a durable source outside the database, and why unlimited retention of the event, heartbeat, and DLQ topics is a hard requirement; none of them is ever compacted. A future task will move their old records to cold storage to reduce Kafka load; replay must still read them by offset, as Kafka tiered storage does.

| Tables | Meaning | Rebuilt from |
|---|---|---|
| `resources`, `state_changes`, `dimension_changes`, `processed_events`, `applied_offsets` | What should be billed | `osac.events.<tenant>`, after `applied_offsets` |
| `billed_intervals`, `last_heartbeat`, `heartbeat_positions` | What was emitted | `osac.metering.heartbeat.<tenant>`, from `heartbeat_positions` |
| `rule_revisions` | Rules used | The revision ConfigMaps |

On every start, for each tenant, before its first round:

1. Read the tenant's heartbeat topic from `heartbeat_positions` to its end and apply each heartbeat to `billed_intervals` by adding its multiplier delta, `quantity ÷ (to − from)`, over its interval, splitting rows where needed and dropping rows that reach zero. Skip a heartbeat whose ID was already applied, or whose `heartbeat_time` is not after the restored `last_heartbeat` (that round is already recorded). Only after reading to the end, advance `last_heartbeat` to the newest `heartbeat_time` applied, and `heartbeat_positions` to the topic's end. All of step 1 commits in one PostgreSQL transaction per tenant, so a crash during recovery leaves nothing half-applied and the next start repeats it.
2. Apply events after `applied_offsets`.
3. Resume heartbeat rounds.

Example: a backup records a running VM as billed through 10:02; heartbeats for 10:02–10:05 were sent before the database was lost, and the backup is restored at 10:10. Without step 1, the 10:11 round would send 10:02–10:11 (540 s), and M360 would bill 10:02–10:05 twice. With step 1, the 10:11 round sends only 10:05–10:11 (360 s). With empty tables, the same steps from offset 0 rebuild the whole database.

`applied_offsets` advances with a compare-and-set, so a stale consumer cannot apply an event twice after a rebalance. A tenant's topics may be purged only after its final invoice.

#### Release prerequisites

- `Event.id` remains the UUIDv7 `changes.id`, and `metadata.version` increments on every captured write; keep source protobuf field meanings immutable and wire-compatible.
- Database triggers enforce the source contract for every writer, including direct SQL writes, which OSAC-983 also captures. On each update of a billable resource, the trigger sets `metadata.version` to the old value plus one; a changed state must come with a `state_transition_time` later than the old one; and a changed billing field must come with its change-time field later than the old one. An update that changes no billable field needs neither. These triggers only check times and never write them, so operator-reported times are kept as written. A non-compliant write fails with an error and its whole transaction rolls back, so nothing is stored or captured.
- New fields hold actual values, not requested ones, and are set by the operator when the change takes effect: ComputeInstance `status.instance_type` and `status.instance_type_transition_time`, and `size` with `size_transition_time` in each ClusterOrder node set's status. The DELETE trigger stamps `changes.timestamp` with `clock_timestamp()` after finalizers are gone; the publisher copies it to `Event.timestamp`.
- Unconvertible capture rows are quarantined with a notification, and the publisher holds back every later event for that tenant until the row is resolved, so each resource's versions reach the fold without gaps; trigger, snapshot-parity, and redaction checks run in CI.
- OSAC-983 onboarding creates the three tenant topics (Workflow step 2). Metering has read/group ACLs on `osac.events.*` and read/write on `osac.metering.heartbeat.*`; the M360 adapter reads `osac.metering.heartbeat.*` and writes `osac.metering.dlq.*`; fulfillment has no topic-create permission. Run one fenced event publisher per tenant topic.
- Everything here that contradicts OSAC-983 (direct Kafka consumption instead of Watch, `Event.id` as the stable `changes.id`, unlimited retention, and per-tenant heartbeat and DLQ topics created at onboarding) is addressed in a separate PR to OSAC-983.
- The M360 contract test confirms that negative quantities are rated as negative charges, that a repeated event ID is dropped permanently, that an event is billed in the UTC-day-aligned period containing its time, and that an invalid heartbeat is rejected synchronously; it also pins down how M360 handles an event dated in an already-invoiced period.
- A notification mechanism exists. Metering, fulfillment, and the M360 adapter use it to report a startup refusal, a quarantined capture row, and a non-empty DLQ; OSAC has none today.

#### Interface changes

| ID | Change | Requirements |
|---|---|---|
| IC-1 | Direct Kafka consumption of stable-ID full snapshots, resumed from offsets stored in PostgreSQL. | CAP-14, CAP-15, CAP-16 |
| IC-2 | Immutable meter-definition revision ConfigMaps with history-aware predicates and a pinned fold version, and a deterministic fold into PostgreSQL. | CAP-2, CAP-5, CAP-6, CAP-11, CAP-12, CAP-17 |
| IC-3 | Signed v1 heartbeats on per-tenant topics, with the billed record rebuilt from them. | CAP-4, CAP-11, CAP-12, CAP-15, CAP-16 |
| IC-4 | Per-tenant event and heartbeat topics created at onboarding, with ACLs and unlimited retention. | CAP-7, CAP-14 |
| IC-5 | Source fields for dimension change times: ComputeInstance `instance_type_transition_time`, ClusterOrder node-set `size_transition_time`. | CAP-11, CAP-12 |

## Test Plan

Every test checks one oracle: once the system settles, the heartbeats on each tenant's topic sum to `shouldBeBilled` over that tenant's full event log, and no heartbeat ID is billed twice; after any DLQ replay, M360 holds exactly the emitted heartbeats. The companion test plan details the cases.

Unit and integration tests, with real PostgreSQL and Kafka, gate every merge:

- **Determinism:** fold recorded event logs in one pass and with restarts at random offsets; the resulting rows must be identical.
- **Fold version:** replay recorded event logs with the new build; any result before the newest revision's `effective_at` that differs from the previous build fails CI.
- **Meter definitions:** every state pair of every meter, including PROVISIONING → DELETING, FAILED → DELETING, and a cluster that fails before READY.
- **Rule revisions:** shipped revisions parse, read only allowlisted fields, name only fold versions the metering code has, and never change an existing revision.
- **Recovery:** a restore that misses several rounds, each covering many meters, re-sends nothing; after a node set shrinks from 2 nodes to 1, a restore leaves its billed multiplier at 1.
- **Durations:** a run from 10:00:00.2 to 10:00:02.8 bills exactly 2.6 s; a dimension change at 10:00:01.5 splits it into 1.3 s and 1.3 s; a run under one second bills nothing; a positive or negative piece spanning midnight splits into one piece per day.
- **Capture:** the database triggers reject a write that skips the version bump, omits a change time, or moves one backwards.

The M360 contract test runs the Release prerequisites against a real M360 tenant.

E2E chaos tests run on a deployed hub: kill metering at random points (mid-fold, mid-round, between the Kafka acknowledgement and the outbox delete); restart and roll upgrades with two pods overlapping; restore database backups minutes and hours old while heartbeats keep flowing, and rebuild from an empty database; restart Kafka brokers and cut the network to Kafka and to PostgreSQL; delay a controller's updates for hours; jump the metering pod's clock and the database's clock, forward and back; take M360 down, and make it reject a heartbeat with an unknown dimension, then fix the cause and replay the DLQ.

Graduation: the E2E chaos suite passes repeatedly with zero billing difference, and the M360 contract test passes.

---

## Provenance

Authored: draft @ design 0.11.3 - 9b25062, workspace feat/osac-4500-quota-foundation @ 2b2a641db
Final: revise @ design 0.11.3 - 9b25062, workspace feat/osac-4500-quota-foundation @ f2afb1b17

> Context changed between draft and revise.

<!-- ai-workflow-provenance:{"schema_version":1,"provenance_kind":"session","workflow":"design","workflow_version":"0.11.3","ai_workflows":"9b25062","source_repo":"f2afb1b17","source_repo_branch":"feat/osac-4500-quota-foundation","commits_behind_main":0,"commits_ahead_main":6,"main_ref":"main","phases":["draft","manual-edit","revise","revise"],"authoring_modes":["manual","skill"],"context_changed":true,"origin_untracked":false} -->
