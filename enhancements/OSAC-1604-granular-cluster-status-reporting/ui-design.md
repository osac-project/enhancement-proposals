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

## Summary

The tenant cluster list and detail pages present lifecycle, current stage, independent control-plane and worker health, and node-set progress from the public `Cluster` response. The UI displays operator-reported status; it does not derive health from `Cluster.spec` or read HyperShift resources. See the [PRD](prd.md) and [backend design](design.md).

Cloud Provider Admins have no cluster navigation or list/detail routes in the UI, including direct URLs. This follows the feature owner's later UI visibility decision. [User decision]

## Data flow and source of truth

HyperShift `HostedCluster`/`NodePool` → `ClusterOrder` → operator feedback → Fulfillment `Cluster.status` → public `Clusters.List/Get` → existing Connect proxy and `useClusters`/`useCluster` hooks → shared presentation helper → list/detail. The backend owns signal interpretation; the UI receives status in the existing cluster request. [Codebase: `osac-ui/libs/ui-components/src/api/v1/cluster.ts`; `osac-operator/internal/controller/feedback_controller.go`]

| Data | UI meaning | Availability |
|---|---|---|
| `status.state` | Cluster lifecycle label. | Present. |
| `status.conditions[PROGRESSING].reason/message` | Provisioning or teardown stage and stalled detail. | Provisioning present; teardown producer pending. |
| `status.conditions[CONTROL_PLANE_AVAILABLE, WORKERS_READY]` | Independent health axes. `AVAILABLE` is the full-health rollup; `DEGRADED`/`FAILED` are problem signals. | New health contract and producer pending. |
| `spec.node_sets[key].size` | Tenant-requested nodes in a set. | Present. |
| `status.node_sets[key].size` | Existing observed NodePool replica count, when reported. | Present; differs from the backend design's requested-size description. |
| `status.node_sets[key].desired_replicas/current_replicas/ready_replicas/state` | Operator target, observed count, reported ready count, and per-set progress. | New contract and producer pending. |
| `status.api_url/console_url` | Existing endpoint display. | Present. |

The UI never treats `spec.node_sets.size` as a ready count or an absent count as zero. It consumes new generated `@osac/types` fields only after the public proto and operator agree on their meanings.

## Status interpretation

### Lifecycle and stage

`ClusterStatusLabel` continues to render `status.state`. The list's existing **Lifecycle** column describes the cluster *version*; the cluster lifecycle stays in **Status**. A shared pure helper chooses the stage by lifecycle:

| Lifecycle | Stage | Missing source |
|---|---|---|
| `PROGRESSING` | `PROGRESSING.reason` | **Stage unknown** |
| `DELETING` | `PROGRESSING.reason`, after the teardown producer lands | **Stage unknown** |
| `READY` with any node set `SCALING` | **Scaling** | — |
| `READY` without scaling, `FAILED`, or `DELETE_FAILED` | No active stage: **—**. Failure detail remains in conditions. | — |
| Unrecognized lifecycle | No inference | **Unknown** |

Look up conditions by generated enum type, independent of array order. Humanize ordinary backend reasons for display without branching on the operator-owned stage vocabulary. The stable exceptions are `StageUnknown` → **Stage unknown** and `Stalled` → a warning labeled **Stalled**; the detail view also shows its message naming the stuck stage. A prior provisioning reason is not shown as active work after `READY` unless a node set reports `SCALING`.

### Health and node sets

The Health display contains separately labeled **Control plane** and **Workers** indicators. `CONTROL_PLANE_AVAILABLE=True/False` maps to **Available/Unavailable**; `WORKERS_READY=True/False` maps to **Ready/Not ready**. Missing or unknown statuses display **Unknown**. A true `DEGRADED` or `FAILED` condition adds a problem label. `AVAILABLE` remains visible in the full conditions table. Never infer either health axis from lifecycle state, URLs, replica counts, or the current `READY` condition.

For example, `state=READY`, control plane available, workers not ready, and `DEGRADED=True` display **Ready** as lifecycle, **Available** for control plane, **Not ready** for workers, and **Degraded** as a separate signal.

The Node sets tab iterates configured `spec.node_sets` keys in stable order and joins `status.node_sets` by the same key, never by host type. It shows **Requested** (`spec.size`), **Desired**, **Current**, **Ready**, and **State** from the new status fields. Missing status displays **Unknown**; a reported zero displays **0**. Unrecognized enum values show **Unknown** with their raw value available in detail. The backend currently reports readiness for a node set as a whole, so `ready_replicas` must not be described as precise per-node health. Until the new fields land, retain the existing requested-size table; do not relabel the old observed `status.size` as Desired or Ready.

## Views and component changes

