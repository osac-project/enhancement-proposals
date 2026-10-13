---
title: cluster-upgrade-caas-ui
authors:
  - elayaha@gmail.com
creation-date: 2026-10-13
last-updated: 2026-10-13
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

The existing cluster detail page gains an upgrade action, progress, and history for Tenant Users and Tenant Admins. Phase 1 follows the serial `Cluster` upgrade contract in [design-phase1.md](design-phase1.md); later UI capabilities follow [design.md](design.md). See the [PRD](prd.md) for the full scope.

## Phase 1 workflow

1. An **Upgrades** tab shows the observed control-plane and named node-set versions, the current or last attempt (component, source and target versions, state, timestamps, and message), and terminal history. Upgrade state stays distinct from cluster provisioning state.
2. One **Upgrade** action opens a PatternFly dialog to select the control plane or one node set and a target from enabled, non-obsolete `ClusterVersion` entries; deprecated versions remain selectable. The UI permits only a newer target that keeps every node pool within three minor versions of the control plane; a node-pool target also cannot exceed the observed control-plane version. A false or missing `CanUpgrade` condition, unavailable catalog, or empty target list disables submission with an explanation.
3. The dialog links to the external OpenShift update graph and explains that Phase 1 does not verify one-hop reachability or assess upgrade risks. Confirmation updates only the chosen desired version through public `Clusters.Update`: use `spec.version` for the control plane or `spec.node_sets` with unchanged sibling entries for a node set, plus the current `metadata.version` and optimistic lock. The server makes the final admission decision.
4. After acceptance, refresh `Cluster` and poll while the attempt is Pending, Progressing, or TimedOut. TimedOut remains nonterminal and blocks another upgrade. Show server rejection or failure messages without changing the displayed observed version; stop polling at Succeeded or Failed.

## UI integration

Reuse `ClusterDetailsPageContent`, its Node sets view, `api/v1/cluster.ts`, and `api/v1/cluster-versions.ts`. Add a typed update hook and advance `@osac/types` to the Phase 1 public API when it lands. The console reads status and history from `Cluster`; it never writes HyperShift resources or creates a second upgrade API. Existing tenant-scoped `Cluster` permissions govern visibility and updates. No UI-owned schema or proxy change is required.

## Later phases

- **Phase 2:** Replace catalog-only choices with one-hop options for the cluster's existing channel; show conditional risks and require explicit acknowledgment before submission, using the Phase 2 API contract.
- **Phase 3+:** Add pending-only cancellation and divergence, near-N-3, and end-of-life notices on cluster details and the tenant-admin fleet list when those status contracts land. Running upgrades remain uncancellable.

## Verification and open question

`osac-ui` unit tests should cover target eligibility, blocked reasons, the selected-field update without changing sibling node sets, rejection handling, and progress/history rendering. The companion [Phase 1 test plan](testplan-phase1.md) records the deployed browser journey as an unresolved runner/owner gap. **Open question (CaaS API/design team):** Which later phase supports the PRD's parallel control-plane and node-pool upgrades? The answer changes when this UI enables another upgrade during an active attempt.

---

## Provenance

Authored: draft @ design 0.11.5 - 1c6e8de, workspace main @ f51d7c726

<!-- ai-workflow-provenance:{"schema_version":1,"provenance_kind":"session","workflow":"design","workflow_version":"0.11.5","ai_workflows":"1c6e8de","source_repo":"f51d7c726","source_repo_branch":"main","commits_behind_main":0,"commits_ahead_main":205,"main_ref":"main","phases":["draft"],"authoring_modes":["skill"],"context_changed":false,"origin_untracked":false} -->
