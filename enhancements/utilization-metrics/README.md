---
title: utilization-metrics
authors:
  - Adrien Gentil
creation-date: 2026-05-12
last-updated: 2026-05-12
tracking-link:
  - https://redhat.atlassian.net/browse/OSAC-261
see-also:
  - "/enhancements/vmaas"
  - "/enhancements/organizations"
  - "/enhancements/caas"
replaces:
superseded-by:
---

# Utilization Metrics

## Summary

This proposal introduces utilization metrics for OSAC resources — compute
instances (VMs), CaaS clusters, storage, and GPUs. Tenant Users gain visibility
into their own resource consumption; Tenant Admins gain an organization-wide
view across all their projects; Cloud Provider Admins gain a platform-wide view
across all organizations. The metrics are exposed through the standard
Prometheus HTTP API, making OSAC utilization data compatible with the broader
Prometheus ecosystem — existing tooling such as Grafana, alerting pipelines, or
cost management systems can consume it without custom integration. Utilization
data is deliberately kept separate from billing/metering: billing is driven by
resource allocation, while utilization metrics expose actual consumption patterns
to support capacity planning and internal cost allocation.

## Motivation

Tenant Users can today provision compute instances, clusters, and storage, but
have no API-level visibility into how much of those resources they actually
consume. This creates several problems:

- Tenant Users cannot detect underutilized resources to rightsize or reclaim them.
- Tenant Admins have no organization-wide view of resource consumption to help
  their teams optimize usage.
- Cloud Provider Admins cannot make data-driven capacity planning decisions per hub.
- There is no foundation for cost allocation models that reward efficient
  resource use.
- GPU resources, which are scarce and expensive, have no consumption
  observability at all.

### User Stories

- As a Tenant User, I want to query the CPU and memory utilization of my
  compute instances over the past 24 hours so that I can identify idle VMs and
  reclaim quota.
- As a Tenant User, I want to see the storage consumption of my volumes
  relative to their provisioned capacity so that I can decide when to expand or
  clean up.
- As a Tenant User, I want to see GPU utilization for my compute instances so
  that I can optimize job scheduling on expensive hardware.
- As a Tenant Admin, I want to see aggregated utilization across all projects
  in my organization so that I can help my teams rightsize their resources and
  optimize overall consumption.
- As a Cloud Provider Admin, I want to see aggregated utilization across all
  organizations per hub so that I can plan capacity additions and identify
  hotspots.
- As a Cloud Provider Admin, I want to export per-organization utilization data
  for a billing period so that I can build cost allocation reports.
- As a Cloud Provider Admin, I want utilization metrics retention to be
  configurable so that I can balance storage costs against reporting needs.

### Goals

- Expose per-resource utilization metrics (CPU, memory, storage, GPU) through
  the OSAC public HTTP API, scoped to the caller's access level: Tenant Users
  see their project's resources, Tenant Admins see their organization's
  resources, Cloud Provider Admins see all resources.
- Support querying metrics at two granularities: 5-minute raw and 1-hour
  rollups, selectable via PromQL metric name.
- Retain raw metrics for 30 days and hourly rollups for 13 months.
- Define the relationship between utilization metrics and metering/billing
  data clearly in the API.

### Non-Goals

- **Billing and metering**: Billing remains allocation-based. This proposal
  does not change how organizations are billed. Utilization data may inform
  future cost allocation models but that work is out of scope here.
- **Alerting and SLO monitoring**: No alert rules or SLO tracking are defined
  in this proposal; those belong in a future observability enhancement.
- **External infrastructure metrics**: Metrics from infrastructure components
  outside the OCP hub cluster — such as OpenStack or Netris — are not in
  scope. The architecture defined here (dedicated OSAC Prometheus Agent) is
  designed to accommodate these in a future enhancement without structural
  changes.
- **User-defined metrics**: Only OSAC-defined infrastructure metrics are exposed
  (CPU, memory, storage, GPU for compute instances, clusters, and volumes).
  Any custom metrics that Tenant Users want to publish from their workloads —
  whether from VM processes, application pods, or any other user-managed
  component — are out of scope.
