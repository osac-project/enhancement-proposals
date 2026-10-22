---
title: cluster-upgrade-caas-ui
authors:
  - elayaha@gmail.com
creation-date: 2026-10-13
last-updated: 2026-10-22
tracking-link:
  - https://redhat.atlassian.net/browse/OSAC-1415
prd:
  - "prd.md"
see-also:
  - "design.md"
replaces:
  - "N/A"
superseded-by:
  - "N/A"
---

# Cluster Upgrade — CaaS UI

## Summary

Tenant Users and Tenant Admins choose one target OpenShift version for a cluster from the list or detail page. OSAC upgrades the control plane first, then automatically upgrades every node set (HyperShift node pool) to that version. The UI offers no independent component upgrade action. See the [PRD](prd.md), [Phase 1 contract](design-phase1.md), and [phase plan](design.md).

## What the user sees

An **Upgrades** card on **Overview** shows the current or latest cluster upgrade, its control-plane and node-set stages, and earlier history: source and target versions, state, message, and timing. Control-plane success is an intermediate stage; the cluster upgrade completes only after every node set reaches the target. Upgrade progress stays separate from cluster provisioning status.

The existing **Version** column in the Clusters table becomes **Current version** and reads `Cluster.status.observed_cp_version` (or `—` until observed); the configuration card uses the same value. The list and card lifecycle badges describe that observed version, or are hidden when no catalog entry matches. The **Node sets** table adds one **Current version** column from `Cluster.status.node_sets[name].observed_version` (or `—` until observed).

During the control-plane stage, show **Upgrade in progress from {current version} to {target version}** beside its observed version. While node sets follow, keep a cluster-level **Upgrading node sets to {target version}** indicator and show the from-to label beside each node set being upgraded. A TimedOut stage has no active label; the card still shows its recorded outcome.

## Starting an upgrade

**Upgrade version** in the details header and each cluster row's **Actions** menu opens the same dialog. It shows only the cluster's observed **Current version** and one **New version** selector. An information note explains that the control plane upgrades first, then all node sets upgrade automatically. There is no component selector or node-set version list. Targets come from enabled ACTIVE or DEPRECATED `ClusterVersion` entries. Compare semver values, not catalog names: a target must be newer than the observed control plane and keep every node set within three minor versions during the control-plane stage.

Disable **Upgrade version** with a reason at either entry point when `CanUpgrade` is not true or the cluster is `FAILED`, `DELETING`, or `DELETE_FAILED`. In the dialog, disable confirmation with a reason when an observed baseline or eligible target is unavailable. A `PROGRESSING` cluster can upgrade when `CanUpgrade=True`. The API makes the final admission decision.

Before confirmation, summarize the cluster's current → target version and reiterate that node sets upgrade automatically after the control plane; state that Phase 1 cannot cancel an accepted upgrade. Tell the tenant they **must check the current-to-target path and risks** in the external [OpenShift Update Graph](https://access.redhat.com/labs/ocpupgradegraph/update_path/). Phase 1 does not perform or verify that check.

## Request and progress

Use the `Cluster` from the existing list or details query. Submit one `Clusters.Update` through `useUpdateResource(Clusters)` with its `id` and the selected `ClusterVersionReference`, changing and masking only `spec.version`. The UI does not update `spec.node_sets` or send a request per node set. The backend coordinates the control-plane stage followed by the node-set stages.

Do not send status or a release image. Show API rejections without retrying automatically.

After acceptance, link from the cluster list to its Overview card for monitoring. Generic query invalidation and the app's default polling keep the list and details current, including after TimedOut. Show TimedOut as the recorded attempt outcome; observed versions may still advance if HyperShift converges. Use `CanUpgrade`, not the history outcome, to decide whether another upgrade is available. [Source: feature-owner review of the Phase 1 status model]

## Implementation notes

Add a `ClusterUpgradeCard` to `ClusterOverviewTab`; show observed versions and stage labels in `ClustersTable`, `ClusterConfigurationCard`, and the Node sets table. Resolve lifecycle badges against the observed control-plane version. Open one `UpgradeClusterDialog` from `ClusterDetailsActionButtons` and `ClusterActionsMenu`; use the current `Cluster` for the version summary and warning, and keep the table menu available to show disabled reasons.

Migrate cluster and version reads to `useGetResource`/`useListResource`, preserving project scoping and `CLUSTER_VERSION_ACTIVE_LIST_FILTER`. Use `useUpdateResource(Clusters)` and its matching cache invalidation instead of adding `useUpdateCluster`; use one semver/skew helper for cluster target filtering and disabled reasons.

The published PRD and Phase 1 design still specify independent component requests. Their backend contract must be aligned so one `spec.version` change drives the full sequence and status identifies its stages and overall completion. The UI must not infer completion from control-plane success alone. The backend design must also address clusters with a node set already three minor versions behind: a control-plane-first move to the next minor would exceed the skew limit.

Unit tests cover both action locations, target filtering across all node sets, the cluster-only version dialog and sequencing note, the warning, the `spec.version`-only request, errors and cache invalidation, observed versions, stage labels, history, and a later observed-version change after TimedOut; the [Phase 1 test plan](testplan-phase1.md) tracks deployed coverage.

Phase 2 adds graph-based choices and risk acknowledgment. Phase 3+ adds pending cancellation and version-attention views.

---

## Provenance

Authored: draft @ design 0.11.5 - 1c6e8de, workspace main @ f51d7c726
Final: revise @ design 0.11.5 - e2b0d87, workspace cluster-page-updates @ 469b04b2d

> Context changed between draft and revise.

<!-- ai-workflow-provenance:{"schema_version":1,"provenance_kind":"session","workflow":"design","workflow_version":"0.11.5","ai_workflows":"e2b0d87","source_repo":"469b04b2d","source_repo_branch":"cluster-page-updates","commits_behind_main":0,"commits_ahead_main":369,"main_ref":"main","phases":["draft","revise","revise","revise","respond","revise","revise","revise","revise","revise","respond","revise","revise"],"authoring_modes":["skill"],"context_changed":true,"origin_untracked":false} -->
