---
title: cluster-upgrade-caas-ui
authors:
  - elayaha@gmail.com
creation-date: 2026-10-13
last-updated: 2026-10-14
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

Tenant Users and Tenant Admins can upgrade a cluster's control plane or one node set from its detail page. Phase 1 allows one upgrade per cluster at a time through the public `Cluster` API. See the [PRD](prd.md), [Phase 1 contract](design-phase1.md), and [phase plan](design.md).

## What the user sees

An **Upgrades** tab shows the control plane and each named node set (one node pool) with both desired and observed versions. Observed versions come from `Cluster.status.observed_cp_version` and `Cluster.status.node_sets[name].observed_version`; the desired version must not be shown as the running version. `status.version_history` includes the current attempt, if any; its last entry supplies the current or most recent attempt, and earlier entries show prior attempts. Upgrade progress stays separate from cluster provisioning status.

## Starting an upgrade

An **Upgrade** dialog selects the control plane or one node set, then a target from enabled ACTIVE or DEPRECATED `ClusterVersion` entries. Compare their semver values, not catalog names:

- **Control plane:** target is newer than its observed version and leaves every node pool within three minor versions.
- **Node set:** target is newer than that pool's observed version, no newer than the observed control plane (including patch), and within three minor versions of it.

Disable the action with a reason when the `CanUpgrade` condition is not true, an observed baseline or eligible target is unavailable, or the cluster is `FAILED`, `DELETING`, or `DELETE_FAILED`. A `PROGRESSING` cluster can upgrade when `CanUpgrade=True`. The API makes the final admission decision.

Before confirmation, tell the tenant they **must check the current-to-target path and risks** in the external [OpenShift Update Graph](https://access.redhat.com/labs/ocpupgradegraph/update_path/). Phase 1 does not perform or verify that check.

## Request and progress

Refetch the `Cluster` before submission. Call `Clusters.Update` with its `id`, current `metadata.version`, and `lock: true`:

- **Control plane:** change `spec.version`; mask `spec.version`.
- **Node set:** change only its version in the full `spec.node_sets` map, preserving sibling entries; mask `spec.node_sets`.

Use a `ClusterVersionReference`; do not send status or a release image. Show API rejections and refetch rather than retrying automatically.

Refetch `Cluster` after acceptance and poll while the Upgrades tab is visible, including after the last history entry becomes TimedOut. Show TimedOut as the recorded attempt outcome; observed versions may still advance if HyperShift converges. Use `CanUpgrade`, not the history outcome, to decide whether another upgrade is available. [Source: feature-owner review of the Phase 1 status model]

## Implementation and later phases

Extend the existing `osac-ui` cluster and version hooks when the Phase 1 public fields reach `@osac/types`. The UI requires the pending Phase 1 contract update so active attempts appear in `status.version_history`; the published design still uses `status.upgrade`. Unit tests cover eligibility, the update mask and preserved node sets, blocked actions, the current attempt in history, polling after timeout, and a later observed-version change; the [Phase 1 test plan](testplan-phase1.md) tracks deployed coverage.

Phase 2 adds graph-based choices and risk acknowledgment. Phase 3+ adds pending cancellation and version-attention views. **Open question:** The phase for parallel control-plane and node-pool upgrades is not specified; Phase 1 remains serial.

---

## Provenance

Authored: draft @ design 0.11.5 - 1c6e8de, workspace main @ f51d7c726
Final: respond @ design 0.11.5 - 1c6e8de, workspace fix-osac-5393 @ a2efec0b4

> Context changed between draft and respond.

<!-- ai-workflow-provenance:{"schema_version":1,"provenance_kind":"session","workflow":"design","workflow_version":"0.11.5","ai_workflows":"1c6e8de","source_repo":"a2efec0b4","source_repo_branch":"fix-osac-5393","commits_behind_main":0,"commits_ahead_main":249,"main_ref":"main","phases":["draft","revise","revise","revise","respond"],"authoring_modes":["skill"],"context_changed":true,"origin_untracked":false} -->
