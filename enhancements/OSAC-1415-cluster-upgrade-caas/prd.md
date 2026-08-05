# Cluster Upgrade — CaaS

| Field      | Value                                                                      |
|------------|----------------------------------------------------------------------------|
| Author(s)  | Vitaliy Emporopulo                                                         |
| Jira       | [OSAC-1415](https://redhat.atlassian.net/browse/OSAC-1415)                 |
| Date       | 2026-07-27                                                                 |

## Problem Statement

OSAC CaaS manages the full cluster lifecycle — creation, scaling, and deletion — but provides no managed path for upgrading a cluster's OpenShift version. Clusters are provisioned via Hosted Control Planes (HCP), where the control plane and node pools are independent upgrade targets with distinct ownership and ordering constraints; today neither has first-class support in the OSAC API. Tenants who need a newer version must interact directly with HCP infrastructure, bypassing OSAC entirely. As clusters age, the gap widens: end-of-life (EOL) versions lose Red Hat support coverage and security patches, but OSAC has no mechanism to surface upgrade readiness, track version transitions, or apply platform-wide patches.

## In Scope

- Upgrading CaaS-provisioned, HCP OpenShift clusters
- Upgrade version discovery and restrictions
- Upgrade initiation, monitoring
- Cancellation of pending upgrades
- Tenant-initiated y-stream (minor version, e.g., 4.15 → 4.16) control plane upgrades
- Platform-forced end-of-life (EOL) y-stream control plane upgrades
- Platform-initiated z-stream (patch version, e.g., 4.15.10 → 4.15.11) control plane upgrades
- Tenant-initiated node pool upgrades

## Out of Scope

- SNO and traditional (non-HCP) cluster upgrades
- Upgrade rollback or version downgrade
- Tenant-initiated z-stream control plane upgrades
- Platform-initiated node pool upgrades
- Cancellation of running upgrades

## User Stories

### Tenant User / Tenant Admin / Cloud Provider Admin

- As a Tenant User, Tenant Admin, or Cloud Provider Admin, I want to select an upgrade version for a cluster component that is directly reachable (one hop) and allowed by the platform, so that I can initiate a valid upgrade.
- As a Tenant User, Tenant Admin, or Cloud Provider Admin, I want to review any risks associated with a target upgrade version before initiating an upgrade, so that I can make an informed upgrade decision.
- As a Tenant User, Tenant Admin, or Cloud Provider Admin, I want to acknowledge the risks associated with an upgrade version and proceed, or decline and keep the current version, so that the cluster remains operational and supported.
- As a Tenant User, Tenant Admin, or Cloud Provider Admin, I want to monitor the status of an upgrade — its current state (pending, running, succeeded, or failed), the source and target versions, and when each state transition happened, so that I can take an appropriate action in a timely manner.
- As a Tenant User, Tenant Admin, or Cloud Provider Admin, I want a brief cancellation window after initiating an upgrade, so that I can cancel the upgrade, correct a mistake, and re-initiate if needed.
- As a Tenant User, Tenant Admin, or Cloud Provider Admin, I want to see when a cluster has entered limited support state due to a failed forced EOL upgrade, so that I understand the impact on the cluster's support status.

### Tenant User

- As a Tenant User, I want to initiate a node pool version upgrade, so that my cluster remains operational and supported.
- As a Tenant User, I want to initiate a control plane y-stream upgrade, so that my cluster remains operational and supported.
- As a Tenant User, I want the same target version applied uniformly across all node sets within a node pool when I upgrade it, so that all node sets in that pool remain aligned.
- As a Tenant User, I want a node pool upgrade marked as failed if any node set fails to upgrade, so that I can investigate and remediate the problem.
- As a Tenant User, I want to see failure details per node set when a node pool upgrade fails, so that I can identify and address the problem.
- As a Tenant User, I want the node pool version capped at the control plane version of the same cluster, so that the cluster remains operational and supported.
- As a Tenant User, if a control plane upgrade is in progress, I want the node pool version cap to remain at the control plane's current version until the upgrade succeeds, so that the node pool version always remains correctly capped, even if the control plane upgrade fails.
- As a Tenant User, I want to be informed when a node pool is approaching the N-2 y-stream (minor) version skew limit relative to the control plane, so that I can initiate a node pool upgrade before it falls out of the supported range.
- As a Tenant User, I want to view the upgrade history for my cluster (control plane and node pool), so that I can see which version transitions have occurred and their outcomes.
- As a Tenant User, I want to know when the platform applies a control plane upgrade to my cluster, so that I am aware of platform-managed changes to my cluster's version.
- As a Tenant User, I want to be informed whenever my cluster's control plane and node pool versions diverge — even within the supported skew range — so that I can decide when to initiate a node pool upgrade and keep versions aligned.
- As a Tenant User, I want my cluster's control plane and node pool to be upgraded concurrently, so that I can minimize the total upgrade duration.
- As a Tenant User, I want only one upgrade at a time to be active for a given cluster component (control plane or node pool), so that I can avoid conflicts and race conditions.

### Tenant Admin

- As a Tenant Admin, I want to act as the Tenant User on any cluster within my organization, so that I can manage the version lifecycle on behalf of my organization.
- As a Tenant Admin, I want to see which clusters across my organization have diverged control plane and node pool versions needing a node pool upgrade, so that I can coordinate upgrades across my fleet without checking each cluster individually.

### Cloud Provider Admin

- As a Cloud Provider Admin, I want all upgrades to target only versions allowed by the platform as per OSAC-1269 (i.e., not blocked), so that the platform runs only approved and supported versions.
- As a Cloud Provider Admin, I want all control plane y-stream upgrades capped at the target y-stream's current fleet-wide z-stream version, so that all z-stream versions remain aligned and managed by the platform.
- As a Cloud Provider Admin, I want to select a target z-stream version for a given y-stream version cohort and initiate a progressive rollout, so that all clusters running that y-stream version that can be directly upgraded are brought to a consistent z-stream level without requiring tenant action.
- As a Cloud Provider Admin, I want to pause a z-stream rollout that is causing regressions, so that I can stop further clusters from being upgraded while I assess the impact.
- As a Cloud Provider Admin, I want to resume a paused z-stream rollout once the regression is resolved, so that clusters not yet upgraded at the time of pause continue receiving the upgrade.
- As a Cloud Provider Admin, I want to monitor the progress of a z-stream rollout across all targeted clusters, so that I can detect clusters with stalled or failed upgrades and intervene.
- As a Cloud Provider Admin, I want to know which clusters in a z-stream rollout will be excluded because the target version is not directly reachable from their current version, so that I can assess the cause and plan remediation.
- As a Cloud Provider Admin, I want to force a control plane y-stream upgrade for a specific cluster approaching EOL, so that the platform can maintain supportability independently of tenant scheduling.

### Cloud Infrastructure Admin

No active role in this feature; all platform-level upgrade operations are covered by the Cloud Provider Admin stories above.

## Dependencies

- **OSAC-1269 (ClusterVersion API):** A version is available for upgrade only if an allowed (not blocked) ClusterVersion exists for it

---

## Provenance

Authored: respond @ prd 0.6.3 - 68284c8, workspace main @ 43c34a8
Final: revise @ prd 0.7.1 - b8b3f86, workspace main @ 8f899d5

> Context changed between respond and revise.

> This document's phase history does not include an initial /draft — structure was not verified against the template from origin.

<!-- ai-workflow-provenance:{"schema_version":1,"provenance_kind":"session","workflow":"prd","workflow_version":"0.7.1","ai_workflows":"b8b3f86","source_repo":"8f899d5","source_repo_branch":"main","commits_behind_main":0,"commits_ahead_main":0,"main_ref":"main","phases":["respond","revise","revise","revise","revise","revise","revise","revise","revise","revise","revise","manual-edit","revise","revise"],"authoring_modes":["manual","skill"],"context_changed":true,"origin_untracked":true} -->
