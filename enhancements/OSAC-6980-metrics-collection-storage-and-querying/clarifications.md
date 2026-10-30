# Clarification Log — OSAC-6980

## Status

- Rounds completed: 3
- Open gaps: 0 (non-blocking)
- Exit criteria met: Yes

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

---

### R2.Q2: Authentication on the query interface

Does OSAC have an existing IdP to integrate with?

#### Answer

Yes — OSAC has an existing Keycloak for Cloud Provider Admins. Tenant Admins can connect their own OIDC-compatible IdP.

#### Impact

The metrics query interface authenticates callers via OSAC's existing Keycloak. The OCP-on-NERC Keycloak proxy pattern maps naturally onto this — Keycloak issues OIDC tokens, the proxy enforces per-tenant permissions before forwarding to Thanos Query.

#### Decision (D4)

Authentication uses OSAC's existing Keycloak (Cloud Provider Admin) and tenant OIDC-compatible IdPs (Tenant Admin). No new IdP is deployed.

---

### R2.Q3: Collection model per component (Prometheus scrape vs. OTLP push)

Which components push via OTLP vs. are scraped via Prometheus?

#### Answer

From the OSAC metrics reference (`/Users/amit/tmp/osac-observability/osac-metrics-reference.md`): all existing OSAC components use `prometheus/client_golang` and expose Prometheus scrape endpoints. No component currently pushes OTLP. Key findings:

- **OSAC fulfillment service**: HTTP on `localhost:8002` (unauthenticated) — Prometheus scrape
- **osac-operator, bmf-operator**: HTTPS on `:8443` with TokenReview/SubjectAccessReview — Prometheus scrape (bearer token required)
- **osac-metering**: HTTP on `:8080` (unauthenticated) — Prometheus scrape
- **echo-adapter, m360-adapter**: HTTP on `:2112` (unauthenticated) — Prometheus scrape
- **KubeVirt, HyperShift**: already scraped by Cluster Monitoring Operator (CMO) — federation or remote-write to Thanos
- **No ServiceMonitor or PodMonitor exists anywhere in the repo** — all wiring is unimplemented and is a core deliverable of OSAC-6980

#### Impact

OSAC-6980 deploys ServiceMonitors (+ RBAC prerequisites: namespace labels, Role/RoleBinding for prometheus-k8s service account, metrics-reader ClusterRoleBinding) for all OSAC components. Operators require bearer-token auth in ServiceMonitors. KubeVirt and HyperShift metrics are aggregated from CMO via Thanos federation or remote-write. OTLP is not required for any currently instrumented component.

#### Decision (D5)

All existing OSAC components use Prometheus scrape. OSAC-6980 delivers ServiceMonitors and all RBAC prerequisites for each component. KubeVirt and HyperShift metrics are aggregated from CMO. OTLP is not in scope for this Feature (no existing component uses it).

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

Tenant isolation in OSAC-6980 uses namespace-based permissions via the Keycloak proxy. Explicit `osac_tenant` and resource identity label enrichment is scoped to OSAC-6988.
