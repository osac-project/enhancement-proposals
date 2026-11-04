# Metrics Collection, Storage and Querying

| Field     | Value                                                             |
|-----------|-------------------------------------------------------------------|
| Author(s) | Amit Oren                                                         |
| Jira      | https://redhat.atlassian.net/browse/OSAC-6980                    |
| Date      | 2026-10-29                                                        |
| Service   | Platform-wide — BMaaS, CaaS, VMaaS, MaaS, Enclave                  |

## Problem Statement

OSAC platform components — the fulfillment service, operators, and metering — expose Prometheus-format metrics endpoints, and KubeVirt, HyperShift, and OpenShift AI metrics are visible within OpenShift's Cluster Monitoring stack. That monitoring is per-cluster, retained for a short fixed period, and has no tenant-aware query boundary. As a result, Cloud Provider Admins cannot run cross-component queries over a long history, Cloud Infrastructure Admins cannot correlate VM behavior with control-plane health across clusters, and tenants cannot query metrics for their own resources without a boundary that keeps other organizations' metrics out of view. Without this pipeline, every downstream observability capability — alerting, dashboards, health monitoring, and tenant-visible resource metrics — has no durable data source to build on.

## Goals

- One Prometheus-compatible HTTP query API serves Cloud Provider Admins, Cloud Infrastructure Admins, and tenants, each scoped to the resources they are authorized to see.
- Metrics from every OSAC control-plane component, KubeVirt VMs, and OpenShift clusters are retained in one long-term store and remain queryable across the configured retention window.
- Tenant queries return only metrics for the querying organization's resources, including queries written against platform-wide metric names.
- Cloud Infrastructure Admins can tell from the same query API whether collection and storage are healthy.

## In Scope

- This Feature applies to all OSAC services: BMaaS, CaaS, VMaaS, MaaS, and Enclave.
- Metrics from all OSAC control-plane components — the fulfillment service, the OSAC operator and the bare-metal fulfillment operator, the metering service, and the metering adapters — are queryable from the platform-wide store. [Clarify: D5]
- VM workload metrics observable at the hypervisor and node level (CPU, memory, network, storage) are aggregated into the platform-wide store, available per VM and grouped by the node hosting each VM. [Clarify: D5]
- OpenShift cluster metrics from the management cluster, from OSAC-provisioned clusters including their hosted control planes, and from ACM HUB-registered clusters imported into OSAC through OSAC-6488 are aggregated into the platform-wide store.
- Metrics from KubeVirt, HyperShift, OpenShift AI, and the OpenShift Cluster Monitoring stack are queryable through one consistent set of metric names and labels, with no required changes to those products. [Jira: OSAC-6978, Clarify: D5]
- Long-term metrics storage with configurable hot, warm, and cold retention tiers and per-environment retention durations. [Jira: OSAC-6978]
- A Prometheus-compatible HTTP (PromQL) query interface for Cloud Provider Admins, Cloud Infrastructure Admins, and tenants. [Clarify: D2]
- Tenant-isolated query access: tenants authenticate through the OIDC-compatible identity provider registered for their organization and can query only metrics for that organization's resources. A token is accepted only from an identity provider registered for an organization, and the authenticated identity maps to that organization. Platform-wide series and other organizations' series are never returned, including through series, label, and metadata enumeration. [Clarify: D4, D8]
- Cloud Provider Admin cross-tenant visibility: Cloud Provider Admins can query metrics for any tenant, including a single tenant's VM and cluster metrics during incident investigation.
- Basic metrics pipeline health — collection success rates and storage component health — is queryable by Cloud Infrastructure Admins and Cloud Provider Admins through the same query interface. [Clarify: D6]
- Scale target: at least 100 tenants and 10,000 OSAC-managed resources, with the resulting active time series sized and validated during the Design phase.

## Out of Scope