- **Real-time streaming**: The API returns point-in-time or range queries; live
  streaming of metrics is not in scope.

## Proposal

### Overview

The Fulfillment Service exposes utilization metrics through the standard
Prometheus HTTP API. Adopting this industry-standard interface means any tool
in the Prometheus ecosystem — Grafana, alertmanager, or custom scripts — can
consume OSAC metrics without custom integration code. The Fulfillment Service
enforces access scoping by rewriting incoming PromQL queries to inject label
selectors derived from the caller's token claims before forwarding them to a
dedicated OSAC Thanos Query instance. Tenant Users, Tenant Admins, and Cloud
Provider Admins each get a different scope; all write standard PromQL and the
service enforces what data they can see.

OSAC operates a dedicated, isolated Prometheus/Thanos stack that is entirely
separate from the ACM Multicluster Observability Operator (MCO) stack. The OSAC
stack federates only the utilization metrics it cares about from ACM's central
Thanos Query — it does not deploy any collection agents on the hubs. This
design provides three distinct properties:

- **Operational isolation**: the ACM/MCO stack remains fully operational even
  if the OSAC metrics stack is down or degraded due to a bug or a bad user
  query. Cloud Provider Admins retain their platform view regardless of OSAC
  state.
- **Data isolation**: because the federation filter is applied at ingestion
  time, the OSAC Thanos store only ever contains the specific metrics OSAC
  has declared (`kubevirt_vmi_*`, `dcgm_fi_*`, `kubelet_volume_stats_*`). A
  bug or security incident in the OSAC stack cannot expose the full platform
  metric data that lives in ACM's Thanos.
- **Extensibility**: the OSAC Prometheus Agent is the single ingestion boundary
  for the stack. Future metric sources — such as OpenStack (via STF) or Netris
  (via COO ScrapeConfig) — can be added as new scrape targets on the agent
  without any changes to ACM or the hub clusters.

```
 Grafana / Fulfillment Service
   │ Prometheus HTTP API
   │ URL: https://osac.example.com/api/fulfillment/v1/metrics
   │
   ▼ PromQL (rewritten, scoped)
   │
┌──┴──────────────────────────────────────────────────────────────┐
│  OSAC dedicated Thanos stack                                     │
│                                                                  │
│  Thanos Query ──► Thanos Store ──► Object storage (S3)          │
│       ▲                                                          │
│  Prometheus Agent                                                │
│  (federates from ACM, filters to OSAC metrics only)             │
│  GET /federate?match[]=kubevirt_vmi_*                           │
│               &match[]=dcgm_fi_*                                │
│               &match[]=kubelet_volume_stats_*                   │
└───────────────────────────────┬─────────────────────────────────┘
                                │ federation (pull)
                                │ only OSAC-relevant metrics
                                │
┌───────────────────────────────▼─────────────────────────────────┐
│  ACM / MCO stack (unchanged)                                     │
│                                                                  │
│  Thanos Query (MCO-managed) ◄── Thanos Receive ◄── Hub remotes  │
│                                                                  │
│  Hub A (CMO Prometheus)          Hub B (CMO Prometheus)         │
│  KubeVirt VMI, DCGM, storage     KubeVirt VMI, storage          │
└─────────────────────────────────────────────────────────────────┘
```

### Metrics Exposed

#### Compute Instances (VMs)

| Metric | Description | Source |
|---|---|---|
| `cpu_usage_percent` | vCPU utilization (0–100%) averaged over the interval | `kubevirt_vmi_vcpu_seconds_total` |
| `memory_usage_bytes` | Guest memory in use | `kubevirt_vmi_memory_used_bytes` |
| `memory_requested_bytes` | Guest memory allocated | `kubevirt_vmi_memory_available_bytes` |
| `network_rx_bytes_total` | Bytes received since creation | `kubevirt_vmi_network_receive_bytes_total` |
| `network_tx_bytes_total` | Bytes transmitted since creation | `kubevirt_vmi_network_transmit_bytes_total` |
| `disk_read_bytes_total` | Disk bytes read since creation | `kubevirt_vmi_storage_read_bytes_total` |
| `disk_write_bytes_total` | Disk bytes written since creation | `kubevirt_vmi_storage_write_bytes_total` |

