---
title: import-hub-registered-clusters-for-ai-workloads
authors:
  - eranco@redhat.com
creation-date: 2026-10-19
last-updated: 2026-10-21
tracking-link:
  - https://redhat.atlassian.net/browse/OSAC-6488
prd:
  - "prd.md"
see-also:
  - "/enhancements/OSAC-3046-per-service-enablement"
  - "/enhancements/OSAC-1604-granular-cluster-status-reporting"
replaces:
  - N/A
superseded-by:
  - N/A
---

# Register Hub-Managed Clusters as Workload Clusters

| Field       | Value |
|-------------|-------|
| Author(s)   | Eran Cohen |
| Jira        | [OSAC-6488](https://redhat.atlassian.net/browse/OSAC-6488) |
| PRD         | [prd.md](prd.md) |
| Date        | 2026-10-21 |

# 1. Overview

This design introduces a provider-global `WorkloadCluster` resource in the
fulfillment-service that allows Cloud Provider Admins (CPAs) to register
ACM hub-managed clusters for use as OSAC workload targets. Each
WorkloadCluster is a canonical representation of one physical cluster
identified by a `(source_hub_id, managed_cluster_name)` pair with global
uniqueness. The WorkloadCluster is a provider-level resource visible and
manageable only by CPAs. All registered clusters provide shared provider
capacity; tenant-to-workload-cluster assignment and placement/isolation
policy are deferred to a future cross-workload design that collects use
cases across MaaS, VMaaS, and other workload types. See [PRD](prd.md)
for detailed requirements.

The design directly consumes OCM `ManagedCluster` CRDs on the Hub via
list/watch reconciliation, uses declarative conditions rather than an
imperative state machine, and defines an additive `supported_workloads`
capability list that starts with MaaS and accommodates future workload
types (e.g., VMaaS) without schema migration. A single ACM Hub is active
in this increment; the schema includes an immutable `source_hub_id` for
future multi-hub compatibility.

## 1.1 Terminology

| Term | Definition |
|------|------------|
| **WorkloadCluster** | The provider-global OSAC resource introduced by this design, representing one registered physical cluster. |
| **CPA** | Cloud Provider Admin — the OSAC role authorized to register and manage WorkloadClusters. |
| **ACM Hub** | The Advanced Cluster Management for Kubernetes management plane that tracks ManagedClusters. |
| **ManagedCluster** | An OCM custom resource on the Hub representing a cluster accepted into ACM management. |
| **OCM** | Open Cluster Management — the CNCF project providing the `cluster.open-cluster-management.io/v1` CRD API consumed by the controller. |
| **MaaS** | The OSAC managed AI workload placement service; the initial workload type for registered clusters. |

# 2. Goals and Non-Goals

## 2.1 Goals

- Define a provider-global canonical `WorkloadCluster` resource with
  global physical uniqueness enforced by `UNIQUE (source_hub_id,
  managed_cluster_name)` at the database layer, independent of the existing
  CaaS `Cluster` resource.
- Include an immutable `source_hub_id` field in the spec validated against
  the configured single Hub, with documented future multi-hub resolution
  path.
- Continuously reflect Hub cluster state by consuming OCM
  `ManagedCluster` CRDs directly via list/watch on the Hub's Kubernetes
  API, with explicit trust, RBAC, version, and availability contracts
  documented.
- Surface cluster readiness through declarative conditions (`Available`,
  `HubReachable`) that reflect current observed state, avoiding
  imperative state machines or polling.
- Allow clusters to declare workload capabilities via an additive
  `supported_workloads` list starting with `maas`, enabling future
  `vmaas` coexistence without schema migration.
- Model registration as explicit external-infrastructure registration
  while preserving a canonical day-2 WorkloadCluster shape that future
  CaaS automatic provisioning can create.
- Restrict all WorkloadCluster discovery and management to the CPA role;
  tenant workloads consume capacity indirectly through MaaS placement.

## 2.2 Non-Goals

- Disconnecting registered clusters from OSAC (deferred per PRD Out of
  Scope).
- Introducing an anti-corruption adapter between OSAC and OCM CRDs.
  Direct CRD consumption is the chosen approach; extraction triggers are
  documented in §4.8.
- Active multi-hub routing or dynamic Hub discovery. This increment uses
  one configured Hub.
- Site-level or multi-cluster datacenter aggregation. Each WorkloadCluster
  maps 1:1 to a ManagedCluster leaf. Parent aggregate resources require a
  future PRD.
- CaaS automatic cluster provisioning. This increment covers external
  registration only; future CaaS integration creates WorkloadClusters
  automatically through the same resource shape.
- Managing ACM/Praxis policies, cluster labels, or customer GitOps
  workflows for AI Grid configuration.

# 3. Motivation / Background

OSAC needs to track and interact with the clusters on which it places
tenant workloads. Cloud providers that manage AI Grid clusters through ACM
currently have no way to register those clusters in OSAC, so their
capacity cannot participate in MaaS AI workload placement. The
`WorkloadCluster` resource introduced by this design gives OSAC a
canonical representation of each registered cluster, enabling visibility,
condition monitoring, and future placement integration. See the
[PRD](prd.md) for the full requirements context.

**Background note:** OSAC's existing CaaS `Cluster` resource serves a
different purpose — it is coupled to HyperShift-based provisioning and
carries fields inapplicable to externally managed clusters. The
`WorkloadCluster` resource is distinct and new, providing clean separation
between provisioned and registered cluster lifecycles while sharing a
canonical shape that future provisioning modes can also target.

# 4. Design

## 4.1 Architecture

The `WorkloadCluster` resource lives entirely within the
fulfillment-service. No Kubernetes CRD is created on the OSAC operator
or on the target cluster. The fulfillment controller validates and
monitors the referenced `ManagedCluster` directly on the ACM Hub's
Kubernetes API.

**Components:**

1. **WorkloadCluster gRPC service** — List, Get, Create, Update, Signal
   RPCs in the fulfillment-service, registered conditionally behind the
   `--enable-maas` flag per the OSAC-3046 pattern. Delete is deferred
   to a future increment aligned with disconnect scope (see IC-4).
2. **Fulfillment controller** — A reconciler in
   `fulfillment-service/internal/controllers/` that maintains a
   SharedInformer (list/watch) on `managedclusters.cluster.open-cluster-management.io/v1`
   on the Hub. On ManagedCluster events, it reconciles the corresponding
   WorkloadCluster's conditions.
3. **PostgreSQL database** — Standard OSAC table with a global uniqueness
   constraint on `(source_hub_id, managed_cluster_name)`.

**Registration flow:**

```mermaid
sequenceDiagram
    participant CPA as Cloud Provider Admin
    participant API as Fulfillment API
    participant DB as PostgreSQL
    participant Ctrl as Fulfillment Controller
    participant Hub as ACM Hub K8s API

    CPA->>API: WorkloadClusters.Create(source_hub_id, managed_cluster_name, supported_workloads)
    API->>DB: Validate uniqueness, insert record
    API-->>CPA: WorkloadCluster (Available=Unknown)

    Note over Ctrl,Hub: Controller maintains list/watch on ManagedCluster resources
    Note over Ctrl: Registration-triggered reconciliation: Hub readiness gate
    alt Hub client authenticated and informer synced
        alt ManagedCluster exists and accepted
            Ctrl->>DB: Set Available=True, HubReachable=True, store managed_cluster_uid
        else Not found or not accepted
            Ctrl->>DB: Set Available=False with reason
        end
    else Hub client not ready (credential failure, informer not synced)
        Ctrl->>DB: Set HubReachable=False, Available=False (HubUnreachable)
    end
    Hub-->>Ctrl: ManagedCluster event (add/update)
    Ctrl->>DB: Reconcile conditions (same Hub readiness gate applies)

    CPA->>API: WorkloadClusters.Get(id)
    API-->>CPA: WorkloadCluster (conditions reflect current state)
```

The diagram shows the registration and reconciliation flow. The Create RPC
returns immediately after database insertion. The controller independently
watches ManagedCluster resources on the Hub and updates conditions as the
cluster's state changes. This is a declarative model: conditions always
reflect the current observed state of the ManagedCluster, not the history
of a one-time import operation. The CPA observes the outcome by reading
the resource at any time.

**Reconciliation triggers:** The Hub list/watch informer is the primary
reconciliation path for ongoing state changes. Three additional triggers
ensure timely initial reconciliation and resilience:

1. **Registration-triggered reconciliation.** After a successful Create
   RPC inserts the database record, the controller performs a **Hub
   readiness check** before consulting the informer cache:

   1. **Hub readiness gate.** The controller checks whether the Hub
      client is authenticated and the SharedInformer has completed its
      initial list-and-sync (i.e., `HasSynced()` returns true). If the
      Hub client is not authenticated or the informer has not synced,
      the controller sets `HubReachable=False` and `Available=False`
      with reason `HubUnreachable` on the newly created record. It
      must **not** consult the informer cache in this state — an
      empty or unsynchronized cache would falsely report
      `ManagedClusterNotFound` for clusters that exist on the Hub but
      have not been cached. This gate applies identically to newly
      created and existing records during any reconciliation path.

   2. **Informer cache lookup (Hub ready only).** When the Hub client
      is authenticated and the informer has synced, the controller
      looks up the referenced `managed_cluster_name` in the informer's
      current cache. If the ManagedCluster exists, the controller
      writes the appropriate conditions (`Available=True` or
      `Available=False` with reason). If the ManagedCluster is not in
      the cache, the controller sets `Available=False` with reason
      `ManagedClusterNotFound`.

   This two-step ordering ensures that `ManagedClusterNotFound` is
   reported only when the informer cache is authoritative (Hub client
   authenticated, informer synced), and that credential or connectivity
   failures are always surfaced as `HubUnreachable`. A registration
   for an already-synced upstream name transitions out of `Unknown`
   without waiting for a subsequent Hub event; a registration created
   during a credential outage reports `HubUnreachable` promptly rather
   than the misleading `ManagedClusterNotFound`.

2. **Startup reconciliation.** On controller startup, the controller
   reconciles all existing WorkloadCluster records in the database.
   The same Hub readiness gate applies: if the Hub client fails
   authentication during startup (missing or invalid credential), all
   existing records receive `HubReachable=False` and `Available=False`
   with reason `HubUnreachable` before any informer cache lookup is
   attempted. When the Hub client is authenticated and the
   SharedInformer completes its initial list and cache sync, the
   controller reconciles each record against the current informer
   cache. When the credential is later corrected and the service
   restarted, startup reconciliation runs again with a healthy Hub
   client and synced informer, restoring accurate conditions for all
   records. This recovers conditions after controller restarts and
   corrects any stale condition state, including stale
   `HubUnreachable` conditions from a prior credential outage.

3. **Retry after failed status writes.** If a condition write to
   PostgreSQL fails (transient database error, connection timeout), the
   controller retries with exponential backoff. The pending update is
   re-enqueued; the controller does not silently drop the observation.
   The retry applies to all reconciliation paths (Hub events,
   registration-triggered, and startup).

**Direct OCM CRD consumption:** The fulfillment controller directly
consumes `ManagedCluster` CRDs from the Hub's Kubernetes API without an
intermediate anti-corruption adapter. This follows existing OSAC patterns
for external CRD consumption. The trust contract is:

| Dependency | Contract |
|---|---|
| API group | `cluster.open-cluster-management.io/v1` (GA, stable) |
| RBAC | Read-only: `get`, `list`, `watch` on `managedclusters` |
| Required conditions | `HubAcceptedManagedCluster`, `ManagedClusterConditionAvailable` |
| Required claims | `id.k8s.io` ClusterClaim for stable UID |
| Availability | Hub API must be reachable; transient failures are tolerated via watch reconnect |
| Version pinning | Client pins `cluster.open-cluster-management.io/v1`; version bumps require controller update |

**Extraction triggers** for introducing an adapter layer in the future:
- OCM deprecates the `v1` ManagedCluster API with a breaking successor
- A second Hub vendor with a different CRD schema must be supported
- The consumed CRD surface exceeds the current read-only contract (e.g.,
  write operations become necessary)

**1:1 ManagedCluster leaf mapping:** Each WorkloadCluster maps to exactly
one ManagedCluster on one Hub. Site-level or multi-cluster datacenter
aggregation (grouping multiple ManagedClusters under a parent resource)
is out of scope and requires a future parent aggregate PRD.

## 4.2 Data Model / Schema Changes

New migration creates the `workload_clusters` table. This is a
provider-level resource with no `tenant` column — all registered clusters
provide shared provider capacity.

```sql
CREATE TABLE workload_clusters (
  id TEXT PRIMARY KEY,
  name TEXT,
  creation_timestamp TIMESTAMP,
  deletion_timestamp TIMESTAMP,
  finalizers TEXT[],
  creator TEXT,
  labels JSONB,
  annotations JSONB,
  data JSONB,
  version INTEGER
);

CREATE TABLE archived_workload_clusters (
  LIKE workload_clusters INCLUDING ALL,
  archival_timestamp TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_workload_clusters_name
  ON workload_clusters (name);
CREATE INDEX idx_workload_clusters_labels
  ON workload_clusters USING GIN (labels);

-- Global physical uniqueness: one canonical record per physical cluster.
-- Enforces that no two non-deleted WorkloadClusters reference the same
-- ManagedCluster on the same Hub.
CREATE UNIQUE INDEX uq_workload_clusters_hub_identity
  ON workload_clusters (
    (data->'spec'->>'source_hub_id'),
    (data->'spec'->>'managed_cluster_name')
  )
  WHERE deletion_timestamp IS NULL;
```

The `uq_workload_clusters_hub_identity` index is the authoritative
concurrency guard for physical uniqueness. The DAO translates a
constraint-violation error from this index into an `AlreadyExists` gRPC
status. The application-level lookup described in §4.3 is an early error
check that provides user-friendly messages but is not the concurrency
guard.

**Provider-global generic server adaptation:** The OSAC generic server
layer normally scopes resources by tenant (tenant column, tenant filter
in List/Get, `(tenant, project, resource_type, name)` uniqueness). Because
WorkloadCluster is a provider-level resource with no tenant column, the
following adaptations are required:

- **DAO:** The WorkloadCluster DAO must omit tenant filtering from List
  and Get queries. Name uniqueness is enforced globally per resource type,
  not per tenant/project.
- **OPA:** The WorkloadCluster authorization policy must evaluate CPA role
  membership without requiring a tenant context in the request. All four
  permissions (`workload_cluster:{list,get,create,update}`) are granted
  only to the CPA role. Delete is deferred (see IC-4).
- **Generic server registration:** The WorkloadCluster service must be
  registered as a provider-level resource so the generic server layer
  bypasses tenant scoping.

These adaptations match the approach used for other provider-level
resources (e.g., the Tenant resource itself is managed by admins, not
scoped to a tenant).

**Post-validation immutable UID:** After the controller first validates
the ManagedCluster, it extracts the `id.k8s.io` ClusterClaim and stores
it as `managed_cluster_uid` in the status JSONB. This UID is immutable after
first write — if the controller detects a different UID for the same
`managed_cluster_name`, it sets `Available=False` with reason
`ClusterIdentityMismatch`, indicating the name now points to a different
physical cluster.

**Recovery from identity mismatch:** Because the UID is immutable and
Delete is deferred, self-service replacement is blocked in this
increment. The CPA cannot create a new WorkloadCluster with the same
`(source_hub_id, managed_cluster_name)` because the uniqueness constraint
rejects it while the existing non-deleted record holds the slot. The CPA
also cannot update `managed_cluster_uid` because it is a controller-managed
status field. The authorized recovery paths are:

1. **Platform operator database cleanup:** The platform operator
   soft-deletes the mismatched WorkloadCluster record (sets
   `deletion_timestamp` and archives the row), releasing the uniqueness
   slot. The CPA then creates a new registration with the same Hub
   identity, and the controller populates the new UID.
2. **Wait for disconnect:** When the disconnect increment is
   implemented, the CPA will be able to delete the mismatched
   registration through the API and re-register.

This is an honest limitation of deferring Delete — see §16 Drawbacks.

## 4.3 API Changes

### Proto Schema

**`proto/private/osac/private/v1/workload_cluster_type.proto`**

```protobuf
message WorkloadCluster {
  string id = 1;
  Metadata metadata = 2;
  WorkloadClusterSpec spec = 3;
  WorkloadClusterStatus status = 4;
}

message WorkloadClusterSpec {
  // Identifier of the ACM Hub where the ManagedCluster is registered.
  // Immutable after creation. Required.
  // Validated against the fulfillment-service's configured Hub identity.
  // Future increments may support multiple Hubs with dynamic routing;
  // the schema supports this without migration.
  string source_hub_id = 1;

  // Name of the ManagedCluster resource on the Hub.
  // Immutable after creation. Required.
  // Together with source_hub_id, forms the globally unique physical
  // identity of this cluster.
  string managed_cluster_name = 2;

  // Additive list of workload capabilities this cluster supports.
  // At least one value required. Known values: "maas".
  // Unknown values are rejected with InvalidArgument.
  // Future values (e.g., "vmaas") are added to the validation
  // allow-list without schema migration.
  repeated string supported_workloads = 3;
}

message WorkloadClusterStatus {
  // Conditions describing the current observed state.
  // No state enum — conditions are the canonical status representation.
  repeated WorkloadClusterCondition conditions = 1;

  // Stable cluster UUID from the ManagedCluster's id.k8s.io
  // ClusterClaim. Set by the controller after first successful
  // validation. Immutable after first write. Used for physical
  // identity verification.
  string managed_cluster_uid = 2
      [(cleanapi.field).private = true];
}

message WorkloadClusterCondition {
  // Condition type.
  string type = 1;
  // Condition status: "True", "False", or "Unknown".
  string status = 2;
  // Machine-readable reason code (CamelCase).
  string reason = 3;
  // Human-readable message.
  string message = 4;
  // Timestamp of last status/reason change. Updated only when status
  // or reason actually transitions to a different value.
  google.protobuf.Timestamp last_transition_time = 5;
  // Timestamp of last controller observation confirming this condition.
  // Updated on every re-validation cycle (every 5 minutes) and on
  // every reconciliation event, regardless of whether status changed.
  // Consumers use this for freshness checks (see §4.6).
  google.protobuf.Timestamp last_observed_time = 6;
}
```

**Condition types and semantics:**

These conditions report **registration and Hub state only**. They do not
assert workload-placement eligibility, AI operator readiness, or policy
compliance. Placement decisions are owned by Praxis (see §4.3 Placement
Filtering); AI-readiness checks (e.g., verifying that AI Grid operators
or inference policies are installed) are deferred to the integration
follow-up.

| Condition | True | False | Unknown |
|---|---|---|---|
| `Available` | ManagedCluster exists on Hub, is accepted, reports `ManagedClusterConditionAvailable=True`, and Hub is reachable. This is a Hub/registration availability signal; it does not establish that AI operators or workload policies are installed. | ManagedCluster not found, not accepted, `ManagedClusterConditionAvailable` is not True, or identity mismatch. | Initial state after Create; controller has not yet reconciled. |
| `HubReachable` | Hub Kubernetes API is reachable and responding. | Hub API is unreachable. Transient condition; controller reconnects via watch. | Initial state or during controller restart. |

**`ManagedClusterConditionAvailable` mapping:** ACM's
`ManagedClusterConditionAvailable` indicates that the Hub can reach the
managed cluster's API server. The controller maps it as follows:
- `ManagedClusterConditionAvailable=True`: contributes to `Available=True`
  (along with existence, acceptance, and reachability).
- `ManagedClusterConditionAvailable=False` or absent: sets `Available=False`
  with reason `ManagedClusterUnavailable`. This is an ACM-level
  availability signal; it does not indicate whether AI inference
  infrastructure is installed or functional on the cluster.

The trust-contract table in §4.1 lists `ManagedClusterConditionAvailable`
as a required condition. AI-readiness verification (operator presence,
policy compliance, GPU availability) is explicitly deferred to the Praxis
integration follow-up.

**Condition reasons (predefined, allow-listed):**

| Reason | Condition | Meaning |
|---|---|---|
| `ValidationSucceeded` | Available=True | ManagedCluster validated and accepted |
| `ManagedClusterNotFound` | Available=False | No ManagedCluster with this name on the Hub |
| `ManagedClusterNotAccepted` | Available=False | ManagedCluster exists but `HubAcceptedManagedCluster` is not True |
| `HubUnreachable` | Available=False, HubReachable=False | Cannot reach Hub API |
| `ClusterIdentityMismatch` | Available=False | `managed_cluster_uid` changed — name points to different physical cluster |
| `ManagedClusterUnavailable` | Available=False | ManagedCluster exists and is accepted but `ManagedClusterConditionAvailable` is not True |

Note: there is no `Failed` state or condition on the WorkloadCluster. A
registration lookup failure does not mean the cluster itself has failed —
it means the referenced ManagedCluster was not found or not accepted on
the Hub at the time of observation. The `Available` condition reflects the
current observed state and updates declaratively as the situation changes.

**Validation rules:**

| Field | Rule | Error |
|---|---|---|
| `source_hub_id` | Non-empty; must match the configured Hub identity | `InvalidArgument` |
| `managed_cluster_name` | Non-empty; DNS label format (RFC 1123) | `InvalidArgument` |
| `supported_workloads` | At least one value; all values in allow-list (`maas`) | `InvalidArgument` for empty or unknown values |
| `source_hub_id` | Immutable after creation | `InvalidArgument` on update |
| `managed_cluster_name` | Immutable after creation | `InvalidArgument` on update |

**Unknown `supported_workloads` value behavior:** The Create and Update
handlers reject any value not in the current allow-list with
`InvalidArgument` and a message listing accepted values. This prevents
clusters from being registered with capabilities the system cannot verify
or use. The allow-list is extended in code when new workload types are
implemented — no database migration is needed.

**`proto/private/osac/private/v1/workload_clusters_service.proto`**

Standard service following the OSAC pattern: List, Get, Create, Update,
Signal (private). Create is the public registration operation. Delete is
deferred (see IC-4).

HTTP route mapping: `option (cleanapi.file).http_route_prefix_map =
"private:fulfillment"` rewrites `/api/private/v1/workload-clusters` to
`/api/fulfillment/v1/workload-clusters` in the public API.

### Duplicate Detection

The Create handler performs one application-level check before insertion:

- Queries existing non-deleted WorkloadClusters for a matching
  `(source_hub_id, managed_cluster_name)` pair. Returns `AlreadyExists`
  with a generic message: "a workload cluster with the specified hub
  identity already exists." The message does not interpolate
  `managed_cluster_name` or `source_hub_id` — the CPA can identify the
  conflict from the request parameters.

This check is an early user-friendly error path. The database unique
index `uq_workload_clusters_hub_identity` is the authoritative
concurrency guard: two concurrent Create requests with the same
`(source_hub_id, managed_cluster_name)` but different OSAC names may both
pass the application check, but only one insert succeeds. The DAO
translates the constraint violation to `AlreadyExists`.

Name uniqueness within the resource type is enforced by the generic server
layer.

### Placement Query (Data Foundation)

This increment defines the **data foundation** for placement queries.
The WorkloadCluster schema and List RPC support filtering by
`supported_workloads` and `Available` condition status. These filters
enable a future trusted consumer to discover eligible clusters:

1. Filter by `supported_workloads` containing `"maas"`.
2. Filter by `Available=True` condition (with freshness check per §4.6).

This query uses the standard List RPC with CEL filter expressions. No
additional query endpoints are required for this increment.

**Praxis integration (deferred — follow-up required):** The detailed
Praxis placement integration — including trusted service authorization,
the placement API contract, and actual workload scheduling on registered
clusters — is deferred to a dedicated follow-up. This increment provides
the queryable resource and capacity metadata; it does not implement the
placement consumer. The following boundaries are preserved for the
follow-up:

- **Praxis owns placement** across registered clusters. The
  WorkloadCluster List RPC provides the discovery query; Praxis
  determines actual scheduling.
- **Human-facing management remains CPA-only.** No tenant role gains
  WorkloadCluster visibility through the placement integration.

**Tenant-to-cluster assignment and isolation (deferred):** This increment
does not model tenant-specific cluster assignment, dedicated tenant
infrastructure, or workload-level isolation policy. These concerns
span multiple workload types (MaaS, VMaaS, and future services) and
require use cases to be collected across those types before designing
a cross-workload tenant-to-cluster model. Specific deferred items
include:

- Tenant entitlement fields on WorkloadCluster (e.g., restricting
  clusters to specific tenants).
- Dedicated vs. shared tenant infrastructure and exclusive-placement
  guarantees.
- Workload-level isolation within a shared cluster.
- Trusted service access enforcement for placement consumers.

These are deferred to a future cross-workload design.

**Follow-up owner:** Praxis/MaaS team. Delivery dependency: FR-5 is
satisfied for this registration increment by providing shared provider
capacity metadata. The detailed Praxis placement, trusted service access,
tenant isolation, and dedicated infrastructure are not acceptance criteria
for this increment — they are tracked as follow-up work.
See [OSAC-6488 follow-up tracking](https://redhat.atlassian.net/browse/OSAC-6488)
(sub-tasks to be created by Feature owner).

## 4.4 Scalability and Performance

**CPU and memory:** The fulfillment controller maintains one
SharedInformer for ManagedCluster resources on the Hub. Memory usage
scales linearly with the number of ManagedClusters on the Hub
(typically tens to low hundreds). CPU usage is event-driven — the
controller processes only ManagedCluster add/update/delete events.

**Database load:** Registration is a low-frequency CPA operation (tens of
clusters, not thousands). Read load from MaaS placement queries scales
with placement frequency, not cluster count. The GIN index on labels and
the uniqueness index are sufficient for this scale.

**Storage:** Each WorkloadCluster record is a single JSONB row.
Negligible storage impact.

**Assumptions:** The deployment supports up to ~500 registered
WorkloadClusters per Hub. Beyond this, the SharedInformer's memory
footprint should be evaluated. The current design does not require
pagination or sharding for the ManagedCluster watch.

## 4.5 Security Considerations

The WorkloadCluster resource inherits the existing OSAC security model:
JWT authentication and OPA authorization.

**OPA permissions (CPA-only):**
- `workload_cluster:list` — Cloud Provider Admin
- `workload_cluster:get` — Cloud Provider Admin
- `workload_cluster:create` — Cloud Provider Admin
- `workload_cluster:update` — Cloud Provider Admin

Delete is deferred (see IC-4). The `workload_cluster:delete` permission
is intentionally absent from the OPA policy; all Delete requests receive
`PermissionDenied` at the authorization layer regardless of caller role.
No other role has any WorkloadCluster permission. Tenant workloads
consume capacity indirectly through MaaS placement.

**Input validation:**
- `managed_cluster_name` validated as DNS label (RFC 1123).
- `source_hub_id` validated against the configured Hub identity.
- `supported_workloads` validated against the allow-list.
- No user-supplied data is forwarded to the Hub API without validation.

**Credential ownership and lifecycle:** The fulfillment controller
authenticates to the Hub using a kubeconfig mounted from the
`hub-kubeconfig` Secret in the fulfillment-service namespace.

- **Provisioning:** The Secret is not created by the controller. The
  OSAC Helm chart's `values.yaml` includes a
  `fulfillment.hubKubeconfig.secretName` reference. The operator or
  installer creates the Secret from an existing kubeconfig provided by
  the CPA during installation or day-2 configuration. The controller
  assumes the Secret exists and is valid at startup.
- **Scope:** The credential grants read-only access (`get`, `list`,
  `watch`) to `managedclusters` on the Hub — no write operations are
  performed.
- **Missing or invalid credential:** If the Secret is missing or its
  contents fail authentication, the controller logs a redacted error at
  startup (no credential content in the log) and sets both
  `HubReachable=False` and `Available=False` (reason `HubUnreachable`)
  on all existing WorkloadClusters. Stale `Available=True` conditions
  must not persist when the controller cannot verify Hub state.
- **Create during credential failure:** The Create RPC remains a local
  database registration operation — it succeeds whenever local
  validation and uniqueness checks pass, regardless of Hub client
  state. Create does not gate on Hub reachability because registration
  is a persistence operation, not a Hub operation. However,
  registration-triggered reconciliation (§4.1) applies the Hub
  readiness gate: because the Hub client is not authenticated and the
  informer has not synced, reconciliation sets `HubReachable=False`
  and `Available=False` with reason `HubUnreachable` on the newly
  created record. It must **not** consult the empty/unsynchronized
  informer cache — doing so would falsely report
  `ManagedClusterNotFound` for clusters that exist on the Hub but
  have not been cached. This ensures the CPA sees an honest
  `HubUnreachable` condition, not a misleading `NotFound`.
- **Recovery after credential fix:** When the credential is corrected
  and the fulfillment-service is restarted, the controller
  re-establishes the Hub watch and startup reconciliation (§4.1)
  refreshes all conditions — both pre-existing records and records
  created during the outage. Clusters whose ManagedClusters are
  healthy transition from `HubUnreachable` to `Available=True`
  automatically. Records whose `managed_cluster_name` does not match any
  ManagedCluster transition to `Available=False` with the accurate
  reason `ManagedClusterNotFound` (now trustworthy because the
  informer cache is synchronized).
- **Rotation:** Credential rotation requires updating the Secret
  contents and restarting the fulfillment-service pod (or pods, if
  scaled) to pick up the new credential. The controller does not
  watch the Secret for changes. Operational documentation must include
  the rotation procedure (update Secret, rollout restart). During the
  restart window, the Hub watch is temporarily interrupted; both
  `HubReachable=False` and `Available=False` are set until the new
  credential establishes a connection and startup reconciliation
  refreshes conditions.
- **Zeroization:** The kubeconfig is mounted as a read-only volume.
  The controller reads it into memory at startup to initialize the Hub
  client. The in-memory client object holds the credential for the
  process lifetime. On pod termination, the container's memory is
  reclaimed by the container runtime. No additional zeroization is
  performed beyond standard container lifecycle cleanup.
- **Post-quantum cryptography:** Post-quantum TLS or credential
  protection for the Hub connection is out of scope for this increment.
  The connection uses the standard TLS configuration of the Kubernetes
  client library.

**Failure message exposure:** Condition `reason` and `message` fields
use only predefined reason codes and generic cause descriptions (see
§4.3 condition reasons table). Messages must not interpolate
`managed_cluster_name`, `ManagedCluster` names, Hub URLs, or any value
listed in the denied-fields set below. These fields are visible only to
CPAs. Condition messages are treated as potentially loggable — they must
comply with the redaction policy even though they are not log entries
themselves. The CPA uses the WorkloadCluster's own spec fields
(`source_hub_id`, `managed_cluster_name`) alongside the generic condition
message to identify the affected cluster.

**Logging redaction policy:** All structured log entries emitted by the
WorkloadCluster service and controller comply with the following policy:

- **Allowed fields:** opaque OSAC resource ID (`workload_cluster_id`),
  `supported_workloads` values, condition type and status, predefined
  reason code, Prometheus metric labels, request latency.
  **Required metadata fields** (always present in structured log
  entries): `component` (service name), `operation` (RPC or controller
  action name), `request_id` (opaque, non-sensitive correlation ID).
  These metadata fields are part of the allow-list.
- **Denied fields (must never appear in any log level):** tenant
  identifiers, ManagedCluster names, `managed_cluster_name` spec values,
  credentials, kubeconfig content, raw Hub API error bodies, stack
  traces, Hub URLs, internal network addresses, and bearer tokens.
- **Format:** JSON structured logging via the project's standard `slog`
  configuration.
- **Validation:** Unit tests assert that controller log output for each
  failure mode contains only allowed fields. Integration tests assert
  that no denied field appears in combined service log output for a
  complete registration cycle. See §10 Test Plan.

## 4.6 Failure Handling and Recovery

All controller operations are idempotent and declarative. Conditions
reflect current observed state, not operation history. Recovery is
automatic when the underlying situation resolves.

| Failure Mode | Condition Effect | Recovery | CPA Observes |
|---|---|---|---|
| ManagedCluster not found on Hub | `Available=False`, reason `ManagedClusterNotFound` | Automatic: when ManagedCluster is created on Hub, watch event or registration-triggered lookup updates conditions | Condition message: "Referenced managed cluster not found on the hub" |
| ManagedCluster not accepted by Hub | `Available=False`, reason `ManagedClusterNotAccepted` | Automatic: when Hub accepts the ManagedCluster, watch event triggers update | Condition message: "Referenced managed cluster exists but is not accepted by the hub" |
| ManagedCluster unavailable on Hub | `Available=False`, reason `ManagedClusterUnavailable` | Automatic: when `ManagedClusterConditionAvailable` becomes True, watch event triggers update | Condition message: "Referenced managed cluster is accepted but not available" |
| Hub API unreachable | `Available=False`, `HubReachable=False`, reason `HubUnreachable` | Automatic: watch reconnects when Hub recovers; conditions update on reconnection | Condition message: "Cannot reach hub to validate cluster registration" |
| Create during Hub credential failure | Create RPC succeeds (local validation/uniqueness only). Registration-triggered reconciliation applies Hub readiness gate: `Available=False`, `HubReachable=False`, reason `HubUnreachable`. Informer cache is **not** consulted — `ManagedClusterNotFound` is never reported in this state. | After credential fix and restart, startup reconciliation restores accurate conditions via synced informer cache | Create returns WorkloadCluster with conditions `Unknown`; reconciliation quickly sets `HubUnreachable`. After recovery, conditions reflect actual ManagedCluster state. |
| Hub recovers after outage | `HubReachable=True`; `Available` updated based on ManagedCluster state | Automatic via watch reconnect | Conditions reflect current state |
| ManagedCluster removed from Hub after registration | `Available=False`, reason `ManagedClusterNotFound` | Automatic: when ManagedCluster is re-created on Hub, watch event triggers condition update to `Available=True` | Condition message: "Referenced managed cluster not found on the hub" |
| Cluster identity mismatch (UID changed) | `Available=False`, reason `ClusterIdentityMismatch` | Self-service replacement is blocked in this increment (uniqueness constraint + deferred Delete). Platform operator can soft-delete the record to release the uniqueness slot; CPA then re-registers. See §4.2 recovery path. | Condition message: "Cluster identity changed; administrative action required" |
| Database write failure during Create | Create RPC returns gRPC error | Standard gRPC retry by client | gRPC error (e.g., `Internal`) |
| Duplicate registration attempt | Create RPC returns `AlreadyExists` | No action needed — the existing record is canonical | `AlreadyExists` with descriptive message |

Note: there is no terminal `FAILED` state. The `Available=False` condition
is not a final judgment on the cluster — it describes the current observed
state. If a ManagedCluster that was not found is later created on the Hub,
the watch event or next startup reconciliation triggers condition update
and the condition transitions to `Available=True`. The CPA's only recovery
action is to correct the underlying situation (fix Hub connectivity,
correct the ManagedCluster name, accept the cluster on the Hub) — the
system reconciles automatically.

**Freshness expiry:** Conditions are persisted in PostgreSQL and survive
controller restarts. To prevent stale `Available=True` conditions from
persisting indefinitely when the controller stops observing the Hub, each
condition carries two timestamps: `last_transition_time` (updated only
when the condition's status or reason actually changes) and
`last_observed_time` (updated on every controller observation, including
periodic re-validation). The controller periodically (every 5 minutes)
re-validates all WorkloadCluster conditions against the informer cache
and updates `last_observed_time` on confirmation, whether or not the
status changed. `last_transition_time` changes only on actual status or
reason transitions, preserving Kubernetes condition semantics. Consumers
that require freshness guarantees (e.g., placement queries) should
compare `last_observed_time` against a staleness threshold (recommended:
15 minutes). If the controller is down for longer than the threshold,
`last_observed_time` becomes stale and the cluster should not be selected
for new placements. Startup reconciliation (§4.1) refreshes all
conditions and `last_observed_time` on controller restart, restoring
freshness. The staleness threshold and re-validation interval are
configurable via controller flags.

## 4.7 RBAC / Tenancy

The WorkloadCluster is a **provider-level resource**, not scoped to any
tenant or project. This reflects that the physical cluster infrastructure
belongs to the cloud service provider, not to any individual tenant.

**CPA-only management:** All WorkloadCluster operations — discovery
(List), inspection (Get), registration (Create), and modification
(Update) — are restricted to the Cloud Provider Admin role. Delete is
deferred (see IC-4). Tenant Admins, Tenant Users, and all other roles
receive `PermissionDenied` for every WorkloadCluster RPC. They never
observe WorkloadCluster resources in any API, CLI, or UI surface.

**Shared provider capacity:** All registered WorkloadClusters provide
shared provider capacity available to all tenants through MaaS placement.
Tenant-specific cluster assignment (restricting specific clusters to
specific tenants, dedicated tenant infrastructure, exclusive-placement
guarantees) is deferred to a future cross-workload design that collects
use cases across MaaS, VMaaS, and other workload types. See §4.3
Placement Query for details.

**Tenant workload consumption:** Tenants access registered cluster
capacity indirectly through MaaS AI workload flows. MaaS placement
queries WorkloadClusters with `Available=True` and the appropriate
`supported_workloads` value. Tenants do not know which specific
WorkloadCluster serves their workload — they see only the MaaS workload
result.

**No owner-reference or tenant annotation:** Because WorkloadCluster is
a provider-level resource, it does not carry the standard
`osac.openshift.io/tenant` annotation or `osac.openshift.io/owner-reference`
annotation. The `creator` field in the generic server layer records the
CPA identity for audit purposes.

## 4.8 Extensibility / Future-Proofing

**Adding workload capabilities:** To support VMaaS workloads on
registered clusters, a future increment adds `"vmaas"` to the
`supported_workloads` validation allow-list. No database migration,
schema change, or proto field addition is required. A single cluster can
support both `["maas", "vmaas"]` simultaneously — capabilities are
additive, not exclusive.

**Multi-hub support:** The `source_hub_id` field in the spec uniquely
identifies the Hub. In this increment, the fulfillment controller
validates it against the single configured Hub identity and uses the
single Hub connection. A future multi-hub increment would:
1. Introduce a Hub registry mapping `source_hub_id` to connection
   configuration.
2. Route controller reconciliation to the appropriate Hub connection
   based on `source_hub_id`.
3. No WorkloadCluster schema migration — `source_hub_id` is already
   part of the uniqueness constraint.

The design does not implement dynamic Hub resolution; it documents the
schema readiness for it.

**CaaS automatic registration:** Future CaaS provisioning can create
WorkloadClusters automatically after cluster provisioning completes. The
WorkloadCluster shape is the same regardless of whether registration is
manual (CPA-driven) or automatic (CaaS-driven). A CaaS integration would
call `WorkloadClusters.Create` internally after the provisioned cluster
is registered on the Hub.

**OCM adapter extraction:** The direct OCM CRD consumption described in
§4.1 is the current approach. If an anti-corruption adapter becomes
necessary (see extraction triggers in §4.1), it would be introduced as an
internal layer between the controller and the Hub API without changing the
WorkloadCluster API or schema.

**Sites and cluster groups:** Aggregating multiple WorkloadClusters into
site-level or datacenter-level groups is out of scope. If needed, a future
parent aggregate resource would reference WorkloadClusters without
changing their schema.

# 5. Interface Changes

## IC-1: WorkloadCluster Create (Register) RPC

**Requirements:** FR-1

CPA registers a Hub-managed cluster by calling
`WorkloadClusters.Create` via gRPC or REST
(`POST /api/fulfillment/v1/workload-clusters`), providing
`source_hub_id`, `managed_cluster_name`, `supported_workloads`, and
optionally a display name. Returns the
WorkloadCluster with conditions in `Unknown` state. See §4.3 for the
request schema, validation rules, and duplicate detection.

## IC-2: WorkloadCluster Get/List RPCs

**Requirements:** FR-2, FR-3

CPA retrieves registration status and conditions via
`WorkloadClusters.Get` (by ID) or `WorkloadClusters.List` (with CEL
filter and pagination) through gRPC or REST
(`GET /api/fulfillment/v1/workload-clusters[/{id}]`). Conditions
(`Available`, `HubReachable`) convey the current state. Only CPAs may
call these RPCs. See §4.3 and §4.7.

## IC-3: WorkloadCluster Update RPC

**Requirements:** FR-1

CPA modifies mutable fields (`supported_workloads`, labels) via
`WorkloadClusters.Update`. Immutable fields
(`source_hub_id`, `managed_cluster_name`) are rejected on update. See §4.3
validation rules.

## IC-4: WorkloadCluster Delete RPC — Deferred

**Requirements:** — (Deferred: aligned with PRD disconnect scope)

The PRD explicitly defers disconnecting a registered cluster and removing
its OSAC representation. Exposing a Delete RPC in this registration-only
increment would implement the removal half of disconnect. Delete is
therefore deferred to the increment that defines the full disconnect
lifecycle, including handling of in-flight workloads and placement
dependencies.

**Authorization and dispatch:** The OPA policy does not include a
`workload_cluster:delete` permission. Because the OSAC generic server
runs OPA authorization before handler dispatch, all Delete requests —
from any role, including CPA — receive `PermissionDenied` at the
authorization layer. The Delete handler (`Unimplemented`) is never
reached in practice; it serves as defense-in-depth. This means tests
(U12, E7) expect `PermissionDenied`, not `Unimplemented`.

The proto definition includes the Delete RPC for schema completeness
(standard OSAC pattern). When the disconnect increment adds the full
Delete lifecycle, it adds `workload_cluster:delete` to the OPA policy
for the CPA role and replaces the `Unimplemented` handler with the
actual implementation.

**Cleanup of invalid registrations:** If a narrowly justified
invalid-registration cleanup is required before disconnect is designed
(e.g., correcting a typo in `managed_cluster_name`), the CPA can create a
new WorkloadCluster with the correct name — the old registration with
`Available=False` remains inert and does not affect placement. For
identity-mismatch scenarios where the same `managed_cluster_name` is
needed, see §4.2 recovery path.

## IC-5: CLI Commands

**Requirements:** FR-1, FR-2

- `osac workload-cluster create` — register a cluster.
- `osac workload-cluster list` — list registered clusters with state.
- `osac workload-cluster describe <id>` — show conditions, spec, and
  metadata.
- `osac workload-cluster update` — modify mutable fields.

CLI commands map to the gRPC service. Delete is deferred (see IC-4).
See §4.3 for the underlying API.

## IC-6: UI Registration and Status Views

**Requirements:** FR-1, FR-2, FR-3, FR-4

- Registration form submits `WorkloadClusters.Create` with Hub
  identity, cluster name, and capabilities.
- List view shows registered clusters with `Available` condition
  status.
- Detail view shows conditions with reasons and messages for
  registration issues.
- All views restricted to CPA role.

The UI is built from generated protobuf TypeScript types after the proto
is merged. No pre-existing UI mapping exists.

## IC-7: MaaS Placement Query (Data Foundation)

**Requirements:** FR-5 (registration provides shared provider capacity
metadata; detailed Praxis placement, trusted service access, tenant
isolation, and dedicated infrastructure are deferred)

This increment provides the queryable resource and capacity metadata
that a future MaaS placement consumer will use. The List RPC supports
CEL filters for `supported_workloads` containing `"maas"` and
`Available=True` (with freshness check). See §4.3 Placement Query.

FR-5 is satisfied for this registration increment by providing shared
provider capacity metadata through the WorkloadCluster resource. The
detailed Praxis placement integration, trusted service access, tenant
isolation, and dedicated infrastructure are not acceptance criteria for
this increment — they are tracked as follow-up work (see §4.3 Placement
Query, deferred section).

# 6. Alternatives Considered

## 6.1 Extend `Cluster` with an Origin Field

Add an `origin` enum (`PROVISIONED`, `IMPORTED`) to `ClusterSpec` and
make provisioning fields optional when origin is `IMPORTED`.

**Pros:** Single resource type for all clusters; fewer concepts.
**Cons:** Proto validation becomes conditional. Fulfillment controller
must branch on origin to avoid creating ClusterOrder CRDs. Every consumer
(operator, feedback controller, CLI, UI, metering) must handle both
origins, creating regression risk in the mature CaaS flow. Status fields
(MetalLB VIPs, HostedCluster references) are meaningless for registered
clusters.
**Rejection:** Provisioned and registered clusters have fundamentally
different lifecycles, state models, and operator integrations. A separate
resource provides cleaner separation with lower regression risk.

## 6.2 Operator CRD for Registered Clusters

Create a `WorkloadClusterOrder` CRD in the osac-operator, mirroring the
ClusterOrder pattern.

**Pros:** Consistent with existing Cluster → ClusterOrder pattern;
operator has direct Hub access.
**Cons:** Registration is not a provisioning operation — no AAP jobs,
HostedClusters, or NodePools are needed. A CRD for a database
registration adds unnecessary Kubernetes controller complexity. Signal
round-trip from operator to fulfillment-service adds latency.
**Rejection:** The fulfillment controller can validate the Hub cluster
directly. A CRD is warranted only when Kubernetes-level reconciliation
of child resources is needed.

## 6.3 Exclusive WorkloadRole Enum

Define a `WorkloadRole` enum with `MAAS_AI_INFERENCE` as the single
accepted value, extensible to `VMAAS` in the future.

**Pros:** Compile-time type safety; simple validation.
**Cons:** Exclusive enum forces a choice: a cluster supports one role or
requires multiple registrations. Adding VMaaS support would require
either allowing multiple values (breaking the enum semantics) or creating
duplicate WorkloadCluster records for the same physical cluster.
**Rejection:** An additive `supported_workloads` list naturally
represents clusters that support multiple workload types without schema
changes or duplicate records.

## 6.4 Anti-Corruption Adapter for OCM

Introduce an internal abstraction layer between the fulfillment
controller and OCM CRDs to isolate OSAC from OCM API changes.

**Pros:** Decouples OSAC from OCM API surface; easier to swap Hub
implementations.
**Cons:** Premature abstraction for a single, stable, GA API. Adds
indirection, testing surface, and maintenance cost without immediate
benefit. The `ManagedCluster` v1 API is GA and stable.
**Rejection:** Direct consumption follows existing OSAC patterns.
Extraction triggers are documented in §4.1 for when an adapter becomes
warranted.

## 6.5 Do Nothing

Rely on external tooling or manual database entries.

**Pros:** No OSAC changes.
**Cons:** No API visibility, no MaaS placement integration, no
observability.
**Rejection:** PRD requires API, CLI, and UI visibility for registered
clusters.

# 7. Observability and Monitoring

**Metrics (Prometheus):**

| Metric | Type | Labels | Description |
|---|---|---|---|
| `osac_workload_cluster_registrations_total` | Counter | `result` (success, already_exists, invalid) | Total registration attempts |
| `osac_workload_cluster_available` | Gauge | — | Count of WorkloadClusters with `Available=True` |
| `osac_workload_cluster_unavailable` | Gauge | — | Count of WorkloadClusters with `Available=False` |
| `osac_workload_cluster_hub_watch_errors_total` | Counter | `hub_id` | Hub watch connection errors |
| `osac_workload_cluster_condition_transitions_total` | Counter | `condition`, `from_status`, `to_status` | Condition state changes |

**Events:** The fulfillment controller emits Kubernetes-style events
through the OSAC eventing mechanism (not the osac-operator):

| Event | Type | Reason | When |
|---|---|---|---|
| Registration created | Normal | `Registered` | WorkloadCluster created |
| Cluster available | Normal | `Available` | `Available` condition → True |
| Cluster unavailable | Warning | `Unavailable` | `Available` condition → False |
| Hub watch reconnected | Normal | `HubReconnected` | Watch connection restored after failure |
| Identity mismatch | Warning | `IdentityMismatch` | `managed_cluster_uid` changed unexpectedly |

**Structured logging:** See §4.5 for the complete logging redaction
policy, allowed fields, denied fields, and required test coverage.

# 8. Impact and Compatibility

**Backward compatibility:** This is a new API resource with no existing
consumers. No breaking changes to existing resources or services.

**Database migration:** New numbered migration creates the
`workload_clusters` and `archived_workload_clusters` tables. Existing
tables and data are not affected. Migration is additive.

**Upgrade:** The new tables are created by the migration. No data
backfill.

**Downgrade:** Reverting the migration drops the `workload_clusters` and
`archived_workload_clusters` tables. Any existing WorkloadCluster records
are lost. Because Delete is deferred, operational cleanup before
downgrade requires direct database access by the platform operator. No
impact on existing `clusters` or `cluster_orders` resources.

**Version skew:** No cross-component version dependency. The
fulfillment-service hosts both the WorkloadCluster service and
controller. If MaaS components begin consuming the WorkloadCluster API,
version skew is handled via API versioning (the `v1` API is
additive-only).

**Service gate:** The WorkloadCluster gRPC service is registered
conditionally behind `--enable-maas` per the OSAC-3046 pattern. When
MaaS is disabled, all RPCs return `codes.Unavailable` with a descriptive
message. Existing records remain in the database but are not queryable.
Re-enabling MaaS restores access.

# 9. Baseline Resolutions and Remaining Deltas

This section documents where the baselined architectural decisions resolve
or supersede PRD open questions, and identifies remaining deltas between
the PRD and this design.

## 9.1 PRD Open Question 1: Tenant Allocation — RESOLVED

**PRD question:** "Are imported workload clusters shared provider
capacity available to multiple tenants, or assigned to one tenant?"

**Resolution (Baseline Decision 1):** WorkloadCluster is a
provider-level resource, not scoped to any tenant. All registered
clusters provide shared provider capacity available to all tenants.
Tenant-specific cluster assignment (restricting clusters to specific
tenants, dedicated tenant infrastructure, exclusive-placement guarantees)
is deferred to a future cross-workload design that collects use cases
across MaaS, VMaaS, and other workload types.

This replaces the previous design's tenant-scoped ownership model and
resolves the PRD open question for this registration increment.

## 9.2 PRD Scope Delta: VMaaS / Future Workloads

**PRD Out of Scope:** "Using imported clusters for VMaaS, CaaS, or BMaaS
workloads."

**Design position (Baseline Decision 4):** The `supported_workloads`
capability list enables future VMaaS coexistence without schema migration.
This increment validates only `"maas"` — VMaaS support requires a future
increment to add `"vmaas"` to the allow-list and implement VMaaS-specific
validation. The schema accommodates this; the functionality does not.
This is a deliberate design-for-extensibility, not a scope expansion.

## 9.3 PRD Scope Delta: Registration vs. Import Terminology

**PRD language:** "Import clusters" / "imported clusters."

**Design position (Baseline Decision 5):** This design uses "register"
semantics to reflect that the operation records an externally prepared
cluster rather than performing a provisioning or data-import action.
The API uses standard CRUD semantics (`Create`), consistent with
Kubernetes and OSAC patterns where creating a record does not imply
creating the thing it represents. Future CaaS automatic registration
uses the same `Create` RPC. This is a terminology clarification, not a
functional change.

## 9.4 Jira Definition of Done — Disconnect

The Jira OSAC-6488 Definition of Done includes a disconnect capability
removed from the PRD during review. Disconnect remains out of scope per
the merged PRD. The DoD should be updated to match. This is a Jira
hygiene action with no impact on this design.

- **Owner:** Eran Cohen (Feature owner)

# 10. Test Plan

## 10.1 Requirement Traceability

| ID | PRD In Scope Item | Summary |
|---|---|---|
| FR-1 | Register clusters through OSAC UI, CLI, and API | Create a WorkloadCluster referencing a Hub-managed cluster |
| FR-2 | See registration outcome through UI, CLI, and API | View conditions and metadata |
| FR-3 | Registered cluster details visible only to CPAs | CPA-only authorization |
| FR-4 | Registration issues show the cause; no recovery action required | Condition-based failure reporting |
| FR-5 | AI workloads can use workload clusters preserving tenant isolation | Registration provides shared provider capacity metadata; detailed Praxis placement, trusted service access, tenant isolation, and dedicated infrastructure are deferred to a future cross-workload design |

## 10.2 Unit Tests

**Location:** `fulfillment-service/internal/servers/` (Ginkgo/Gomega)

| # | Scenario | Requirement | Expected Behavior |
|---|---|---|---|
| U1 | Create with valid source_hub_id, managed_cluster_name, supported_workloads=["maas"] | FR-1 | Returns WorkloadCluster with conditions Unknown |
| U2 | Create with empty managed_cluster_name | FR-1 | Returns InvalidArgument |
| U3 | Create with unknown supported_workloads value | FR-1 | Returns InvalidArgument listing accepted values |
| U4 | Create with source_hub_id not matching configured Hub | FR-1 | Returns InvalidArgument |
| U5 | Create with duplicate (source_hub_id, managed_cluster_name) — application check | FR-4 | Returns AlreadyExists with descriptive message |
| U6 | Concurrent duplicate (source_hub_id, managed_cluster_name) — DB constraint | FR-4 | Exactly one succeeds; other returns AlreadyExists |
| U7 | Create with same managed_cluster_name but different source_hub_id | FR-1 | Returns InvalidArgument — source_hub_id must match the single configured Hub identity (§4.3). Multi-hub scenarios where different source_hub_ids coexist are deferred to the multi-hub increment (§4.8). |
| U8 | Update source_hub_id (immutable) | FR-1 | Returns InvalidArgument |
| U9 | Update managed_cluster_name (immutable) | FR-1 | Returns InvalidArgument |
| U10 | List returns only WorkloadClusters (no tenant filter) | FR-2, FR-3 | All clusters returned to CPA |
| U11 | Get by ID | FR-2 | Returns WorkloadCluster with current conditions |
| U12 | Delete RPC returns PermissionDenied | — | Returns PermissionDenied — no `workload_cluster:delete` permission in OPA policy (see IC-4) |
| U13 | Private fields not in public API | FR-3 | `managed_cluster_uid` absent from public response |
| U14 | MaaS service disabled | — | All RPCs return Unavailable |
| U15 | Registration-triggered reconciliation for existing ManagedCluster | FR-2 | Conditions transition from Unknown immediately after Create |
| U16 | Registration-triggered reconciliation for missing ManagedCluster (Hub client ready, informer synced) | FR-4 | Available=False with ManagedClusterNotFound after Create |
| U17 | ManagedCluster exists but ManagedClusterConditionAvailable=False | FR-4 | Available=False with ManagedClusterUnavailable |
| U18 | Registration-triggered reconciliation when Hub client not authenticated (credential failure) | FR-4 | Hub readiness gate prevents informer cache lookup; sets HubReachable=False and Available=False with HubUnreachable — never ManagedClusterNotFound |

## 10.3 Integration Tests

**Location:** `fulfillment-service/it/` (deployed service + database)

| # | Scenario | Requirement | Expected Behavior |
|---|---|---|---|
| I1 | Register end-to-end with mocked Hub (ManagedCluster exists) | FR-1, FR-2 | Create → controller watches → Available=True |
| I2 | Register with non-existent ManagedCluster | FR-4 | Available=False, reason ManagedClusterNotFound |
| I3 | Register with unaccepted ManagedCluster | FR-4 | Available=False, reason ManagedClusterNotAccepted |
| I4 | Register with unreachable Hub | FR-4 | Available=False, HubReachable=False |
| I5 | Hub watch reconnect after transient failure | — | HubReachable transitions False→True; Available updates |
| I6 | ManagedCluster removed after registration | — | Available=False, reason ManagedClusterNotFound |
| I7 | ManagedCluster created after registration (delayed availability) | FR-4 | Available transitions Unknown→True |
| I8 | Cluster identity mismatch (UID changes) | — | Available=False, reason ClusterIdentityMismatch |
| I9 | Duplicate (source_hub_id, managed_cluster_name) via DB constraint | FR-4 | One succeeds, other returns AlreadyExists |
| I10 | Placement filter: supported_workloads, Available | FR-5 | Only matching clusters returned |
| I11 | Registration after informer sync — existing upstream name | FR-2 | Create returns; conditions transition from Unknown immediately via registration-triggered reconciliation |
| I12 | Registration after informer sync — missing upstream name (Hub ready) | FR-4 | Create returns; Available=False with ManagedClusterNotFound via registration-triggered reconciliation |
| I13 | Startup reconciliation after controller restart | FR-2 | All WorkloadCluster conditions refreshed against informer cache |
| I14 | Retry after failed status write | FR-4 | Condition write retried; eventually succeeds |
| I15 | ManagedCluster accepted but ManagedClusterConditionAvailable=False | FR-4 | Available=False, reason ManagedClusterUnavailable |
| I16 | Freshness re-validation updates last_observed_time without changing last_transition_time | — | last_observed_time updated within re-validation interval; last_transition_time unchanged when status/reason did not transition |
| I17 | Create during Hub credential failure, then recovery | FR-4 | Create RPC succeeds; registration-triggered reconciliation sets HubReachable=False and Available=False (HubUnreachable), not ManagedClusterNotFound. After credential fix and restart, startup reconciliation restores accurate conditions (Available=True for existing ManagedClusters) |

## 10.4 API Tests

| # | Scenario | Requirement | Expected Behavior |
|---|---|---|---|
| A1 | REST POST /api/fulfillment/v1/workload-clusters | FR-1 | Creates WorkloadCluster |
| A2 | REST GET /api/fulfillment/v1/workload-clusters | FR-2 | Lists with filter/pagination |
| A3 | REST GET /api/fulfillment/v1/workload-clusters/{id} | FR-2 | Returns single WorkloadCluster |
| A4 | gRPC WorkloadClusters.Create | FR-1 | Creates WorkloadCluster |
| A5 | Public API excludes private fields | FR-3 | managed_cluster_uid not present |

## 10.5 UI Tests

| # | Scenario | Requirement | Expected Behavior |
|---|---|---|---|
| V1 | Registration form submits Create RPC | FR-1 | UI sends Create with Hub identity and capabilities |
| V2 | Registration outcome displayed | FR-2 | Conditions rendered in detail view |
| V3 | Condition reason displayed for issues | FR-4 | Available=False reason and message shown |
| V4 | CPA-only view enforcement | FR-3 | Non-CPA roles cannot access WorkloadCluster views |

## 10.6 Security and Isolation Tests

| # | Scenario | Requirement | Expected Behavior |
|---|---|---|---|
| S1 | CPA can create WorkloadCluster | FR-1 | Create succeeds |
| S2 | CPA can list WorkloadClusters | FR-2, FR-3 | List succeeds |
| S3 | Tenant Admin cannot create WorkloadCluster | FR-3 | PermissionDenied |
| S4 | Tenant Admin cannot list WorkloadClusters | FR-3 | PermissionDenied |
| S5 | Tenant User cannot list WorkloadClusters | FR-3 | PermissionDenied |
| S6 | Tenant User cannot get WorkloadCluster by ID | FR-3 | PermissionDenied |
| S7 | Unauthenticated request rejected | FR-3 | Unauthenticated |

## 10.7 Capability and Placement Tests

| # | Scenario | Requirement | Expected Behavior |
|---|---|---|---|
| C1 | Register with supported_workloads=["maas"] | FR-1 | Succeeds; cluster registered with MaaS capability declared |
| C2 | Register with supported_workloads=["vmaas"] (not yet allowed) | FR-1 | InvalidArgument — "vmaas" not in allow-list |
| C3 | Placement filters by supported_workloads | FR-5 | Only clusters with "maas" in list returned |
| C4 | Placement filters by Available=True | FR-5 | Unavailable clusters excluded |

## 10.8 Hub Identity and Watch Tests

| # | Scenario | Requirement | Expected Behavior |
|---|---|---|---|
| H1 | source_hub_id validated against configured Hub | FR-1 | Mismatched hub_id returns InvalidArgument |
| H2 | Controller watch receives ManagedCluster add event | FR-2 | Corresponding WorkloadCluster conditions update |
| H3 | Controller watch receives ManagedCluster delete event | — | Available=False, reason ManagedClusterNotFound |
| H4 | Watch relist after reconnect | — | All WorkloadCluster conditions reconciled |
| H5 | managed_cluster_uid immutability enforced | — | UID change sets Available=False |

## 10.9 Credential Tests

| # | Scenario | Requirement | Expected Behavior |
|---|---|---|---|
| K1 | hub-kubeconfig Secret present and valid | — | Controller starts, watch established |
| K2 | hub-kubeconfig Secret missing | — | Controller logs error, HubReachable=False and Available=False (reason HubUnreachable) on all clusters; recovery after credential fix and restart restores conditions via startup reconciliation |
| K3 | hub-kubeconfig Secret with invalid credentials | — | HubReachable=False and Available=False (reason HubUnreachable) on all clusters; condition message describes auth failure without exposing credentials |
| K4 | Create WorkloadCluster while Hub credential is invalid, then fix credential and restart | FR-4 | Create RPC succeeds (local validation only). Registration-triggered reconciliation sets HubReachable=False and Available=False (HubUnreachable) — informer cache not consulted, ManagedClusterNotFound never reported. After credential fix and restart, startup reconciliation transitions to accurate conditions (Available=True if ManagedCluster exists and is healthy) |

## 10.10 Direct OCM Compatibility Tests

| # | Scenario | Requirement | Expected Behavior |
|---|---|---|---|
| O1 | ManagedCluster v1 API available on Hub | — | Watch established, conditions reconcile |
| O2 | ManagedCluster has HubAcceptedManagedCluster=True | FR-1 | Available=True |
| O3 | ManagedCluster has id.k8s.io ClusterClaim | — | managed_cluster_uid populated |
| O4 | ManagedCluster lacks id.k8s.io claim | — | managed_cluster_uid empty; conditions still reconcile |

## 10.11 External Registration and Scope Tests

| # | Scenario | Requirement | Expected Behavior |
|---|---|---|---|
| R1 | Register externally prepared cluster | FR-1 | WorkloadCluster created; no provisioning triggered |
| R2 | No CRD created on target cluster or operator | FR-1 | Verify no CRD side effects |
| R3 | Site/multi-cluster aggregation not supported | — | No parent resource API exists; document confirms 1:1 mapping |

## 10.12 Logging Redaction Tests

| # | Scenario | Expected Behavior |
|---|---|---|
| L1 | Registration success — log contains only allowed fields | workload_cluster_id, supported_workloads, condition, component, operation, request_id; no denied fields |
| L2 | Registration failure — log redacts denied fields | Reason code present; no ManagedCluster name, Hub URL, credentials, stack trace |
| L3 | Hub watch error — log redacts denied fields | Error category present; no internal addresses, bearer tokens |

## 10.13 Failure Tests

| # | Scenario | Requirement | Expected Behavior |
|---|---|---|---|
| F1 | Hub unreachable during registration | FR-4 | Available=False, HubReachable=False |
| F2 | Hub recovers after outage | — | Available condition updates via watch |
| F3 | Controller restart mid-reconciliation | FR-4 | Resumes from database state; no duplicate records |
| F4 | Database unavailable during Create | FR-4 | Returns Internal error; no partial state |
| F5 | Concurrent duplicate registrations (DB constraint) | FR-4 | Exactly one succeeds |
| F6 | Create during Hub credential failure (Hub readiness gate) | FR-4 | Create succeeds locally; reconciliation sets HubUnreachable, never ManagedClusterNotFound; recovery restores accurate conditions |

## 10.14 Integration-Test Planning Evidence Matrix

The following matrix satisfies the [Integration testing: planning
evidence](https://github.com/osac-project/osac/blob/main/docs/INTEGRATION-TESTING.md#planning-evidence)
requirement. Each row identifies the owning component, required tier,
real vs. simulated dependencies, and follow-up gaps.

| Component | Behavior / Boundary | Required Tier | DEV/QE Owner | Case IDs / Suite Location | Command / Prerequisites | Real Dependencies | Simulated / Mocked Dependencies | Follow-up Gaps |
|---|---|---|---|---|---|---|---|---|
| fulfillment-service | Create RPC validation, uniqueness, immutability, Hub readiness gate | Unit | [DEV] | U1–U14, U18 / `fulfillment-service/internal/servers/` (Ginkgo) | `make -C fulfillment-service test-unit` | None | DAO mocked; Hub client mocked | U18 verifies Hub readiness gate in registration-triggered reconciliation |
| fulfillment-service | Registration-triggered reconciliation, informer lookup | Unit | [DEV] | U15–U17 / `fulfillment-service/internal/controllers/` (Ginkgo) | `make -C fulfillment-service test-unit` | None | Informer cache stubbed; DB mocked | Real informer behavior tested at component-integration tier |
| fulfillment-service | Controller watch, condition transitions, startup reconciliation | Component integration | [DEV] | I1–I17 / `fulfillment-service/it/` | `make -C fulfillment-service test-integration` (requires PostgreSQL testcontainer) | PostgreSQL (testcontainer) | **Hub API is mocked** (fake ManagedCluster resources injected into a fake informer or test API server). This exercises the controller's client-side handling but does not prove compatibility with a real ACM Hub API. | Real ACM Hub compatibility: deferred to E2E with live Hub (E1–E6). No envtest suite exists for the controller; proposed. |
| fulfillment-service | DB uniqueness constraint under concurrency | Component integration | [DEV] | I9 / `fulfillment-service/it/` | Same as above | PostgreSQL (testcontainer) | Hub mocked | — |
| fulfillment-service | Placement filter query (List with CEL) | Component integration | [DEV] | I10 / `fulfillment-service/it/` | Same as above | PostgreSQL (testcontainer) | Hub mocked; no actual Praxis consumer | Actual Praxis placement consumer and tenant-to-cluster assignment: deferred to future cross-workload design |
| fulfillment-service | OPA authorization (CPA-only) | Component integration | [DEV] | S1–S7 / `fulfillment-service/it/` | Same as above | PostgreSQL, OPA policy (testcontainer or embedded) | Hub mocked | — |
| fulfillment-service | Credential lifecycle (missing/invalid Secret, Create during outage) | Component integration | [DEV] | K1–K4, I17 / `fulfillment-service/it/` | Same as above | PostgreSQL (testcontainer) | Hub client configured with invalid credentials or missing mount | Real Secret mount behavior tested in E2E. K4 verifies Hub readiness gate prevents ManagedClusterNotFound during credential outage. I17 verifies end-to-end Create-during-outage and recovery via startup reconciliation |
| fulfillment-service | Logging redaction | Unit + component integration | [DEV] | L1–L3 / `fulfillment-service/internal/` + `it/` | `make -C fulfillment-service test-unit test-integration` | None (unit); PostgreSQL (integration) | Hub mocked | — |
| fulfillment-service | Freshness re-validation and staleness | Component integration | [DEV] | I16 / `fulfillment-service/it/` | Same as integration command | PostgreSQL (testcontainer) | Hub mocked; clock stubbed for staleness window | Staleness threshold interaction with Praxis: deferred to follow-up |
| tests/e2e | Register, verify, CPA-only access, duplicate detection | E2E | [QE] | E1–E8 / `tests/e2e/` (pytest via osac-test-infra) | `pytest tests/e2e/test_workload_cluster.py` (proposed; requires deployed OSAC + live ACM Hub) | Deployed OSAC stack, PostgreSQL, live ACM Hub with ManagedCluster | None — all dependencies real | ACM Hub availability in CI: unresolved — requires dedicated test Hub or integration with existing ACM test environment. No existing test Hub is provisioned in CI. |
| tests/e2e | Tenant-to-cluster assignment and placement isolation | E2E | [QE] | Deferred | Deferred to future cross-workload design | — | — | Tenant-specific cluster assignment, dedicated infrastructure, and placement isolation E2E: deferred until cross-workload tenant-to-cluster model is designed. Owner: Praxis/MaaS team. |
| UI | Registration form, condition display, CPA-only views | UI integration | [UI] | V1–V4 / proposed: `ui/tests/` (Cypress or equivalent — **not yet defined**) | Proposed: `npm run test:e2e -- --spec workload-cluster` | Fulfillment API (mocked or deployed) | API responses mocked for unit; deployed for integration | UI test framework selection: unresolved — harness and runner not yet chosen. |

**Limitations and honest disclosures:**

- **Mocked Hub limitation:** Component-integration tests (I1–I17) use a
  mocked or fake Hub API. This exercises the controller's client-side
  handling of ManagedCluster events but does not prove wire
  compatibility with a real ACM Hub — specifically, it does not test
  real `ManagedCluster` CRD serialization, watch protocol behavior,
  or OCM-specific error responses. Real ACM Hub compatibility is
  covered only by E2E tests (E1–E6), which require a live Hub in the
  test environment.
- **No existing ACM Hub in CI:** The E2E test environment does not
  currently provision an ACM Hub. E2E tests (E1–E8) require a dedicated
  test Hub or integration with an existing ACM test environment. This
  is an unresolved infrastructure prerequisite.
- **Proposed commands and locations:** Test file paths and commands
  marked "proposed" do not yet exist. They represent the intended
  location following existing fulfillment-service conventions.
- **UI test harness:** The UI test framework (Cypress, Playwright, or
  equivalent) is not yet selected. V1–V4 are test scenarios, not
  executable tests.
- **Praxis placement E2E:** Tenant-to-cluster assignment, dedicated
  infrastructure, and placement isolation E2E are deferred to the future
  cross-workload design. The List-filter test (E8) proves query behavior
  for shared provider capacity.

## 10.15 E2E Tests

**Location:** `tests/e2e/` (pytest via osac-test-infra)

| # | Scenario | Requirement | Expected Behavior |
|---|---|---|---|
| E1 | Register Hub-managed cluster via API | FR-1 | WorkloadCluster with Available=True |
| E2 | Verify outcome via CLI `osac workload-cluster list` | FR-2 | Cluster in list with Available status |
| E3 | Verify outcome via CLI `osac workload-cluster describe` | FR-2 | Conditions, spec, metadata shown |
| E4 | Register non-existent ManagedCluster | FR-4 | Available=False with descriptive reason |
| E5 | Verify CPA-only access | FR-3 | Tenant roles get PermissionDenied |
| E6 | Register same cluster twice | FR-4 | AlreadyExists |
| E7 | Delete RPC returns PermissionDenied | — | PermissionDenied — no `workload_cluster:delete` in OPA policy; handler not reached (see IC-4) |
| E8 | List query with capability and condition filter | FR-5 | Only clusters with supported_workloads=["maas"] and Available=True returned |

**E2E infrastructure requirement:** An ACM Hub with at least one
registered ManagedCluster in the test environment.

# 11. Graduation Criteria

## Dev Preview → Tech Preview

- All unit, integration, and API tests pass in CI.
- E2E registration-and-verify scenario executes against a live ACM Hub.
- Documentation (API reference, CLI help, UI tooltips) published.
- At least one CPA has registered a cluster in staging and confirmed the
  workflow (register, view conditions, update).

## Tech Preview → GA

- Zero P1/P2 open bugs for two consecutive sprints.
- Hub watch reconnection validated in long-running soak test (>= 72 hours).
- Security review completed — OPA policies audited, logging redaction
  verified, no denied fields in collected logs.
- Service gate (`--enable-maas`) verified for enable and disable paths.

# 12. Upgrade / Downgrade Strategy

This is a new API with no upgrade impact on existing resources.

**Upgrade:** New numbered migration creates `workload_clusters` and
`archived_workload_clusters` tables. Existing tables and data are not
affected.

**Downgrade:** Reverting the migration drops the `workload_clusters` and
`archived_workload_clusters` tables. Records are lost. Because Delete is
deferred, cleanup before downgrade requires direct database access. No
impact on existing `clusters` or `cluster_orders` resources.

# 13. Version Skew Strategy

No version skew concerns. This is a new resource type. The
fulfillment-service hosts both the service and controller as a single
deployment unit.

If MaaS components begin consuming the WorkloadCluster API, version skew
is handled via API versioning (the `v1` API is additive-only).

# 14. Support Procedures

**Detecting issues:**

- Cluster stuck with `Available=Unknown`: fulfillment controller may not
  be running or Hub watch is not established. Check controller logs and
  `osac_workload_cluster_hub_watch_errors_total` metric.
- Clusters with `Available=False`: inspect the `Available` condition's
  `reason` and `message`. Common causes: `ManagedClusterNotFound` (wrong
  name — only reported when Hub client is authenticated and informer is
  synced), `HubUnreachable` (connectivity or credential failure),
  `ManagedClusterNotAccepted` (Hub-side acceptance).
- Clusters created during a credential outage show `HubUnreachable`:
  this is expected — the Hub readiness gate prevents misleading
  `ManagedClusterNotFound` when the informer cache is not synchronized.
  Fix the credential, restart the fulfillment-service, and startup
  reconciliation restores accurate conditions automatically.
- Hub watch errors increasing: check
  `osac_workload_cluster_hub_watch_errors_total`. May indicate Hub
  credential rotation needed or network issue.

**Disabling the feature:** Set `services.maas.enabled: false` in Helm
values and run `helm upgrade`. This unregisters the WorkloadCluster gRPC
service. Existing records remain but are not queryable. Re-enabling
restores access.

**Consequences of disabling:**
- MaaS placement cannot discover WorkloadCluster capacity.
- Existing placed workloads are not affected (placement is a separate
  concern).
- No impact on CaaS, VMaaS, or BMaaS services.

**Recovery:** The controller is stateless — all state is in the database.
Restarting the fulfillment-service resumes normal operation including
Hub watch re-establishment.

**Identity mismatch recovery:** When a WorkloadCluster reports
`ClusterIdentityMismatch` (the ManagedCluster's `id.k8s.io` UID changed
under the same name), self-service resolution is blocked in this
increment because the UID is immutable and Delete is deferred. The
platform operator can resolve this by:

1. Soft-deleting the mismatched record: set `deletion_timestamp` on the
   `workload_clusters` row and copy it to `archived_workload_clusters`.
2. Notify the CPA to create a new WorkloadCluster registration with the
   same Hub identity.

This requires direct database access and should be documented in
operational runbooks. See §4.2 recovery path for details.

**Invalid registration cleanup:** For registrations with incorrect
`managed_cluster_name` (typos), the CPA creates a new WorkloadCluster with
the correct name. The old registration remains as an inert record with
`Available=False` (reason `ManagedClusterNotFound`). It does not affect
placement or consume resources beyond database storage. Removing inert
records requires platform operator database access until Delete is
implemented (see IC-4).

# 15. Infrastructure Needed

- **E2E test environment:** An ACM Hub with at least one registered
  ManagedCluster. May require a dedicated test Hub or integration with an
  existing ACM test environment.
- No new repositories, subprojects, or CI infrastructure changes.

# 16. Drawbacks

- **Separate resource type increases surface area.** Introducing
  `WorkloadCluster` alongside the existing `Cluster` resource means two
  resource types represent clusters in OSAC. Consumers (UI, CLI, docs,
  metering) must handle both. The alternative (extending `Cluster`) was
  rejected in §6.1 due to higher regression risk, but the surface-area
  cost is real.

- **Direct OCM CRD coupling.** Consuming `ManagedCluster` CRDs without
  an adapter creates a compile-time dependency on the OCM API. A
  breaking OCM version change requires controller updates. Extraction
  triggers are documented in §4.1, but the coupling exists until an
  adapter is introduced.

- **No Delete in this increment.** Deferring Delete means invalid
  registrations (typos, wrong Hub) and identity-mismatched records
  accumulate as inert records. The CPA cannot self-service remove them.
  For name typos, the CPA creates a new registration with the correct
  name — the old record remains inert. For identity mismatches, where
  the same `managed_cluster_name` is needed, the uniqueness constraint
  blocks re-registration; platform operator database cleanup is required
  (see §4.2 recovery path). All Delete requests return
  `PermissionDenied` because no `workload_cluster:delete` OPA
  permission exists (see IC-4).

- **Freshness-based staleness adds operational complexity.** The
  freshness expiry mechanism requires placement consumers to check
  `last_observed_time` (a dedicated observation timestamp separate from
  `last_transition_time`), and operators must monitor controller health
  to ensure conditions stay fresh. The two-timestamp model preserves
  Kubernetes condition semantics (`last_transition_time` changes only on
  actual transitions) while providing a reliable freshness signal. A
  simpler time-unbounded design would be operationally simpler but risks
  stale placement.

- **Single Hub limits scale.** The single configured Hub connection
  limits this increment to one Hub's managed clusters. Multi-hub
  environments require the deferred multi-hub routing.

# 17. Risks and Mitigations

| Risk | Mitigation |
|---|---|
| Hub cluster removed while OSAC workloads are active | `Available=False` with reason `ManagedClusterNotFound` signals MaaS placement to stop scheduling new workloads. Existing workload handling is a MaaS concern. |
| ACM API version changes break Hub watch | The `cluster.open-cluster-management.io/v1` ManagedCluster API is GA and stable. Client pins the API version. Extraction triggers documented in §4.1. |
| SharedInformer memory for large Hub | Scales linearly with ManagedCluster count. Acceptable for expected scale (~500 clusters). Monitor and evaluate if scale exceeds assumptions. |
| Hub credential rotation | hub-kubeconfig Secret update requires fulfillment-service pod restart (rollout restart) to pick up new credentials. Rotation procedure documented in §4.5. During restart window, both HubReachable=False and Available=False are set (§4.5); startup reconciliation restores conditions when the new credential establishes a connection. |

---

## Provenance

Revised: revise @ design 0.9.0 - 155e7d6, workspace design/OSAC-6488 @ a74d9f5
Reviewed: respond @ design/OSAC-6488 — trusted corrections (eranco74) and CodeRabbit findings
Reviewed: independent review @ design/OSAC-6488 — evidence matrix case-ID corrections (I1–I15, I16), all eranco74 baselines preserved, all CodeRabbit findings verified addressed
Reviewed: respond @ design/OSAC-6488 — five CodeRabbit consistency findings: U7 single-Hub validation, credential failure clears Available, UID replacement recovery path, freshness last_observed_time, Delete authorization/dispatch alignment
Reviewed: respond @ design/OSAC-6488 — CodeRabbit finding: Create behavior during Hub credential failure. Defined Hub readiness/authentication gate in registration-triggered reconciliation (§4.1), credential lifecycle (§4.5), failure table (§4.6), support procedures (§14). Added tests U24, I17, K4, F6. Qualified U22/I12 to Hub-ready state. Asynchronous registration baseline preserved: Create remains a local persistence operation; Hub readiness gate is a reconciliation concern, not a Create gate.
Reviewed: independent review @ design/OSAC-6488 — credential-outage revision: verified Hub readiness gate coherence (no invented API; HasSynced is real, authentication is controller-owned state). Fixed startup reconciliation §4.1 sequencing contradiction (opening clause assumed informer sync before describing auth-failure path). Reordered I17 to sequential position after I16. Added I17 to evidence-matrix credential-lifecycle row and mocked-Hub limitation range (I1–I17). All baselines and prior corrections preserved.
Reviewed: respond @ design/OSAC-6488 — five mhrivnak review corrections: (1) renamed hub_cluster_name→managed_cluster_name everywhere (proto, SQL index, uniqueness, API/CLI/UI, logs, tests, prose); (2) rewrote Motivation to focus on OSAC tracking workload-placement clusters with brief CaaS background note; (3) removed allowed_tenants field and all tenant-specific assignment/filtering — deferred to future cross-workload design; (4) removed ManagedClusterRemoved reason — all absence cases use ManagedClusterNotFound for declarative current-state semantics; (5) removed placement algorithm and entitlement tests — deferred dedicated/shared tenant infrastructure and placement/isolation policy. Preserved provider-global CPA-only management, source_hub_id, supported_workloads, direct OCM consumption, asynchronous reconciliation, credential handling, and all other accepted contracts. Aligned with PR #405 shared-provider-capacity direction.
Phases: draft, revise, revise, respond, respond, respond, respond, respond, respond, respond
Sources: PRD (prd.md), PR #394 review feedback (eranco74 trusted corrections, CodeRabbit inline findings, mhrivnak trusted corrections), baselined architectural decisions, INTEGRATION-TESTING.md planning evidence requirements, OSAC source storage shape verification, PR #405 shared-provider-capacity direction

<!-- ai-workflow-provenance:{"schema_version":1,"provenance_kind":"session","workflow":"design","workflow_version":"0.9.0","ai_workflows":"155e7d6","source_repo":"432d6b0","source_repo_branch":"design/OSAC-6488","commits_behind_main":0,"commits_ahead_main":2,"main_ref":"main","phases":["draft","revise","revise","respond","respond","respond","respond","respond","respond","respond"],"authoring_modes":["skill"],"context_changed":true,"origin_untracked":false} -->