- Alerting rules and dashboards — OSAC-6984.
- Log collection and aggregation — OSAC-6982.
- BMC/IPMI hardware health metrics (node temperature, power draw, fan speed, physical host availability) — OSAC-6986.
- GPU metrics — utilization, temperature, power draw, and error counts, including NVIDIA DCGM Exporter collection. Deferred to a later Feature, OSAC-7246 (GPU Metrics Collection and Querying).
- Explicit tenant-attribution and resource-identity label enrichment for cross-tenant dashboards and chargeback — OSAC-6988. Isolation in this Feature uses the organization boundaries OSAC already maintains and does not depend on those labels.
- Metrics that require a guest agent inside a VM, such as guest OS memory usage, filesystem free space, and in-guest network throughput. Only metrics observable at the hypervisor or node level are in scope.
- Metrics from clusters that OSAC neither provisions nor imports, including ACM-registered clusters that have not been imported through OSAC-6488.
- Deep observability-of-observability (collector throughput, pipeline latency, alert delivery health) — OSAC-6990.
- Audit logging — OSAC-63.

## User Stories

### Cloud Provider Admin

- As a Cloud Provider Admin, I want to query metrics across all OSAC control plane components and all tenants — API request rates, database latency, operator health, and billing pipeline state — via a Prometheus-compatible HTTP API so that I can identify platform-wide hotspots and support capacity planning.
- As a Cloud Provider Admin, I want to query metrics for a specific tenant's VMs and clusters so that I can investigate an incident or answer a tenant's support request.
- As a Cloud Provider Admin, I want metrics retained in configurable hot, warm, and cold storage tiers so that I can run historical queries for SLA reporting and trend analysis.

### Cloud Infrastructure Admin

- As a Cloud Infrastructure Admin, I want metrics from all OSAC control plane components available in a unified query interface so that I do not need to manually configure scrape targets or access individual component endpoints.
- As a Cloud Infrastructure Admin, I want node-level and control-plane metrics for the management cluster and OSAC-managed clusters, together with VM workload metrics grouped by the node hosting each VM, so that I can identify infrastructure saturation and noisy-neighbor effects without needing per-tenant visibility.
- As a Cloud Infrastructure Admin, I want basic metrics pipeline health visible — collection success rates and storage component health — so that I know when the collection system itself is degraded before it affects alerting or dashboards.

### Tenant Admin / Tenant User

- As a Tenant Admin or Tenant User, I want to query utilization metrics for my organization's provisioned resources — VM CPU, memory, network, storage, and cluster health — via the Prometheus-compatible API so that I can understand workload performance and resource consumption.
- As a Tenant Admin or Tenant User, I want tenant isolation enforced so that my query credentials return only my organization's metrics, regardless of how the query is constructed, including queries written against platform-wide metric names.

## Non-Functional Requirements

- **NFR-1 (Isolation):** Every query response, including series, label, and metadata enumeration, contains only data for resources the caller is authorized to see. A query from one tenant never returns another tenant's data.
- **NFR-2 (Query performance):** A query over a 24-hour range scoped to one resource or one tenant returns within 5 seconds at the 95th percentile.
- **NFR-3 (Availability):** The query interface is available 99.9% of the time measured monthly.
- **NFR-4 (Retention):** Default retention is at least 15 days in the hot tier, 90 days in the warm tier, and 12 months in the cold tier. Each deployment environment (for example, staging or production) can configure its own durations, and the defaults are documented for admins.
- **NFR-5 (Scale):** The Design phase states and validates the active time-series count the pipeline supports for the tenant and resource targets above.
- **NFR-6 (Fair use):** Per-tenant query concurrency and time-range limits prevent one tenant from exhausting the shared query layer.
- **NFR-7 (Compatibility):** The query interface implements the Prometheus HTTP API and PromQL, so users can query it with standard Prometheus-compatible clients.

## Acceptance Criteria

- [ ] A Cloud Provider Admin can query metrics for every OSAC control-plane component and see results after the components are deployed.
- [ ] A Cloud Provider Admin can query a named tenant's VM and cluster metrics.
- [ ] A Cloud Infrastructure Admin can query node-level and control-plane metrics for the management cluster and OSAC-managed clusters.
- [ ] A Tenant Admin or Tenant User can query VM and cluster utilization metrics for their organization's resources.
- [ ] A tenant query that targets another organization's resource returns no series and no labels or metadata for that resource.
- [ ] A tenant query written against a platform-wide metric name returns only series owned by the tenant's organization, or no results.
- [ ] A user presenting a token from an identity provider not registered for any OSAC organization is rejected.
- [ ] When a tenant organization's identity provider registration is removed, queries authenticated through that provider are rejected.
- [ ] A query for data older than the hot-tier retention period returns results from the warm or cold tier for the configured retention window.
- [ ] A Cloud Infrastructure Admin can query collection success rates and storage component health through the same query interface.
- [ ] VM workload metrics are viewable per VM and grouped by the node hosting the VM.