GPU metrics are exposed only for instances provisioned from a GPU-enabled
template:

| Metric | Description | Source |
|---|---|---|
| `gpu_usage_percent` | GPU compute utilization (0–100%) | DCGM `DCGM_FI_DEV_GPU_UTIL` |
| `gpu_memory_usage_bytes` | GPU memory in use | DCGM `DCGM_FI_DEV_FB_USED` |
| `gpu_memory_total_bytes` | Total GPU memory | DCGM `DCGM_FI_DEV_FB_TOTAL` |

#### Storage Volumes

| Metric | Description | Source |
|---|---|---|
| `volume_used_bytes` | Bytes used by the volume | OCP `kubelet_volume_stats_used_bytes` |
| `volume_capacity_bytes` | Provisioned volume size | OCP `kubelet_volume_stats_capacity_bytes` |

Storage metrics are attributed to the project that owns the PVC.

#### CaaS Clusters

CaaS cluster metrics aggregate over all worker nodes in the cluster:

| Metric | Description | Source |
|---|---|---|
| `node_cpu_usage_percent` | Average node CPU utilization across the cluster | `node_cpu_seconds_total` |
| `node_memory_usage_bytes` | Total memory in use across nodes | `node_memory_MemTotal_bytes - node_memory_MemAvailable_bytes` |
| `node_count` | Number of nodes (current) | `kube_node_info` |

### Granularity and Retention

| Level | Metric name suffix | Resolution | Retention |
|---|---|---|---|
| Raw | _(none)_ | 5 minutes | 30 days |
| Hourly rollup | `_1h` | 1 hour | 13 months |

Hourly rollup metrics are pre-computed by Thanos Ruler recording rules using
`avg_over_time` for percentages and `max_over_time` for byte totals. They are
exposed under a separate metric name (e.g. `cpu_usage_percent_1h`) so callers
choose the granularity explicitly in their PromQL. Both tiers are available via
the same API endpoints.

Retention values are configurable by Cloud Provider Admins via the OSAC Thanos
stack configuration. The values above are defaults.

### Workflow Description

The following actors are involved. See the
[organizations enhancement](/enhancements/organizations) for full definitions.

**Tenant User** is a regular user within an organization who authenticates
through the organization's IdP and uses OSAC Tenant APIs within projects.

**Tenant Admin** is a user with the `tenant-admin` role, scoped to one
organization, responsible for managing that organization's projects and users.

**Cloud Provider Admin** is a user with the `cloud-provider-admin` role in the
System organization, with full control across all organizations.

---

**Tenant User building a Grafana dashboard:**

1. Tenant User authenticates with Keycloak and obtains an OSAC Bearer token
   carrying their `{org, project}` claims.
2. Grafana is configured with a Prometheus datasource pointing at
   `https://osac.example.com/api/fulfillment/v1/metrics`, with the Tenant
   User's Bearer token in the `Authorization` header.
3. Tenant User builds a panel using standard PromQL, e.g.
   `cpu_usage_percent{osac_compute_instance="ci-xyz"}`.
4. Grafana POSTs to `/api/fulfillment/v1/metrics/api/v1/query_range`.
5. Fulfillment Service authenticates the token, extracts `{org, project}` from
   claims, parses the PromQL, and injects
   `{osac_org="org1", osac_project="p1"}` into every metric selector.
6. Fulfillment Service forwards the rewritten query to the OSAC Thanos Query.
7. Thanos returns the time-series matrix; Fulfillment Service proxies the
   Prometheus JSON response back to Grafana verbatim.
8. Grafana renders the panel.

**Tenant Admin viewing org-wide utilization:**

Steps 1–4 are the same. At step 5, the token carries the `tenant-admin` role;
the Fulfillment Service injects only the org-level selector
`{osac_org="org1"}`, omitting the project restriction. The Tenant Admin sees
metrics across all projects within their organization.