- **List (`ClustersTable`):** retain Status, version Lifecycle, API URL, and actions. Add Stage and Health cells from the shared presentation helper. Keep the cluster name linked to details while `DELETING`; continue suppressing its actions and API URL during deletion. Use text with PatternFly labels so color is not the only signal.
- **Detail (`ClusterDetailsPageContent`):** show lifecycle and stage in the header, both health axes in Overview, and the existing `ResourceConditionsTable` with type, status, reason, message, and transition time. Keep API/console URLs. Expand the Node sets tab as above. Relabel the existing spec-derived worker summary **Requested workers** so it is not mistaken for observed capacity.
- **Deletion/error (`ClusterDetailsPage`):** keep deletion details readable until archival. Map Connect `NotFound` from `Clusters.Get` to the existing not-found view; keep transient errors on the retryable load-error path. The existing delete action stays disabled during `DELETING`.
- **Access (`AppShell`/`shellNav`):** retain the role gate that omits `/clusters/*` and cluster navigation for `admin`; `cloud-provider-admin` maps to `admin`. Direct URLs must not mount cluster pages or call `Clusters.List/Get`. Tenant data access remains enforced by the public API. [User decision]

Introduce a pure `deriveClusterStatusPresentation(cluster)` helper near the Cluster components. It returns semantic stage, control-plane, worker, and problem states; list and detail format those values consistently. Use generated enum symbols, not numeric values or condition-array positions. Keep the existing `useClusters`/`useCluster` hooks and 10-second active-query refresh. Add no per-row request, new RPC, or local status store. Regenerate `@osac/types` with `pnpm gen-types` only after the selected public API baseline includes the resolved contract; extract fixed UI strings with `pnpm i18n`. [Codebase: `osac-ui/apps/app-frontend/src/main.tsx`; `osac-ui/AGENTS.md`]

## Backend readiness gates

These are delivery gates for later Jira decomposition, not Jira tasks. Each UI behavior can be completed when its stated backend contract is available.

| Gate | UI behavior | Backend prerequisite |
|---|---|---|
| Current API | Provisioning stage, `StageUnknown`/`Stalled`, and a reachable deletion detail page. Cloud Provider Admin route exclusion already exists. | Current `PROGRESSING.reason`, `status.state`, and routes. |
| Health | Separate control-plane/worker indicators and problem labels while lifecycle remains `READY` through scaling or degradation. | Public health condition types plus operator production/clearing of `CONTROL_PLANE_AVAILABLE`, `WORKERS_READY`, and `AVAILABLE`; lifecycle semantics settled. |
| Node sets/scaling | Requested/desired/current/ready/state per set, plus **Scaling** while `READY`. | Public replica/state fields populated for each node-set key. |
| Teardown | Current deletion stage, stalled teardown, and deletion failure until archival. | Teardown `PROGRESSING.reason`, `Stalled`, and actual `DELETE_FAILED`/`FAILED` signals in the public API. |

Before the health gate, reconcile the backend design with current code: condition numbers `5` and `6` already identify worker-provisioning conditions; `ClusterAvailable` now maps to the existing `READY` condition, so renaming value `2` needs compatibility review; and `status.node_sets.size` currently comes from observed NodePool replicas. The UI does not alias the old `READY` condition to the proposed full-health `AVAILABLE` meaning. [Codebase: `proto/private/osac/private/v1/cluster_type.proto`; `osac-operator/internal/controller/feedback_controller.go`]

## Verification

| Behavior | Tier / owner | Test boundary |
|---|---|---|
| Stage, health, and node-set formatting: shuffled/missing conditions, zero versus absent counts, `READY` with degraded workers or scaling, unknown enum values | Unit, UI `[DEV]` | Component/helper tests use generated-proto fixtures; route tests use fake Connect transport. Backend/operator are omitted. |
| Deletion link, Connect `NotFound` after archival, and retryable transport failure | Unit, UI `[DEV]` | Cluster list/detail tests use fake `Clusters.Get/List` responses. |
| Cloud Provider Admin navigation/direct URL exclusion and zero cluster RPCs | Unit, UI `[DEV]` | Extend `shellNav.test.ts` for navigation and `AppShell.test.tsx` with fake Connect transport for direct routes and calls. |
| Real provisioning, degradation, scaling, and deletion in the browser | E2E, `[QE]` | Backend CaaS E2E must verify producer behavior. A persisted browser E2E suite does not yet exist; `osac-ui/apps/playwright` supports manual live-cluster checks. Resolve a persistent harness and owning Jira task during decomposition before claiming automated UI E2E coverage. |

Run `pnpm run typecheck`, `pnpm lint`, and `pnpm test` from `osac-ui/` for UI implementation. The existing 10-second query interval is UI polling, not proof of end-to-end freshness; deployed validation must measure backend propagation separately.

---

## Provenance

Authored: draft @ design 0.11.5 - 1c6e8de, workspace main @ f51d7c726
Final: revise @ design 0.11.5 - 1c6e8de, workspace fix-osac-5393 @ a2efec0b4

> Context changed between draft and revise.

<!-- ai-workflow-provenance:{"schema_version":1,"provenance_kind":"session","workflow":"design","workflow_version":"0.11.5","ai_workflows":"1c6e8de","source_repo":"a2efec0b4","source_repo_branch":"fix-osac-5393","commits_behind_main":0,"commits_ahead_main":249,"main_ref":"main","phases":["draft","revise","revise","revise","revise"],"authoring_modes":["skill"],"context_changed":true,"origin_untracked":false} -->
