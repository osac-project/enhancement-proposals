# Metrics Collection, Storage and Querying

| Field     | Value                                                             |
|-----------|-------------------------------------------------------------------|
| Author(s) | Amit Oren                                                         |
| Jira      | https://redhat.atlassian.net/browse/OSAC-6980                     |
| Date      | 2026-10-29                                                        |
| Service   | Platform-wide — BMaaS, CaaS, VMaaS                                |

## Problem Statement

OSAC platform components — the fulfillment service, operators, and metering — already expose metrics, and KubeVirt and HyperShift metrics are already visible in each cluster's OpenShift monitoring. That monitoring is per-cluster, retained for a short fixed period, and has no tenant-aware query boundary. As a result, Cloud Provider Admins cannot run cross-component queries over a long history, Cloud Infrastructure Admins cannot correlate hypervisor and node behavior with control-plane health across clusters, and tenants cannot query metrics for the infrastructure they provision — their VMs and clusters — without a boundary that keeps other organizations' metrics out of view. Without this pipeline, every downstream observability capability — alerting, dashboards, health monitoring, and tenant-visible infrastructure metrics — has no durable data source to build on.

## In Scope

This Feature covers metrics about the infrastructure OSAC provisions and operates: OSAC control-plane components, the nodes and hypervisors hosting tenant VMs, the storage volumes backing those VMs, and the control planes of covered clusters. Pods and containers of OSAC's own control plane on the management cluster describe the platform itself, not tenant workload, and are in scope as control-plane telemetry. Tenant workload metrics are out of scope; see Out of Scope.

- Metrics from all OSAC control-plane components — the fulfillment service, the OSAC operator and the bare-metal fulfillment operator, the metering service, and the metering adapters — are queryable from the platform-wide store.
- VM utilization metrics observable at the hypervisor and node level (CPU, memory, network, storage) are aggregated into the platform-wide store, available per VM and grouped by the node hosting each VM.
- Storage volume object metrics for the volumes that back tenant VMs — claim phase, provisioned capacity, and in-use state, as observed by the platform — are aggregated into the platform-wide store. Persistent volume claims inside a tenant cluster belong to that cluster's workloads and are out of scope.
- Node and control-plane metrics from the management cluster, from OSAC-provisioned clusters including their hosted control planes, and from clusters imported into OSAC through OSAC-6488 are aggregated into the platform-wide store.
- The infrastructure metrics these products expose — KubeVirt VM and hypervisor series and HyperShift control-plane series — are queryable through the metric names those products already emit. This feature does not change those products.
- Long-term metrics storage with a configurable retention duration, set per environment by a Cloud Infrastructure Admin. A query inside the retention window returns the stored metrics for its range; a query past the duration returns nothing. The retention window is the same for every role.
- A Prometheus-compatible HTTP (PromQL) query interface for Cloud Provider Admins, Cloud Infrastructure Admins, and tenants.
- Tenant query access: tenants sign in with the identity provider registered for their organization. A token from an identity provider that is not registered for an organization is rejected. When that registration is removed, later queries from that provider are rejected.
- Per-tenant fair use: a query that exceeds the tenant's concurrency limit or the allowed time range is rejected. The time-range limit is separate from how long metrics are kept. A Cloud Infrastructure Admin sets the concurrency limit and the allowed time range per environment. These limits apply to Tenant Admin and Tenant User; Cloud Provider Admins and Cloud Infrastructure Admins are not subject to them. The limits are in this increment because NFR-3 depends on them: no single tenant's query load can make the interface unavailable to another tenant.
- Basic metrics pipeline health — which clusters have stopped reporting, and whether a query for recent data returns data — is queryable by Cloud Infrastructure Admins and Cloud Provider Admins through the same query interface.

Query authorization by role:

| Metric class | Cloud Provider Admin | Cloud Infrastructure Admin | Tenant Admin | Tenant User |
|---|---|---|---|---|
| OSAC control-plane — fulfillment, operators, metering, adapters | any | any | none | none |
| Platform pod and container — pods and containers of OSAC's own control plane on the management cluster | any | any | none | none |
| Node, hypervisor, and per-VM utilization | any tenant | any tenant | own organization | projects they belong to |
| Volume object — claim phase, capacity, and in-use state for volumes backing tenant VMs | any tenant | any tenant | own organization | projects they belong to |
| Cluster node and control-plane | any covered cluster | any covered cluster | own organization's covered clusters | covered clusters owned by their projects |
| Tenant workload — pod, container, namespace, application, model-serving | not collected | not collected | not collected | not collected |

A covered cluster is the management cluster, a cluster OSAC provisions, or a cluster imported through OSAC-6488.
Hosted control plane metrics of a provisioned cluster are Cluster node and control-plane metrics, not Platform pod and container.
Imported clusters and the management cluster have no organization and no project, so neither tenant role sees them; Cloud Provider Admins and Cloud Infrastructure Admins see every covered cluster.
An unset project means the tenant's default project, which is visible to every user in the tenant; project membership only adds named projects.
A metric class collected for platform operations is visible to a tenant only where the table grants it.

## Out of Scope

