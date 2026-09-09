---
title: metering-bmaas
authors:
  - amoren@redhat.com
creation-date: 2026-08-19
last-updated: 2026-09-08
tracking-link:
  - https://redhat.atlassian.net/browse/OSAC-2506
prd:
  - "prd.md"
see-also:
  - "/enhancements/OSAC-985-metering-and-usage-tracking"
  - "/enhancements/OSAC-2675-bare-metal-instance-type"
replaces:
  - N/A
superseded-by:
  - N/A
---

# BMaaS Metering (Part 2a)

## Summary

This design extends the OSAC Metering Service to meter bare metal hosts using a dual-meter event decomposition model: an allocation meter (`bare-metal-instance-type-seconds`) that runs from provisioning complete until the host enters `FAILED` or is deleted, regardless of power state, and a consumption meter (`bare-metal-compute-seconds`) that runs only while the host is powered on. A host in `FAILED` state is never billable for either meter. The design reuses the Part 1 metering infrastructure (Watch Consumer, State Projection, Heartbeat Generator, Reconciliation Loop, Kafka, Provider Adapters) and introduces a per-meter event decomposer that produces independent CloudEvent streams for each meter from a single Watch event. See [PRD](prd.md) for detailed requirements.

## Motivation

Part 1 (OSAC-985) established OSAC metering for VMaaS and CaaS — both consumption-based meters where `IsBillable` maps to a single boolean: `RUNNING` for VMs, `PROGRESSING`/`READY` for clusters. Bare metal hosts have a fundamentally different capacity profile. A bare metal host occupies physical rack space, a power port, and related networking infrastructure from the moment it is provisioned until it enters `FAILED` or is deleted — regardless of whether the tenant has powered it on. This physical capacity commitment has no equivalent in VMaaS (where stopped VMs release compute) or CaaS (where clusters are always running or failed).

The Part 1 design states that "_the canonical event model supports future resource types without architectural changes._" This holds for single-meter resources — adding BMaaS consumption-only metering would follow the exact `ComputeInstance` pattern. The dual-meter model is the exception: the existing single-boolean `IsBillable` projection, the single transition table per resource type, and the single-event-per-transition assumption all require targeted extensions. This design proposes those extensions while preserving backward compatibility with existing VMaaS and CaaS metering.

### Goals