**Cloud Provider Admin querying cross-organization:**

Steps 1–4 are the same. At step 5, the token carries the `cloud-provider-admin`
role; the Fulfillment Service applies no org or project label injection.
The PromQL is forwarded as-is (still subject to metric name allowlist),
allowing queries across all organizations and hubs.

### API Extensions

No new gRPC service is introduced. Instead, the Fulfillment Service REST
gateway registers Prometheus HTTP API-compatible handlers using the existing
`gatewayMux.HandlePath()` mechanism (the same hook used for `/healthz`). No
existing CRDs, protos, or admission webhooks are modified.

#### Endpoints

The following endpoints are registered under the prefix
`/api/fulfillment/v1/metrics`. A Prometheus datasource is configured with URL
`https://<gateway>/api/fulfillment/v1/metrics`.

| Method | Path | Purpose |
|---|---|---|
| `GET`, `POST` | `/api/fulfillment/v1/metrics/api/v1/query` | Instant PromQL query |
| `GET`, `POST` | `/api/fulfillment/v1/metrics/api/v1/query_range` | Range PromQL query |
| `GET`, `POST` | `/api/fulfillment/v1/metrics/api/v1/labels` | Label name autocomplete |
| `GET`, `POST` | `/api/fulfillment/v1/metrics/api/v1/label/{name}/values` | Label value autocomplete |

These four endpoints are sufficient for full Grafana dashboard and Explore
support (query, variable dropdowns, autocomplete).

#### Request / response shape

Standard Prometheus HTTP API JSON. Example range query response:

```json
{
  "status": "success",
  "data": {
    "resultType": "matrix",
    "result": [
      {
        "metric": {
          "__name__": "cpu_usage_percent",
          "osac_project": "project-abc",
          "osac_compute_instance": "ci-xyz"
        },
        "values": [
          [1715510400, "12.3"],
          [1715510700, "14.1"]
        ]
      }
    ]
  }
}
```

#### PromQL scoping and security

The Fulfillment Service must prevent callers from reading data outside their
access scope:

1. **Parse** the incoming PromQL using
   `github.com/prometheus/prometheus/promql/parser`.
2. **Inject** mandatory label matchers derived from the caller's token role into
   every metric selector in the AST:

   | Role | Injected selectors |
   |---|---|
   | Tenant User | `{osac_org="org1", osac_project="p1"}` |
   | Tenant Admin | `{osac_org="org1"}` |
   | Cloud Provider Admin | _(none)_ |

3. **Allowlist** metric names: reject queries referencing metric names not in
   the set of OSAC-defined utilization metrics. Applies to all roles.
4. **Forward** the rewritten PromQL to the OSAC Thanos Query (internal).

### Relationship to Metering and Billing Data

Utilization metrics and metering/billing data serve different purposes and
are kept deliberately separate:

| Dimension | Utilization Metrics | Metering / Billing |
|---|---|---|
| What is measured | Actual resource consumption (CPU %, bytes used) | Resource allocation (reserved cores, GiB, GPU slots) |
| Granularity | 5 min / 1 h | Hourly allocation events |
| Retention | 30 days raw / 13 months rollup | Determined by billing system |
| Who reads it | Tenant User (own project), Tenant Admin (own org), Cloud Provider Admin (all orgs) | Billing system, Finance |
| API | Prometheus HTTP API (this proposal) | Separate metering API (future) |

A Tenant User that provisions a 16-core VM but only uses 2 cores will see
`cpu_usage_percent ≈ 12.5%` in utilization metrics but will be billed for
16 cores in the metering record. Utilization data can inform rightsizing
recommendations and cost allocation policies, but does not replace
allocation-based metering.

### Implementation Details/Notes/Constraints

- **HTTP handler registration**: The four Prometheus API endpoints are
  registered via `gatewayMux.HandlePath()` in `start_rest_gateway_cmd.go`,
  following the same pattern as `/healthz`. No new proto files or generated
  code are required.
