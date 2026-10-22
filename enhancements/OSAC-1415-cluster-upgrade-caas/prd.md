# Cluster Upgrade — CaaS

| Field      | Value                                                                      |
|------------|----------------------------------------------------------------------------|
| Author(s)  | Vitaliy Emporopulo                                                         |
| Jira       | [OSAC-1415](https://redhat.atlassian.net/browse/OSAC-1415)                 |
| Date       | 2026-10-22                                                                 |

## Problem Statement

OSAC CaaS manages the full cluster lifecycle — creation, scaling, and deletion — but provides no managed path for upgrading a cluster's OpenShift version. Clusters are provisioned via Hosted Control Planes (HCP), where the control plane and node pools are each an independent upgrade targets with distinct ownership and ordering constraints; today neither has first-class support in the OSAC API. Tenants who need a newer version have no way to upgrade their cluster at all — they cannot access the underlying HCP infrastructure directly, and OSAC exposes no upgrade capability in its place. As clusters age, the gap widens: end-of-life (EOL) versions lose Red Hat support coverage and security patches, but OSAC has no mechanism to surface upgrade readiness or track version transitions, leaving tenants without the information or tools needed to keep their clusters on supported versions.

## In Scope

- Tenant-initiated upgrades of CaaS-provisioned HCP OpenShift clusters
- Control-plane and node-pool upgrades, with only one active upgrade per cluster
- Version eligibility and control-plane/node-pool version-skew enforcement
- Upgrade initiation, progress monitoring, and history
- API, CLI, and console (UI) support for initiating upgrades and viewing status/history (Tenant User, Tenant Admin)
- User documentation for upgrade initiation and monitoring

## Out of Scope

- SNO and traditional (non-HCP) cluster upgrades
- Upgrade rollback or version downgrade
- Platform-initiated control plane upgrades — deferred to a future version
- Platform-initiated node pool upgrades
- Upgrade-channel management, upgrade-path discovery, and conditional-update risk review/acknowledgment
- A cancellation window for pending upgrades
- Version-divergence or end-of-life notifications
- Fleet-level upgrade views and management
- Cancellation of running upgrades, as OpenShift does not support it
- Version upgrades in disconnected environments

## User Stories

### Tenant User

- As a Tenant User, I want to initiate a version upgrade for my cluster, so that my cluster remains operational and supported.
- As a Tenant User, I want to select an upgrade version allowed by the platform, so that I can initiate a valid upgrade.
- As a Tenant User, I want all my upgrades to be restricted only to versions allowed by the platform as per OSAC-1269 (i.e., not blocked), so that the platform runs only approved and supported versions.
- As a Tenant User, I want to monitor an upgrade's state, source and target versions, and state-transition times, so that I can take an appropriate action in a timely manner.
- As a Tenant User, I want my node pools upgraded after the control plane to conform to HyperShift requirements, so that my cluster remains operational and supported.
- As a Tenant User, I want each node pool's version capped at the control plane version of the same cluster, so that the cluster remains operational and supported. This is an HCP requirement.
- As a Tenant User, I want control-plane and node-pool targets checked against HCP version-skew limits, so that I cannot request an unsupported version combination.
- As a Tenant User, I want only one upgrade to be active for my cluster at a time, so that upgrade requests do not conflict.
- As a Tenant User, I want to view the upgrade history for my cluster (control plane and node pools), so that I can see which version transitions have occurred and their outcomes.

### Tenant Admin

- As a Tenant Admin, I want to act as the Tenant User on any cluster within my organization, so that I can manage the version lifecycle on behalf of my organization.

### Cloud Provider Admin

No active role in this feature; all platform-level upgrade operations are out of scope in this version.

### Cloud Infrastructure Admin

No active role in this feature; all platform-level upgrade operations are out of scope in this version.

## Assumptions

This PRD assumes the following OpenShift and HCP capabilities, verified against the
[OCP 4.22 Hosted Control Planes documentation](https://docs.redhat.com/en/documentation/openshift_container_platform/4.22/html/hosted_control_planes/hcp-updating):

1. **Independent control plane and node pool upgrades.** HCP decouples the control plane from node pools, allowing each to be upgraded separately.
2. **Node pool version ceiling.** HCP does not support a node-pool version above the control-plane version, including a newer patch version.
3. **Version skew between control plane and node pools.** HCP supports node-pool versions up to three minor versions behind the hosted cluster version.
4. **Upgrade version discovery via upgrade graph.** For a cluster not connected to the OpenShift upgrade graph, it is the user responsibility to discover valid, directly reachable (one-hop) target versions.
5. **Conditional updates with risk metadata.** For a cluster not connected to the OpenShift upgrade graph, it is the user responsibility to discover and review the risks associated with an update.
4. **Irreversible control-plane upgrades.** OpenShift does not support control-plane or whole-cluster version rollback or downgrade once an upgrade has started; a failed upgrade requires Red Hat support intervention. HCP does support rolling a node pool back to a control-plane-compatible version.
5. **No native cancellation of running upgrades.** Once an upgrade begins execution, it cannot be stopped.
6. **OSAC node sets map 1:1 to HCP NodePools.** Each OSAC node set corresponds to a separate HCP node pool. A "node pool upgrade" in OSAC terms means upgrading the selected node pool associated with the cluster.

## Dependencies

- **OSAC-1269 (ClusterVersion API):** A version is available for upgrade only if an allowed (not blocked) ClusterVersion exists for it

<!-- ai-workflow-provenance:{"schema_version":1,"provenance_kind":"declined"} -->
