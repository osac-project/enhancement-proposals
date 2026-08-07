# CaaS Bare-Metal Worker Node Provisioning

| Field       | Value |
|-------------|-------|
| Author(s)   | CaaS and BMaaS Product Teams |
| Jira        | OSAC-2135 |
| Date        | 2026-08-02 |
| test        | true |

## Problem Statement

Cluster as a Service (CaaS) requires bare-metal compute hosts to back OpenShift cluster worker nodes. Currently, this process relies on a background cron job that maintains a static pool of agents (pre-booted hosts running the Assisted Installer ISO).

This approach introduces severe operational and resource inefficiencies:
- **Idle Resource Waste:** Physical hosts remain booted and idle in the static pool, consuming power and hardware resources without active workloads.
- **Sizing Inaccuracies:** The static pool size is difficult to predict and scale, leading to either resource exhaustion or excessive waste.
- **Architectural Coupling:** Cluster-specific concepts (such as agents and InfraEnvs) are tightly coupled into the Bare-Metal-as-a-Service (BMaaS) layer, violating the principle of separation of concerns.

If this is not addressed, OSAC will suffer from high operational costs due to underutilized hardware, slow or failing cluster scale-up requests, and maintainability issues stemming from coupled service domains.

## In Scope

- **On-Demand Provisioning:** Direct, automated creation of `BareMetalInstances` for cluster worker nodes.
- **Standardized Boot Payload:** Booting of worker nodes using a standard `ComputeImage` combined with cluster-specific discovery configurations.
- **MAC Address Correlation:** CaaS automatically correlates provisioned hosts to cluster agents. It retrieves host physical network interface identifiers from BMaaS and matches them against discovered agent identifiers. CaaS handles missing, duplicate, or changed MAC addresses reliably to prevent misassociation, flagging errors or pausing provisioning if hardware details cannot be resolved.
- **Tenant Isolation & Security:** Complete exclusion of CaaS-managed `BareMetalInstances` and underlying `ComputeImages` from tenant-facing APIs and UI consoles.
- **Automatic Lifecycle Cleanup:** Provisioned hosts are automatically and securely cleaned up on decommissioning or manual node pool scale-down. Deletion of cluster resources triggers mandatory, automated, blocking host cleanup before the underlying physical hardware is returned to the general active inventory pool.
- **Race Prevention:** Isolated registration environments are maintained per cluster to guarantee that agents from different tenants or clusters register to their correct control planes, completely preventing cross-tenant registration races.
- **Resource Definition:** Integration of `ClusterOrder` specifications with BMaaS resource definitions. Each requested resource class in the `ClusterOrder` maps deterministically to the corresponding bare-metal instance type. Any unsupported or unavailable resource class values must be explicitly rejected rather than mapped to another hardware class.

## Out of Scope

- **Day-2 Autoscaling:** Automated dynamic, workload-driven scaling based on real-time resource utilization, CPU/memory pressure, or pod scheduling states. This remains out of scope for the current phase, as scaling down requires complex orchestration around cluster node draining and agent unbinding. Therefore, `BareMetalInstance` deletion and cleanup are restricted solely to explicit, manual administrator-initiated decommission or scale-down operations.
- **Virtual Machine Worker Nodes:** Provisioning VM-based worker nodes using this on-demand pattern (deferred to future VMaaS integrations).
- **Admin Tuning APIs:** Dedicated administrator-facing APIs for tweaking CaaS provisioning heuristics or retry thresholds.
- **Boot Optimization:** Network boot acceleration or advanced bare-metal caching strategies `[Jira: OSAC-2134]`.
- **Custom Networking Configuration:** Direct management of tenant-specific VLANs or advanced network routing by CaaS (CaaS will consume default BMaaS-provided network interfaces).

## User Stories

### Tenant Admin

- As a Tenant Admin, I want to create a `ClusterOrder` specifying supported `BareMetalInstanceTypes` by selecting a resource class for my worker nodes, so that my Kubernetes/OpenShift clusters are backed by high-performance physical hardware without me having to manage raw infrastructure directly.
- As a Tenant Admin, I want my resource usage, quotas, and billing to be tracked at the cluster level rather than at the individual bare-metal instance level, so that I can easily budget and monitor my organization's cloud spend.

### Tenant User

- As a Tenant User, I want my cluster creation and self-service management experience to remain entirely unchanged, so that I am never exposed to underlying `BareMetalInstances`, images, installers, or physical MAC addresses.

### Cloud Provider Admin

- As a Cloud Provider Admin, I want all CaaS-provisioned `BareMetalInstances` and standard `ComputeImages` to be hidden from tenant-facing views and catalogs, so that tenants cannot accidentally modify or delete underlying infrastructure nodes.
- As a Cloud Provider Admin, I want deprovisioned bare-metal hosts to be securely cleaned up before being returned to the general inventory pool, so that tenant boundaries are preserved and data leaks are prevented.

### Cloud Infrastructure Admin

- Not affected by this feature.

## Assumptions

- **Ignition Support:** BMaaS can ingest and reliably pass through standard discovery ignition payloads as user data to the target physical host.
- **Agent Initialization:** The standard qcow2 `ComputeImage` provided is pre-configured to boot, process the ignition payload, and start the Assisted Installer agent without manual intervention.

## Dependencies

- **MAC Address Status Exposure:** BMaaS must expose the physical MAC addresses of the host's network interfaces within the `BareMetalInstance` status information to support CaaS host-to-agent correlation `[Jira: OSAC-2308]`.
- **BareMetalInstanceType Definition:** The `BareMetalInstanceType` specifications and schema definitions must be finalized and available `[Jira: OSAC-2675]`.
- **User Data Pass-through:** BMaaS must support the ingestion and pass-through of ignition configurations within bare-metal instance specifications.

---

## Provenance

Authored: draft @ prd 0.5.0 - 92734a2, workspace main @ aac0f8e
Final: revise @ prd 0.5.0 - 92734a2, workspace main @ aac0f8e

> Context changed between draft and revise.

<!-- ai-workflow-provenance:{"schema_version":1,"provenance_kind":"session","workflow":"prd","workflow_version":"0.5.0","ai_workflows":"92734a2","source_repo":"aac0f8e","source_repo_branch":"main","commits_behind_main":0,"commits_ahead_main":0,"main_ref":"main","phases":["draft","revise"],"authoring_modes":["skill"],"context_changed":true} -->