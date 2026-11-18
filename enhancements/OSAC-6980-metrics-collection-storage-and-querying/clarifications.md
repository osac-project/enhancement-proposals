# Clarification Log — OSAC-6980

## Status

- Rounds completed: 5
- Open gaps: 0 (non-blocking)
- Exit criteria met: Yes

> **Round 4 supersedes parts of Rounds 1–2.** GPU metrics moved out of this Feature (D9 supersedes D3), and the scope, identity, and scale decisions were restated against the revised PRD (D10–D13). D5's decision stands; its factual premise about ServiceMonitor inventory was corrected.
>
> **Round 5 (2026-11-09) supersedes D4, D8, and D12 and adds D14–D16.** It records the review-driven boundary between provider infrastructure metrics and tenant workload metrics, Cloud Infrastructure Admin authentication through OpenShift OAuth, the per-role authorization table, the deferred OSAC-6978 convention layer, and the boundary between imported-cluster metrics and the OSAC-6488 visibility rule.

---

## Round 1 — Storage, Query Interface, and Tenant Isolation

### R1.Q1: Metrics storage backend

"Scalable backend" was unspecified. Which technology?

#### Answer

Thanos — aligns with common stacks in this domain (OpenShift, OpenShift AI).

#### Impact

Thanos is the adopted metrics storage backend. This determines the collection architecture (Prometheus scrape → Thanos Receive or remote-write, or federation from CMO) and the query interface (Thanos Query as the PromQL engine).

#### Decision (D1)

Thanos is the metrics storage backend for OSAC-6980.

---

### R1.Q2: Query interface technology

Does the query interface extend the OSAC fulfillment API or deploy a dedicated metrics query server?

#### Answer

The API must be Prometheus-compatible HTTP API via Thanos Query.

#### Impact

OSAC-6980 deploys Thanos Query as the metrics query endpoint. It is not integrated into the fulfillment API. Tenants and operators query via a Prometheus-compatible HTTP API (PromQL). Authentication and access control sit in front of Thanos Query.

#### Decision (D2)

The metrics query interface is a Prometheus-compatible HTTP API served by Thanos Query. No integration with the OSAC fulfillment REST API.

---

### R1.Q3: Tenant isolation mechanism

Separate Prometheus instances per tenant, or a shared backend with a multi-tenancy proxy?

#### Answer

