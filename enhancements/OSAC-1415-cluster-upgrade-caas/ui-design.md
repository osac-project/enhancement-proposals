---
title: cluster-upgrade-caas-ui
authors:
  - elayaha@gmail.com
creation-date: 2026-10-13
last-updated: 2026-10-19
tracking-link:
  - https://redhat.atlassian.net/browse/OSAC-1415
prd:
  - "prd.md"
see-also:
  - "design.md"
  - "design-phase1.md"
replaces:
  - "N/A"
superseded-by:
  - "N/A"
---

# Cluster Upgrade — CaaS UI

## Summary

Tenant Users and Tenant Admins can upgrade a cluster's control plane or one node set from the cluster list or detail page. Phase 1 allows one upgrade per cluster at a time through the public `Cluster` API. See the [PRD](prd.md), [Phase 1 contract](design-phase1.md), and [phase plan](design.md).

## What the user sees

An **Upgrades** card on **Overview** shows the latest attempt and earlier history: component, source and target versions, state, and timing. The last `status.version_history` entry is the current or most recent attempt; earlier entries are prior attempts. Upgrade progress stays separate from cluster provisioning status.

The existing **Version** column in the Clusters table becomes **Current version** and reads `Cluster.status.observed_cp_version` (or `—` until observed); the configuration card uses the same value. The list and card lifecycle badges describe that observed version, or are hidden when no catalog entry matches. The **Node sets** table adds one **Current version** column from `Cluster.status.node_sets[name].observed_version` (or `—` until observed).

When the last `status.version_history` entry is Pending or Progressing, show **Upgrade in progress from {current version} to {desired version}** beside the affected control-plane version in the list and configuration card, or in the matching node-set row. The desired version is the entry's target semver; TimedOut does not show this label.

## Starting an upgrade

**Upgrade version** in the details header and each cluster row's **Actions** menu opens the same dialog. It names the cluster, lets the tenant choose the control plane or one node set, and shows that component's observed **Current version** beside a **New version** selector. Targets come from enabled ACTIVE or DEPRECATED `ClusterVersion` entries. Compare their semver values, not catalog names:

- **Control plane:** target is newer than its observed version and leaves every node pool within three minor versions.
- **Node set:** target is newer than that pool's observed version, no newer than the observed control plane (including patch), and within three minor versions of it.

Disable **Upgrade version** with a reason at either entry point when `CanUpgrade` is not true or the cluster is `FAILED`, `DELETING`, or `DELETE_FAILED`. In the dialog, disable confirmation with a reason when an observed baseline or eligible target is unavailable. A `PROGRESSING` cluster can upgrade when `CanUpgrade=True`. The API makes the final admission decision.

Before confirmation, summarize the cluster, component, and observed current → target version; state that Phase 1 cannot cancel an accepted upgrade. Tell the tenant they **must check the current-to-target path and risks** in the external [OpenShift Update Graph](https://access.redhat.com/labs/ocpupgradegraph/update_path/). Phase 1 does not perform or verify that check.

## Request and progress

Use the `Cluster` from the existing list or details query. Submit `Clusters.Update` through `useUpdateResource(Clusters)` with its `id` and the selected `ClusterVersionReference`:

- **Control plane:** change `spec.version`; the generic hook masks `spec.version`.
- **Node set:** change only the selected version. A whole-map `spec.node_sets` mask could overwrite concurrent changes to sibling node sets, so extend the generic hook to accept an explicit `spec.node_sets.<name>.version` mask for this case and verify sibling fields remain unchanged.

Do not send status or a release image. Show API rejections without retrying automatically.

After acceptance, link from the cluster list to its Overview card for monitoring. Generic query invalidation and the app's default polling keep the list and details current, including after TimedOut. Show TimedOut as the recorded attempt outcome; observed versions may still advance if HyperShift converges. Use `CanUpgrade`, not the history outcome, to decide whether another upgrade is available. [Source: feature-owner review of the Phase 1 status model]

## Implementation and later phases

Add a `ClusterUpgradeCard` to `ClusterOverviewTab`; show observed versions and matching active-attempt labels in `ClustersTable`, `ClusterConfigurationCard`, and the Node sets table. Resolve lifecycle badges against the observed control-plane version. Open one `UpgradeClusterDialog` from `ClusterDetailsActionButtons` and `ClusterActionsMenu`; use the current `Cluster` for the version summary and warning, and keep the table menu available to show disabled reasons.

Migrate cluster and version reads to `useGetResource`/`useListResource`, preserving project scoping and `CLUSTER_VERSION_ACTIVE_LIST_FILTER`. Use `useUpdateResource(Clusters)` and its matching cache invalidation instead of adding `useUpdateCluster`; use one semver/skew helper for target filtering and disabled reasons.

The UI requires the pending Phase 1 contract update so active attempts appear in `status.version_history`; the published design still uses `status.upgrade`. Unit tests cover both action locations, eligibility, observed versions and active-only labels in the list and details, lifecycle alignment, and the dialog's component/current/target summary and no-cancellation warning. They also cover a masked node-set update that preserves sibling fields, generic cache invalidation, blocked reasons, current and prior attempts, and a later observed-version change after TimedOut; the [Phase 1 test plan](testplan-phase1.md) tracks deployed coverage.

Phase 2 adds graph-based choices and risk acknowledgment. Phase 3+ adds pending cancellation and version-attention views. **Open question:** The phase for parallel control-plane and node-pool upgrades is not specified; Phase 1 remains serial.

---

## Provenance

Authored: draft @ design 0.11.5 - 1c6e8de, workspace main @ f51d7c726
Final: respond @ design 0.11.5 - a58bdf7, workspace main @ 8e9f80546

> Context changed between draft and respond.

<!-- ai-workflow-provenance:{"schema_version":1,"provenance_kind":"session","workflow":"design","workflow_version":"0.11.5","ai_workflows":"a58bdf7","source_repo":"8e9f80546","source_repo_branch":"main","commits_behind_main":0,"commits_ahead_main":268,"main_ref":"main","phases":["draft","revise","revise","revise","respond","revise","revise","revise","revise","revise","respond"],"authoring_modes":["skill"],"context_changed":true,"origin_untracked":false} -->
