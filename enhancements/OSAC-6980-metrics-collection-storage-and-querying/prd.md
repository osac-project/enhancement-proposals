# Metrics Collection, Storage and Querying

| Field     | Value                                                             |
|-----------|-------------------------------------------------------------------|
| Author(s) | Amit Oren                                                         |
| Jira      | https://redhat.atlassian.net/browse/OSAC-6980                    |
| Date      | 2026-10-29                                                        |

## Problem Statement

OSAC platform components — fulfillment service, operators, and metering — already expose Prometheus-format metrics endpoints, and KubeVirt VM metrics and HyperShift cluster metrics are visible within OpenShift's Cluster Monitoring stack. None of these signals are collected into a unified, long-term store, and no platform-wide query interface exists. As a result, Cloud Provider Admins cannot run cross-component PromQL queries, Cloud Infrastructure Admins cannot correlate VM metrics with control plane health, and tenants have no way to query metrics scoped to their organization. Without this pipeline, every downstream observability capability — alerting, dashboards, health monitoring, and tenant-visible resource metrics — has no data source to build on. [Clarify: D5]

## In Scope

- Metrics collection wired for all OSAC control plane components: fulfillment service binaries, OSAC and bare-metal operators, metering service, and metering adapters. No collection configuration for these components exists today; this Feature delivers it. [Clarify: D5]
- VM workload metrics (CPU, memory, network, storage) and cluster metrics from the OpenShift Cluster Monitoring stack aggregated into the platform-wide store, available both at the node/infrastructure level for Cloud Infrastructure Admins and scoped to individual resources for tenants. [Clarify: D5]
- NVIDIA GPU health metrics — utilization, temperature, power draw, and error counts — available for querying with vendor-agnostic naming conventions. [Clarify: D3]
- Signals from shelf products (KubeVirt, HyperShift, OpenShift AI/MaaS, CMO) queryable through the OSAC telemetry schema with consistent naming, with no upstream dependency on changes to those products. [Jira: OSAC-6978, Clarify: D5]
- Long-term metrics storage with configurable retention tiers (hot, warm, cold) and per-environment duration parameters. [Jira: OSAC-6978]
- Prometheus-compatible HTTP API (PromQL) as the query interface, accessible to authorized operators and tenants. [Clarify: D2]
- Tenant-isolated query access: tenants authenticate with their existing Keycloak or OIDC-compatible IdP credentials and can only query metrics from their own organization's resources, enforced by the query interface. [Clarify: D4, D8]
- Basic metrics pipeline health visible to Cloud Infrastructure Admins: collection success rates and storage component health. [Clarify: D6]
- Scale target: tens of tenants and hundreds of OSAC-managed resources. [Jira: OSAC-6978]

## Out of Scope

- Alerting rules and dashboards — OSAC-6984.
- Log collection and aggregation — OSAC-6982.
- BMC/IPMI hardware health metrics (node temperature, power draw, fan speed, physical host availability) — OSAC-6986.
- Tenant and resource identity label enrichment for per-tenant attribution and multi-tenant dashboards — OSAC-6988. Isolation in this Feature uses existing organizational boundaries; explicit `osac_tenant` labels are a separate concern.
- Deep observability-of-observability (collector throughput, pipeline latency, alert delivery health) — OSAC-6990.
- Audit logging — OSAC-63.

## User Stories

### Cloud Provider Admin

- As a Cloud Provider Admin, I want to query metrics across all OSAC control plane components — API request rates, database latency, operator health, and billing pipeline state — via a Prometheus-compatible HTTP API so that I can identify platform-wide hotspots and support capacity planning.
- As a Cloud Provider Admin, I want metrics retained in configurable hot, warm, and cold storage tiers so that I can run historical queries for SLA reporting and trend analysis.

### Cloud Infrastructure Admin

- As a Cloud Infrastructure Admin, I want metrics from all OSAC control plane components available in a unified query interface so that I do not need to manually configure scrape targets or access individual component endpoints.
- As a Cloud Infrastructure Admin, I want VM workload metrics (CPU, memory, network, storage) aggregated at the node level available alongside node and control plane metrics so that I can identify infrastructure saturation and noisy-neighbor effects without needing per-tenant visibility.
- As a Cloud Infrastructure Admin, I want NVIDIA GPU health metrics (utilization, temperature, power draw, error counts) queryable per cluster so that I can monitor fleet-wide GPU health proactively.
- As a Cloud Infrastructure Admin, I want basic metrics pipeline health visible — collection success rates and storage component health — so that I know when the collection system itself is degraded before it affects alerting or dashboards.

### Tenant Admin / Tenant User

- As a Tenant Admin or Tenant User, I want to query metrics for my organization's provisioned resources — VM utilization, cluster health — via the Prometheus-compatible API so that I can understand workload performance and resource consumption.
- As a Tenant Admin or Tenant User, I want tenant isolation enforced so that my query credentials can only return my organization's metrics, regardless of how the query is constructed.

## Assumptions

- The OSAC-6978 architecture standards document (currently tracked as a Task under OSAC-6981) will be approved before the OSAC-6980 Design phase begins. The collection schemas, telemetry conventions, and naming and label conventions depend on that document.
- OpenShift's Cluster Monitoring Operator is deployed and functional in the target environment; KubeVirt and HyperShift metrics are being collected by CMO and are accessible for aggregation.
- OSAC's existing Keycloak deployment is configurable for the metrics query access control layer without requiring a new Keycloak instance.

## Dependencies

- **OSAC-6978 (Architecture Standards Document):** The telemetry conventions, resource identity schema, and shelf-product adaptation rules defined there are required inputs before the Design phase can finalize collection configuration and naming and label conventions.
- **OpenShift Cluster Monitoring Operator (CMO):** KubeVirt and HyperShift metrics are sourced from CMO. OSAC-6980 aggregates them; it does not replace CMO's collection.
- **OSAC Keycloak:** The existing Cloud Provider Admin Keycloak instance is used for query interface authentication.
- **OpenShift AI (MaaS):** A platform metric source alongside KubeVirt and HyperShift. Its metrics are expected to be accessible via CMO or its own Prometheus endpoints. DCGM Exporter for GPU metrics may already be deployed by OpenShift AI; OSAC-6980 integrates with the existing deployment or provisions it if absent.
- **Downstream Features (OSAC-6982, OSAC-6984, OSAC-6986, OSAC-6988, OSAC-6990, OSAC-6992):** All depend on this pipeline being operational. Their Design phases should not begin until this Feature's metrics store and query interface are available.

---

## Provenance

Authored: draft @ prd 0.11.5 - 7b2b8de, workspace prd/OSAC-6978 @ 6b22017
Final: revise @ prd 0.11.5 - 7b2b8de, workspace prd/OSAC-6980 @ c41712c

> Context changed between draft and revise.

<!-- ai-workflow-provenance:{"schema_version":1,"provenance_kind":"session","workflow":"prd","workflow_version":"0.11.5","ai_workflows":"7b2b8de","source_repo":"c41712c","source_repo_branch":"prd/OSAC-6980","commits_behind_main":0,"commits_ahead_main":4,"main_ref":"main","phases":["draft","revise","revise","revise","revise","revise"],"authoring_modes":["skill"],"context_changed":true,"origin_untracked":false} -->