Lean toward separate instances, but the OCP-on-NERC Keycloak proxy pattern (https://github.com/OCP-on-NERC/docs/blob/main/architecture/observability/access-control-to-metrics/README.md) is the primary design inspiration. Further clarified in Round 3.

#### Impact

The OCP-on-NERC approach uses a shared Thanos backend with a Keycloak-backed proxy (Prometheus Keycloak Proxy) enforcing per-tenant, per-namespace fine-grained permissions via OIDC tokens. This is the reference architecture for OSAC-6980's tenant isolation. The specific mechanism (separate vs. shared + proxy) is a Design phase decision; the PRD requirement is that tenants cannot access another tenant's metrics through any query interface.

---

## Round 2 — GPU Collection, Auth, Collection Model, and Pipeline Self-Monitoring

### R2.Q1: GPU collection mechanism

Is DCGM Exporter the expected collection mechanism for NVIDIA GPU metrics?

#### Answer

Yes — DCGM Exporter is the only known mechanism. OpenShift AI likely already uses it.

#### Impact

OSAC-6980 deploys (or integrates with an existing deployment of) DCGM Exporter for NVIDIA GPU health metrics (utilization, temperature, power draw, error counts) per the GPU telemetry conventions from the OSAC-6978 architecture standards.

#### Decision (D3)

DCGM Exporter is the GPU metrics collection mechanism. OSAC-6980 integrates with DCGM Exporter — deploying it if not already present via OpenShift AI.

> **Superseded by D9 (Round 4).** GPU metrics, including DCGM Exporter collection, are out of scope for OSAC-6980 and deferred to OSAC-7246.

---

### R2.Q2: Authentication on the query interface

Does OSAC have an existing IdP to integrate with?

#### Answer

Yes — OSAC has an existing Keycloak for Cloud Provider Admins. Tenant Admins can connect their own OIDC-compatible IdP.

#### Impact

The metrics query interface authenticates callers via OSAC's existing Keycloak. The OCP-on-NERC Keycloak proxy pattern maps naturally onto this — Keycloak issues OIDC tokens, the proxy enforces per-tenant permissions before forwarding to Thanos Query.

#### Decision (D4)

Authentication uses OSAC's existing Keycloak (Cloud Provider Admin) and tenant OIDC-compatible IdPs (Tenant Admin). No new IdP is deployed.

> **Revised in Round 5 (2026-11-09).** Cloud Infrastructure Admins authenticate through OpenShift OAuth, consistent with OSAC-1030; they do not authenticate through Keycloak. Keycloak remains the Cloud Provider Admin identity provider and the tenant identity broker. The rest of D4 stands.

---

### R2.Q3: Collection model per component (Prometheus scrape vs. OTLP push)

Which components push via OTLP vs. are scraped via Prometheus?

#### Answer

From a review of the metrics endpoints in the OSAC components: all existing OSAC components use `prometheus/client_golang` and expose Prometheus scrape endpoints. No component currently pushes OTLP. Key findings:

- **OSAC fulfillment service**: HTTP on `0.0.0.0:8002` (unauthenticated); the chart sets `--metrics-listener-address=0.0.0.0:8002` for all five binaries, overriding the binary default of `localhost:8002`. Each Service exposes a named `metrics` port mapped to 8002 — Prometheus scrape
- **osac-operator, bmf-operator**: HTTPS on `:8443` with TokenReview/SubjectAccessReview — Prometheus scrape (bearer token required)
- **osac-metering**: HTTP on `:8080` (unauthenticated) — Prometheus scrape
- **echo-adapter, m360-adapter**: HTTP on `:2112` (unauthenticated) — Prometheus scrape
- **KubeVirt, HyperShift**: already scraped by Cluster Monitoring Operator (CMO) — federation or remote-write to Thanos
- **No ServiceMonitor or PodMonitor exists anywhere in the repo** — all wiring is unimplemented and is a core deliverable of OSAC-6980

#### Impact

OSAC-6980 deploys ServiceMonitors (+ RBAC prerequisites: namespace labels, Role/RoleBinding for prometheus-k8s service account, metrics-reader ClusterRoleBinding) for all OSAC components. Operators require bearer-token auth in ServiceMonitors. KubeVirt and HyperShift metrics are aggregated from CMO via Thanos federation or remote-write. OTLP is not required for any currently instrumented component.

#### Decision (D5)

All existing OSAC components use Prometheus scrape. OSAC-6980 delivers ServiceMonitors and all RBAC prerequisites for each component. KubeVirt and HyperShift metrics are aggregated from CMO. OTLP is not in scope for this Feature (no existing component uses it).

> **Factual correction (Round 4).** The answer's statement that "no ServiceMonitor or PodMonitor exists anywhere in the repo" is wrong: `osac-metering/charts/osac-metering/templates/servicemonitor.yaml` exists and is gated by `serviceMonitor.enabled` (default `false`). The decision is unchanged — OSAC-6980 enables that template and adds ServiceMonitors for the remaining components.

---

### R2.Q4: Pipeline self-monitoring scope

Is basic pipeline health monitoring in scope for OSAC-6980?

#### Answer

Yes — basic availability should be monitored as part of OSAC-6980.

#### Impact

OSAC-6980 includes basic metrics pipeline health monitoring: Prometheus scrape success rates, Thanos component health (Receive, Store, Query). Deep pipeline observability (collector throughput, pipeline latency, alert delivery) belongs to OSAC-6990.

#### Decision (D6)

Basic pipeline health monitoring (Prometheus scrape health, Thanos component health) is in scope for OSAC-6980. Deep observability-of-observability is deferred to OSAC-6990.

---

## Round 3 — BMC Hardware Metrics and Tenant Label Gap

### R3.Q1: BMC hardware metrics scope

Is deploying an IPMI/Redfish exporter for bare-metal hardware health in scope for OSAC-6980?

#### Answer

Deferred to OSAC-6986 (Health and Availability Monitoring). OSAC-6980 covers "platform components" meaning the OSAC-managed resource stack — control plane, KubeVirt, HyperShift, and DCGM GPU. BMC/IPMI physical hardware health belongs to the infrastructure health monitoring Feature. OSAC-6986 updated accordingly.

#### Impact

BMC/IPMI/Redfish hardware health exporter is out of scope for OSAC-6980. OSAC-6986 now explicitly includes it.

#### Decision (D7)

BMC hardware health metrics (temperature, power draw, fan speed, host availability via IPMI/Redfish exporter) are scoped to OSAC-6986. Out of scope for OSAC-6980.

---

### R3.Q2: Tenant label enrichment as prerequisite for isolation

Is adding explicit tenant labels to metrics a prerequisite for the OSAC-6980 isolation requirement?

#### Answer

No. For OSAC-6980's isolation requirement ("tenants can only query their own metrics"), namespace-based permissions via the Keycloak proxy pattern are sufficient — namespace already maps to tenant for KubeVirt, HyperShift, and OSAC operators. Explicit tenant/resource label enrichment (e.g., `osac_tenant` label) is the attribution layer, which belongs to OSAC-6988. OSAC-6988 updated accordingly.

#### Impact

OSAC-6980 enforces isolation using namespace-based Keycloak permissions. No new tenant label is added by this Feature. OSAC-6988 is responsible for label enrichment enabling per-tenant attribution and multi-tenant dashboards.

#### Decision (D8)

Tenant isolation in OSAC-6980 uses namespace-based enforcement in the query proxy. Keycloak brokers the tenant identity provider and issues an `organization` claim that maps to the tenant namespace; `prom-label-proxy` enforces that namespace on queries and on series, label, and metadata enumeration. Explicit `osac_tenant` and resource identity label enrichment is scoped to OSAC-6988.

> **Revised in Round 5 (2026-11-09).** The earlier wording said "namespace-based Keycloak permissions." Identity is mapped through the organization claim; the enforcement point remains the namespace label. The mechanism and the no-new-labels decision are unchanged.

---

## Round 4 — Revised PRD Scope, Identity, and Scale

The PRD was revised after Rounds 1–3. This round records the decisions that changed or were restated, so the design and testplan trace to the current PRD rather than to the superseded text.

### R4.Q1: Does GPU metrics collection remain in OSAC-6980?

#### Answer

No. GPU metrics — utilization, temperature, power draw, error counts, including NVIDIA DCGM Exporter collection — are deferred to a later Feature, OSAC-7246 (GPU Metrics Collection and Querying), under Outcome OSAC-3415.

#### Impact

The design drops the GPU Operator ClusterPolicy prerequisite, the DCGM relabeling path, and the GPU test cases. Device-level DCGM families and their tenant attribution are OSAC-7246's problem, not OSAC-6988's.

#### Decision (D9)

GPU metrics are out of scope for OSAC-6980 and deferred to OSAC-7246. D9 supersedes D3.

---

### R4.Q2: Which clusters are in scope for cluster metrics?

#### Answer

The management cluster, clusters OSAC provisions (including their hosted control planes), and ACM HUB-registered clusters imported into OSAC through OSAC-6488. Clusters OSAC neither provisions nor imports — including ACM-registered clusters that were not imported through OSAC-6488 — are out of scope.

#### Impact

The design adds a cross-cluster collection path: an authenticated remote-write Route on the management cluster (IC-9) plus per-cluster remote-write configuration delivered by the provisioning flow for provisioned clusters and by an ACM policy for imported clusters (IC-10). Series from every cluster carry a `cluster` external label and `managed_by=osac`.

#### Decision (D10)

Cluster-metric scope is the management cluster, OSAC-provisioned clusters including hosted control planes, and ACM HUB clusters imported through OSAC-6488. Metrics from any other cluster are out of scope.

---

### R4.Q3: How is a tenant identity proven, and what happens when an organization's IdP changes?

#### Answer

A token is accepted only from an OIDC-compatible identity provider registered for an OSAC organization, and the authenticated identity maps to that organization. Removing the organization's IdP registration makes queries authenticated through that provider fail. Isolation covers series, label, and metadata enumeration, not only range queries.

#### Impact

The tenant path uses Keycloak identity brokering: Keycloak validates the tenant IdP token and issues an OSAC token carrying an organization claim, which the proxy maps to the tenant namespace. `prom-label-proxy` runs with `--enable-label-apis` so `/series`, `/labels`, `/label/*/values`, and `/metadata` are enforced identically. A cross-namespace query returns an empty result set; a request without an organization claim is rejected.

#### Decision (D11)

Tenant tokens must come from an IdP registered for an OSAC organization and map to that organization. Deregistration revokes access. Enumeration endpoints are enforced the same way as queries. Isolation mechanism remains D8's namespace proxy.

---

### R4.Q4: Can a Cloud Provider Admin query a specific tenant's metrics?

#### Answer

Yes. Cross-tenant visibility for Cloud Provider Admins is required, including a single tenant's VM and cluster metrics during incident investigation. Cloud Infrastructure Admins also use the admin endpoint and are not namespace-restricted by this Feature.

#### Impact

The admin endpoint accepts both `cloud-provider-admin` and `cloud-infrastructure-admin`. No label enforcement on that path. Whether Cloud Infrastructure Admins should be restricted from tenant workload series is left as a design open question (OQ-5 in the design), because the PRD neither requires nor forbids it.

#### Decision (D12)

Cloud Provider Admins can query any tenant's metrics across clusters through the admin endpoint. Cloud Infrastructure Admins use the same endpoint, bounded by the PRD's authorization table: node, hypervisor, and per-VM metrics for any tenant, and cluster node/control-plane metrics for any managed cluster. The workload metric class is not collected at all, so there is no tenant-workload data for either role to see. Design OQ-5 is closed.

> **Revised in Round 5 (2026-11-09).** The earlier wording said Cloud Infrastructure Admins use the endpoint without restriction and that limiting their visibility was undecided. The workload exclusion removes the data class that question was about, and the PRD's authorization table now bounds both roles.

---

### R4.Q5: What scale target replaces "tens of tenants, hundreds of resources"?

#### Answer

The PRD no longer sets a tenant/resource scale bullet. NFR-5 requires the Design phase to state and validate the active time-series count the pipeline supports. NFR-6 adds per-tenant query concurrency and time-range limits.

#### Impact

The design states a supported ceiling of 500,000 active series, sizes Thanos Receive for it, and validates it with a synthetic-load test. The tenant endpoint gains a per-organization fair-use limiter with configurable concurrency, maximum range, and timeout.

#### Decision (D13)

OSAC-6980 supports and validates 500,000 active time series, with per-organization query fair-use limits. There is no fixed tenant or resource count target.

---

## Round 5 — Review-Driven Scope, Authorization, and Naming

The PRD was revised on 2026-11-09 in response to review on PR #438. This round records the decisions that changed or were restated, so the design and test plan trace to the current PRD.

### R5.Q1: Where is the boundary between provider infrastructure metrics and tenant workload metrics?

#### Answer

The Feature covers metrics about the infrastructure OSAC provisions and operates: OSAC control-plane components, the nodes and hypervisors hosting tenant VMs, and the control planes of OSAC-provisioned and imported clusters. Metrics about workloads running inside a tenant VM or a tenant cluster — pod, container, namespace, application, and model-serving — are not collected for any role. Tenants observe their workloads through the cluster's own OpenShift monitoring, not through OSAC's platform-wide store. Tenant workload observability is a separate future initiative.

#### Impact

The design drops tenant-workload collection paths, including the user-workload monitoring (UWM) remote-write whose only purpose was to carry those series. Cluster coverage is limited to the node and control-plane signals needed to operate and manage each cluster. The test plan asserts none-collected behavior for a pod metric rather than tenant workload visibility.

#### Decision (D14)

Tenant workload metrics — pod, container, namespace, application, and model-serving — are not collected by OSAC-6980 for any role. Tenants observe their workloads through their cluster's native OpenShift monitoring. Tenant workload observability is a separate future initiative.

---

### R5.Q2: How do Cloud Infrastructure Admins authenticate?

#### Answer

Through OpenShift OAuth, consistent with OSAC-1030. The existing OSAC Keycloak continues to authenticate Cloud Provider Admins and to broker each tenant organization's OIDC-compatible identity provider. No new identity provider is deployed.

#### Impact

The admin query endpoint accepts an OpenShift OAuth token for the Cloud Infrastructure Admin role and a Keycloak-issued token for Cloud Provider Admins. The Keycloak realm-role gating for `cloud-infrastructure-admin` is removed. Revises D4.

#### Decision (D4, revised)

Authentication uses OSAC's existing Keycloak (Cloud Provider Admin) and tenant OIDC-compatible IdPs (Tenant Admin). Cloud Infrastructure Admins authenticate through OpenShift OAuth, consistent with OSAC-1030. No new IdP is deployed.

---

### R5.Q3: What is each role authorized to query?

#### Answer

| Metric class | Cloud Provider Admin | Cloud Infrastructure Admin | Tenant |
|---|---|---|---|
| OSAC control-plane — fulfillment, operators, metering, adapters | any | any | none |
| Node, hypervisor, and per-VM utilization | any tenant | any tenant | own organization only |
| Cluster node and control-plane | any cluster | any managed cluster | own organization's clusters only |
| Workload — pod, container, namespace, application, model-serving | not collected | not collected | not collected |

#### Impact

Collection does not imply exposure: a metric class collected for platform operations is visible to tenants only where the table grants it. The tenant path enforces "own organization only" through the organization claim and namespace label (D8/D11). Design OQ-5 is closed because the workload class does not exist in the store. Revises D12.

#### Decision (D12, revised)

Cloud Provider Admins can query any tenant's metrics across clusters through the admin endpoint. Cloud Infrastructure Admins use the same endpoint, bounded by the authorization table above: node, hypervisor, and per-VM metrics for any tenant, and cluster node/control-plane metrics for any managed cluster. The workload metric class is not collected at all.

---

### R5.Q4: When are the OSAC-6978 naming and label conventions applied?

#### Answer

Later, as a separate convention layer. OSAC-6980 collects, stores, and queries using the metric names each source already emits — KubeVirt, HyperShift, OpenShift AI, and CMO product-native names. When OSAC-6978 is approved, canonical names and labels are applied as a versioned mapping (relabel rules at ingest or recording rules at query time); stored data is not re-ingested.

#### Impact

The collection, storage, and query pipeline is not gated on OSAC-6978 approval. Queries and dashboards written before the mapping lands use product-native names and may need rewriting when it arrives. The design already passes metrics through unchanged, so no design change is required; only the PRD's framing of the dependency changes.

#### Decision (D15)

OSAC-6978 canonical metric names and labels are a later, versioned convention layer, not a prerequisite for OSAC-6980's collection, storage, or query. Product-native metric names are the query surface until that layer is delivered.

---

### R5.Q5: Do Cloud Infrastructure Admins see metrics for imported clusters, given OSAC-6488's visibility rule?

#### Answer

Yes, for node and control-plane series only. OSAC-6488's rule that imported workload-cluster details are visible only to Cloud Provider Admins covers the workload-cluster resource and its configuration — its design grants `workload_cluster:list/get/create/update` to Cloud Provider Admins alone — and its stated rationale is that tenant access must not expose provider cluster configuration. Metrics are infrastructure telemetry: they carry no cluster configuration, lifecycle state, ownership, or tenant assignment. Imported clusters are shared provider capacity, not assigned to an organization, so no tenant sees their metrics.

#### Impact

The PRD adds the distinction to its OSAC-6488 dependency so the CIA grant in the authorization table and acceptance criteria is not read as contradicting OSAC-6488. No design change is required beyond the existing per-class authorization.

#### Decision (D16)

Imported-cluster metrics are infrastructure telemetry, not the workload-cluster details and configuration that OSAC-6488 makes visible only to Cloud Provider Admins. Cloud Infrastructure Admins may query node and control-plane series for imported clusters; no configuration, lifecycle state, ownership, tenant assignment, or cluster management access is exposed, and no tenant sees them.
