---
title: metering-for-block-storage
authors:
  - ovishlit@redhat.com
creation-date: 2026-09-08
last-updated: 2026-09-09
tracking-link:
  - https://redhat.atlassian.net/browse/OSAC-3141
prd: "prd.md"
see-also:
  - "/enhancements/OSAC-985-metering-and-usage-tracking"
  - "/enhancements/OSAC-983-reliable-event-distribution"
  - "/enhancements/OSAC-2506-metering-bmaas"
  - "/enhancements/OSAC-3145-metering-networking"
replaces:
  - "N/A"
superseded-by:
  - "N/A"
---

# Metering for block storage

## Summary
Meter standalone block Volumes through the existing Watch, projection, reconciliation, heartbeat, Kafka, and adapter pipeline. The current code has no Volume mapper, no quantity contract, and no usable correction consumer; this design specifies those changes and gates graduation on their delivery. See [PRD](prd.md) for detailed requirements.

## Motivation
The shared metering API currently maps only ComputeInstance and ClusterOrder (`osac-metering/metering-service/internal/events/mapper.go:102-117`), and its Watch filter requests only those payloads (`internal/watch/consumer.go:48-57`). Block Volume metering therefore requires a new Volume event and metering path.

### Goals
- Bill logical block capacity from `AVAILABLE` until the durable platform deletion request.
- Make state, quantity, unit, correction, pagination, feature-gate, and adapter behavior deterministic.
- Preserve tenant isolation, existing meters, and Part 1 retention/deduplication.

### Non-Goals
File/object/NFS metering, pricing, quota, UI, provider physical-byte usage, and parent attribution. OSAC-984 owns the Volume API reference; OSAC-4884 owns the separate attach/detach lifecycle follow-up; OSAC-2506 owns the bare-metal host footprint.

