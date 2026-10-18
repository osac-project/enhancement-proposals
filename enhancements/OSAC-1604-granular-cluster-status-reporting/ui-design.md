---
title: granular-cluster-status-reporting-ui
authors:
  - Elay Aharoni
creation-date: 2026-10-13
last-updated: 2026-10-18
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

Tenant users see **State** and **Health** on the cluster list and detail page, with current activity beneath State. The list keeps **Version** and removes the ambiguous **Lifecycle** column; the version lifecycle label remains beside Version on details. Details remain accessible during deletion. The detail page keeps its conditions and endpoint URLs and shows a compact node count and state for each node set.

Cloud Provider Admins cannot see cluster navigation or open cluster pages, including direct URLs. [User decision]

## Display rules

All values come from the public `Cluster` returned by `Clusters.List/Get`. The UI does not read HyperShift resources.

- **State and activity:** Show `status.state` as the primary value. For `PROGRESSING` or `DELETING`, put the `PROGRESSING` condition's `reason` on a second line (for example, **Workers joining** below **Provisioning**). `Stalled` is a warning; `StageUnknown` or a missing reason displays **Stage unknown**. For `READY`, show **Scaling** beneath the state only when a node set reports `SCALING`. Other states have no activity text. `READY` can coexist with degraded health.
- **Health:** Use `CONTROL_PLANE_AVAILABLE` and `WORKERS_READY` for separate Control plane and Workers indicators. Their true/false labels are **Available/Unavailable** and **Ready/Not ready**. Missing or unknown conditions show **Unknown**. Show true `DEGRADED` or `FAILED` conditions separately; never infer health from lifecycle or replica counts.
- **Node sets:** In the existing table, keep Name and Host type; replace Size with **Nodes** as current/requested (for example, **1/3 nodes present**) and add the per-set **State**. Join `spec.node_sets` and `status.node_sets` by key: current is `current_replicas`, requested is `spec.size`. Missing current count or state shows **Unknown**; a reported zero shows **0**. Do not label the ratio “ready”: the backend reports whole-set readiness, not individual nodes. The public `Cluster` has no individual node inventory.

## UI changes

- `ClustersTable`: rename Status to State, show activity beneath it, add Health, and remove Lifecycle while keeping Version. Keep the cluster name clickable while `DELETING`.
- `ClusterDetailsPageContent`: show activity beneath the existing state badge and Health beside it. In the existing Conditions table, new health conditions appear as rows; the `PROGRESSING` row shows its reason and message in the existing Reason and Message columns. Give condition types readable labels; add no popover or columns.
- Node sets tab: replace Size with Nodes and add State in its existing table.
- `ClusterDetailsPage`: show the existing not-found view when `Clusters.Get` returns `NotFound` after archival; other errors remain retryable.
- Share one formatter between list and detail. Keep the existing `useClusters`/`useCluster` hooks and 10-second refresh; add no RPC or per-row request. Preserve the admin route gate. Use generated enum names and regenerate `@osac/types` after the backend API changes.

## Backend dependencies

- **Ready now:** Provisioning stage and `Stalled`/`StageUnknown` use the current API. The UI can remove Lifecycle from the list, keep the cluster name clickable while `DELETING`, and verify the existing admin route gate.
- **Wait for health:** The backend must publish and populate the control-plane and worker conditions and preserve `READY` during degradation and scaling.
- **Wait for node sets:** The backend must publish and populate `current_replicas` and per-set `state`, including `SCALING`.
- **Wait for teardown:** The backend must publish deletion stage reasons and `DELETE_FAILED` signals.

## Verification

UI unit tests cover State with activity text, list Version without Lifecycle, version lifecycle on details, new condition rows and readable labels, the existing condition message column, missing and zero node counts, current/requested display, `READY` with degraded workers or scaling, deletion and `NotFound`, and admin direct URLs with no cluster RPCs. Run `pnpm run typecheck`, `pnpm lint`, and `pnpm test` for implementation. Browser E2E checks require the corresponding backend phase and an owned UI E2E harness.

---

## Provenance

Authored: draft @ design 0.11.5 - 1c6e8de, workspace main @ f51d7c726
Final: respond @ design 0.11.5 - a58bdf7, workspace main @ 8e9f80546

> Context changed between draft and respond.

<!-- ai-workflow-provenance:{"schema_version":1,"provenance_kind":"session","workflow":"design","workflow_version":"0.11.5","ai_workflows":"a58bdf7","source_repo":"8e9f80546","source_repo_branch":"main","commits_behind_main":0,"commits_ahead_main":268,"main_ref":"main","phases":["draft","revise","revise","revise","revise","revise","revise","revise","revise","respond","respond"],"authoring_modes":["skill"],"context_changed":true,"origin_untracked":false} -->