1. **Reuse Part 1 infrastructure** — no new services, Kafka topics, or deployment artifacts; BMaaS metering is a code-level extension of the existing metering-service and adapter framework
2. **Extend, don't replace, the event decomposition pattern** — the CaaS `N+1` per-component decomposer is the precedent; BMaaS adds a per-meter decomposer that produces independent CloudEvent streams with independent event types
3. **Allocation and consumption meters are independently queryable** — each meter has a distinct `meter_type` billing dimension, so downstream systems can filter, aggregate, and price them separately
4. **No new metering API surface** — the existing `Events.Watch` stream carries the `spec.instance_type` reference introduced by [OSAC-1201](https://redhat.atlassian.net/browse/OSAC-1201); the fulfillment controller now exposes and populates `BareMetalInstanceStatus.state_transition_time` through merged [OSAC-4969](https://redhat.atlassian.net/browse/OSAC-4969)

### Non-Goals

- Storage and networking metering for resources attached to bare metal hosts ([OSAC-3141](https://redhat.atlassian.net/browse/OSAC-3141), [OSAC-3145](https://redhat.atlassian.net/browse/OSAC-3145))
- Usage Query API implementation or tenant-facing usage views; this design defines the event contract and unified-footprint semantics that a query implementation consumes
- Costing, billing, or quota enforcement
- Changes to the `BareMetalInstance` provisioning or lifecycle workflow

## Terminology

**Allocation Meter** — A billing stream that tracks capacity commitment for a bare metal host from provisioning complete (`RUNNING`, `STOPPED`, `STARTING`, `STOPPING`, and in-progress `DELETING` states) until the host enters `FAILED` or is confirmed deleted. Runs continuously across power cycles and deletion finalization while the host is not `FAILED`. Represents the physical rack space, power port, and networking infrastructure reserved by the provider for the tenant.

**Consumption Meter** — A billing stream that tracks actual compute usage for a bare metal host. Runs only when the host is powered on (`RUNNING` state). Independent of allocation; enables providers to charge separately for reserved capacity vs. active consumption.

**Billable State** — A resource state that incurs metering charges. Distinct per meter: allocation-billable states are `RUNNING`, `STOPPED`, `STARTING`, `STOPPING`, and in-progress `DELETING` (the host remains reserved); consumption-billable state is `RUNNING` only (the host is powered on). `FAILED` is non-billable for both meters, so no metering charges accrue while a host is in `FAILED` state.

**Transition Table** — A state machine table defining which state transitions trigger meter events (started, suspended, resumed). Independent transition table per meter; evaluated for each Watch event to determine which CloudEvents to produce.

**Event Decomposer** — A function that evaluates multiple transition tables (allocation + consumption) against a single Watch event and produces up to two CloudEvents, each with its own event type and meter-specific billing dimensions. BMaaS decomposer extends the CaaS precedent (N+1 per-component decomposition).

**Meter Type** — A billing dimension (`meter_type`) that discriminates between allocation and consumption events. Enables downstream systems to filter, aggregate, and price each meter independently. Carried in CloudEvent `billing_dimensions`, not as a CloudEvent extension attribute.

**Billing Dimensions** — Structured metadata attached to CloudEvents that describe resource attributes for billing purposes. BMaaS includes: `meter_type` (allocation or consumption), `bm_instance_type` (e.g., gpu-large), `catalog_item` (e.g., bmi-gpu-workstation).

**State Projection** — A PostgreSQL-backed runtime view of resource state. Tracks `IsBillable`, `CurrentState`, `BillableSince`, and per-component billable timestamps (`ComponentBillableSince`). Used by the Heartbeat Generator to determine which resources are metering and the Watch Consumer to detect transitions.

**Watch Event** — A streaming event from the fulfillment-service when a resource's state changes. The Watch Consumer consumes `BareMetalInstance` Watch events, evaluates transition tables, and publishes CloudEvents to Kafka.

**CloudEvent** — A standardized event format (CNCF spec) published to Kafka. BMaaS CloudEvents include: event type (_e.g._, `osac.resource.started.v1`), meter-specific billing dimensions, tenant attribution, resource IDs, and timestamps. Consumed by provider adapters for billing integration.

**BareMetalInstanceType** — An OSAC resource that identifies a provider-defined bare metal hardware configuration. A `BareMetalInstance` references it through `spec.instance_type`; the reference is the primary pricing dimension for allocation and consumption meters.

## Proposal

The design introduces four changes to the metering-service codebase:

1. `bareMetalInstanceMapper` — a new `ResourceMapper` implementation that extracts metering data, including the `BareMetalInstanceType` reference, from `BareMetalInstance` Watch events, with `IsBillable()` returning allocation-billable (the broader meter)
2. **Dual-meter event decomposer** — a new `EventDecomposer` that evaluates two independent transition tables (allocation and consumption) per Watch event and produces up to two CloudEvents, each with its own CloudEvent type and `meter_type` billing dimension
3. **Extended reconciliation** — a `BareMetalInstancesClient` and loader for the hourly reconciliation loop, with a billability checker that uses the allocation meter's state set
4. **M360 adapter route** — a `/bmaas/event` endpoint that passes the `meter_type` billing dimension through to the M360 Usage API

No new Kafka topics, no State Projection schema changes, no new deployment artifacts. The existing `osac.metering.lifecycle`, `osac.metering.heartbeat`, and `osac.metering.corrections` topics carry BMaaS events alongside VMaaS and CaaS events, differentiated by the `osacresourcetype` extension attribute (`bare_metal_instance`). Kafka's 30-day retention replays BMaaS events after they have been published, but cannot recover a transition that the fulfillment `Events.Watch` stream never delivered. Provider adapters persist published usage data for at least 13 months via their respective storage backends.

### Workflow Description

#### BMaaS Host Lifecycle — Dual-Meter Metering

When a Tenant Admin provisions a bare metal host, the Metering Service tracks both meters independently:

```mermaid
sequenceDiagram
    participant FS as Fulfillment Service
    participant WC as Watch Consumer
    participant SP as State Projection
    participant KP as Kafka Publisher
    participant HG as Heartbeat Generator
    participant K as Kafka

    FS->>WC: OBJECT_CREATED (state=PROVISIONING)
    WC->>SP: upsert(resource_id, state=PROVISIONING, is_billable=false)
    WC->>KP: osac.resource.created.v1
    KP->>K: publish → osac.metering.lifecycle

    FS->>WC: OBJECT_UPDATED (state=RUNNING)
    WC->>SP: read previous_state=PROVISIONING
    WC->>SP: upsert(state=RUNNING, is_billable=true, billable_since=state_transition_time)
    Note right of WC: Decomposer evaluates both meters
    WC->>KP: osac.resource.started.v1 (meter_type=allocation)
    WC->>KP: osac.resource.started.v1 (meter_type=consumption)
    KP->>K: publish → osac.metering.lifecycle (2 records)

    loop Every 60 seconds while RUNNING
        HG->>SP: query(is_billable=true)
        SP-->>HG: [resource_id, state=RUNNING]
        Note right of HG: RUNNING → 2 heartbeats
        HG->>KP: osac.resource.heartbeat.v1 (meter_type=allocation)
        HG->>KP: osac.resource.heartbeat.v1 (meter_type=consumption)
        KP->>K: publish → osac.metering.heartbeat (2 records)
    end

    FS->>WC: OBJECT_UPDATED (state=STOPPING)
    WC->>SP: read previous_state=RUNNING
    WC->>SP: upsert(state=STOPPING, is_billable=true)
    Note right of WC: Consumption stops, allocation continues
    WC->>KP: osac.resource.suspended.v1 (meter_type=consumption, duration_seconds)
    KP->>K: publish → osac.metering.lifecycle (1 record)

    FS->>WC: OBJECT_UPDATED (state=STOPPED)
    WC->>SP: read previous_state=STOPPING
    WC->>SP: upsert(state=STOPPED, is_billable=true)

    loop Every 60 seconds while STOPPED
        HG->>SP: query(is_billable=true)
        SP-->>HG: [resource_id, state=STOPPED]
        Note right of HG: STOPPED → 1 heartbeat
        HG->>KP: osac.resource.heartbeat.v1 (meter_type=allocation)
        KP->>K: publish → osac.metering.heartbeat (1 record)
    end

    FS->>WC: OBJECT_UPDATED (state=RUNNING)
    WC->>SP: read previous_state=STOPPED
    WC->>SP: upsert(state=RUNNING, is_billable=true)
    Note right of WC: Allocation continues, consumption resumes
    WC->>KP: osac.resource.resumed.v1 (meter_type=consumption)
    KP->>K: publish → osac.metering.lifecycle (1 record)

    FS->>WC: OBJECT_DELETED
    WC->>SP: read allocation and consumption interval timestamps
    Note right of WC: Close each active meter independently
    WC->>KP: osac.resource.suspended.v1 (meter_type=allocation, duration_seconds; if allocation active)
    WC->>KP: osac.resource.suspended.v1 (meter_type=consumption, duration_seconds; if consumption active)
    WC->>KP: osac.resource.deleted.v1
    KP->>K: publish → osac.metering.lifecycle (up to 3 records)
    WC->>SP: delete(resource_id)
```

Key observations:

- `PROVISIONING` → `RUNNING` produces two `started.v1` events (both meters start simultaneously)
- `RUNNING` → `STOPPING` produces one `suspended.v1` (consumption stops; allocation continues — no event needed)
- `STOPPED` → `RUNNING` produces one `resumed.v1` (consumption resumes; allocation unchanged)
- Any transition into `FAILED` suspends every active meter; a host in `FAILED` state produces no allocation or consumption heartbeats and accrues no charges
- `OBJECT_DELETED` closes each currently active meter independently, then produces one `deleted.v1` audit event. A meter that is already inactive (for example after `FAILED`) produces no synthetic suspension.
- Heartbeats vary by state: `RUNNING` produces two (allocation + consumption), `STOPPED`/`STARTING`/`STOPPING`/`DELETING` produce one (allocation only). Allocation heartbeat duration is measured from `BillableSince`; a `RUNNING` consumption heartbeat is measured from `ComponentBillableSince["consumption"]`.

### API Extensions

The Metering Service introduces no new CRDs, webhooks, or API surfaces. It consumes existing fulfillment-service private APIs:

- `Events.Watch` — the existing fulfillment event stream. BMaaS events are carried in `Event.bare_metal_instance` (field 3); field 15 is `secret`. The metering-service Watch filter must include the `bare_metal_instance` payload so these events reach the BMaaS mapper.
- `PrivateBareMetalInstancesService.List` — used by the Reconciliation Loop for drift detection
- The fulfillment deletion event contract must add `deletion_completion_time` to `OBJECT_DELETED`. Fulfillment sets it only after the BareMetalInstance has been removed and its finalizers have completed; `Metadata.deletion_timestamp` records the deletion request and is not a completion timestamp. The field must be retained by the durable history/cursor API.

**CloudEvent changes:** No new extension attributes. The existing `osacresourcetype` carries `bare_metal_instance`. The new `meter_type` value lives in `billing_dimensions`, not as a CloudEvent extension — it is a billing attribute, not an infrastructure routing key.

**Provider Adapter interface:** Unchanged. Adapters receive BMaaS events as standard `MeteringEvent` structs. The M360 adapter adds a `/bmaas/event` route.

## UX Alignment

No `@temp-api` file exists for metering resources in `osac-ux/libs/ui-components/src/api/v1/`. The Metering Service is a backend event pipeline; tenant-facing usage views are a separate design concern (Usage Query API).

### Implementation Details/Notes/Constraints

#### Dual-Meter Event Decomposition

The central architectural extension is a per-meter `EventDecomposer` for BMaaS. Unlike CaaS decomposition (which fans out one event type into `N+1` records with different billing dimensions), BMaaS decomposition fans out one Watch event into up to two records with **different CloudEvent types** and different billing dimensions per meter.

Two independent transition tables define each meter's billing boundaries:

`FAILED` is explicitly non-billable for both meters. Entering `FAILED` closes any active allocation and consumption intervals, and the heartbeat generator emits no events while the host remains in `FAILED`. Recovery from `FAILED` starts or resumes metering only after the host reaches a billable state (`RUNNING`); no time spent in `FAILED` is included in either meter.

**Allocation transition table** — billable states: `RUNNING`, `STOPPED`, `STARTING`, `STOPPING`, `DELETING` until the `OBJECT_DELETED` event confirms removal.

The resolver performs exact `(from, to)` lookups. The following is the complete accepted pair set; repeated snapshots are included explicitly and every row represents one registered pair. No wildcard transition is permitted. Pairs outside this set are invalid controller transitions and should be reported as configuration errors rather than silently interpreted.

`FAILED` is recoverable only through the explicitly registered `FAILED` → `RUNNING` path or by entering `DELETING`; repeated `FAILED` updates are accepted. `DELETING` is terminal until the deletion event, so only repeated `DELETING` updates are accepted. These rules are exact entries in the table, not wildcard fallbacks.

| From           | To             | Allocation Effect                     |
| -------------- | -------------- | ------------------------------------- |
| "" (initial)   | `PROVISIONING` | Skip                                  |
| ""             | `RUNNING`      | `billableStart`                       |
| ""             | `STOPPED`      | `billableStart`                       |
| ""             | `STARTING`     | Transient                             |
| ""             | `STOPPING`     | Transient                             |
| ""             | `FAILED`       | Skip                                  |
| ""             | `DELETING`     | Skip                                  |
| ""             | `UNSPECIFIED`  | Skip                                  |
| `PROVISIONING` | `PROVISIONING` | Skip                                  |
| `PROVISIONING` | `RUNNING`      | `billableStart`                       |
| `PROVISIONING` | `STOPPED`      | `billableStart`                       |
| `PROVISIONING` | `STARTING`     | Transient                             |
| `PROVISIONING` | `STOPPING`     | Transient                             |
| `PROVISIONING` | `FAILED`       | Skip                                  |
| `PROVISIONING` | `DELETING`     | Skip                                  |
| `RUNNING`      | `RUNNING`      | Skip                                  |
| `RUNNING`      | `STOPPED`      | Skip (still allocation-billable)      |
| `RUNNING`      | `STARTING`     | Transient (still allocation-billable) |
| `RUNNING`      | `STOPPING`     | Transient (still allocation-billable) |
| `RUNNING`      | `FAILED`       | Suspended                             |
| `RUNNING`      | `DELETING`     | Skip (allocation continues until deletion) |
| `STOPPED`      | `STOPPED`      | Skip                                  |
| `STOPPED`      | `RUNNING`      | Skip (still allocation-billable)      |
| `STOPPED`      | `STARTING`     | Transient (still allocation-billable) |
| `STOPPED`      | `FAILED`       | Suspended                             |
| `STOPPED`      | `DELETING`     | Skip (allocation continues until deletion) |
| `STARTING`     | `STARTING`     | Transient                             |
| `STARTING`     | `RUNNING`      | Skip (still allocation-billable)      |
| `STARTING`     | `STOPPED`      | Skip (still allocation-billable)      |
| `STARTING`     | `FAILED`       | Suspended                             |
| `STARTING`     | `DELETING`     | Skip (allocation continues until deletion) |
| `STOPPING`     | `STOPPING`     | Transient                             |
| `STOPPING`     | `STOPPED`      | Skip (still allocation-billable)      |
| `STOPPING`     | `RUNNING`      | Skip (still allocation-billable)      |
| `STOPPING`     | `FAILED`       | Suspended                             |
| `STOPPING`     | `DELETING`     | Skip (allocation continues until deletion) |
| `FAILED`       | `FAILED`       | Skip                                  |
| `FAILED`       | `RUNNING`      | `billableResume`                      |
| `FAILED`       | `DELETING`     | Skip                                  |
| `DELETING`     | `DELETING`     | Skip (allocation continues until deletion) |

**Consumption transition table** — billable state: `RUNNING` only. It registers the same complete pair set above. `PROVISIONING`, `STOPPED`, `STARTING`, and `FAILED` → `RUNNING` open a consumption interval; every `RUNNING` → `STOPPING`, `STOPPED`, `FAILED`, or `DELETING` pair closes it; all remaining registered pairs are `Skip`. The `RUNNING` → `STOPPING` boundary is intentional: consumption ends when the stop operation begins, while allocation continues through the transient state.

The decomposer evaluates both tables for each Watch event and produces one CloudEvent per meter that crosses a billing boundary. Transitions where neither meter crosses a boundary (_e.g._, `STOPPED` → `STOPPED`) produce no lifecycle events. Every lifecycle event receives the transition timestamp and the active interval for its own meter; the allocation and consumption intervals are never calculated from one shared timestamp.

`OBJECT_CREATED` and `OBJECT_DELETED` are fixed resource-level events and bypass the transition table. `OBJECT_DELETED` must nevertheless close active meter intervals before removing the projection row: it emits an allocation suspension only when `BillableSince` is present, a consumption suspension only when `ComponentBillableSince["consumption"]` is present, and then the audit deletion event. The fulfillment-service team must add `deletion_completion_time` to this event and set it only after deletion has completed, including finalizer processing. `Metadata.deletion_timestamp` is the deletion-request time and must not be used for billing closure. The suspension duration uses `deletion_completion_time`; if it is absent, the consumer holds the closure for retry rather than using metadata deletion time or receipt time. The suspension IDs are `{baseID}/allocation` and `{baseID}/consumption`, and the deletion ID is `{baseID}`. Replayed or duplicated deletion notifications therefore resolve to the same IDs and cannot create duplicate billing intervals. A preceding `DELETING` update is not required for closure.

**Deletion completion contract:** **Owner:** fulfillment-service team. **Implementation:** when finalizer processing confirms that the BareMetalInstance is gone, fulfillment records that instant as `deletion_completion_time` and includes it in the `OBJECT_DELETED` event and every durable-history replay record. This field is distinct from `Metadata.deletion_timestamp`, which marks the deletion request. **Impact:** metering closes the allocation interval at the actual deletion-completion instant; it retains the closure for retry when the completion timestamp is unavailable and never substitutes event receipt time.

```go
type BMaaSMeterIntervals struct {
    AllocationSince  *time.Time
    ConsumptionSince *time.Time
}

func DecomposeBMIEvents(
    billingDims map[string]any,
    baseID string,
    transitionTime time.Time,
    intervals BMaaSMeterIntervals,
    buildFn EventBuilder,
    allocType string,
    consumType string,
) ([]cloudevents.Event, error)
```

The decomposer receives the resolved CloudEvent types for each meter (or empty string if no boundary), plus the two active interval timestamps from `StateContext`. It computes `duration_seconds` as `transitionTime - intervals.AllocationSince` for allocation events and `transitionTime - intervals.ConsumptionSince` for consumption events. A consumer must not calculate one duration from `ResourceState.BillableSince` and reuse it for both meters. It builds independent events with deterministic IDs: `{baseID}/allocation` and `{baseID}/consumption`.

#### BMaaS Pipeline Integration Contract

The BMaaS decomposer is an explicit resource-type handler in the existing Metering Service pipeline. The shared Watch, heartbeat, and reconciliation components call this handler through the following contract:

| Pipeline component | BMaaS integration contract |
| --- | --- |
| Watch filter and dispatcher | Subscribe to `Events.Watch` with `bare_metal_instance` enabled. Route `Event.bare_metal_instance` events to the BMaaS mapper and handler based on `osacresourcetype`; do not send them through a generic single-meter transition path. `OBJECT_DELETED` enters the BMaaS closure handler before the projection row is removed. |
| Mapper | Extract the BareMetalInstance resource ID, tenant/project metadata, the string `spec.instance_type`, catalog item, current state, and authoritative `state_transition_time`. For `OBJECT_UPDATED`, load the previous state and per-meter interval timestamps from the projection. |
| Transition handler | Resolve the exact `(previous_state, current_state)` pair in both BMaaS tables, update `CurrentState` and both meter intervals, and pass the resulting meter event specifications to `DecomposeBMIEvents`. Persist the projection update and all generated events as one idempotent operation. |
| Event builder | Build each CloudEvent from the meter-specific event type, meter type, transition timestamp, duration, resource identity, and billing dimensions supplied by the decomposer. The allocation and consumption records use independent event IDs and never share a calculated duration. |
| Heartbeat generator | Query allocation-billable BMaaS projection rows, inspect `CurrentState`, and invoke the BMaaS heartbeat decomposer. It builds one allocation heartbeat for `STOPPED`, `STARTING`, `STOPPING`, and `DELETING`, and allocation plus consumption heartbeats for `RUNNING`, using each meter's own interval timestamp. |
| Reconciliation loop | Use the same mapper, transition tables, decomposer, event builder, and `OBJECT_DELETED` closure handler as Watch processing. A correction carries the authoritative fulfillment transition timestamp; it does not use reconciliation read time. Durable history replay is applied through this same path before snapshot drift correction. |

The event-builder contract is internal to the Metering Service and has the inputs required to reach the canonical CloudEvent schema:

```go
type BMaaSEventBuildRequest struct {
    EventType         string
    MeterType         string
    BaseID            string
    ResourceID        string
    PreviousState     string
    CurrentState      string
    TransitionTime    time.Time
    DurationSeconds   *int64
    BillingDimensions map[string]any
}

type EventBuilder func(BMaaSEventBuildRequest) (cloudevents.Event, error)
```

`DecomposeBMIEvents` creates one build request for each meter boundary, setting `DurationSeconds` from that meter's interval timestamp and setting the CloudEvent type to `started.v1`, `suspended.v1`, `resumed.v1`, or the applicable correction type. The dispatcher, heartbeat generator, and reconciliation loop must use this contract so `meter_type`, event type, transition timestamp, and meter-specific duration reach every emitted event.

#### State Projection

The existing `ResourceState` struct is sufficient without schema changes:

| Field                    | BMaaS Usage                                                                                                                                                   |
| ------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `IsBillable`             | Allocation-billable (true for `RUNNING`, `STOPPED`, `STARTING`, `STOPPING`, `DELETING` until `OBJECT_DELETED`)                                                   |
| `EverBillable`           | True once the host has ever been allocation-billable                                                                                                          |
| `BillableSince`          | Start of the active allocation interval. It is set when allocation becomes billable and cleared after allocation suspension.                                  |
| `ComponentBillableSince` | `{"consumption": <time>}` — start of the active consumption interval. It is set on entry to `RUNNING` and cleared when consumption stops.               |
| `CurrentState`           | BareMetalInstance state (`PROVISIONING`, `RUNNING`, `STOPPED`, _etc._)                                                                                        |
| `BillingDimensions`      | BM instance type, catalog item, and other BMaaS-specific dimensions                                                                                          |

The Watch Consumer carries both timestamps from the projection into `StateContext` and then into the decomposer. The consumption meter's `duration_seconds` on `suspended.v1` events is computed from `ComponentBillableSince["consumption"]`; the allocation meter uses `BillableSince`. On `RUNNING` → `STOPPING`, consumption is closed and its timestamp is cleared while the allocation timestamp remains unchanged. On a later transition to `RUNNING`, a new consumption timestamp is set at that transition time while the allocation interval continues.

The field is additive and optional for existing resource types. VMaaS and CaaS retain their current `EverBillable` and component behavior, and their handlers ignore the BMaaS-only keys. The projection migration initializes the map empty for existing rows. BMaaS sets `ComponentEverStarted["allocation"]` or `ComponentEverStarted["consumption"]` atomically when the corresponding meter first opens, and chooses `started.v1` or `resumed.v1` from that flag. The projection update and emitted events are committed idempotently together.

`ListBillable()` returns BMaaS resources that are allocation-billable. The heartbeat decomposer checks `CurrentState` to determine whether to produce one heartbeat (allocation only, for `STOPPED`/`STARTING`/`STOPPING`/`DELETING`) or two (allocation + consumption, for `RUNNING`).

#### BMaaS Watch Consumer State Application

The generic Watch Consumer's projection-only handling for transient states is not sufficient for BMaaS. The BMaaS handler loads the previous `ResourceState`, resolves the exact `(from, to)` pair, applies both meter effects, and persists the projection and deterministic lifecycle events as one idempotent transition. A transition that leaves one meter unchanged still updates `CurrentState` so the heartbeat generator sees the correct power state.

The meter-specific application rules are:

| Transition | Projection update | Lifecycle events |
| --- | --- | --- |
| `PROVISIONING` → `STARTING`/`STOPPING` | Set `BillableSince` to `state_transition_time`; set `ComponentEverStarted["allocation"]`; leave consumption inactive; set `IsBillable=true` | `started.v1` for allocation |
| `PROVISIONING` → `RUNNING` | Set `BillableSince` and `ComponentBillableSince["consumption"]` to `state_transition_time`; set both `ComponentEverStarted` flags and `IsBillable=true` | `started.v1` for allocation and consumption |
| `PROVISIONING` → `STOPPED` | Set `BillableSince` to `state_transition_time`; set `ComponentEverStarted["allocation"]`; leave consumption inactive; set `IsBillable=true` | `started.v1` for allocation |
| `STOPPED`/`STARTING` → `RUNNING` | Preserve `BillableSince`; set `ComponentBillableSince["consumption"]` to `state_transition_time`; set `ComponentEverStarted["consumption"]` if false | `started.v1` for a first consumption opening, otherwise `resumed.v1` |
| `FAILED` → `RUNNING` | Set active timestamps to `state_transition_time` for meters that open; set `IsBillable=true`; preserve and update each `ComponentEverStarted` flag | `started.v1` or `resumed.v1` independently for each meter, based on its flag |
| `RUNNING` → `STOPPING` | Preserve `BillableSince`; clear the consumption timestamp; keep `IsBillable=true` | `suspended.v1` for consumption |
| `STOPPING` → `STOPPED`, or `STOPPED` → `STARTING` | Preserve the allocation timestamp and consumption inactivity; keep `IsBillable=true` | No lifecycle event |
| `RUNNING`/`STOPPED`/`STARTING`/`STOPPING` → `DELETING` | Preserve `BillableSince`; clear the consumption timestamp if active; keep `IsBillable=true` until `OBJECT_DELETED` | Suspend consumption if active; allocation remains open |
| An allocation-billable state → `FAILED` | Clear `BillableSince` and any active consumption timestamp; set `IsBillable=false` | Suspend each meter that was active |

`started.v1` is reserved for the first opening of each meter interval. `resumed.v1` is used when that same meter opens again after suspension. A missing creation event is handled by reconciliation using the current state and its authoritative `state_transition_time`: `RUNNING` seeds both meters and marks both first-use flags, allocation-billable non-`RUNNING` states seed allocation only, and `FAILED` seeds neither. Reconciliation emits correction events with the same meter-specific effects and IDs. A state snapshot cannot infer a completed stop/start cycle; replayable durable history is therefore a release prerequisite for the exact billing guarantee.

#### BMaaS Watch Consumer State Application

The generic Watch Consumer's projection-only handling for transient states is not sufficient for BMaaS. The BMaaS handler loads the previous `ResourceState`, resolves the exact `(from, to)` pair, applies both meter effects, and persists the projection and deterministic lifecycle events as one idempotent transition. A transition that leaves one meter unchanged still updates `CurrentState` so the heartbeat generator sees the correct power state.

The meter-specific application rules are:

| Transition | Projection update | Lifecycle events |
| --- | --- | --- |
| `PROVISIONING` → `RUNNING` | Set `BillableSince` and `ComponentBillableSince["consumption"]` to `state_transition_time`; set `IsBillable=true` | `started.v1` for allocation and consumption |
| `PROVISIONING` → `STOPPED` | Set `BillableSince` to `state_transition_time`; leave consumption inactive; set `IsBillable=true` | `started.v1` for allocation |
| `STOPPED`/`STARTING` → `RUNNING` | Preserve `BillableSince`; set `ComponentBillableSince["consumption"]` to `state_transition_time` | `resumed.v1` for consumption |
| `FAILED` → `RUNNING` | Set both active timestamps to `state_transition_time`; set `IsBillable=true` | `resumed.v1` for allocation and consumption |
| `RUNNING` → `STOPPING` | Preserve `BillableSince`; clear the consumption timestamp; keep `IsBillable=true` | `suspended.v1` for consumption |
| `STOPPING` → `STOPPED`, or `STOPPED` → `STARTING` | Preserve the allocation timestamp and consumption inactivity; keep `IsBillable=true` | No lifecycle event |
| `RUNNING`/`STOPPED`/`STARTING`/`STOPPING` → `DELETING` | Preserve `BillableSince`; clear the consumption timestamp if active; keep `IsBillable=true` until `OBJECT_DELETED` | Suspend consumption if active; allocation remains open |
| An allocation-billable state → `FAILED` | Clear `BillableSince` and any active consumption timestamp; set `IsBillable=false` | Suspend each meter that was active |

`started.v1` is reserved for the first opening of a meter interval. `resumed.v1` is used when a previously suspended interval opens again. A missing creation event is handled by reconciliation using the current state and its authoritative `state_transition_time`: `RUNNING` seeds both meters, allocation-billable non-`RUNNING` states seed allocation only, and `FAILED` seeds neither. Reconciliation emits correction events with the same meter-specific effects and IDs. A state snapshot cannot infer a completed stop/start cycle; that limitation is covered by the deferred durable-history dependency above.

#### BareMetalInstanceType Resolution

The PRD's primary metering dimension is the `BareMetalInstanceType` selected for the host. OSAC-1201 exposes `spec.instance_type` as a non-empty string containing the `BareMetalInstanceType` name. The canonical `bm_instance_type` value is that string as carried by the fulfillment API; the metering service does not dereference or rewrite it. OSAC-1201 adds the field to `BareMetalInstance`; the Watch stream carries it with the resource:

```go
func BareMetalInstanceBillingDimensions(bmi *privatev1.BareMetalInstance) map[string]any {
    dims := map[string]any{}
    if spec := bmi.GetSpec(); spec != nil {
        if instanceType := spec.GetInstanceType(); instanceType != "" {
            dims["bm_instance_type"] = instanceType
        }
        if ci := spec.GetCatalogItem(); ci != nil {
            dims["catalog_item"] = ci.GetName()
        }
    }
    return dims
}
```

The metering service does not resolve hardware metadata through `BareMetalInstanceType` List/Get calls and does not maintain a type cache or watch the type resource. The `spec.instance_type` value identifies the billing dimension for each meter interval. Whether OSAC-1201 makes this field immutable is an open question. Immutability is the simpler contract. If updates remain permitted, a separate contract must define an authoritative dimension-change timestamp, durable old and new interval storage, deterministic close-and-reopen events, and heartbeat attribution rules before metering can support those updates. No heartbeat or lifecycle event may silently change dimensions within an existing interval. Changes to descriptive or hardware metadata do not rewrite historical metering events. BMaaS metering requires this field to be populated; legacy catalog-item-only resources must be migrated before they can satisfy the BMaaS metering dimension requirement. An empty `instance_type` string is a configuration error and must prevent billable BMaaS events from being published until reconciliation can resolve the configuration.

#### BMaaS Billing Dimensions

BMaaS CloudEvents carry the following billing dimensions. Each event includes a `meter_type` discriminator:

**Lifecycle and heartbeat events:**

```json
{
  "meter_type": "allocation",
  "bm_instance_type": "gpu-large",
  "catalog_item": "bmi-gpu-workstation"
}
```

Here `gpu-large` is the string value carried in `spec.instance_type`.

```json
{
  "meter_type": "consumption",
  "bm_instance_type": "gpu-large",
  "catalog_item": "bmi-gpu-workstation"
}
```

The `meter_type` discriminator enables downstream systems to filter and price each meter independently. The `bm_instance_type` reference is the primary pricing dimension (analogous to `instance_type` for VMaaS). The `catalog_item` supports the PRD's queryability requirement (_CAP-3_).

Base event fields (`tenant_id`, `project_id`, `catalog_item_id`, `template_id`) are populated from the BareMetalInstance metadata and spec, following the same pattern as ComputeInstance.

#### BMaaS State Machine — Allocation Meter

```mermaid
stateDiagram-v2
    [*] --> PROVISIONING : resource created\n→ osac.resource.created.v1

    PROVISIONING --> RUNNING : provisioning complete\n→ osac.resource.started.v1 (allocation)
    PROVISIONING --> FAILED : provisioning failure

    RUNNING --> STOPPING : stop requested\n(transient — allocation continues)
    RUNNING --> FAILED : hardware failure\n→ osac.resource.suspended.v1 (allocation)
    RUNNING --> DELETING : delete requested\n(allocation continues until confirmed deletion)

    note right of RUNNING
        ALLOCATION-BILLABLE
        60s heartbeat (allocation)
    end note

    STOPPING --> STOPPED : power off confirmed

    note right of STOPPED
        ALLOCATION-BILLABLE
        60s heartbeat (allocation)
    end note

    STOPPED --> STARTING : start requested\n(transient — allocation continues)
    STOPPED --> FAILED : hardware failure\n→ osac.resource.suspended.v1 (allocation)
    STOPPED --> DELETING : delete requested\n(allocation continues until confirmed deletion)

    STARTING --> RUNNING : power on confirmed

    FAILED --> RUNNING : recovery\n→ osac.resource.resumed.v1 (allocation)
    FAILED --> DELETING : delete requested

    note right of DELETING
        ALLOCATION-BILLABLE
        60s heartbeat (allocation)
    end note

    DELETING --> [*] : confirmed deleted\n→ allocation suspended + osac.resource.deleted.v1
```

Allocation-billable states: `RUNNING`, `STOPPED`, `STARTING`, `STOPPING`, and `DELETING` while deletion is in progress. The meter runs continuously across power cycles and deletion finalization. `FAILED` stops it immediately; `OBJECT_DELETED` closes it at the confirmed deletion timestamp.

#### BMaaS State Machine — Consumption Meter

```mermaid
stateDiagram-v2
    [*] --> PROVISIONING : resource created

    PROVISIONING --> RUNNING : provisioning complete\n→ osac.resource.started.v1 (consumption)

    RUNNING --> STOPPING : stop requested\n→ osac.resource.suspended.v1 (consumption; allocation continues)
    RUNNING --> FAILED : hardware failure\n→ osac.resource.suspended.v1 (consumption)
    RUNNING --> DELETING : delete requested\n→ osac.resource.suspended.v1 (consumption)

    note right of RUNNING
        CONSUMPTION-BILLABLE
        60s heartbeat (consumption)
    end note

    STOPPING --> STOPPED : confirmed stopped

    STOPPED --> STARTING : start requested\n(transient)
    STOPPED --> DELETING : delete requested

    STARTING --> RUNNING : power on confirmed\n→ osac.resource.resumed.v1 (consumption)

    FAILED --> RUNNING : recovery\n→ osac.resource.resumed.v1 (consumption)

    DELETING --> [*] : confirmed deleted
```

Consumption-billable state: `RUNNING` only. The consumption interval ends when `STOPPING` begins, so the transient `STOPPING` and terminal `STOPPED` states produce allocation heartbeats only. `FAILED` is non-billable, so the consumption meter is suspended on entry and produces no heartbeats until recovery to `RUNNING`. Structurally identical to the VMaaS `ComputeInstance` pattern.

#### Reconciliation

The Reconciler gains a `BareMetalInstancesClient` interface and `loadBareMetalInstances()` method, following the existing `loadComputeInstances()` and `loadClusters()` patterns:

```go
type BareMetalInstancesClient interface {
    List(ctx context.Context, in *privatev1.BareMetalInstancesListRequest,
        opts ...grpc.CallOption) (*privatev1.BareMetalInstancesListResponse, error)
}
```

The `billabilityCheckers` map gains an entry for `bare_metal_instance` that returns true for allocation-billable states (`RUNNING`, `STOPPED`, `STARTING`, `STOPPING`, `DELETING`).

Reconciliation corrections for BMaaS resources use the same decomposer as the Watch Consumer — a state drift correction that moves from `RUNNING` to `STOPPING` produces a consumption `suspended.v1` correction but no allocation correction. The correction uses the fulfillment transition timestamp; it cannot use the time at which the snapshot was read.

**Reconciliation Interval:** Each hour, the reconciliation loop queries the fulfillment-service's `PrivateBareMetalInstancesService.List` API and compares the returned state against the State Projection. Endpoint drift (missed creations, a resource remaining in a different state, or a missing deletion) triggers correction events. The 60-minute interval is configurable via the `metering.reconciliation_interval_seconds` Helm value (default: 3600).

**Startup Reconciliation:** On metering-service startup, reconciliation runs immediately before the Watch Consumer resumes and seeds the projection with current BareMetalInstance state from fulfillment. It repairs endpoint drift but does not reconstruct transitions that began and ended while the service was unavailable.

**Durable transition history requirement:** `List` is a snapshot API and cannot detect a complete `RUNNING` → `STOPPING`/`STOPPED` → `STARTING`/`RUNNING` cycle that occurs while Watch or Kafka is unavailable: both the source snapshot and the projection can end in `RUNNING`. Snapshot reconciliation therefore cannot recover the stopped interval or correct the consumption meter.

The current fulfillment `Events.Watch` contract does not provide this history. Its proto explicitly makes no guarantee about delivery or order, events that occur while the client is disconnected are not delivered, and the API has no replay cursor. `Event.id` identifies an event but is not a cursor or ordering guarantee. [OSAC PR #799](https://github.com/osac-project/osac/pull/799) adds the authoritative `state_transition_time` to BMaaS status; it does not change these Watch delivery semantics.

**Blocking release gate — durable fulfillment transition history/cursor:** BMaaS MUST NOT be deployed with billing enabled until fulfillment provides the replay contract below. This is required to satisfy the Part 1 exact lifecycle billing guarantee for outages that can contain a complete transient cycle. Snapshot reconciliation and event receipt timestamps cannot substitute for replayable history.

**Owner:** Fulfillment-service team

**Implementation:** Provide an ordered, replayable stream or history endpoint with a durable per-consumer cursor or sequence, stable event ID, event type, complete resource payload, authoritative transition timestamp, and retention long enough to cover the maximum metering outage. Cursor resumption must define inclusive/exclusive semantics and allow the metering service to acknowledge progress after idempotently applying each event. The metering service will resume from that cursor before applying replayed events.

**Impact:** Until this dependency is available, BMaaS billing cannot be enabled. Reconciliation is limited to endpoint corrections and cannot reconstruct an unseen cycle.

#### Heartbeat Generation

The heartbeat decomposer for BMaaS checks `ResourceState.CurrentState`:

| State      | Heartbeat Events            |
| ---------- | --------------------------- |
| `RUNNING`  | 2: allocation + consumption |
| `STOPPED`  | 1: allocation only          |
| `STARTING` | 1: allocation only          |
| `STOPPING` | 1: allocation only          |
| `DELETING` | 1: allocation only          |
| `FAILED`   | 0                           |

Each heartbeat carries its own `meter_type` in billing dimensions and a deterministic event ID: `{base-hb-id}/allocation` and `{base-hb-id}/consumption`.

The heartbeat builder calculates `duration_seconds` independently for each emitted record: `now - ResourceState.BillableSince` for allocation and `now - ResourceState.ComponentBillableSince["consumption"]` for a `RUNNING` consumption heartbeat. It never uses `BillableSince` for the consumption record. A consumption heartbeat is suppressed when the consumption timestamp is absent; an allocation heartbeat is suppressed when the allocation timestamp is absent. This preserves the separate intervals across stop/start cycles.

#### M360 Adapter

The M360 adapter adds a `/bmaas/event` route alongside the existing `/vmaas/event`, `/caas/event`, and `/maas/event` routes. BMaaS events are translated to M360's flat payload format with `meter_type` passed through as a field. The M360 API treats allocation and consumption events identically — the `meter_type` is metadata for M360's own aggregation and pricing logic.

The echo adapter requires no changes — it stores all CloudEvents by ID regardless of resource type.

#### Parent-Child Attribution

The PRD requires storage volumes and public IPs attached to a bare metal host to be queryable as a unified usage view (_CAP-5_ acceptance criterion). This is an attribution and query relationship, not a second meter for the attached resources. The ownership boundary is:

- [OSAC-3141](https://redhat.atlassian.net/browse/OSAC-3141) owns the block-volume meter (`GiB-seconds`) for every volume, including volumes attached to bare metal hosts.
- [OSAC-2506](https://redhat.atlassian.net/browse/OSAC-2506) owns the bare metal host-resource meters and the unified bare metal host footprint view that rolls already-metered child usage into the host view.
- [OSAC-3145](https://redhat.atlassian.net/browse/OSAC-3145) owns the public-IP/networking meter, including for resources attached to bare metal hosts.

OSAC-2506 does not emit a second block-volume or public-IP meter event. Child-resource events owned by OSAC-3141 and OSAC-3145 carry the parent relationship in the canonical event data:

```json
{
  "resource_id": "volume-123",
  "resource_type": "block_volume",
  "parent_resource_id": "bmi-456",
  "parent_resource_type": "bare_metal_instance"
}
```

`parent_resource_id` is the direct parent's stable resource ID and `parent_resource_type` identifies its resource kind. These are optional top-level event-data fields, rather than CloudEvent extension attributes or billing dimensions. Parent host events omit both fields. The canonical event schema and field semantics are owned by the Part 1 metering-service team.

OSAC-3141 and OSAC-3145 are responsible for discovering attachment ownership and populating the parent fields for the portion of a child meter interval during which the attachment exists. An attach or detach operation closes the prior child interval and opens a new one at its authoritative attachment timestamp. A child resource can have only one direct parent in an event; nested roll-ups are the responsibility of the query layer.

The parent-child contract has two parts. At the event level, each child meter event retains its owning resource, meter type, units, and direct parent fields; the parent host events retain the host `resource_id` and omit parent fields. At the usage level, the Usage Query API accepts `parent_resource_type`, `parent_resource_id`, a time range, and the caller's tenant/project scope. It returns the host-resource meters plus the already-metered child usage attributed to that parent, preserving each child's resource ID, meter type, unit, and attachment-bounded interval without emitting or counting a duplicate child meter.

**Owner:** Metering team, with the Part 1 metering-service team owning the canonical event fields and OSAC-3141/OSAC-3145 owning attachment discovery and child-meter attribution.

**Implementation:** The Metering team implements the Usage Query API contract, including the parent filters, authorization, pagination, and response shape. The [OSAC-985 metering design](../OSAC-985-metering-and-usage-tracking/design.md) identifies this API as a planned companion design; no dedicated Usage Query API design exists yet in this workspace. OSAC-3141 and OSAC-3145 populate attachment-bounded `parent_resource_id` and `parent_resource_type` fields in their child events. No duplicate child meter is emitted.

**Impact:** The unified-footprint acceptance criterion (CAP-5) remains blocked until the canonical parent fields, child attribution, and Usage Query API are available. The query returns host-resource meters and already-metered child usage without double-counting it.

### Security Considerations

BMaaS metering inherits the existing security model without changes:

- The metering-service consumes the fulfillment-service **private** Watch stream, authenticated via mTLS (Kubernetes service mesh). No new authentication paths are introduced.
- Tenant isolation is enforced by the fulfillment-service's OPA policies — the metering-service receives all BareMetalInstance events across tenants and attributes them via `tenant_id` from the resource's metadata. The metering-service itself performs no authorization checks; it is a trusted internal consumer.
- CloudEvents published to Kafka carry `osactenant` extension attributes for downstream tenant-scoped filtering.
- No sensitive data is added to CloudEvents beyond what Part 1 already exposes (resource IDs, tenant IDs, states, billing dimensions).

### Failure Handling and Recovery

| Failure Mode                                    | Effect                                                              | Recovery                                                                                                                                                                | User Observation                                                                  |
| ----------------------------------------------- | ------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------- |
| Watch stream disconnect                         | Missed BareMetalInstance transitions                                | Durable Watch history is replayed from the last cursor. Snapshot reconciliation handles endpoint drift only; it cannot reconstruct a complete cycle that returns to the same state.                                      | BMaaS billing is not enabled unless replayable transition history is available |
| Kafka publish failure                           | Events buffered in metering-service; backpressure on Watch Consumer | Kafka producer retries with exponential backoff. If buffered events are lost, the durable fulfillment history/cursor dependency must replay them; snapshot reconciliation can repair endpoint drift only. | Delayed event availability; exact billing remains dependent on replayable history |
| Reconciliation detects missed BareMetalInstance | Resource was created but Watch event was lost                       | Reconciliation emits `correction.v1 (reason=missed_creation)` and seeds the projection                                                                                  | Downstream system receives correction with adjusted interval                      |
| Metering-service restart mid-lifecycle          | In-memory state projection lost                                     | PostgreSQL-backed projection survives restarts. Durable Watch history replays the gap; startup reconciliation repairs endpoint drift when no transient cycle was missed.                   | No user-visible impact when replayable history is available                         |

### RBAC / Tenancy

No RBAC or tenancy changes required. BMaaS metering is a backend pipeline that reads from the fulfillment-service private API, which already enforces tenant isolation via OPA. The metering-service is a cluster-scoped internal service, not tenant-facing. All CloudEvents carry `tenant_id` for downstream attribution.

### Observability and Monitoring

New Prometheus metrics for BMaaS metering:

| Metric                                          | Type    | Labels                     | Description                                          |
| ----------------------------------------------- | ------- | -------------------------- | ---------------------------------------------------- |
| `osac_metering_bmi_events_total`                | Counter | `meter_type`, `event_type` | BMaaS lifecycle events produced, by meter and type   |
| `osac_metering_bmi_heartbeats_total`            | Counter | `meter_type`               | BMaaS heartbeat events produced, by meter            |

Existing metrics (`osac_metering_reconciliation_corrections_total`, `osac_metering_reconciliation_duration_seconds`) gain `bare_metal_instance` as a new `resource_type` label value. No new alerts — existing reconciliation and Kafka health alerts cover BMaaS.

### Risks and Mitigations

| Risk                                                                                                                                           | Mitigation                                                                                                                                                                                                                                                                      |
| ---------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Dual-meter decomposition complexity** — the per-meter decomposer is a novel pattern not used by VMaaS or CaaS, increasing maintenance burden | The decomposer is self-contained in `bare_metal_instance.go` and isolated behind the `EventDecomposer` interface. Unit tests cover all (from, to, meter) combinations via the two transition tables.                                                                            |
| **Blocking release gate: durable fulfillment transition history/cursor** — the current `Events.Watch` stream does not guarantee delivery or order and cannot replay events missed during disconnects | Fulfillment-service team must provide the ordered replay contract described in the Reconciliation section. BMaaS billing remains disabled until it is available. |
| **OSAC-1201 dependency** — BareMetalInstanceTypes must be defined and referenced before BMaaS metering is useful                                  | [OSAC-1201](https://redhat.atlassian.net/browse/OSAC-1201) must define the `BareMetalInstanceType` resource and populate the `BareMetalInstance.spec.instance_type` string. Whether that field is immutable remains an open question; if updates are allowed, the separate dimension-rollover contract described above must be resolved before those updates can be metered. |
| **Deletion completion timestamp dependency** — metadata records deletion requested, not deletion completed | Fulfillment-service team must add `deletion_completion_time` to `OBJECT_DELETED` and durable history, populated after finalizers complete. Metering closes allocation at that timestamp and waits for it when absent. |
| **Parent attribution/query dependency** — the current canonical event schema, child-meter designs, and Usage Query API do not yet define the parent relationship contract | The Part 1 metering-service team must add the optional parent fields; OSAC-3141 and OSAC-3145 must populate them for attachment-bounded child intervals; the Metering team must implement the parent query contract. CAP-5 remains blocked until these contracts are available. |
| **Part 1 not yet deployed** — BMaaS metering depends on the metering-service infrastructure from OSAC-985                                      | Part 1 design is complete; implementation is in progress. BMaaS metering code can be developed in parallel but cannot be deployed or tested end-to-end until Part 1 infrastructure is operational.                                                                              |

### Drawbacks

The dual-meter decomposition pattern introduces a precedent: a single OSAC resource producing multiple independent billing streams from one Watch event. This is architecturally clean but increases the surface area of the event decomposition layer. Future resource types with multi-meter requirements (_e.g._, GPU instances with allocation + compute + memory meters) would follow this pattern, which could lead to combinatorial growth in transition table coverage.

The alternative — treating each meter as a fully independent virtual resource with its own projection row — would be structurally simpler per-meter but would double the projection store size for BMaaS resources and require changes to the Store interface (composite keys instead of resource ID alone). The decomposition approach was chosen because it preserves the 1:1 resource→projection invariant and reuses the existing CaaS decomposition machinery.

## Alternatives (Not Implemented)

### A1: Two Projection Rows per Resource

Treat allocation and consumption as independent virtual resources: `bare_metal_instance:allocation:{id}` and `bare_metal_instance:consumption:{id}`, each with its own `ResourceState` row, `IsBillable`, and heartbeat cycle.

**Pros:** Each meter is fully independent; no decomposer needed; heartbeat generator works without state inspection.
**Cons:** Doubles projection store size for BMaaS; breaks the 1:1 resource ID → projection row assumption used by reconciliation, missed-deletion detection, and stale-version checks; requires Store interface changes for composite keys; `ListBillable()` would return two rows per host in RUNNING state.
**Rejected because:** The projection schema change would ripple through the reconciler, heartbeat generator, and Watch Consumer for all resource types, not just BMaaS.

### A2: Single Transition Table with Union Boundaries

Use one transition table where every row that crosses a boundary for either meter produces an event, and embed both meters' effects in the `TransitionResult`:

```go
type TransitionResult struct {
    AllocationEventType  string
    ConsumptionEventType string
    Transient            bool
    Skip                 bool
}
```

**Pros:** Single table, explicit per-transition effect for both meters.
**Cons:** Changes the `TransitionResult` struct used by all resource types (VMaaS, CaaS); requires adapting `resolveTransition()` and all callers.
**Rejected because:** Modifying shared types forces changes in VMaaS and CaaS code paths that have no dual-meter requirement.

### A3: Consumption-Only Metering (Single Meter)

Meter BMaaS like VMaaS — `RUNNING` only. Drop the allocation meter.

**Pros:** Zero architectural changes; exact ComputeInstance pattern.
**Cons:** Does not meet PRD requirements. The allocation meter (_CAP-1_) is the primary requirement — providers need to track capacity commitment for physically reserved hardware regardless of power state.
**Rejected because:** Fails to meet the PRD.

## Open Questions

### 1. state_transition_time Availability for BMaaS

**STATUS: RESOLVED; IMPLEMENTATION MERGED** — [OSAC-4969](https://redhat.atlassian.net/browse/OSAC-4969) tracks the fulfillment change, which has merged. It adds `BareMetalInstanceStatus.state_transition_time` and populates it on every state change. The fulfillment version consumed by BMaaS metering must include this merged change.

The Watch event's receipt time is not a valid substitute: Watch disconnects, Kafka backlog, consumer backlog, and reconciliation can delay delivery by minutes or hours. The metering service must not estimate a transition timestamp from event receipt time, use a missing timestamp to advance either meter interval, or publish a billable lifecycle, correction, or heartbeat event for a state whose transition timestamp is unavailable. It must retain or reject the event for retry and surface the missing field as a dependency failure.

The transition timestamp is carried from `BareMetalInstanceStatus` through the Watch Consumer and `StateContext` into the per-meter decomposer. Reconciliation also requires the same timestamp and cannot infer it from the time that a snapshot is read. Once the controller supplies the field, the fulfillment event stream must preserve it for replay and correction processing.

**Owner:** Platform team (`BareMetalInstance` controller) / Amit Oren (amoren@redhat.com)
**Implementation:** [OSAC-4969](https://redhat.atlassian.net/browse/OSAC-4969) added `optional google.protobuf.Timestamp state_transition_time` to `BareMetalInstanceStatus`, populates it whenever the state transitions, and follows the pattern in `ComputeInstanceStatus`. The value must be preserved in every Watch payload and replay path.
**Impact:** The state-transition timestamp prerequisite is satisfied once BMaaS consumes a fulfillment version containing OSAC-4969; no receipt-time fallback is permitted.

### 2. Exact Part 1 Billing Guarantee During Watch Outages

**STATUS: RESOLVED IN DESIGN; RELEASE GATE** — The PRD requires BMaaS meters to use the same accuracy and data-availability guarantees as Part 1, while the current fulfillment `Events.Watch` API cannot replay transitions missed during a disconnect. Snapshot reconciliation cannot reconstruct a complete transient cycle that starts and ends in the same state.

Durable fulfillment transition history with cursor-based replay is a release-blocking prerequisite for the Part 1 guarantee. The design does not weaken the guarantee or use `List` reconciliation as a substitute. Research of the current fulfillment implementation found only the live `Events.Watch` subscription; it has no history store or cursor, and its proto documents that disconnected events are lost. BMaaS billing cannot be enabled until the contract above is implemented.

**Owner:** OSAC-2506 product/design owners and the fulfillment-service team
**Impact:** BMaaS deployment and billing remain blocked until the durable replay contract is implemented and verified.

### 3. BareMetalInstance.spec.instance_type Immutability

**STATUS: OPEN** — OSAC-1201 currently requires a non-empty string but does not settle whether `spec.instance_type` is immutable. Immutability avoids billing-dimension rollover. Allowing changes requires an authoritative dimension-change timestamp, durable old and new interval handling, deterministic close-and-reopen events, and heartbeat attribution rules. Which contract should fulfillment provide?

**Owner:** OSAC-1201/fulfillment-service team and Metering Service team
**Impact:** BMaaS instance-type dimension behavior cannot be finalized until this choice is resolved.

## Test Plan

### Unit Tests

- `bareMetalInstanceMapper` extracts resource type, ID, tenant, project, catalog item, instance type, and state from a `BareMetalInstance` proto
- `BareMetalInstanceBillingDimensions()` populates `bm_instance_type` from the non-empty `spec.instance_type` string and populates `catalog_item` from the BareMetalInstance spec
- `BareMetalInstanceBillingDimensions()` does not emit a billable dimension for a missing `spec.instance_type` and records the configuration error
- A changed `spec.instance_type` closes active meter intervals at the authoritative dimension-change timestamp and reopens still-billable meters with the new dimension; historical events retain the old value
- `PROVISIONING` → `STOPPED` sets only `ComponentEverStarted["allocation"]` and emits allocation `started.v1`
- The first `STOPPED` → `RUNNING` sets `ComponentEverStarted["consumption"]` and emits consumption `started.v1`; a later stop/start cycle emits consumption `resumed.v1`
- `IsAllocationBillableState()` returns true for `RUNNING`, `STOPPED`, `STARTING`, `STOPPING`, `DELETING`; false for `PROVISIONING`, `FAILED`, `UNSPECIFIED`
- `IsConsumptionBillableState()` returns true for `RUNNING` only
- Allocation transition table registers every pair in the explicit accepted transition set, including repeated snapshots and all provisioning/transient paths
- Consumption transition table registers the same complete pair set with the correct meter-specific effect
- `DecomposeBMIEvents()` produces 0, 1, or 2 events per transition based on meter boundary crossings:
  - `PROVISIONING → RUNNING: 2 events (allocation started + consumption started)
- `RUNNING` → `STOPPING`: 1 event (consumption suspended)
  - `STOPPED` → `RUNNING`: 1 event (consumption resumed)
  - `RUNNING` → `DELETING`: 1 event (consumption suspended; allocation remains active)
  - `STOPPED`/`STARTING`/`STOPPING` → `DELETING`: 0 events (allocation remains active)
  - `RUNNING` → `FAILED`: 2 events (allocation suspended + consumption suspended)
  - `FAILED` → `RUNNING`: 2 events (allocation resumed + consumption resumed)
  - `PROVISIONING` → `STOPPED`: 1 event (allocation started; consumption remains inactive)
  - `STOPPED` → `STARTING`: 0 events (allocation remains active; consumption remains inactive)
  - `OBJECT_DELETED` with both intervals active: 2 suspensions plus 1 deletion audit event, with stable IDs on redelivery
  - `OBJECT_DELETED` with no active intervals: deletion audit event only
  - `STOPPED` → `STOPPED`: 0 events
- Heartbeat decomposer produces 2 heartbeats for `RUNNING`, 1 for `STOPPED`/`STARTING`/`STOPPING`/`DELETING`, and 0 for `FAILED`
- Reconciliation billability checker uses allocation-billable states
- Correction event decomposer produces per-meter corrections matching the state drift direction

### Integration Tests

- Reconciliation detects a `BareMetalInstance` present in fulfillment but missing from projection and emits `missed_creation` correction with correct allocation billability
- Reconciliation replays a `RUNNING` → `STOPPING` transition when the projection has `RUNNING` and fulfillment has `STOPPED`, emitting a correction for the consumption meter only; allocation remains billable
- Release gate: reconciliation replays a complete `RUNNING` → `STOPPED` → `RUNNING` cycle during a simulated Watch outage and restores the stopped interval from the replayed transitions before BMaaS billing is enabled.
- Reconciliation detects a BareMetalInstance in projection but absent from fulfillment and emits `missed_deletion` correction
- Stale heartbeat detection generates synthetic heartbeats for allocation-billable BMaaS resources with correct meter decomposition

### E2E Tests

- Full BMaaS lifecycle: create host → wait for `RUNNING` → verify allocation and consumption events in echo adapter → stop host → verify consumption suspended, allocation heartbeats continue → start host → verify consumption resumed → delete host → verify both meters suspended
- Verify echo adapter stores events with correct `meter_type` billing dimension
- Verify event `duration_seconds` accuracy: stop a host after a known interval and assert the consumption `suspended.v1` event's `duration_seconds` is within tolerance

## Upgrade / Downgrade Strategy

This is a new metering capability with no upgrade impact on existing VMaaS/CaaS metering. The metering-service binary gains BMaaS support — on upgrade, it begins consuming BareMetalInstance Watch events and producing CloudEvents. On downgrade, BMaaS events stop being produced; no cleanup is needed since Kafka topics are shared and BMaaS events are differentiated by `osacresourcetype`.

The State Projection schema does not change — `ComponentBillableSince` is an existing JSONB column that gains a `"consumption"` key for BMaaS resources. Downgrade leaves orphaned `"consumption"` keys in the JSONB column, which are harmless (ignored by VMaaS/CaaS code paths).

## Version Skew Strategy

The metering-service is a standalone deployment — it does not run alongside a previous version during upgrades. The fulfillment-service Watch stream is backward-compatible (new event payload types are additive). If the metering-service is upgraded before the fulfillment-service has BareMetalInstance support, the metering-service simply receives no BareMetalInstance events (Watch subscription is filtered by resource type). No coordination is required beyond ensuring the fulfillment-service includes BareMetalInstance in its Watch stream.

## Support Procedures

**Detecting BMaaS metering failures:**

- `osac_metering_bmi_events_total` flatlines while `BareMetalInstance` lifecycle changes are occurring → Watch Consumer is not receiving BMaaS events
- `osac_metering_reconciliation_corrections_total{resource_type="bare_metal_instance"}` consistently > 0 → Watch Consumer is missing events; investigate Watch stream connectivity

**Disabling BMaaS metering:** Remove `bare_metal_instance` from the metering-service's Watch subscription filter (configurable via Helm values). Existing BMaaS projection rows remain in PostgreSQL but are cleaned up by the next reconciliation cycle (missed_deletion). No impact on VMaaS/CaaS metering.

**Re-enabling:** Restore the Watch subscription filter. Startup reconciliation seeds the projection with current BareMetalInstance state. Brief gap until reconciliation completes; heartbeats resume immediately after.

## Infrastructure Needed

No new metering deployment artifacts are required. BMaaS metering depends on the fulfillment-service durable transition history/cursor and deletion completion timestamp contracts described above, in addition to the existing metering-service binary, Kafka topics, PostgreSQL State Projection, and Provider Adapter framework.
