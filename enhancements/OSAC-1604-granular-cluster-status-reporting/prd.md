# Granular Cluster Status Reporting

| Field       | Value   |
|-------------|---------|
| Author(s)   | Elad Tabak |
| Jira        | [OSAC-1604](https://issues.redhat.com/browse/OSAC-1604) |
| Date        | 2026-08-16 |

## Problem Statement

Tenants and cloud provider admins have limited visibility into cluster provisioning progress. When a cluster is being created, the only status they see is "PROGRESSING" - with no indication of whether the system is creating infrastructure, waiting for the control plane, or provisioning worker nodes. Cluster provisioning takes significantly longer than VM provisioning, making this opacity more painful. Users cannot distinguish between a cluster that is progressing normally and one that is stuck.

Today the status a user sees mirrors only the broad lifecycle phase; it does not surface independent health signals or where the cluster is within provisioning. That finer-grained information exists internally but is collapsed before it reaches the user. VMaaS already solved the equivalent problem for ComputeInstance in OSAC-1027, giving VM users granular provisioning progress and health signals that are independent of the lifecycle phase. CaaS clusters need the same treatment, adapted for cluster-specific provisioning stages.

## In Scope

- Granular provisioning progress visible through the API, CLI, and UI - tenants can see where in the provisioning pipeline their cluster is (e.g., infrastructure being prepared, control plane starting, worker nodes joining) [Clarify: D1, D3]
- Independent health signals - users can see indicators such as control plane readiness and worker node readiness separately from the overall lifecycle phase, rather than a single status that duplicates the phase [Clarify: D1]
- Scaling progress visibility - when a tenant scales a node set, they can see the scaling operation's progress separately from the overall cluster state
- Deletion progress visibility - tenants can see that deletion is proceeding and track its progress
- CLI `describe` output that shows health signals, provisioning progress, API URL, console URL, and node set status
- UI status display for cluster provisioning and lifecycle, covering both tenant and provider admin views [Clarify: D3]
- Monitoring signals - such as metrics and provisioning-transition events - that provider admins can consume to build dashboards and alerts
- CaaS clusters only [Clarify: D2]

## Out of Scope

- Power state phases (start, stop, pause, resume) - clusters are always running once provisioned, unlike VMs [Clarify: D1]
- VMaaS or BMaaS status reporting - VMaaS is already addressed by OSAC-1027; BMaaS is separate
- Cluster upgrade status tracking - upgrade workflows are future work (OSAC-1415)
- AAP job-level progress detail - AAP job status is already available in the jobs array; this feature focuses on status derived from the cluster's observed state [Clarify: D4]
- Auto-scaling or capacity-based status signals

## User Stories

*The status a cluster reports is identical regardless of who views it; personas differ only in which clusters they can see (their own vs. across all tenants).*

### Tenant User

- As a Tenant User, I want to see where my cluster is in the provisioning pipeline so that I know whether it is progressing normally or stuck.
- As a Tenant User, I want to see when my cluster's control plane is available separately from when worker nodes are ready so that I understand what is happening during provisioning.
- As a Tenant User, I want to see provisioning progress when I scale a node set so that I know the scaling operation is proceeding.
- As a Tenant User, I want to see deletion progress when I delete a cluster so that I can track whether resource cleanup is completing.
- As a Tenant User, I want to run `osac describe cluster <id>` and see health signals, provisioning status, API URL, console URL, and node set status so that I have a complete picture of my cluster without needing the raw YAML output.
- As a Tenant User, I want to see the same granular status in the web console so that I do not need the CLI for basic status checks.

### Cloud Provider Admin

- As a Cloud Provider Admin, I want to see granular provisioning status across tenant clusters so that I can identify which clusters are stuck and at which stage.
- As a Cloud Provider Admin, I want health signals that distinguish between control plane issues and worker node issues so that I can triage problems efficiently.
- As a Cloud Provider Admin, I want to see when a cluster is degraded (e.g., some workers failed to join but the control plane is functional) with enough detail to understand the scope of the degradation.
- As a Cloud Provider Admin, I want observability signals emitted at key provisioning transitions so that I can build monitoring dashboards and set alerts on provisioning failures.

## Assumptions

- The provisioning stages named in the Acceptance Criteria map to distinct, observable signals from the underlying platform; the exact mapping is defined in the design EP.

## Dependencies

- **OSAC-1027 (ComputeInstance Phase & Condition Expansion):** Establishes the pattern this feature follows, adapted for CaaS. Already implemented.
- **Hosted Control Planes (HyperShift):** The underlying platform already exposes the granular provisioning milestones and health signals this feature surfaces (infrastructure readiness, control plane availability, worker node readiness, and per-node-set readiness counts). No upstream changes are required.

## Acceptance Criteria

- A tenant can observe their cluster progress through distinct provisioning stages - at minimum: preparing infrastructure, control plane available (API reachable), worker nodes joining, and ready - rather than a single "PROGRESSING" status.
- A tenant can distinguish a normally-progressing cluster from a stalled one, because the current stage is visible and updates as provisioning advances.
- A cluster with a problem shows a Failed or Degraded signal that is independent of the provisioning stage (e.g., the control plane is healthy but some worker nodes failed to join).
- When a tenant scales a node set, the scaling operation's progress is visible separately from the overall cluster status.
- When a tenant deletes a cluster, deletion progress is visible until cleanup completes.
- `osac describe cluster <id>` shows the cluster's health signals, current provisioning stage, API URL, console URL, and node set status without requiring raw YAML.
- The web console shows the same provisioning stage, health signals, and lifecycle status that are available via the API and CLI.
- Granular status is available for CaaS clusters; VMaaS and BMaaS are unchanged.
- When a provisioning stage cannot be determined (e.g., the underlying signal is temporarily unavailable), the cluster surfaces an explicit "stage unknown" state rather than a stale or misleading stage.

## Non-Functional Requirements

- **Freshness:** the status shown reflects the cluster's actual state within a bounded, documented time - on the order of seconds, not minutes - so users are not misled by stale status. (The exact bound is defined in the design EP.)
- **Consistency:** the API, CLI, and UI report the same status for the same cluster at a given point in time.
- **No regression:** adding granular status does not degrade the latency or reliability of existing cluster status behavior.

---

## Provenance

Authored: manual-edit [manual] @ prd 0.8.0 - 7efcedb (dirty), workspace main @ 43c34a8
Phases: draft, manual-edit

<!-- ai-workflow-provenance:{"schema_version":1,"provenance_kind":"session","workflow":"prd","workflow_version":"0.8.0","ai_workflows":"7efcedb (dirty)","source_repo":"43c34a8","source_repo_branch":"main","commits_behind_main":null,"commits_ahead_main":null,"main_ref":"main","phases":["draft","manual-edit"],"authoring_modes":["manual","skill"],"context_changed":false,"origin_untracked":false} -->