## Assumptions

- The OSAC-6978 architecture standards document (currently tracked as a Task under OSAC-6981) will be approved before the OSAC-6980 Design phase begins. The collection schemas, telemetry conventions, and naming and label conventions depend on that document.
- OpenShift's Cluster Monitoring Operator is deployed and functional in the target environment; KubeVirt, HyperShift, and OpenShift AI metrics are being collected by it and are accessible for aggregation.
- OpenShift AI exposes model-serving metrics through the Cluster Monitoring stack or a Prometheus-compatible endpoint.
- OSAC's existing Keycloak deployment authenticates Cloud Provider Admins and Cloud Infrastructure Admins without requiring a new Keycloak instance, and each tenant organization can register an OIDC-compatible identity provider for its own users.
- The organization boundaries OSAC already maintains separate tenant-owned series from platform-wide series, so tenant isolation does not require new attribution labels.

## Dependencies

- **OSAC-6978 (Architecture Standards Document):** The telemetry conventions, resource identity schema, and shelf-product adaptation rules defined there are required inputs before the Design phase can finalize collection configuration and naming and label conventions.
- **OpenShift Cluster Monitoring Operator (CMO):** KubeVirt, HyperShift, and OpenShift AI metrics are sourced from CMO. OSAC-6980 aggregates them; it does not replace CMO's collection.
- **OSAC Keycloak and tenant identity providers:** The existing OSAC Keycloak authenticates Cloud Provider Admins and Cloud Infrastructure Admins. Each tenant organization's OIDC-compatible identity provider authenticates its Tenant Admins and Tenant Users. Tenant identity providers are registered during tenant onboarding.
- **OpenShift AI:** A platform metric source alongside KubeVirt and HyperShift, including the model-serving workloads that back OSAC MaaS. Its model-serving metrics are expected through CMO or a Prometheus-compatible endpoint. No changes to OpenShift AI are required.
- **OSAC-6488 (imported HUB clusters):** Clusters imported into OSAC through OSAC-6488 become OSAC-managed resources and are covered by the cluster-metric scope above.
- **Downstream Features (OSAC-6982, OSAC-6984, OSAC-6986, OSAC-6988, OSAC-6990, OSAC-6992):** All depend on this pipeline being operational. Their Design phases should not begin until this Feature's metrics store and query interface are available.

## Risks

### 1. Cross-tenant exposure through platform-wide series

**Owner:** To be determined
**Mitigation:** The authorized-series boundary is applied to every response, including series, label, and metadata enumeration. Acceptance tests cover a tenant querying another tenant's resource and a tenant querying a platform-wide metric name.

### 2. Isolation depends on existing organization boundaries

**Owner:** To be determined
**Mitigation:** Validate during the Design phase that tenant-owned and platform-wide series are separable without new attribution labels. If they are not, define an explicit metric classification before implementation and revisit the OSAC-6988 boundary.

### 3. Metric cardinality exceeds the storage and query budget

**Owner:** To be determined
**Mitigation:** Size active time series during the Design phase from the expected tenant, resource, and VM counts; apply retention tiering and per-tenant query limits.

### 4. The OSAC-6978 standards are not approved before Design starts

**Owner:** To be determined
**Mitigation:** Gate the Design phase on OSAC-6978 approval; if approval slips, defer the naming and label conventions rather than blocking the pipeline.

---

## Provenance

Authored: draft @ prd 0.11.5 - 7b2b8de, workspace prd/OSAC-6978 @ 6b22017
Final: revise @ prd 0.11.5 - b369da0, workspace prd/OSAC-6980 @ d4b4123 (dirty)

> Context changed between draft and revise.

<!-- ai-workflow-provenance:{"schema_version":1,"provenance_kind":"session","workflow":"prd","workflow_version":"0.11.5","ai_workflows":"b369da0","source_repo":"d4b4123 (dirty)","source_repo_branch":"prd/OSAC-6980","commits_behind_main":0,"commits_ahead_main":6,"main_ref":"main","phases":["draft","revise","revise","revise","revise","revise","revise","revise"],"authoring_modes":["skill"],"context_changed":true,"origin_untracked":false} -->
