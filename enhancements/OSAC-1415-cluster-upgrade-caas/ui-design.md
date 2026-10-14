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

The tenant cluster detail page gains control-plane and node-set upgrade actions, progress, and history. Phase 1 uses the serial public `Cluster` contract in [design-phase1.md](design-phase1.md); later UI capabilities follow [design.md](design.md). See the [PRD](prd.md) for requirements.

## Phase 1 integration

Add an **Upgrades** tab to `ClusterDetailsPageContent` and its loading state in `ClusterDetailsPage`. Reuse `useCluster(id)` for the public `Clusters.Get` response and `useClusterVersions` with `CLUSTER_VERSION_ACTIVE_LIST_FILTER` for enabled ACTIVE/DEPRECATED targets. Add a typed `Clusters.Update` mutation in `api/v1/cluster.ts`; invalidate cluster detail and list queries after acceptance. Advance the selected `@osac/types` protobuf baseline with `pnpm gen-types` when the Phase 1 fields land; generated types are not hand-edited. [Codebase: `osac-ui/libs/ui-components/src/components/Cluster/`, `osac-ui/libs/ui-components/src/api/v1/`]

| UI value | Public `Cluster` source |
|---|---|
| Control-plane desired / observed | `spec.version` / `status.observed_cp_version` |
| Node-set desired / observed | `spec.node_sets[name].version` / `status.node_sets[name].observed_version` |
| Current or last attempt | `status.upgrade`: component, source/target semver, state, times, message |
| Completed attempts | `status.version_history`: terminal successes and failures only |
| Admission gate | `status.conditions` entry of type `CLUSTER_CONDITION_TYPE_CAN_UPGRADE` |

The tab shows one control-plane row and one row per `spec.node_sets` key, using the same public names as the existing Node sets tab. Desired and observed versions remain separate while an upgrade runs. Display an unresolved observed version as unknown and block submission; never infer it from the desired reference. Upgrade state does not replace the cluster provisioning state. Status fields are rendered according to the final generated Phase 1 types; the Phase 1 design leaves their exact member names to implementation.

## Selection and admission

An **Upgrade** action opens a PatternFly dialog with the selected component, its observed semver, and eligible target `ClusterVersion.spec.version` values. Changing component clears the target. Use SemVer comparison, including patch and prerelease ordering, rather than catalog-name or lexical comparison.

| Target | Client-side eligibility mirror |
|---|---|
| Control plane | Target exceeds observed control-plane semver; every observed node pool remains at most three minor releases behind the target. |
| One node set | Target exceeds that pool's observed semver, does not exceed observed control-plane semver (including patch), and remains within three minor releases of it. |

