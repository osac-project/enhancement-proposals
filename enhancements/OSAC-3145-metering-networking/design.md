---
title: metering-for-networking-resources
authors:
  - masayag@redhat.com
creation-date: 2026-09-08
last-updated: 2026-09-09
tracking-link:
  - https://redhat.atlassian.net/browse/OSAC-3145
prd: "prd.md"
see-also:
  - "/enhancements/OSAC-985-metering-and-usage-tracking"
  - "/enhancements/OSAC-983-reliable-event-distribution"
  - "/enhancements/OSAC-2506-metering-bmaas"
  - "/enhancements/OSAC-3141-metering-storage"
replaces:
  - "N/A"
superseded-by:
  - "N/A"
---

# Metering for networking resources

## Summary
Meter ExternalIP and NATGateway allocation time through the existing pipeline. The current code has no networking mapper, no initial quantity/correction consumer, no resource-level gate, and no M360 networking contract; those are required changes, not delivered behavior. See [PRD](prd.md) for detailed requirements.

## Motivation
The event proto carries ExternalIP, ExternalIPAttachment, and NATGateway, but `BuildFilter` and `MapperForEvent` do not consume them. Fulfillment and the operator both currently write `ExternalIP.status.attached` (`fulfillment-service/internal/servers/private_external_ip_attachments_server.go:225-287`, `osac-operator/internal/controller/externalipattachment_controller.go:675-718`), so attribution can precede READY and race.

### Goals
- Bill ExternalIP from `ALLOCATED` and NATGateway from `READY` until `DELETING`.
- Attribute ExternalIP attachments only to ComputeInstance, Cluster, or BareMetalInstance.
- Define exact usage, correction, pagination, feature-gate, tenancy, failure, and adapter contracts.

### Non-Goals
VirtualNetwork/Subnet/SecurityGroup, bandwidth, pricing, quota, inventory, and UI. NATGateway is not an ExternalIPAttachment target. Its meter uses its own NATGateway ID, ExternalIP reference, VirtualNetwork reference, tenant, project, and deployment identity. CAP-6 remains a Part 1 dependency.