- **OSAC labels on source objects**: This proposal depends on the
  `osac-operator` labeling every `VirtualMachine` and `PersistentVolumeClaim`
  it creates with `osac.io/org` and `osac.io/project` at creation time. These
  labels are the single source of truth for the org/project attribution of a
  resource and flow through the entire metrics pipeline.
- **Label propagation via info metrics**: KubeVirt exports VMI labels through
  the `kubevirt_vmi_info` metric as `label_osac_io_org` and
  `label_osac_io_project`. kube-state-metrics (already part of the OCP
  monitoring stack) does the same for PVCs via
  `kube_persistentvolumeclaim_labels`. Hub-level recording rules join raw
  metrics with these info metrics using `group_left` to produce OSAC-labeled
  series:
  ```promql
  kubevirt_vmi_vcpu_seconds_total
    * on(name, namespace) group_left(label_osac_io_org, label_osac_io_project)
    kubevirt_vmi_info
  ```
  A label rename step normalizes `label_osac_io_org` → `osac_org` and
  `label_osac_io_project` → `osac_project`.
- **PromQL rewriting**: The Fulfillment Service uses
  `github.com/prometheus/prometheus/promql/parser` to parse and rewrite
  queries. The rewriter walks the AST and appends label matchers to every
  `VectorSelector` node. This is the security-critical path; it must be unit
  tested exhaustively (nested selectors, subqueries, binary operations).
- **Metric allowlist**: The allowlist is a static set of metric names defined
  in the Fulfillment Service configuration. Queries referencing unlisted names
  return an HTTP 400 with a Prometheus-format error body
  (`{"status":"error","errorType":"bad_data","error":"metric not allowed"}`).
- **DCGM**: GPU metrics require the NVIDIA DCGM exporter on GPU-enabled nodes.
  If DCGM is absent, the recording rules for GPU metrics produce no series;
  queries return an empty result set, not an error.
- **Federation from ACM**: The OSAC Prometheus Agent runs on the OSAC control
  plane and pulls only the metrics it needs from ACM's central Thanos Query via
  the `/federate` endpoint, filtering with explicit metric name matchers. No
  per-hub components are added. The ACM/MCO stack is read-only from OSAC's
  perspective and remains unaffected by OSAC stack failures.

### Risks and Mitigations

| Risk | Mitigation |
|---|---|
| OSAC Thanos stack becomes a single point of failure | Deploy Thanos Query with multiple replicas; Thanos Receive with replication factor ≥ 2 |
| Label cardinality explosion from many VMs | Pre-aggregate at recording rule level; avoid high-cardinality labels in queries |
| DCGM not deployed on all hubs | API returns empty GPU result set (HTTP 200, not 500) |
| Tenant User constructs a query targeting another organization's resources | PromQL label injection forces `osac_org` and `osac_project` matchers — cross-org selectors are silently overridden |
| Bug in PromQL label injection exposes metrics beyond tenant scope | The OSAC Thanos store only contains the federation-filtered metric subset — even a complete bypass of label injection cannot expose full hub platform data |

### Drawbacks

- Introduces a dedicated OSAC Thanos stack (Prometheus Agent, Receive, Query,
  Store Gateway, Compactor, object storage) alongside the existing ACM/MCO
  stack. This is an intentional trade-off for operational and data independence:
  the two stacks do not share fate, but Cloud Provider Admins must operate both.
- Adding new HTTP endpoints increases the Fulfillment Service surface area.
  Teams must maintain the PromQL label injection logic as internal resource
  naming evolves.
- Utilization metrics may give Tenant Users incorrect intuitions about billing
  if the distinction between utilization and allocation is not surfaced clearly
  in documentation and the console UX.

## Alternatives (Not Implemented)

### Custom gRPC metrics service

Design a bespoke gRPC service with a custom `MetricSample` type. Rejected
because a custom API creates an integration burden for every consumer: Grafana,
alerting pipelines, cost management tools, and scripts would all need custom
adapters. The Prometheus HTTP API is an industry standard already supported
natively by the entire observability ecosystem, and costs no more to implement
on the server side.