Submission also requires `CanUpgrade=True`, a loaded catalog, resolved observed baselines, and a cluster state other than `FAILED`, `DELETING`, or `DELETE_FAILED`. `PROGRESSING` alone does not block when `CanUpgrade=True`. A missing or false condition, active attempt, or empty eligible list disables confirmation and shows the condition message or a specific local reason. The UI mirrors admission for feedback; Fulfillment rechecks the current versions and gate under its row lock and remains authoritative. [Source: [Phase 1 admission](design-phase1.md#admission-and-version-validation)]

Before confirming, the tenant **must check the current-to-target path and associated risks** in the external [Red Hat OpenShift Container Platform Update Graph](https://access.redhat.com/labs/ocpupgradegraph/update_path/). The dialog states this requirement and links the graph. Phase 1 neither verifies one-hop reachability nor assesses or records risk acknowledgment, so the UI does not imply either check occurred. [Source: [Phase 1 graph limitation](design-phase1.md#failure-handling-and-recovery)]

## Update request and concurrency

On confirmation, refetch the `Cluster`, re-evaluate eligibility, and build the request from its fresh `metadata.version`. Both cases call public `Clusters.Update` with `object.id`, `object.metadata.version`, `lock: true`, and a single update-mask path:

| Selected component | Submitted `object.spec` | `update_mask.paths` |
|---|---|---|
| Control plane | `{ version: selectedClusterVersionReference }` | `spec.version` |
| Node set | Full latest `node_sets` map with only the selected entry's `version` changed; preserve its other fields and all sibling entries. | `spec.node_sets` |

The target is a `ClusterVersionReference`, not a user-supplied release image. Do not send `status` or unrelated `spec` fields. The map-level mask is required because `node_sets` is a protobuf map; optimistic locking prevents a stale map from overwriting another update. On a stale-version or admission rejection, refetch and show the API reason without automatic resubmission. If the response is lost, refetch before offering retry because the request may have been accepted. Existing tenant-scoped `Cluster` permissions govern the read and update; the UI never calls HyperShift or adds a proxy endpoint. [Codebase: `proto/public/osac/public/v1/clusters_service.proto`, `osac-ui/libs/ui-components/src/api/v1/update-mask.ts`]

## Progress and recovery

Refetch on tab activation and after acceptance; while the Upgrades tab is open and the attempt is nonterminal, use the existing query layer's interval refetch. Stop at a terminal state or when the tab unmounts. A read error keeps the last known status visibly stale and offers retry; it never implies success or reopens the action.

| `status.upgrade` state | UI behavior |
|---|---|
| Pending | Show accepted target and waiting message; observed version stays at its baseline. |
| Progressing | Show selected component, source/target semver, and progress message. |
| TimedOut | Show a warning that monitoring continues; keep upgrade disabled and add no history row. |
| Succeeded | Show the new observed semver and terminal history entry. |
| Failed | Show the failure message and terminal history entry; observed semver remains unchanged. Allow a new request only when `CanUpgrade=True` again. |

Render history newest first by completion time, with component (`control_plane` or `node_pool:<node-set-name>`), source/target semver, result, and time. Do not synthesize entries for installation or a nonterminal attempt. Use PatternFly labels, keyboard-accessible dialog controls, and a live error/status announcement. [Source: [Phase 1 progress](design-phase1.md#upgrade-progress-and-feedback)]

## Later phases and verification

- **Phase 2:** Replace catalog-only choices with graph-derived, one-hop options for the existing channel; show conditional risks and require explicit acknowledgment using its future API contract.
- **Phase 3+:** Add pending-only cancellation and divergence, near-N-3, and end-of-life notices on cluster details and the Tenant Admin fleet list when those contracts land. Running upgrades remain uncancellable.

`osac-ui` Vitest/React Testing Library tests with mocked Connect responses cover SemVer and N-3 boundaries, disabled reasons, the exact field mask/map preservation/lock, stale or uncertain mutation outcomes, all five states, and terminal history. This is the `[DEV]` unit tier in [Phase 1 test plan](testplan-phase1.md#tc-nfr1-01-offer-eligible-upgrades-and-explain-blocked-actions). Its deployed browser journey remains a proposed `[QE]` E2E case without a persisted runner or owner.

**Open question — CaaS API/design team:** Which later phase supports the PRD's parallel control-plane and node-pool upgrades? Phase 1 keeps the action disabled during any active attempt; the answer determines when the UI may enable another component concurrently.

---

## Provenance

Authored: draft @ design 0.11.5 - 1c6e8de, workspace main @ f51d7c726
Final: revise @ design 0.11.5 - 1c6e8de, workspace fix-osac-5393 @ a2efec0b4

> Context changed between draft and revise.

<!-- ai-workflow-provenance:{"schema_version":1,"provenance_kind":"session","workflow":"design","workflow_version":"0.11.5","ai_workflows":"1c6e8de","source_repo":"a2efec0b4","source_repo_branch":"fix-osac-5393","commits_behind_main":0,"commits_ahead_main":249,"main_ref":"main","phases":["draft","revise"],"authoring_modes":["skill"],"context_changed":true,"origin_untracked":false} -->
