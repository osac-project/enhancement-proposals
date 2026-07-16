# Cluster Upgrade — CaaS

| Field      | Value                                                                      |
|------------|----------------------------------------------------------------------------|
| Author(s)  | Vitaliy Emporopulo                                                         |
| Jira       | [OSAC-1415](https://redhat.atlassian.net/browse/OSAC-1415)                 |
| Date       | 2026-07-27                                                                 |

## Problem Statement

OSAC CaaS manages the full cluster lifecycle — creation, scaling, and deletion — but provides no managed path for upgrading a cluster's OpenShift version. Clusters are provisioned via Hosted Control Planes (HCP), where the control plane and worker node pools are independent upgrade targets with distinct ownership and ordering constraints; today neither target has first-class support in the OSAC API. Tenants who need a newer version must interact directly with HCP infrastructure, bypassing OSAC governance entirely: upgrades proceed without organizational oversight, leave no record in OSAC, and are invisible to OSAC's monitoring. As clusters age, the gap compounds: EOL versions lose Red Hat support coverage and security patches, but OSAC has no mechanism to surface upgrade readiness, track version transitions, or enforce upgrade progress.

## In Scope

**Services:** CaaS — OpenShift clusters provisioned by OSAC via Hosted Control Planes.

**Tenant upgrade capabilities:**
- Tenant Users and Tenant Admins can view available upgrade versions for a cluster's control plane and node pools; for both components, versions are sourced from the cluster's own Cincinnati evaluation (only directly reachable versions are surfaced) and filtered by the cluster's update channel
- Available node pool versions are additionally capped at the current control plane version; a node pool cannot be upgraded past the version of its control plane
- Tenant Users and Tenant Admins can initiate a control plane y-stream upgrade to any directly reachable version, one hop at a time
- Tenant Users and Tenant Admins can initiate a node pool upgrade (y-stream or z-stream)
- When the platform identifies risks for a target version, those risks are presented to the user before the upgrade can be initiated; the user must explicitly acknowledge the risks to proceed
- After initiating an upgrade, a short cancellation window allows the user to cancel before the upgrade begins; once the window closes, the upgrade cannot be stopped
- Only one active upgrade per cluster component (control plane or node pool) is permitted at a time

**Upgrade tracking and visibility:**
- Each upgrade is tracked as a discrete record per cluster component, with a stable lifecycle: pending (within cancellation window), running, succeeded, or failed
- Each upgrade record includes the following fields:

  | Field | Description |
  |-------|-------------|
  | Target version | The OpenShift version the upgrade is moving to |
  | Upgrade type | Control plane or node pool |
  | State | Current lifecycle state (pending, running, succeeded, failed) with a human-readable description |
  | Creation timestamp | When the upgrade was initiated |
  | Last update timestamp | When the state last changed |

- Upgrade status and progress are visible through conditions on each upgrade record
- Past upgrades per cluster component are available as a history, recording version transitions and their outcomes; history is tied to the cluster's lifetime and is removed when the cluster is deleted
- Tenant Users and Tenant Admins receive a warning condition on a node pool when it approaches the N-2 minor version skew limit relative to the control plane, so they can initiate a node pool upgrade before the node pool falls out of the supported range

**Platform-managed z-stream upgrades:**
- The Cloud Provider Admin selects the fleet-wide z-stream target version for control plane upgrades and applies it across all clusters via progressive rollout; available z-stream versions are sourced from the cluster's own Cincinnati evaluation, the same mechanism used for tenant-visible upgrade versions
- Z-stream upgrades are triggered on-demand by the Cloud Provider Admin; the regular cadence targets critical CVE remediation within FedRAMP-aligned timelines (High CVEs: 30 days, Medium: 90 days)
- If a z-stream rollout causes a significant regression, the Cloud Provider Admin can pause the rollout and roll back affected control planes
- Tenants cannot select or initiate z-stream control plane upgrades; these are applied automatically by the platform
- Tenant Users and Tenant Admins are notified via resource status conditions when the platform applies a z-stream upgrade to their cluster
- The Cloud Provider Admin can force a control plane y-stream upgrade for a specific cluster at end-of-life; if the forced upgrade fails, the cluster enters a limited-support state (SLA no longer applies, but support remains available)

**User-facing API surfaces:**

| Surface | Change |
|---------|--------|
| Fulfillment API (gRPC and REST) | New upgrade sub-resource per cluster component (control plane and node pool) with full CRUD and status. Available upgrade versions endpoint per cluster component. |
| CLI | Upgrade lifecycle commands: list available versions, initiate upgrade, cancel pending upgrade, view upgrade status, view upgrade history. |
| UI | Upgrade lifecycle actions and history in the cluster detail view. Available versions and risk display before upgrade initiation. Cloud Provider Admin: fleet-wide z-stream target selection and upgrade status monitoring. |

**E2E testing:** E2E coverage for upgrade initiation, status tracking, upgrade history, and pending upgrade cancellation in osac-test-infra.

**Documentation:** User guides for upgrade initiation and monitoring (Tenant User), z-stream upgrade visibility (Tenant Admin), and fleet-wide z-stream management (Cloud Provider Admin).

**Interfaces:** Fulfillment API (gRPC and REST), CLI, and UI console.

## Out of Scope

- SNO and traditional (non-HCP) control plane node upgrades
- Tenant-initiated upgrade rollback — clusters cannot be rolled back by tenants; rollback is a platform-level operation reserved for Cloud Provider Admins
- Maintenance windows and upgrade exclusion windows; scheduled upgrades and maintenance windows are both future work
- One-off scheduled upgrades; upgrades execute immediately upon initiation
- Tenant admin version allowlist; version availability is determined by the cluster's Cincinnati evaluation
- Channel selection; channel is set at cluster creation (OSAC-1269)
- Push notification infrastructure (email, webhook, or external alerting)
- Installation and configuration of the OpenShift Update Service Operator for disconnected environments
- Drift detection; out-of-band version changes are not tracked as a distinct event type
- Upgrade history retention after cluster deletion; history does not outlive the cluster
- Standalone audit trail; full operational auditing is a separate capability
- Custom release image upgrades; users can only select from versions surfaced by the cluster's Cincinnati evaluation
- Upgrade policies per cluster tier; configuring different upgrade rules for dev, staging, and production clusters is deferred
- Cancelling an in-progress upgrade; once the cancellation window closes, the upgrade cannot be stopped

## User Stories

The following diagram shows the tenant-initiated upgrade flow. It applies equally to control plane y-stream upgrades and node pool upgrades.

```mermaid
flowchart TD
    A[User requests available upgrade versions] --> B[Platform returns versions\nwith associated risks]
    B --> C{Risks identified\nfor target version?}
    C -- Yes --> D[User acknowledges risks\nin upgrade request]
    C -- No --> E[Upgrade initiated]
    D --> E
    E --> F[Cancellation window opens]
    F --> G{User cancels\nwithin window?}
    G -- Yes --> H[Upgrade record: cancelled]
    G -- No --> I[Upgrade begins]
    I --> J{Outcome}
    J -- Succeeded --> K[Upgrade record: succeeded]
    J -- Failed --> L[Upgrade record: failed\nwith details]
```

### Tenant User

- As a Tenant User, I want to view the available upgrade versions for my cluster's control plane and node pools, including any known risks per version, so that I can make an informed upgrade decision.
- As a Tenant User, I want to initiate a control plane y-stream upgrade for my cluster, acknowledging any identified risks, so that I can keep my cluster's OpenShift version current.
- As a Tenant User, I want to initiate a node pool upgrade for my cluster — acknowledging any identified risks — so that my worker nodes run a supported OpenShift version.
- As a Tenant User, I want to cancel an upgrade I initiated before it starts, so that I can correct a mistake within the cancellation window.
- As a Tenant User, I want to monitor the status and progress of an in-progress upgrade through resource conditions, so that I can track when the upgrade completes or fails.
- As a Tenant User, I want to see a warning condition when a node pool is approaching the N-2 minor version skew limit relative to the control plane, so that I can initiate a node pool upgrade before it falls out of the supported range.
- As a Tenant User, I want to view the upgrade history for my cluster, so that I can see which version transitions have occurred and their outcomes.
- As a Tenant User, I want to be notified via a status condition when the platform applies a z-stream upgrade to my cluster, so that I am aware of platform-managed changes to my cluster's version.

### Tenant Admin

- As a Tenant Admin, I want to view the available upgrade versions for each cluster's control plane and node pools within my organization, so that I can plan and coordinate upgrades across my teams.
- As a Tenant Admin, I want to initiate a control plane y-stream upgrade for any cluster in my organization — acknowledging any identified risks — so that I can manage the OpenShift version lifecycle on behalf of my organization.
- As a Tenant Admin, I want to initiate a node pool upgrade for any cluster in my organization — acknowledging any identified risks — so that worker nodes remain within a supported version range.
- As a Tenant Admin, I want to cancel an upgrade I initiated before it starts, so that I can correct a mistake within the cancellation window.
- As a Tenant Admin, I want to view the upgrade history for any cluster in my organization, so that I can see which version transitions have occurred and their outcomes.
- As a Tenant Admin, I want to be notified via a status condition when the platform applies a z-stream upgrade to a cluster in my organization, so that I have visibility into platform-managed changes affecting my clusters.

### Cloud Provider Admin

- As a Cloud Provider Admin, I want to select and publish the fleet-wide z-stream target version for control plane upgrades, so that all managed clusters run a consistent, supported patch version without requiring tenant action.
- As a Cloud Provider Admin, I want to monitor control plane upgrade status across all clusters, so that I can detect stalled or failed upgrades and intervene.
- As a Cloud Provider Admin, I want to force a control plane y-stream upgrade for a specific cluster approaching end-of-life, so that the platform can maintain supportability independently of tenant scheduling.

## Dependencies

- **OSAC-1269** (Managed Cluster Versions): must be complete before OSAC-1415 ships; provides cluster channel assignment at creation time, which determines the Cincinnati update graph used by this feature.
- **Cincinnati / OpenShift Update Service**: source of available upgrade versions and per-version risk data, read from each cluster's own evaluation. In disconnected environments, the OpenShift Update Service Operator must be pre-configured as a prerequisite.
- **HCP (HostedCluster + NodePool)**: source of upgrade state, conditions, and history; the design will confirm the specific HyperShift API surface used.

## Open Questions

### Q1: Cancelled as a lifecycle state

ROSA includes `cancelled` as a transient lifecycle state — when a user cancels a pending upgrade, the record transitions to `cancelled` before being removed. Should OSAC follow this pattern (cancelled as a transient state before record removal), or should cancellation simply delete the pending record with no intermediate state?

**Owner:** CaaS team
**Impact:** Upgrade record lifecycle definition; API behavior on cancellation.

---

## Provenance

Authored: draft @ prd 0.6.0 - 139e6c1, workspace main @ 411e256
Final: revise @ prd 0.6.1 - 96de078, workspace main @ 7b4fff2

> Context changed between draft and revise.

<!-- ai-workflow-provenance:{"schema_version":1,"provenance_kind":"session","workflow":"prd","workflow_version":"0.6.1","ai_workflows":"96de078","source_repo":"7b4fff2","source_repo_branch":"main","commits_behind_main":0,"commits_ahead_main":0,"main_ref":"main","phases":["draft","revise","revise","revise","revise","revise","revise","revise","revise"],"authoring_modes":["skill"],"context_changed":true} -->