- Alerting rules and dashboards — OSAC-6984.
- Log collection and aggregation — OSAC-6982.
- BMC/IPMI hardware health metrics (node temperature, power draw, fan speed, physical host availability) — OSAC-6986. A bare-metal-only tenant has no metrics to query in this feature; admins query the bare-metal fulfillment operator's metrics on the control-plane row.
- GPU metrics — utilization, temperature, power draw, and error counts, including NVIDIA DCGM Exporter collection. Deferred to a later Feature, OSAC-7246 (GPU Metrics Collection and Querying).
- OpenShift AI platform and operator metrics, and the model-serving workloads that back OSAC MaaS. Deferred to a later Feature; this pipeline collects neither.
- Explicit tenant attribution for chargeback and cross-tenant dashboards stays OSAC-6988 (Resource and Tenant Correlation and RBAC).
- Metrics that require a guest agent inside a VM, such as guest OS memory usage, filesystem free space, and in-guest network throughput.
- Tenant workload metrics inside a VM, a namespace, or a cluster, including model-serving, are not collected. Tenants use that cluster's OpenShift monitoring for those metrics.
- Metrics from clusters that OSAC neither provisions nor imports, including ACM-registered clusters that have not been imported through OSAC-6488.
- Deep observability-of-observability (collector throughput, pipeline latency, alert delivery health) — OSAC-6990. Which clusters have stopped reporting is this feature, not OSAC-6990.
- Audit logging — OSAC-63.

## User Stories

### Cloud Provider Admin

- As a Cloud Provider Admin, I want to query control-plane metrics across all OSAC components and all tenants — API request rates, database latency, operator health, and billing pipeline state — through that API so that I can identify platform-wide hotspots and support capacity planning.
- As a Cloud Provider Admin, I want to query a specific tenant's VMs and clusters through that API so that I can investigate an incident or answer a tenant's support request.
- As a Cloud Provider Admin, I want to query metrics from earlier in the retention window through that API so that I can run historical queries for SLA reporting and trend analysis.

### Cloud Infrastructure Admin

- As a Cloud Infrastructure Admin, I want to query node, hypervisor, and cluster control-plane metrics for the management cluster and every covered cluster through that API, so that I can find capacity saturation and unhealthy control planes across the fleet and schedule maintenance before tenants are affected.
- As a Cloud Infrastructure Admin, I want per-VM hypervisor metrics grouped by the node hosting each VM, so that I can tell when one tenant's VM is degrading its neighbors and decide whether the fix is resizing, migration, or more capacity. I need the infrastructure view of a tenant's VM, not the tenant's business context.
- As a Cloud Infrastructure Admin, I want to see which clusters have stopped reporting and whether a query for recent data returns data, so that I can tell an infrastructure fault from a collection fault before a tenant reports it.

### Tenant Admin

- As a Tenant Admin, I want to query the CPU, memory, network, and storage utilization of every VM in my organization, the capacity and in-use state of the volumes backing those VMs, and the availability and health of every cluster my organization owns, through that API so that I can tell whether the organization's provisioned resources are undersized or degraded — without the provider collecting anything about the workloads running inside them.
- As a Tenant Admin, I want tenant isolation enforced so that my query credentials return only my organization's metrics, regardless of how the query is constructed, including queries written against platform-wide metric names.

### Tenant User

- As a Tenant User, I want to query the CPU, memory, network, and storage utilization of the VMs in the projects I belong to, the capacity and in-use state of the volumes backing those VMs, and the availability and health of the clusters those projects own, so that I can diagnose the resources I am responsible for without seeing resources in projects I do not belong to.
- As a Tenant User, I want isolation enforced so that my query credentials return only what my project memberships authorize, regardless of how the query is constructed, including queries written against platform-wide metric names.

## Non-Functional Requirements

- **NFR-1 (Authorization is not an existence oracle):** A response for a series the caller may not see is indistinguishable, in status and content, from a response for a series that does not exist. This holds for data queries and for metric-name, label, and series listings.
- **NFR-2 (Failure contract):** An unauthenticated caller, or one presenting a token from an identity provider not registered for any organization, receives an authentication error. An authenticated caller asking for data it may not see receives a successful, empty result. An owner that cannot be resolved produces the same successful, empty result.
- **NFR-3 (Availability is per cluster):** The query interface stays available when an individual covered cluster stops reporting; only that cluster's data is missing. No single tenant's query load can make the interface unavailable to another tenant.
- **NFR-4 (Freshness):** Metrics emitted by a running resource become queryable within one collection interval of that resource's metric class. A Cloud Infrastructure Admin sets the collection interval for each metric class.
- **NFR-5 (Compatibility):** The query interface implements the Prometheus HTTP API instant query, range query, label-name listing, label-value listing, and series listing endpoints, so a standard Prometheus client calls them unmodified. An endpoint outside that set returns an explicit not-supported error, never partial data.
- **NFR-6 (Capacity):** Capacity is sized to the covered fleet. Reaching capacity is reported through the pipeline-health signals in In Scope; series are never silently dropped or downsampled to stay within capacity.

## Acceptance Criteria