## Prerequisites and Gates
| Gate | Owner | Required artifact | Test evidence | Graduation gate |
|---|---|---|---|---|
| Part 1 | OSAC platform/metering | Operational projection, Kafka, retention, provider adapter API, and canonical initial `v1` usage/correction contract | Part 1 integration and retention tests | Required before any Volume event |
| Part 1 correctness | OSAC platform/metering | Version guard before publication (#818), canonical correction identity (#826), durable heartbeat idempotency (OSAC-5097), cross-resource external-operation idempotency and completion contract ([OSAC-5116](https://redhat.atlassian.net/browse/OSAC-5116)), and failed-state correction/read-model/provider contract (OSAC-4287, OSAC-4285) | stale-event, replay/idempotency, deletion retry/boundary, and failed-state E2E tests | Required before Part 2 graduation |
| CAP-6 registry | OSAC platform/metering | Shared `MeterResourceRegistry` includes `volume` in Watch filters, loaders/reconciliation, projection/heartbeat selection, topic routing, and adapter routes | add `volume` without rebuild/restart or partial-path activation | Required before any Volume event |
| Parent attribution follow-up | OSAC-984/OSAC-4884 owners | Typed parent reference and attach/detach lifecycle contract | VM, cluster, and bare-metal attribution tests | Separate follow-up; not required for core storage metering |
| OSAC-983 | OSAC platform team | Durable mutation outbox and resume cursor | Watch outage replay E2E | Exact short-lived accuracy |
| Correction/read model | Part 1 owner | Initial correction schema and consumer | Apply/reverse/replay contract tests | No graduation without consumer |
| Volume lifecycle enforcement | Fulfillment/operator owners | Status-only field masks, CAS/version checks, write-once vendor ID, terminal-state rejection, and durable deletion boundary | stale feedback, concurrent update, terminal regression, and deletion-boundary tests | Required before any Volume event |
| State timestamp contract | Fulfillment/operator owners | Single-writer transition timestamps on actual state changes, stable across no-op reconciles ([OSAC-5001](https://redhat.atlassian.net/browse/OSAC-5001), [OSAC-4445](https://redhat.atlassian.net/browse/OSAC-4445)) | state-change and no-op feedback tests | Required before any Volume event |
| Vendor cleanup | Storage/operator owners | Idempotent delete keyed by volume/vendor ID, `NotFound` cleanup semantics, and finalizer retention until cleanup | vendor success, retry, timeout, `NotFound`, and finalizer tests | No backend leaks |
| Project attribution | fulfillment-service/storage API owners | Populate the existing `Metadata.project` field from the authoritative project source; project is a billing dimension, not a project-level volume access-control feature | two-project CreateVolume, default-project, cross-tenant, and mismatched-project tests | Required before any Volume event |
| M360 integration | M360 integration team | OSAC-4285 confirms the storage route, flat payload, normal-event idempotency, and correction contract | adapter HTTP and E2E contract tests | Required before routing storage events to M360; not required for core storage metering |

The current metering schema code is pre-release scaffolding, not a supported external contract. The canonical usage object and correction contract become the initial supported `v1` contract. All Part 1 producers, schema types, projection code, correction consumers, and adapters must adopt it together before Volume events are enabled. No migration or old/new coexistence is required. Future breaking changes increment the event version.

Project attribution is a prerequisite: the existing `Metadata.project` field must be populated before any Volume event claims project breakdown.

## Proposal
Operator feedback is the single writer of output-only `state_transition_time` on actual state changes; fulfillment persists the timestamp unchanged. Fulfillment owns write-once `vendor_volume_id` enforcement. The operator gates `AVAILABLE` on a non-empty vendor ID and persists `DELETED` only after vendor deletion succeeds. Metering adds Volume mapper, transitions, checker, loader, Watch clause, projection/heartbeat support, and a gated storage adapter route.

### Workflow Description
1. The tenant-cluster storage client receives `osac.project` from the StorageClass/CreateVolume parameters and forwards it to fulfillment-service in `CreateVolumeParams`. Fulfillment-service validates the tenant and project scope, then persists `Metadata.project`; empty means the tenant default. The tenant-cluster storage client creates `CREATING` with the selected tier and initial `size_gib`. No interval opens.
2. The operator writes the vendor ID once and reports `AVAILABLE` only with that ID. Operator feedback stamps `state_transition_time` when the state changes and leaves it unchanged on no-op reconciles; metering opens at that timestamp for block protocol.
3. `FAILED` closes only an already billable interval. `CREATING` or failed-without-ID never bills. `DELETING` is not billable, even when the vendor ID is present.
4. Fulfillment durably records `metadata.deletion_timestamp` and effective state `DELETING` in one versioned mutation. The resulting `OBJECT_UPDATED` event includes both fields; no timestamp-only `AVAILABLE -> AVAILABLE` update is used for deletion. That event closes the metering interval. The operator then deletes the vendor volume, writes `phase=Deleted`, and retains both finalizers until cleanup succeeds. Feedback writes proto `DELETED`; a later reconcile removes the resource finalizer. Vendor cleanup after the deletion request is not part of the initial usage interval.
5. A feature-gate rollout must be applied before enabling the Watch clause; disabling freezes this resource meter as described below.

For a deletion-request event, the Volume mapper uses `metadata.deletion_timestamp` as the close boundary regardless of `state_transition_time`. For every other state transition, it uses `state_transition_time`. The mapper emits at most one close for a resource version.

### API Extensions
- Add private output-only `VolumeStatus.state_transition_time`; operator feedback stamps it on actual state changes, and fulfillment persists it unchanged.
- Require the existing project field to be populated: the tenant-cluster storage client may forward an `osac.project` request value, and fulfillment-service persists it as `Metadata.project`. The Volume mapper and reconciliation loader read this metadata field. No Volume event is admitted as project-attributed until this contract and its tests are complete.
- Enforce write-once, output-only `vendor_volume_id`; reject clear/replace attempts and gate `AVAILABLE` in operator feedback.
- Add CRD `VolumePhaseDeleted`; vendor-delete success, status persistence, feedback update, and finalizer removal are separate writes.
- Add schema constant, mapper, exhaustive transition/checker/loader registrations, Watch clause, projection/heartbeat switch, and adapter route. Current maps are code, not runtime configuration.

```proto
message VolumeStatus {
  google.protobuf.Timestamp state_transition_time = 8 [(google.api.field_behavior) = OUTPUT_ONLY];
}
```

## UX Alignment
The UI reference contains a temporary Volume API at `osac-ux/libs/ui-components/src/api/v1/block-volumes.ts`. It is a predicted public API, not a metering contract. OSAC-3141 adds no UI fields or UI behavior.

| Temporary UI field | Volume API relation | Notes |
|---|---|---|
| `id` | `Volume.id` | Same resource identifier. |
| `metadata.name` | `Volume.metadata.name` | User-provided volume name. |
| `spec.sizeGib` | `Volume.spec.size_gib` | Same capacity value with different casing. |
| `spec.storageClass` | `Volume.spec.storage_tier` | Temporary UI naming; the API resolves the tier to backend and protocol. |
| `status.state` | `Volume.status.state` | The temporary UI states need API-specific mapping; metering does not define that mapping. |
| `status.attachedTo` | Future parent association | Parent reference is owned by OSAC-984; attach/detach lifecycle is owned by OSAC-4884; metering does not add either. |

### Implementation Details/Notes/Constraints
Billability is the same object-aware predicate in Watch, reconciliation, projection, and heartbeat: `protocol == BLOCK && vendor_volume_id != "" && state == AVAILABLE && metadata.deletion_timestamp == nil`. `FAILED`, `DELETING`, `DELETED`, `CREATING`, ID-less `DELETING`, NFS, and unspecified protocol are non-billable. Exhaustive tests cover every ordered pair of all six Volume states plus empty initial state, including self-transitions; the design does not require hand-listing the 42 rows.

The following table defines every `OBJECT_UPDATED` state pair. `projection-only` updates the projection without a billing event. `started.v1` opens billing at `state_transition_time` when the object-aware predicate is true; otherwise it is projection-only. `updated.v1` is emitted only when billing dimensions change, closing the old interval and opening the new one at the resize effective timestamp. `suspended.v1` closes billing at the stated timestamp. `reject` rejects the update as a stale or invalid regression.

| From | To | Event | Billing effect |
|---|---|---|---|
| Initial | `UNSPECIFIED` | projection-only | No billing |
| Initial | `CREATING` | projection-only | No billing |
| Initial | `AVAILABLE` | `started.v1` | Open at `state_transition_time` if billable |
| Initial | `FAILED` | projection-only | No billing |
| Initial | `DELETING` | projection-only | No billing |
| Initial | `DELETED` | projection-only | No billing |
| `UNSPECIFIED` | `UNSPECIFIED` | projection-only | No billing |
| `UNSPECIFIED` | `CREATING` | projection-only | No billing |
| `UNSPECIFIED` | `AVAILABLE` | `started.v1` | Open at `state_transition_time` if billable |
| `UNSPECIFIED` | `FAILED` | projection-only | No billing |
| `UNSPECIFIED` | `DELETING` | projection-only | No billing |
| `UNSPECIFIED` | `DELETED` | projection-only | No billing |
| `CREATING` | `UNSPECIFIED` | reject | No billing |
| `CREATING` | `CREATING` | projection-only | No billing |
| `CREATING` | `AVAILABLE` | `started.v1` | Open at `state_transition_time` if billable |
| `CREATING` | `FAILED` | projection-only | No billing |
| `CREATING` | `DELETING` | projection-only | No billing |
| `CREATING` | `DELETED` | projection-only | No billing |
| `AVAILABLE` | `UNSPECIFIED` | reject | No billing |
| `AVAILABLE` | `CREATING` | reject | No billing |
| `AVAILABLE` | `AVAILABLE` | `updated.v1` or projection-only | Close/open only when dimensions change |
| `AVAILABLE` | `FAILED` | `suspended.v1` | Close at `state_transition_time` |
| `AVAILABLE` | `DELETING` | `suspended.v1` | Close at `metadata.deletion_timestamp` |
| `AVAILABLE` | `DELETED` | `suspended.v1` | Close at `metadata.deletion_timestamp` |
| `FAILED` | `UNSPECIFIED` | reject | No billing |
| `FAILED` | `CREATING` | reject | No billing |
| `FAILED` | `AVAILABLE` | reject | No billing |
| `FAILED` | `FAILED` | projection-only | No billing |
| `FAILED` | `DELETING` | projection-only | No billing |
| `FAILED` | `DELETED` | projection-only | No billing |
| `DELETING` | `UNSPECIFIED` | reject | No billing |
| `DELETING` | `CREATING` | reject | No billing |
| `DELETING` | `AVAILABLE` | reject | No billing |
| `DELETING` | `FAILED` | reject | No billing |
| `DELETING` | `DELETING` | projection-only | No billing |
| `DELETING` | `DELETED` | projection-only | No additional boundary |
| `DELETED` | `UNSPECIFIED` | reject | No billing |
| `DELETED` | `CREATING` | reject | No billing |
| `DELETED` | `AVAILABLE` | reject | No billing |
| `DELETED` | `FAILED` | reject | No billing |
| `DELETED` | `DELETING` | reject | No billing |
| `DELETED` | `DELETED` | projection-only | No billing |

`OBJECT_CREATED` must contain `CREATING`; fulfillment rejects or prevents an `OBJECT_CREATED` event with `AVAILABLE` or any other state. It emits the existing `created.v1` audit event and seeds projection state; it does not open billing. The `Initial -> AVAILABLE` table row applies only to a first `OBJECT_UPDATED` or authoritative reconciliation snapshot, not to `OBJECT_CREATED`. `OBJECT_DELETED` emits the existing `deleted.v1` audit event; it does not create another billing boundary. Missing timestamps, a missing vendor ID, NFS, and an unspecified protocol suppress billing and fail exact event processing rather than inventing a boundary.

Initial usage dimensions are `volume_id`, `tenant_id`, `project_id`, `storage_tier`, and `size_gib`. Parent attribution is a follow-up owned by OSAC-984/OSAC-4884. `protocol` is an internal block/NFS eligibility check, while `backend` and `vendor_volume_id` stay out of usage events.

Write-once means a non-empty vendor ID can only be repeated identically. `FAILED` before an ID creates no interval. `AVAILABLE -> FAILED` closes at the state timestamp. `AVAILABLE -> DELETING` closes at durable `metadata.deletion_timestamp`. `DELETING -> DELETED` has no additional billing boundary. `DELETED` never reopens. Finalizer removal must never share the persisted update that writes `DELETED`; otherwise DAO archive happens before the close event.

The current CRD has no `Deleted` phase, the controller removes its finalizer after delete, and feedback reports only `DELETING` (`osac-operator/api/v1alpha1/volume_types.go:71-79`, `internal/controller/volume_controller.go:280-323`, `volume_feedback_controller.go:122-130`). Both are required changes. `DeleteVolume` must be idempotent and keyed by volume/vendor ID so retries do not leak backend volumes. A vendor `NotFound` response is cleanup success only after the delete operation is known to be idempotent. If cleanup fails, the finalizer remains and the resource stays `DELETING`; the metering interval remains closed at `metadata.deletion_timestamp`. A missing vendor ID must still be listed for reconciliation; filtering it out would manufacture missed-deletion corrections.

### Usage and Correction Contract
Current `schema.LifecycleData` has `duration_seconds` only (`osac-metering/schema/lifecycle.go:18-30`), and `correction.go` passes `affected_interval=nil`; current adapters do not apply corrections. They are insufficient.

The initial Part 1 contract adds the canonical usage object:
```json
{"usage":{"semantics":"interval","from":"2026-09-10T10:00:00.000000Z","to":"2026-09-10T10:01:00.000000Z","quantity":"12.500000","unit":"gibibyte_second","precision":"microsecond"}}
```
`from` and `to` are RFC3339 UTC timestamps normalized to microsecond precision; `from` is inclusive and `to` is exclusive. `quantity` is a fixed-point decimal string rounded half-up to six decimals. Lifecycle close events use `semantics=interval`, `from=BillableSince`, `to=transition_time` or the durable deletion-request timestamp, and quantity `size_gib * seconds`; start events use a zero interval. Heartbeats use `semantics=cumulative` from `BillableSince` to event time and replace the prior heartbeat, never add to it. Storage units are exactly `gibibyte_second`; networking uses `resource_second`. This is exact for the selected deletion-request boundary, not for physical vendor release time.

`osac.resource.correction.v1` carries `correction_id`, `source_event_id`, reason, resource identity, and `affected_interval`: `{from,to,precision,unit,adjustments[]}`. Each adjustment has stable `adjustment_id=hash(correction_id,index,sign,dimensions)`, `sign=add|subtract`, non-negative fixed-point quantity, and billing dimensions. The provider idempotency key is `osac-metering/<adjustment_id>`. A correction with multiple adjustments produces one provider submission per adjustment and commits its Kafka offset only after all adjustments are durable. The Part 1 correction consumer is required for core storage metering. OSAC-4285 owns M360 confirmation and the storage route `/api/<M360_API_VERSION>/external/run/storage/event`; storage events are not routed there until that prerequisite passes.

Resize uses the existing dimension-update path. A successful expansion updates `size_gib` and emits `updated.v1` with the committed new logical capacity and effective timestamp. Metering closes the old interval and opens the new one at that timestamp. Failed or reverted expansions do not change billing dimensions.

### Pagination, Feature Gate, and Recovery
Part 1 owns one runtime `MeterResourceRegistry` with independent tokens for `compute_instance`, `cluster_order`, `baremetal_instance`, `maas_inference`, `volume`, `external_ip`, and `nat_gateway`. `ENABLE_CAAS`, `ENABLE_VMAAS`, `ENABLE_BMAAS`, and `ENABLE_MAAS` seed their existing tokens; `METERING_RESOURCES` is an additive token set, never a replacement and never able to disable another resource. Atomic registry reload updates producer Watch clauses, loaders/reconciliation, projection/heartbeat selection, and adapter route selection together. `volume` adds `has(event.volume)`. List requests `limit=500`, advances by returned `size`, and stops only at `offset >= total`; zero size before total is an error. Total/size does not make offset pagination snapshot-safe: if an earlier Volume is deleted between pages, a later active Volume can shift behind the next offset and appear absent. Prefer a server snapshot/keyset cursor. The current API has only offset/limit, so every projection row absent from the collected map must receive authoritative `Get(id)` confirmation; only `NotFound` after a successful Get permits missed-deletion correction/removal, while transient/error aborts the pass. If a resource client cannot provide Get, require absence in two completed passes. Add concurrent-delete/shift tests.

Registry reload is runtime, without redeployment or restart. Removing `volume` removes its filter, loaders/reconciliation, projection/heartbeat selection, and adapter route; existing rows remain for forensics and no automatic close is claimed. Re-enable starts from current authoritative state and cannot reconstruct the disabled interval without the correction contract/OSAC-983. Registry updates are per-token, so a Volume change cannot disable CaaS/VMaaS/BMaaS/MaaS. Support must treat the gap as a billing incident, not silently resume it.

Watch reconnects use current 1-to-30-second backoff, but the API promises no replay/order (`fulfillment-service/proto/private/osac/private/v1/events_service.proto:47-53`). Reconciliation repairs visible resources only. A Volume created and archived during an outage cannot be recovered exactly without OSAC-983.

### Security Considerations
Use authenticated private Watch/gRPC APIs and fulfillment OPA tenancy. Metering never accepts tenant dimensions from callers. Vendor IDs, credentials, and vendor context stay out of events. New fields are output-only and server-validated.

### Failure Handling and Recovery
DAO transaction/callback failure rolls back object and event. Vendor delete failure retains finalizers, but the metering interval is already closed at `metadata.deletion_timestamp`. Projection upsert failure after publish replays with deterministic IDs. Correction publish/apply failure blocks projection correction and retries; malformed corrections go to DLQ and never become ordinary usage. Pagination no-progress fails reconciliation. Feature disable leaves an explicit gap.

### RBAC / Tenancy
No new tenant-facing authorization. Volume is private until OSAC-984's tenant API. Fulfillment controls List/Get visibility; operator CRs remain namespace-scoped with existing tenant metadata. OSAC-984 parent fields must be typed, and OSAC-4884 attach/detach operations must use tenant/owner-reference annotations with OPA enforcement.

### Observability and Monitoring
Add `osac_metering_feature_enabled` Gauge `{resource_type}`; alert when expected enabled resource is 0. Add `osac_metering_reconciliation_list_no_progress_total` Counter `{resource_type}`; alert on any increase. Add `osac_metering_correction_applied_total` Counter `{provider,resource_type,reason,sign}` and `osac_metering_correction_apply_failures_total` Counter `{provider,resource_type}`; alert on failures in 5m. Keep `osac_metering_reconciliation_corrections_total{reason,resource_type}` and `osac_metering_heartbeat_lag_seconds{resource_type}`; alert lag over two intervals. Alert `osac_metering_dlq_depth{topic}` above zero for 15m and `DELETING` cleanup age over the configured threshold. Log gate, version, quantity, interval, correction ID, and route.

### Risks and Mitigations
- Missing mapper/table/checker/loader/filter/gate/route can stop the shared consumer; preflight fails startup.
- State-only reconciliation can bill ID-less Volumes; every path uses the object-aware predicate.
- Part 1 drift repair lacks component timestamp reset; expose observed precision and block exact claims.
- Heartbeats can dominate storage; size Postgres/Kafka before enabling Volume.

### Drawbacks
This spans fulfillment-service, operator, tenant-cluster storage client, metering, adapters, M360, and OSAC-984. A stuck vendor deletion can leak backend capacity without extending the metering interval. Feature disable is not a repair and creates a documented gap.

## Alternatives (Not Implemented)
- Use vendor release time: requires a vendor timestamp contract that the current storage API does not provide.
- Bill by state only: bills ID-less or failed provisions.
- Filter ID-less objects: creates false missed-deletion corrections.
- Use archival time: archive depends on finalizers, not vendor release.
- Add a separate service: Part 1 owns projection, Kafka, retention, and adapters.

## Test Plan
Tests use Ginkgo v2 in `osac-metering/metering-service/internal/{events,watch,reconciliation,projection}` and `osac-metering/adapters/cmd/m360-adapter`; fulfillment-service/server and operator tests use their existing Ginkgo suites; the OSAC CSI driver uses `osac-csi-driver/pkg/driver/controller_test.go`; E2E uses pytest under `tests/e2e/`. Documentation covers the event contract, operator support procedure, and storage route.
### Unit Tests
Assert all Volume transitions, write-once ID, empty-ID/FAILED/DELETING/DELETED predicates, fixed-point quantity, interval/cumulative semantics, correction sign/unit validation, and shared registry union/reload routing.
### Integration Tests
Assert two-pass deletion, deletion-request boundary at `t0`, delayed feedback after `t1` does not extend usage past `t0`, vendor cleanup retry and `NotFound` behavior, tenant-cluster project A/B propagation and default-project behavior, stopped-VM usage, successful and failed/reverted resize, provisioning non-disruption, transaction rollback, correction apply/reverse/replay with one provider submission per adjustment, shared correction/group IDs, unique adjustment/provider keys, per-adjustment durable replay no-ops, offset commit only after all adjustments, retry after partial failure without double application, event IDs, correction topic/chart routing, concurrent pagination confirmation, no-progress failure, and loader/projection/heartbeat gate behavior. OSAC-4285 owns M360 flat-payload translation and routing tests; follow-up owners cover parent attribution tests.
### E2E Tests
Provision block/NFS Volumes, verify GiB-seconds and retention, replay corrections through Echo, test DLQ, disable/restart/re-enable the gate, and assert the documented outage gap. OSAC-4285 covers M360 storage replay after its integration gate passes.

## Graduation Criteria
Target release 0.3. Graduation requires Part 1, OSAC-984, OSAC-983, the initial correction/read-model consumer, and exact create-to-deletion-request usage, including resize interval boundaries. It also requires no ID-less billability, correction replay correctness, pagination confirmation, feature-gate consistency, retention, stopped-VM coverage, provisioning non-disruption, and no existing meter regression. Parent attribution is a separate follow-up. M360 integration is a separate OSAC-4285 gate.

## Upgrade / Downgrade Strategy
The 0.3 release ships the fulfillment fields, operator lifecycle, generated clients, metering registrations, and correction consumer as the initial storage contract. OSAC-4285 ships the M360 route separately. No existing event data requires migration.

## Version Skew Strategy
All 0.3 components use the same initial event contract. A controller unable to write `Deleted` or an adapter unable to apply corrections is unsupported.

## Support Procedures
Check gate state, Watch filter, mapper/transition errors, ID-less resources, open `DELETING`, projection versions, list progress, correction IDs/signs, heartbeat lag, Kafka/DLQ, and M360 responses. Disable the resource gate, not only the filter, and record the resulting usage gap. Never delete projection rows or finalizers manually.

## Infrastructure Needed
Existing Postgres, Kafka/AMQ Streams, fulfillment Watch, and metering are required for core storage metering. M360 is required only for the separate OSAC-4285 integration. No new service is proposed. Helm documentation covers topic provisioning, event fields, support, and retention. Size projection rows, raw events for seven days, aggregates for thirteen months, and heartbeat load per PVC.

---

## Provenance

Committed: commit @ design 0.9.0 - ae9e30e, workspace main @ ca86831

> Authoring phases not recorded this session (commit-time snapshot only).

<!-- ai-workflow-provenance:{"schema_version":1,"provenance_kind":"commit_only","workflow":"design","workflow_version":"0.9.0","ai_workflows":"562b610","source_repo":"ca86831","source_repo_branch":"main","commits_behind_main":0,"commits_ahead_main":2,"main_ref":"main","phases":["commit"],"authoring_modes":["commit"],"context_changed":true,"origin_untracked":false} -->