### OSAC Thanos Query pointing directly at ACM Thanos (no dedicated store)

Configure OSAC's Thanos Query to fan out to ACM's Thanos Query as a remote
store, with a Thanos Query Frontend for result caching. No Prometheus Agent,
no OSAC Thanos Receive or Store required. Rejected for two reasons. First,
there is no data isolation: the OSAC Thanos Query has access to the full ACM
metric namespace at query time — a bug in the PromQL label injection logic would
expose all hub platform metrics to a tenant, not just the filtered utilization
subset. Second, this approach permanently ties OSAC to ACM as its only metric
source, making it impossible to ingest metrics from external infrastructure
(OpenStack, Netris) in the future without a full architectural change.

### Expose raw Prometheus / Thanos endpoints per tenant

Grant each Tenant User a scoped Prometheus / Thanos endpoint directly. Rejected
because it bypasses OSAC's authorization model (Kuadrant/Authorino), requires
managing one endpoint per organization, and exposes internal metric label schemas
to Tenant Users — creating a stability contract that is hard to evolve.

### Store metrics in a relational database

Write metric samples into PostgreSQL alongside existing OSAC state. Rejected
because time-series databases (Prometheus/Thanos) are purpose-built for this
workload. Duplicating data into a relational store adds operational complexity
with no clear benefit.

### Add utilization fields to ComputeInstance status

Expose a `utilization` sub-object in `ComputeInstanceStatus` with current
(point-in-time) CPU/memory values. This is simpler but covers only the current
snapshot, not historical trends. It can be added as a complementary feature
later without conflicting with this proposal.

## Open Questions

1. **GPU metric label schema**: DCGM labels GPU metrics by PCI bus ID, not by
   VM name. Should the hub-level Prometheus recording rules handle the
   `(bus_id → VMI name)` mapping, or should the Fulfillment Service perform
   this translation at query time? The hub-side recording rule approach is
   preferred to keep the central query simple, but requires a per-hub
   configuration step when VMs are assigned GPUs.
2. **Retention configurability scope**: Should retention be configurable
   globally by the Cloud Provider Admin only, or also per-organization by
   Tenant Admins? Per-org retention is useful for compliance (some organizations
   need longer data) but adds complexity. Initial implementation will be
   global only, controlled by Cloud Provider Admins.
3. **MCO spoke metrics collector allowlist**: MCO's `observability-metrics-collector`
   scrapes a fixed allowlist of OCP platform metrics. KubeVirt VMI metrics and
   DCGM GPU metrics are unlikely to be included. If they are not in the MCO
   Thanos, the OSAC Prometheus Agent cannot federate them from ACM. In that
   case, a separate CMO remote write configuration per hub would be required to
   ship those metrics directly to the OSAC Thanos Receive. This must be
   validated against the MCO allowlist before implementation.

## Test Plan

- Unit tests for the PromQL AST rewriter covering all query shapes: simple
  selectors, binary operations, subqueries, aggregations. Verify label
  injection is applied to every `VectorSelector` node.
- Unit tests for the metric allowlist: verify unlisted metric names are
  rejected with a Prometheus-format error body before the query reaches Thanos.
- Integration tests against a Thanos test instance seeded with fixture time
  series: verify the `/api/v1/query_range` response matches expected samples;
  verify cross-project selectors do not return another organization's series.
- Integration test: Cloud Provider Admin token bypasses project label injection;
  verify cross-project results are returned.
- Unit test for the operator: verify `VirtualMachine` and `PVC` objects created
  by `osac-operator` carry `osac.io/org` and `osac.io/project` labels.
- End-to-end test using a real Grafana instance: configure Prometheus datasource,
  build a panel with `cpu_usage_percent`, verify it renders without plugin
  installation.
- Absence of DCGM: query GPU metric returns empty result set, HTTP 200 (not
  500).

## Graduation Criteria

### Dev Preview