## Prerequisites and Gates
| Gate | Owner | Required artifact | Test evidence | Graduation gate |
|---|---|---|---|---|
| Part 1 | OSAC platform/metering | Operational projection, Kafka, retention, adapter API | Part 1 integration/retention tests | Required before events |
| Part 1 correctness | OSAC platform/metering | Version guard before publication (#818), canonical correction identity (#826), durable heartbeat idempotency (OSAC-5097), and failed-state correction/read-model/provider contract (OSAC-4287, OSAC-4285) | stale-event, replay/idempotency, and failed-state E2E tests | Required before Part 2 graduation |
| Networking API | Fulfillment/operator owners | ExternalIP attribution, attachment/state timestamps, NATGateway state timestamp, matching CRD status fields, `METERING_DEPLOYMENT_ID`, real `OUTPUT_ONLY`/`cleanapi.field.private` annotations, an acyclic shared proto, and declarative target/endpoint validation | buf/CRD generation, public-API exposure, validation, feedback, and delayed-event tests | Required before networking events |
| Transaction ordering | Fulfillment owners | Shared parent/child helper with one lock order: ExternalIP, then attachment/NATGateway, then target | concurrent attach/delete and rollback tests | Required before networking events |
| OSAC-983 | OSAC platform team | Durable outbox and resume cursor | outage replay E2E | Exact outage recovery |
| Correction/read model | Part 1 owner | Initial correction schema and consumers | apply/reverse/replay tests | No graduation without consumers |
| OSAC-984 | Storage API team | N/A to networking; no dependency claimed | scope test confirms no Volume join | No networking gate |
| Resize | Storage/CSI owners | N/A to networking; Volume-only dependency | storage gate tracked separately | No networking gate |
| M360 | Billing integration owner | `/networking/event` and initial flat payload | adapter HTTP contract test | Route/correction accepted |
| Deployment | OSAC networking/API owners | stable installer-provided `METERING_DEPLOYMENT_ID` (the OSAC installation name) | API and dimension E2E test | CAP-2 satisfied |
| CAP-6 | Part 1 owner | One reloadable `MeterResourceRegistry` consumed by Watch filters, resource loaders/reconciliation, projection/heartbeat selection, producer topic routing, and every adapter route map | add a meter without rebuild, restart, or partial-path activation | PRD config story |

`METERING_DEPLOYMENT_ID` is the stable OSAC installation name supplied by the installer, normally the Helm release name. If release names are reused across installations that share billing data, the installer qualifies the name with the namespace. The value is required, non-empty, and unchanged for the installation lifetime. Changing it starts a new metering identity; reusing another installation's value is a configuration error. Metering fails startup when the value is missing, and does not attempt central collision detection.

## Proposal
Add state timestamps, output-only ExternalIP attachment attribution, exhaustive registrations, Watch clauses, a shared transaction helper for parent exclusivity, and separate NATGateway dimensions. Fulfillment is the sole writer of settled parent state; operator parent writes and competing direct DAO mutations are removed.

### Workflow Description
1. ExternalIP starts `PENDING`; pool capacity may be reserved but usage starts only at `ALLOCATED`. NATGateway starts `PENDING`; usage starts only at `READY`.
2. An ExternalIPAttachment reaches READY through operator feedback. Fulfillment atomically persists the child state and the ExternalIP attachment attribution. NATGateway reaches READY through its own feedback; its meter reads NATGateway/VirtualNetwork dimensions and does not populate the ExternalIP attachment oneof.
3. The ExternalIP/NATGateway Delete RPC soft-deletes metadata and persists `metadata.deletion_timestamp` in its transaction. That existing timestamp is the authoritative allocation boundary; pool release and ExternalIP exclusivity/parent updates commit in the same transaction. Feedback may later report `DELETING`, but cannot move the billing boundary.
4. The mapper and reconciliation loader treat a non-nil `metadata.deletion_timestamp` as effective `DELETING` and non-billable even while status remains `ALLOCATED`/`READY`. This prevents a feedback outage after a successful Delete RPC from billing past the persisted request timestamp. Finalizer completion is not a billing boundary.
5. A feature-gate rollout must precede the Watch clause. Disabling a resource gate freezes its complete meter, not merely event intake.

### API Extensions
The following fields are prerequisites, not delivered behavior. No networking event is admitted until fulfillment-service, osac-operator, and feedback propagation tests prove them: `ExternalIPStatus.attribution`, `ExternalIPStatus.attachment_transition_time`, `ExternalIPStatus.state_transition_time`, `NATGatewayStatus.state_transition_time`, the matching operator CRD status timestamps, and the configured `METERING_DEPLOYMENT_ID`.

The fulfillment API team owns a new private `external_ip_attribution_type.proto`. It imports `buf/validate/validate.proto`, `cleanapi/cleanapi.proto`, `google/api/field_behavior.proto`, `baremetal_instance_type.proto`, `cluster_type.proto`, and `compute_instance_type.proto`; those target files do not import ExternalIP types. It defines the shared endpoint enum and message below. `external_ip_type.proto` imports only this common file; `external_ip_attachment_type.proto` imports the common file and removes its local endpoint enum. The common file never imports either ExternalIP file, so `buf lint`/generation has no cycle and both API messages share one type.
```protobuf
enum ExternalIPAttributionEndpoint {
  EXTERNAL_IP_ATTRIBUTION_ENDPOINT_UNSPECIFIED = 0;
  EXTERNAL_IP_ATTRIBUTION_ENDPOINT_API = 1;
  EXTERNAL_IP_ATTRIBUTION_ENDPOINT_INGRESS = 2;
}
message ExternalIPAttribution {
  option (buf.validate.message).cel = {
    id: "external_ip_attribution_target_id"
    message: "the selected target must have a non-empty id"
    expression: "has(this.compute_instance) ? this.compute_instance.id != '' : has(this.cluster) ? this.cluster.id != '' : this.baremetal_instance.id != ''"
  };
  option (buf.validate.message).cel = {
    id: "external_ip_attribution_endpoint"
    message: "endpoint is required only for cluster targets"
    expression: "has(this.cluster) ? this.endpoint != 0 : this.endpoint == 0"
  };
  oneof target {
    option (buf.validate.oneof).required = true;

    ComputeInstanceLocalReference compute_instance = 1;
    ClusterLocalReference cluster = 2;
    BareMetalInstanceLocalReference baremetal_instance = 3;
  }
  ExternalIPAttributionEndpoint endpoint = 4;
}
```
The proposed private API additions are:
```protobuf
message ExternalIPStatus {
  ExternalIPAttribution attribution = 7 [(google.api.field_behavior) = OUTPUT_ONLY];
  google.protobuf.Timestamp attachment_transition_time = 8 [(google.api.field_behavior) = OUTPUT_ONLY];
  google.protobuf.Timestamp state_transition_time = 9 [(google.api.field_behavior) = OUTPUT_ONLY];
}

message NATGatewayStatus {
  google.protobuf.Timestamp state_transition_time = 4 [(google.api.field_behavior) = OUTPUT_ONLY];
}
```
`endpoint` is required only for `cluster`, and is `UNSPECIFIED` otherwise. `attached` is true only for a settled `ExternalIPAttachment`; NATGateway exclusivity does not set it. NATGateway attribution is its own meter dimensions, including `spec.virtual_network`, `spec.external_ip`, and the configured deployment identity.

Only fulfillment handlers write `attribution`, `attached`, and timestamps. Operator/CRD transition timestamps are authoritative: ExternalIP and NATGateway state timestamps come from their CRD status, and `attachment_transition_time` comes from the ExternalIPAttachment transition. Fulfillment persists those timestamps unchanged; missing timestamps reject exact usage rather than falling back to feedback receipt or database transaction time. Public callers may update metadata only; `spec.*`, attribution, attached, and timestamps are rejected in update masks. The trusted operator feedback path may request a child `status.state` transition; the server compares the stored state and derives parent output fields. No caller may supply the parent output fields. Delete handlers must preserve the existing `metadata.deletion_timestamp` as the source used by the mapper, reconciler, and correction interval.

## UX Alignment
No matching networking metering file exists under `osac-ux/libs/ui-components/src/api/v1`; no UI fields are added.

### Implementation Details/Notes/Constraints
Predicates are `ExternalIP: state=ALLOCATED && metadata.deletion_timestamp == nil` and `NATGateway: state=READY && metadata.deletion_timestamp == nil`. A non-nil deletion timestamp wins over a stale state. Use exhaustive tables for every ordered pair plus empty initial state, including self-transitions. NATGateway has no current fulfillment transition validator, so every pair is tested.

For `OBJECT_UPDATED` events with a non-nil `metadata.deletion_timestamp`, networking mappers use that timestamp, expose effective state `DELETING`, and return `IsBillable=false` regardless of stale status.

`PrivateExternalIPAttachmentsServer.Update` must compare the stored child with the merged update and, when crossing into or out of READY, update the child and referenced ExternalIP in one database transaction. Its Delete transition must perform the same two-row transaction for `DELETING`; it must not call generic delete and then update the parent separately. `PrivateExternalIPsServer.Delete` and `PrivateNATGatewaysServer.Delete` must retain `metadata.deletion_timestamp` as the boundary while pool/exclusivity changes commit in that transaction. The helper locks both rows in global order: ExternalIP, then attachment or NATGateway, then target. Every direct, auto-created, default, attach, detach, and cleanup path uses that order, validates tenant and one-to-one exclusivity, sets the exact output-only message, and registers one non-empty-ID DAO callback for each direct write. Remove `syncAttachedOnParentExternalIP`, `onProvisionSuccess`, `onDeprovisionSuccess`, and all other operator-side parent writes. Default-networking direct DAO paths use the helper/callback too.

The helper covers every direct auto path, not only defaults: `private_compute_instances_server.go` VMaaS `auto_external_ip_attachment` provision/cleanup, `private_clusters_server.go` CaaS provision/cleanup, and `private_baremetal_instances_server.go` BMaaS provision/cleanup. Each path locks and updates parent and child atomically, registers a non-empty-ID callback, persists child `PENDING` with parent `attached=false`, and lets only a settled child READY update set parent state. Cleanup marks the child deleting and clears parent state through the helper. Tests assert VMaaS create/rollback/pre-READY/cleanup behavior plus the corresponding cluster, bare-metal, default, attachment, and NAT paths.

The existing attachment spec is the authoritative input oneof: `external_ip`, exactly one of `compute_instance|cluster|baremetal_instance`, and `target_endpoint` only for cluster (`fulfillment-service/proto/private/osac/private/v1/external_ip_attachment_type.proto:63-103`). It is immutable. State updates use the private update mask; parent output fields are never accepted in that mask. The mapper reads settled ExternalIP output, never joins attachment streams.

IP family comes from an ExternalIPPool lookup by immutable pool ID; a cache miss is an error. ExternalIP dimensions are resource ID, tenant, project, deployment, IP family, pool, `attached`, and settled attribution. Empty project means tenant default. NATGateway dimensions are resource ID, virtual-network reference, external-IP reference, tenant, project, and deployment. No VirtualNetwork join is needed for metering.

### Usage and Correction Contract
Current `schema.LifecycleData` has only `duration_seconds`, current `correction.go` emits v1 corrections with a nil affected interval, and `m360-adapter/translate.go` has no correction or networking route. Current code is insufficient.

The initial Part 1 contract adds canonical usage: `usage={semantics,from,to,quantity,unit,precision}`. Quantity is a fixed-point decimal string rounded half-up to six decimals. Lifecycle close events are interval deltas from `BillableSince` to `transition_time`; start events are zero-length; heartbeats are cumulative from `BillableSince` to heartbeat time and replace, not add to, the previous heartbeat. Units are exactly `resource_second` for ExternalIP/NATGateway and `gibibyte_second` for Volume.

`osac.resource.correction.v1` carries `correction_id`, `source_event_id`, reason, identity, and `affected_interval={from,to,precision,unit,adjustments[]}`. Each adjustment has stable `adjustment_id=hash(correction_id,index,sign,dimensions)`, `sign=add|subtract`, non-negative fixed-point quantity, and dimensions. The provider idempotency key is `osac-metering/<adjustment_id>`; Runner's TTL dedup is only an optimization, not correctness. One provider submission is made per adjustment, and the Kafka offset commits only after all adjustments are durable. Read models durably record adjustment IDs and replay is a no-op. `exact` requires source timestamps; `observed_upper_bound` is not exact. M360 must honor the provider key; its route and fields are a graduation gate.

One correction CloudEvent may contain multiple adjustments, but the adapter/read model emits or applies exactly one provider submission per adjustment. Every submission carries the same `correction_id` and `correction_group`, plus its unique `adjustment_id` and `provider_idempotency_key`. The consumer stores each adjustment independently and treats replay of each key as a no-op. It commits the Kafka offset only after every adjustment is durable; if any adjustment fails, the correction remains retryable, already durable adjustments are recognized by key, and retry cannot double-apply them.

The initial release registers `osac.resource.correction.v1` on `osac.metering.corrections`, provisions the existing corrections topic, subscribes adapters, and tests publisher/chart/adapter routing. Graduation is blocked until the Part 1 correction consumer and M360/read-model consumer exist.

The exact proposed M360 contract is `/api/<M360_API_VERSION>/external/run/networking/event` for both `external_ip` and `nat_gateway`, with flat fields `event_id,event_type,correction_id,adjustment_id,provider_idempotency_key,resource_id,resource_type,tenant_id,project_id,usage_semantics,interval_from,interval_to,usage_quantity,usage_unit,usage_precision,billing_dimensions,correction_group,correction_reason,correction_sign`. M360 must confirm this path, field types, provider-key idempotency, and correction behavior before implementation; current adapter behavior must not be represented as supporting it.

### Pagination, Feature Gate, and Recovery
Part 1 owns one runtime `MeterResourceRegistry` with independent tokens for `compute_instance`, `cluster_order`, `baremetal_instance`, `maas_inference`, `volume`, `external_ip`, and `nat_gateway`. `ENABLE_CAAS`, `ENABLE_VMAAS`, `ENABLE_BMAAS`, and `ENABLE_MAAS` seed their existing tokens; `METERING_RESOURCES` is additive, never a replacement and never able to disable another resource. Atomic registry reload updates producer Watch filters, clients/loaders/reconciliation, projection/heartbeats, and adapter routes together, without redeploy. List uses `total` and returned `size`, stopping only at `offset >= total`; zero size before total is a no-progress error. Total/size does not make offset pagination snapshot-safe: deleting an earlier object between pages can shift an active object behind the next offset, causing a false missed deletion. Prefer a snapshot/keyset cursor. The current API has only offset/limit, so every absent projection row requires authoritative `Get(id)` confirmation; only successful `NotFound` permits close/removal, while transient/error aborts the pass. If Get cannot be supplied, require absence in two completed passes. Add concurrent-delete/shift tests.

Registry reload is runtime, without redeployment or restart. Removing a token removes its Watch clause, loader, reconciliation, projection mutation, heartbeat, and adapter route; existing rows remain forensic state and no automatic close is claimed. Re-enable starts at current authoritative state and cannot reconstruct the disabled interval without the correction contract/OSAC-983. A token update cannot disable another resource's meter. Support must record the resulting gap.

Watch has current 1-to-30-second reconnect backoff and no replay/order guarantee (`fulfillment-service/proto/private/osac/private/v1/events_service.proto:47-53`). Reconciliation sees only objects still listed. A short-lived resource or attachment entirely inside an outage cannot be recovered exactly without OSAC-983.

### Security Considerations
Use authenticated private gRPC/Watch APIs, OPA tenancy, and existing tenant metadata. Fulfillment rejects cross-tenant targets and callers cannot forge parent output fields. Cache and transaction failures fail closed. Vendor data never enters events.

### Failure Handling and Recovery
Any child/parent transaction or callback error rolls back both rows and operator feedback retries. Row-lock conflicts return retryable `Aborted`. Stale events are version-checked and reconciliation repairs visible drift. Pool cache misses block mapping. Correction validation/apply failures go to DLQ and do not alter usage. M360 4xx is non-retryable except 408/429; 5xx/transport errors retry under Runner.

### RBAC / Tenancy
No new RBAC model. Fulfillment List/Get and OPA enforce tenant visibility; parent and child share tenant and deployment. Existing networking CRs retain `osac.openshift.io/tenant`; typed ownership relationships use `osac.openshift.io/owner-reference` where applicable. Metering adds no tenant API.

### Observability and Monitoring
Add `osac_metering_feature_enabled` Gauge `{resource_type}`; alert when expected enabled resource is 0. Add `osac_fulfillment_parent_attribution_transaction_failures_total` Counter `{resource_type,operation}`; alert on any increase in 5m. Add `osac_metering_reconciliation_list_no_progress_total` Counter `{resource_type}`; alert on any increase. Add `osac_metering_correction_applied_total` Counter `{provider,resource_type,sign}` and `osac_metering_correction_apply_failures_total` Counter `{provider,resource_type}`; alert on failures in 5m. Keep `osac_metering_heartbeat_lag_seconds{resource_type}` alerting over two intervals and `osac_metering_dlq_depth{topic}` over zero for 15m. Alert on ExternalIP `FAILED` age and pool occupancy. Log child/parent IDs, transaction outcome, event ID, correction ID, gate, and route.

### Risks and Mitigations
- NATGateway must not enter the ExternalIPAttachment target oneof; its own meter and VirtualNetwork dimensions prevent double attribution.
- Leaving operator parent writes or direct DAO writes outside the helper creates races; remove them and test rollback.
- Missing mapper/table/checker/loader/filter/gate/route can reconnect-loop the shared consumer; preflight fails startup.
- Deployment identity is not a resource field; require `METERING_DEPLOYMENT_ID` and fail closed when it is absent.
- CAP-6 configuration is not implemented by current hard-coded maps; it remains a Part 1 gate.

### Drawbacks
This changes fulfillment transaction boundaries and removes convenient operator writes. A missed Watch attachment can misattribute an interval until OSAC-983 or exact drift correction exists. Idle IPs remain billable by design.

## Alternatives (Not Implemented)
- Join attachment streams in metering: fulfillment owns relationship validity.
- Put NATGateway in the attachment oneof: contradicts the current API and PRD target set.
- Keep operator parent writes: they race fulfillment and are not authoritative.
- Meter attachments: they consume no separate allocation.
- Use NetworkClass as locality: it is a provider capability resource, not the installation identity required by the PRD.
- Add a new service/configurable registry here: Part 1 owns CAP-6 and shared infrastructure.

## Test Plan
Tests use Ginkgo v2 in `osac-metering/metering-service/internal/{events,watch,reconciliation,projection}`, `osac-metering/adapters/cmd/m360-adapter`, `fulfillment-service/internal/servers`, and `osac-operator/internal/controller`; E2E uses pytest under `tests/e2e/`. Documentation covers the event contract, routes, support, and retention.
### Unit Tests
Assert API oneof rejects NATGateway, common proto imports pass `buf lint`, update masks reject parent output fields, exact predicates/transitions, target endpoint rules, fixed-point quantity, correction sign/unit validation, gate union/reload routing, and total/progress pagination.
### Integration Tests
Assert attachment READY and Delete transitions update both rows atomically; force each DAO failure and assert rollback; exercise VMaaS `auto_external_ip_attachment` create/rollback/pre-READY/cleanup plus cluster, bare-metal, default, attachment, and NAT auto paths; call ExternalIP/NAT Delete successfully, delay feedback, and assert usage closes at `metadata.deletion_timestamp` rather than feedback time; assert no operator parent writes, non-empty event IDs, correction topic/chart/adapter routing, one provider submission per adjustment, shared correction/group IDs, unique adjustment/provider keys, per-adjustment durable replay no-ops, offset commit only after all adjustments, retry after partial failure without double application, NAT dimensions, cache failures, correction apply/reverse, concurrent-delete/shift Get confirmation, and M360 flat payload routing.
### E2E Tests
Exercise unattached ExternalIP, ComputeInstance/Cluster API/Ingress/BareMetal attachments, detach, NATGateway with VirtualNetwork dimensions, excluded VirtualNetwork/Subnet/SecurityGroup negative cases, failures/retries, duplicate replay, Kafka/DLQ, gate reload/disable/re-enable, and resource-seconds totals.

## Graduation Criteria
Target release 0.3. Graduation requires Part 1, OSAC-983, the initial correction/read-model/M360 consumers, deployment identity, CAP-6, and heartbeat sizing gates close. Then require exact allocation totals, transactionally consistent attribution, no NAT attachment target, all event IDs, pagination confirmation, correction replay, ExternalIP FAILED-age alerting, the negative test for excluded network objects, retention/dedup parity, and no existing meter regression.

## Upgrade / Downgrade Strategy
The 0.3 release ships the fulfillment fields/helper, removes operator writers, adds generated clients and metering registrations, confirms the M360 contract, and enables resource tokens. This is the initial event contract; no existing event data requires migration.

## Version Skew Strategy
All 0.3 components use the same initial event contract and transaction helper. An operator that writes parent state or an adapter without correction handling is unsupported.

## Support Procedures
Check feature gauges, transaction failures, operator forbidden-write logs, child/parent versions, pool cache, list progress, projection dimensions, correction IDs/signs, heartbeat lag, Kafka/DLQ, and M360 responses. Disable the resource token, not only the Watch filter, and record the gap. Never edit parent output state or remove finalizers manually.

## Infrastructure Needed
Existing Postgres, Kafka/AMQ Streams, fulfillment Watch, metering, and M360 are required. No new service is proposed. Helm documentation covers `METERING_DEPLOYMENT_ID`, topic provisioning, event fields, support, and retention. Add transaction-conflict, callback, pagination, deployment, correction, and M360 networking fixtures. Raw events retain at least seven days and aggregates at least thirteen months.
