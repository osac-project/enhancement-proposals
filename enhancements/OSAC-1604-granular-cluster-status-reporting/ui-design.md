---
title: granular-cluster-status-reporting-ui
authors:
  - Elay Aharoni
creation-date: 2026-10-13
last-updated: 2026-10-14
tracking-link:
  - https://redhat.atlassian.net/browse/OSAC-2597
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

## Experience

Tenant users see **Status**, **Stage**, and **Health** on the cluster list and detail page. Status is the cluster lifecycle; the list's existing **Lifecycle** column describes the cluster version. Details remain accessible during deletion. The detail page keeps its conditions and endpoint URLs and expands the Node sets tab.

Cloud Provider Admins cannot see cluster navigation or open cluster pages, including direct URLs. [User decision]

## Display rules

All values come from the public `Cluster` returned by `Clusters.List/Get`. The UI does not read HyperShift resources.

- **Status:** Show `status.state`. A cluster can remain `READY` while workers are degraded or a node set is scaling.
- **Stage:** For `PROGRESSING` or `DELETING`, show the `PROGRESSING` condition's `reason`; show its `message` on detail. `Stalled` is a warning; `StageUnknown` or a missing reason displays **Stage unknown**. For `READY`, show **Scaling** only when a node set reports `SCALING`. Other states have no active stage.
- **Health:** Use `CONTROL_PLANE_AVAILABLE` and `WORKERS_READY` for separate Control plane and Workers indicators. Their true/false labels are **Available/Unavailable** and **Ready/Not ready**. Missing or unknown conditions show **Unknown**. Show true `DEGRADED` or `FAILED` conditions separately; never infer health from lifecycle or replica counts.
- **Node sets:** Join `spec.node_sets` and `status.node_sets` by key. **Requested** comes from `spec.size`; **Desired**, **Current**, **Ready**, and **State** come from new status fields. Missing values show **Unknown**; a reported zero shows **0**. The existing `status.node_sets.size` is observed, not requested or desired. Show `ready_replicas` as reported without estimating per-node health.

## UI changes

- `ClustersTable`: add Stage and Health; keep the cluster name clickable while `DELETING`.
- `ClusterDetailsPageContent`: add Stage and Health and expand Node sets; reuse the existing conditions table.
- `ClusterDetailsPage`: show the existing not-found view when `Clusters.Get` returns `NotFound` after archival; other errors remain retryable.
- Share one formatter between list and detail. Keep the existing `useClusters`/`useCluster` hooks and 10-second refresh; add no RPC or per-row request. Preserve the admin route gate. Use generated enum names and regenerate `@osac/types` after the backend API changes.

## Backend dependencies

- **Ready now:** Provisioning stage and `Stalled`/`StageUnknown` use the current API. The UI can keep the cluster name clickable while `DELETING` and verify the existing admin route gate.
- **Wait for health:** The backend must publish and populate the control-plane and worker conditions and preserve `READY` during degradation and scaling.
- **Wait for node sets:** The backend must publish and populate desired/current/ready/state, including `SCALING`.
- **Wait for teardown:** The backend must publish deletion stage reasons and `DELETE_FAILED` signals.

## Verification

UI unit tests cover missing and unknown values, `READY` with degraded workers or scaling, deletion and `NotFound`, and admin direct URLs with no cluster RPCs. Run `pnpm run typecheck`, `pnpm lint`, and `pnpm test` for implementation. Browser E2E checks require the corresponding backend phase and an owned UI E2E harness.

---

## Provenance

Authored: draft @ design 0.11.5 - 1c6e8de, workspace main @ f51d7c726
Final: revise @ design 0.11.5 - 1c6e8de, workspace fix-osac-5393 @ a2efec0b4

> Context changed between draft and revise.

<!-- ai-workflow-provenance:{"schema_version":1,"provenance_kind":"session","workflow":"design","workflow_version":"0.11.5","ai_workflows":"1c6e8de","source_repo":"a2efec0b4","source_repo_branch":"fix-osac-5393","commits_behind_main":0,"commits_ahead_main":249,"main_ref":"main","phases":["draft","revise","revise","revise","revise","revise","revise"],"authoring_modes":["skill"],"context_changed":true,"origin_untracked":false} -->
