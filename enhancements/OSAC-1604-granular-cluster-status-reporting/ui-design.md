---
title: granular-cluster-status-reporting-ui
authors:
  - Elay Aharoni
creation-date: 2026-10-13
last-updated: 2026-10-13
tracking-link:
  - https://redhat.atlassian.net/browse/OSAC-1604
prd:
  - prd.md
see-also:
  - design.md
replaces:
  - N/A
superseded-by:
  - N/A
---

# Granular Cluster Status Reporting — UI

## Summary

Show the public `Cluster.status` lifecycle, provisioning or teardown stage, independent health conditions, and node-set progress on the existing cluster pages for Tenant Users and Cloud Provider Admins. See the [PRD](prd.md) and [backend design](design.md).

## Proposal

| View | Change |
|------|--------|
| Tenant cluster list (`/clusters`) | Keep the lifecycle label; add **Stage** from `PROGRESSING.reason` (or `SCALING` from node-set state) and **Health** showing control-plane and worker readiness separately, plus `DEGRADED`/`FAILED` when true. Keep details reachable during `DELETING`. |
| Cluster detail | Show lifecycle and stage in the header, separate control-plane and worker health, and the existing full conditions table. In **Node sets**, show each set's requested, desired, current, and ready replicas plus its state; `SCALING` remains visible while the cluster lifecycle is `READY`. Keep existing API/console URLs. |
| Provider cluster list/detail | Expose the same read-only views to Cloud Provider Admins, with a **Tenant** column in the list. Do not expose create, delete, kubeconfig, or password actions in this status view. |

Stage labels display the backend's reason as human-readable text without branching on its operator-owned stage vocabulary. `Stalled` is a warning with the condition message naming the stage; `StageUnknown` displays **Stage unknown**. Missing conditions and unfamiliar enum values display **Unknown**, never an inferred healthy state. Deletion shows its teardown reason until the API archives the cluster; a finished deletion uses the existing not-found view. Health remains separate from lifecycle: `READY` can coexist with degraded workers. Missing node-set status displays **Unknown**; `ready_replicas` is shown as reported, without claiming per-node health precision the backend cannot supply.

## Implementation

Reuse `ClustersTable`, `ClusterDetailsPageContent`, `ResourceConditionsTable`, and PatternFly status labels. The admin route/navigation reuses the cluster List/Get views without a client project filter; the server remains the tenant-visibility authority. Use only public `Clusters.List/Get` data, join spec and status node sets by map key, share one status formatter between list and detail, and retain the existing 10-second active-query refresh. Regenerate `@osac/types` with `pnpm gen-types` after the backend status contract lands; no new RPC, local status store, or per-row request is needed.

## Risks and verification

Current proto values `5` and `6` already identify worker-provisioning conditions, while the backend design assigns those numbers to new health conditions. Backend implementation must allocate unique enum values before UI type generation; UI matching uses generated condition names, never numbers.

Vitest/React Testing Library checks the list and detail for stage transitions, `READY` with worker degradation or scaling, stalled/unknown signals, deletion detail access, node-set counts, and provider versus tenant visibility. Run `pnpm run typecheck`, `pnpm lint`, and `pnpm test` when implementing the UI.

---

## Provenance

Authored: draft @ design 0.11.5 - 1c6e8de, workspace main @ f51d7c726

<!-- ai-workflow-provenance:{"schema_version":1,"provenance_kind":"session","workflow":"design","workflow_version":"0.11.5","ai_workflows":"1c6e8de","source_repo":"f51d7c726","source_repo_branch":"main","commits_behind_main":0,"commits_ahead_main":205,"main_ref":"main","phases":["draft"],"authoring_modes":["skill"],"context_changed":false,"origin_untracked":false} -->
