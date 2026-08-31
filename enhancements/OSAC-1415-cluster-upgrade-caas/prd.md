# Cluster Upgrade — CaaS

| Field      | Value                                                                      |
|------------|----------------------------------------------------------------------------|
| Author(s)  | Vitaliy Emporopulo                                                         |
| Jira       | [OSAC-1415](https://redhat.atlassian.net/browse/OSAC-1415)                 |
| Date       | 2026-07-27                                                                 |

## Problem Statement

OSAC CaaS manages the full cluster lifecycle — creation, scaling, and deletion — but provides no managed path for upgrading a cluster's OpenShift version. Clusters are provisioned via Hosted Control Planes (HCP), where the control plane and node pools are each an independent upgrade targets with distinct ownership and ordering constraints; today neither has first-class support in the OSAC API. Tenants who need a newer version have no way to upgrade their cluster at all — they cannot access the underlying HCP infrastructure directly, and OSAC exposes no upgrade capability in its place. As clusters age, the gap widens: end-of-life (EOL) versions lose Red Hat support coverage and security patches, but OSAC has no mechanism to surface upgrade readiness or track version transitions, leaving tenants without the information or tools needed to keep their clusters on supported versions.

## In Scope

- Upgrading CaaS-provisioned, HCP OpenShift clusters
- Upgrade version discovery and restrictions
- Upgrade initiation, monitoring
- Cancellation of pending upgrades
- Tenant-initiated control plane upgrades, as HCP supports upgrading the control plane independently of the node pools
- Tenant-initiated node pool upgrades, as HCP supports upgrading a node pool independently of the control plane or other node pools
- Console (UI) support for version selection, risk review, status monitoring, and cancellation (Tenant User, Tenant Admin)
- User documentation for upgrade initiation and monitoring

## Out of Scope

- SNO and traditional (non-HCP) cluster upgrades
- Upgrade rollback or version downgrade
- Platform-initiated control plane upgrades — deferred to a future version
- Platform-initiated node pool upgrades
- Cancellation of running upgrades, as OpenShift does not support it
- Switching upgrade channels — a cluster remains on the channel it was created with
- Multi-hop upgrades — an upgrade that requires multiple hops can be done as a sequence of one-hop upgrades

## User Stories

### Tenant User

- As a Tenant User, I want to initiate a version upgrade for any node pool in my cluster, so that my cluster remains operational and supported.
- As a Tenant User, I want to initiate a control plane version upgrade, so that my cluster remains operational and supported.
- As a Tenant User, I want to select an upgrade version for a cluster component that is directly reachable (one hop) and allowed by the platform, so that I can initiate a valid upgrade.
- As a Tenant User, I want all my upgrades to be restricted only to versions allowed by the platform as per OSAC-1269 (i.e., not blocked), so that the platform runs only approved and supported versions.
- As a Tenant User, I want to review any risks associated with a target upgrade version before initiating an upgrade, so that I can make an informed upgrade decision.
- As a Tenant User, I want to acknowledge the risks associated with an upgrade version and proceed, or decline and keep the current version, so that the cluster remains operational and supported.
- As a Tenant User, I want a brief cancellation window during which the upgrade remains pending after I initiate it, so that I can cancel the upgrade, correct a mistake, and re-initiate if needed.
- As a Tenant User, I want to monitor the status of an upgrade — its current state (pending, running, succeeded, or failed), the source and target versions, and when each state transition happened, so that I can take an appropriate action in a timely manner.
- As a Tenant User, I want each node pool's version capped at the control plane version of the same cluster, so that the cluster remains operational and supported. This is an HCP requirement.
- As a Tenant User, I want to be able to upgrade my cluster's control plane and node pools in parallel, which is supported by HCP, so that I can minimize the total upgrade duration.
- As a Tenant User, I want only one upgrade at a time to be active for a given cluster component (control plane or individual node pool), so that I can avoid conflicts and race conditions.
- As a Tenant User, if a control plane upgrade is in progress, I want the node pool version cap to remain at the control plane's target version to meet the HCP requirements, so that the cluster remains operational and supported.
- As a Tenant User, I want to be informed when a node pool is approaching the maximum supported version skew of N-3 relative to the control plane (according to the HCP restrictions), so that I can initiate a node pool upgrade before it falls out of the supported range.
- As a Tenant User, I want to view the upgrade history for my cluster (control plane and node pools), so that I can see which version transitions have occurred and their outcomes.
- As a Tenant User, I want to be informed whenever any of my cluster's node pools diverge from the control plane version — even within the supported skew range — so that I can decide when to initiate a node pool upgrade and keep versions aligned.
- As a Tenant User, I want to see when a cluster has entered limited support state due to EOL, so that I understand the impact on the cluster's support status.

### Tenant Admin

- As a Tenant Admin, I want to act as the Tenant User on any cluster within my organization, so that I can manage the version lifecycle on behalf of my organization.
- As a Tenant Admin, I want to see which clusters across my organization have node pools that diverge from the control plane version, so that I can coordinate upgrades across my fleet without checking each cluster individually.

### Cloud Provider Admin

No active role in this feature; all platform-level upgrade operations are out of scope in this version.

### Cloud Infrastructure Admin

No active role in this feature; all platform-level upgrade operations are out of scope in this version.

## Assumptions

This PRD assumes the following OpenShift and HCP capabilities, verified against the
[OCP 4.22 Hosted Control Planes documentation](https://docs.redhat.com/en/documentation/openshift_container_platform/4.22/html/hosted_control_planes/hcp-updating):

1. **Independent control plane and node pool upgrades.** HCP decouples the control plane from node pools, allowing each to be upgraded separately.
2. **Concurrent control plane and node pool upgrades.** HCP does not prevent a node pool upgrade from running while a control plane upgrade is in progress, provided the version skew policy is satisfied.
3. **Node pool version ceiling.** HCP enforces that a node pool version (including patch level) must not exceed the control plane version.
4. **Version skew between control plane and node pools.** The maximum supported skew for all currently offered OCP version is up to N-3 minor versions behind the hosted cluster version.
5. **Upgrade version discovery via upgrade graph.** A cluster connected to the OpenShift upgrade graph can discover the set of directly reachable (one-hop) target versions.
6. **Conditional updates with risk metadata.** The OpenShift upgrade graph provides risk descriptions and matching rules for conditional updates. HCP surfaces this information but does not gate upgrades on it.
7. **Irreversible control-plane upgrades.** OpenShift does not support control-plane or whole-cluster version rollback or downgrade once an upgrade has started; a failed upgrade requires Red Hat support intervention. HCP does support rolling a node pool back to a control-plane-compatible version.
8. **No native cancellation of running upgrades.** Once an upgrade begins execution, it cannot be stopped.
9. **OSAC node sets map 1:1 to HCP NodePools.** Each OSAC node set corresponds to a separate HCP node pool. A "node pool upgrade" in OSAC terms means upgrading the selected node pool associated with the cluster.

## Dependencies

- **OSAC-1269 (ClusterVersion API):** A version is available for upgrade only if an allowed (not blocked) ClusterVersion exists for it

<!-- ai-workflow-provenance:{"schema_version":1,"provenance_kind":"declined"} -->