- [ ] After deployment, a Cloud Provider Admin can query at least one series from each of the fulfillment service, the OSAC operator, the bare-metal fulfillment operator, the metering service, and the metering adapters.
- [ ] A Cloud Provider Admin can query the VM, volume, and cluster metrics of one named tenant and receives that tenant's series only.
- [ ] A Cloud Infrastructure Admin can query node, hypervisor, and control-plane metrics for the management cluster and for every covered cluster, including clusters imported through OSAC-6488.
- [ ] A Tenant Admin can query VM utilization for every VM in the organization, the volume state of the volumes backing those VMs, and cluster node and control-plane metrics for every covered cluster the organization owns.
- [ ] A Tenant Admin query returns nothing for the management cluster's node metrics and for any cluster imported through OSAC-6488.
- [ ] A Tenant User can query VM utilization for the VMs in the projects they belong to, the volume state of the volumes backing those VMs, and cluster node and control-plane metrics for the covered clusters those projects own.
- [ ] A Tenant User query returns nothing for a resource in a project they do not belong to, and nothing for a cluster owned by another project.
- [ ] Hosted control plane metrics of an OSAC-provisioned cluster are returned to the Tenant Admin of the owning organization and to a Tenant User whose project owns the cluster; they are not returned only for the two admin roles.
- [ ] A query for another organization's series returns an empty successful response, including when the caller lists metric names, lists label values, or requests a series listing.
- [ ] A query denied for authorization and a query for a resource that does not exist return the same status and the same empty body.
- [ ] When the organization, project, or cluster owner of a series cannot be resolved, the query returns the same empty successful response as an unauthorized query.
- [ ] A token from an identity provider not registered for any organization is rejected with an authentication error, and a token from that provider is rejected after its registration is removed.
- [ ] A Tenant Admin or Tenant User query that exceeds the concurrency limit or the allowed time range is rejected with a distinct error, while the same query from a Cloud Provider Admin or Cloud Infrastructure Admin succeeds.
- [ ] A query wholly inside the retention window returns data; a query wholly past the configured retention duration returns an empty successful response.
- [ ] A query over the same project and time range returns the same data to the Tenant Admin of the organization and to a Tenant User in that project.
- [ ] A query for a tenant workload series, such as a pod CPU metric inside a tenant cluster, returns nothing for every role.
- [ ] With a covered cluster's collector stopped for longer than one collection interval, a Cloud Infrastructure Admin sees that cluster reported as stopped and a recent-data query for it returns no data; a healthy cluster reports the opposite for both.
- [ ] A standard Prometheus client executes an instant query, a range query, a label listing, and a series listing against the interface without modification.
- [ ] A request to an endpoint outside the supported Prometheus API subset returns an explicit not-supported error, not partial data.

## Assumptions

- OpenShift monitoring in the target environment already shows KubeVirt and HyperShift metrics.
- OSAC's existing Keycloak authenticates Cloud Provider Admins. Cloud Infrastructure Admins authenticate through OpenShift OAuth, consistent with OSAC-1030. Each tenant organization can register an identity provider for its own users.
- OSAC assigns tenant resources to projects in its metadata, and Tenant User access follows project membership.

## Dependencies

- **OpenShift monitoring:** KubeVirt and HyperShift metrics are already visible in each covered cluster's OpenShift monitoring. This feature queries them and does not replace that monitoring.
- **OSAC Keycloak, OpenShift OAuth, and tenant identity providers:** These existing logins are what the personas use. The existing OSAC Keycloak authenticates Cloud Provider Admins. Cloud Infrastructure Admins authenticate through OpenShift OAuth, consistent with OSAC-1030. Each tenant organization's identity provider authenticates its Tenant Admins and Tenant Users, and is registered during tenant onboarding.
- **OSAC-6488 (imported clusters):** Clusters imported through OSAC-6488 are covered clusters for Cloud Provider Admins and Cloud Infrastructure Admins. They have no organization and no project, so no tenant sees them. Workload metrics inside them stay out of scope.
- **OSAC organizations, projects, and project memberships:** The organization claim identifies the tenant, and project membership scopes what each Tenant User may see. This feature reads these records and does not modify them.
- **Downstream Features (OSAC-6982, OSAC-6984, OSAC-6986, OSAC-6988, OSAC-6990, OSAC-6992):** All depend on this pipeline being operational.

---

## Provenance

Authored: draft @ prd 0.11.5 - 7b2b8de, workspace prd/OSAC-6978 @ 6b22017
Final: revise @ prd 0.11.5 - 87d14ea, workspace main @ af6b5a4ea (dirty)

> Context changed between draft and revise.

<!-- ai-workflow-provenance:{"schema_version":1,"provenance_kind":"session","workflow":"prd","workflow_version":"0.11.5","ai_workflows":"87d14ea","source_repo":"af6b5a4ea (dirty)","source_repo_branch":"main","commits_behind_main":0,"commits_ahead_main":1,"main_ref":"main","phases":["draft","revise","revise","revise","revise","revise","revise","revise","revise","revise","revise","revise","revise","revise","revise","revise"],"authoring_modes":["skill"],"context_changed":true,"origin_untracked":false} -->
