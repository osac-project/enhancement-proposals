# Granular Cluster Status Reporting

| Field       | Value   |
|-------------|---------|
| Author(s)   | Elad Tabak |
| Jira        | [OSAC-1604](https://issues.redhat.com/browse/OSAC-1604) |
| Date        | 2026-08-11 |

## Problem Statement

Tenants and cloud provider admins have limited visibility into cluster provisioning progress. When a cluster is being created, the only status they see is "PROGRESSING" - with no indication of whether the system is creating infrastructure, waiting for the control plane, or provisioning worker nodes. Cluster provisioning takes significantly longer than VM provisioning, making this opacity more painful. Users cannot distinguish between a cluster that is progressing normally and one that is stuck.

The fulfillment API currently has four condition types (PROGRESSING, READY, FAILED, DEGRADED) that mirror the lifecycle phase rather than providing independent health signals. The underlying Kubernetes layer already tracks more granular conditions (namespace creation, control plane availability, cluster availability), but this information is collapsed before reaching the API. The ComputeInstance (VMaaS) equivalent was addressed by OSAC-1027, which established the pattern of orthogonal conditions with granular provisioning reasons. CaaS clusters need the same treatment, adapted for cluster-specific lifecycle stages.

## In Scope

- Granular provisioning progress visible through the API, CLI, and UI - tenants can see where in the provisioning pipeline their cluster is (e.g., infrastructure being prepared, control plane starting, worker nodes joining) [Clarify: D1, D3]
- Conditions that are orthogonal to the lifecycle phase - conditions represent independent health signals (e.g., control plane readiness, worker node readiness) rather than duplicating the phase [Clarify: D1]
- Scaling progress visibility - when a tenant scales a node set, they can see the scaling operation's progress separately from the overall cluster state
- Deletion progress visibility - tenants can see that deletion is proceeding and track its progress
- CLI `describe` output that shows conditions, provisioning progress, API URL, console URL, and node set status
- UI status display for cluster provisioning and lifecycle, covering both tenant and provider admin views [Clarify: D3]
- Kubernetes events emitted at key provisioning transitions for observability
- CaaS clusters only [Clarify: D2]

## Out of Scope

- Power state phases (start, stop, pause, resume) - clusters are always running once provisioned, unlike VMs [Clarify: D1]
- VMaaS or BMaaS status reporting - VMaaS is already addressed by OSAC-1027; BMaaS is separate
- Cluster upgrade status tracking - upgrade workflows are future work (OSAC-1415)
- AAP job-level progress detail - AAP job status is already available in the jobs array; this feature focuses on Kubernetes-native status derived from observed resource state [Clarify: D4]
- Auto-scaling or capacity-based status signals

## User Stories

### Tenant User

- As a tenant user, I want to see where my cluster is in the provisioning pipeline so that I know whether it is progressing normally or stuck.
- As a tenant user, I want to see when my cluster's control plane is available separately from when worker nodes are ready so that I understand what is happening during provisioning.
- As a tenant user, I want to see provisioning progress when I scale a node set so that I know the scaling operation is proceeding.
- As a tenant user, I want to see deletion progress when I delete a cluster so that I can track whether resource cleanup is completing.
- As a tenant user, I want to run `osac describe cluster <id>` and see conditions, provisioning status, API URL, console URL, and node set status so that I have a complete picture of my cluster without needing the raw YAML output.
- As a tenant user, I want to see the same granular status in the web console so that I do not need the CLI for basic status checks.

### Cloud Provider Admin

- As a cloud provider admin, I want to see granular provisioning status across tenant clusters so that I can identify which clusters are stuck and at which stage.
- As a cloud provider admin, I want conditions that distinguish between control plane issues and worker node issues so that I can triage problems efficiently.
- As a cloud provider admin, I want to see when a cluster is degraded (e.g., some workers failed to join but the control plane is functional) with enough detail to understand the scope of the degradation.
- As a cloud provider admin, I want Kubernetes events emitted at key provisioning transitions so that I can build monitoring dashboards and set alerts on provisioning failures.

## Dependencies

- **OSAC-1027 (ComputeInstance Phase & Condition Expansion):** Establishes the pattern for orthogonal conditions and granular provisioning progress. This feature follows the same pattern adapted for CaaS. OSAC-1027 is already implemented.
- **HyperShift HostedCluster/NodePool API:** The upstream HyperShift API exposes 43 HostedCluster condition types and 26 NodePool condition types, including InfrastructureReady, KubeAPIServerAvailable, EtcdAvailable, and node-level health signals (Ready, AllMachinesReady, AllNodesHealthy). NodePool also reports desired vs observed replica counts with per-version ready/unready breakdowns. No upstream changes are required.