- CPU and memory metrics for compute instances implemented.
- Tenant User project-scoped access enforced.
- OSAC dedicated Thanos stack running on a single environment.
- No SLA on data completeness or latency.

### Tech Preview

- All metric types (CPU, memory, storage, GPU) implemented.
- Tenant User (project), Tenant Admin (org), and Cloud Provider Admin (all)
  scoping validated in QE environment.
- Multi-hub federation validated on at least two hubs.
- Hourly rollup tier active.

### GA

- 30-day raw retention and 13-month rollup retention operational.
- Documentation published in the OSAC docs.
- No known data loss incidents in Tech Preview period.

## Upgrade / Downgrade Strategy

The metrics API endpoints are a new, additive HTTP surface on the Fulfillment
Service. Existing clients are unaffected.

The OSAC Thanos stack is additive infrastructure; disabling or removing it does
not affect OSAC resource lifecycle operations (provisioning, deletion, etc.). On
downgrade, the metrics endpoints return `UNAVAILABLE` rather than degrading the
control plane.

## Version Skew Strategy

No version skew concerns: the metrics data path (Prometheus exporters → ACM
Thanos → OSAC Prometheus Agent → OSAC Thanos → Fulfillment Service) is entirely
read-only and decoupled from the osac-operator reconcilers and KubeVirt
controllers. A skew between Fulfillment Service versions results in metrics
being temporarily unavailable, not in data corruption.

## Support Procedures

**Symptom: Metrics API returns empty samples**

Check in order:
1. OSAC Prometheus Agent — verify it is scraping ACM's Thanos `/federate`
   endpoint successfully (check Agent logs and targets page).
2. ACM Thanos — verify `kubevirt_vmi_vcpu_seconds_total` is present in ACM's
   Thanos Query (`kubectl port-forward` to `observability-thanos-query`). If
   absent, the MCO allowlist likely excludes KubeVirt metrics (see Open
   Question 3).
3. OSAC Thanos — verify the OSAC Prometheus Agent is remote-writing to OSAC
   Thanos Receive successfully (check `thanos_receive_replication_factor`
   metric on the OSAC Receive).
4. Hub recording rules — verify `osac.io/org` and `osac.io/project` labels are
   present on the `VirtualMachine` or `PVC` object; without them the recording
   rule join produces no series.

**Symptom: Cross-organization data leak (Tenant User sees another organization's metrics)**

This is a P0 incident. Immediately:
1. Disable the metrics API by removing the Gateway API `HTTPRoute` for
   `/api/fulfillment/v1/metrics/*`.
2. Audit Fulfillment Service logs for metric query calls where the
   `osac_org` label injected does not match the caller's token `org` claim.
3. Root cause: PromQL label injection in `rewriteQuery` failed to apply
   matchers — likely an unhandled AST node type.

**Disabling the metrics API** has no impact on OSAC resource operations. The
Gateway `HTTPRoute` for `/metrics` endpoints can be deleted independently of
the main Fulfillment Service routes.

## Infrastructure Needed

**osac-operator change (prerequisite):**
- `VirtualMachine` and `PersistentVolumeClaim` objects must be labeled with
  `osac.io/org` and `osac.io/project` at creation time. Required before any
  metrics enrichment can work.

**Per hub:**
- No new components. ACM/MCO already collects hub metrics and ships them to the
  MCO central Thanos. See Open Question 3: if MCO's allowlist excludes
  KubeVirt/DCGM metrics, a CMO remote write configuration pointing at the OSAC
  Thanos Receive will be needed per hub.
- DCGM exporter on GPU-enabled nodes (new, optional).

**OSAC control plane (new, dedicated stack):**
- Prometheus Agent federating from ACM's Thanos Query (OSAC-relevant metrics
  only).
- Thanos Receive (ingests from the Prometheus Agent).
- Thanos Query (queried by the Fulfillment Service).
- Thanos Store Gateway + Compactor (long-term storage and downsampling).
- Object storage bucket (S3-compatible, e.g. ODF or AWS S3).

This stack is intentionally separate from the MCO stack to preserve operational
and data independence.
