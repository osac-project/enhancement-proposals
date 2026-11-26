# OSAC Provisioning for Multi-Tenant AI Grid Infrastructure

| Field       | Value |
|-------------|-------|
| Author(s)   | Yuval Turgeman |
| Jira        | [OSAC-6435](https://redhat.atlassian.net/browse/OSAC-6435) |
| Date        | 2026-10-26 |

## Problem Statement

Today OSAC can provision a MaaS cluster from its existing template: model
serving on a single cluster, with per-tenant gateways and subscription
tiers. What it cannot do is provide an AI Grid — the multi-cluster
fabric that serves models to tenants for inference, built as a hub with
attached spoke clusters. The AI Grid MVP
exists outside OSAC and requires the Cloud Provider Admin to separately create
the hub, register clusters with ACM, install the AI Grid, and attach inference
capacity. None of it is represented in an OSAC provisioning workflow, so every
AI Grid deployment is a bespoke manual exercise and the provider cannot add
inference capacity on demand.

OSAC is the platform that provisions the clusters; the AI Grid MVP is deployed
on top of them and keeps everything it provides today, including its
tenant-facing experiences.

![AI Grid topology on OSAC](assets/ai-grid-topology.png)

The Cloud Provider Admin provisions the hub and workload clusters through
OSAC, which asks the AI Grid Backend to attach them. The grid then installs
the AI stack on attached clusters, and tenants reach the inference API they
serve. Gateways and request routing within the grid are owned by the existing
AI Grid, not by OSAC.

## In Scope

- Cloud Provider Admin provisioning of the AI Grid Hub — the single ACM/GitOps
  hub shared across tenants — installing ACM, GitOps, and the existing AI Grid
  MVP GitOps applications, ACM policies, backend, and frontend as one
  OSAC-initiated operation. The AI Grid hub is distinct from the OSAC hub that
  provisions clusters; whether they share a cluster is a design decision,
  provided it states who owns the hub's lifecycle, what an AI Grid upgrade
  does to anything else running there, and how a hub failure is isolated.
  Whatever the placement, the Cloud Provider Admin can provision, monitor and
  recover the shared hub without disrupting unrelated OSAC workloads. OSAC
  does not install ACM today; provisioning the AI Grid hub is what adds it.
- OSAC provisioning of spoke clusters — CaaS clusters with GPU-equipped worker
  nodes — attached to the hub automatically after provisioning, with no
  separate operator action.
- Cloud Provider Admin access to provisioning and status through both the OSAC
  UI and API/CLI. Hub and spoke provisioning, and their infrastructure status,
  are visible to Cloud Provider Admins only.
- ACM and GitOps install the AI software stack on attached spokes and keep it
  current, using the existing MVP components.
- OSAC lifecycle visibility: hub provisioned, spoke provisioned, spoke
  attached, and attachment failed. OSAC retries recoverable attachment
  failures automatically. A failure needing intervention stays visible as a
  provisioned spoke with the reason and the required action; attachment
  resumes once the cause is corrected, without reprovisioning. A cluster that
  fails during provisioning never reaches these states; it is reported through
  the CaaS provisioning status OSAC already exposes.
- OSAC reports attachment, not inference readiness. No trustworthy AI Grid
  readiness signal is available today, so inference-readiness visibility is
  deferred rather than approximated from `spoke attached`.
- Spokes provisioned here and clusters imported through OSAC-6488 appear in
  one provider capacity inventory, so the provider sees a single view of AI
  capacity however a cluster arrived. This increment populates that inventory
  with the clusters OSAC provisions; clusters imported through OSAC-6488 join
  it when that handoff lands. How each is represented is a design decision.

## Out of Scope

- Implementing or redesigning the existing AI Grid/MaaS product — tenant-facing
  model catalog, subscription, API key, inference, usage, and billing
  capabilities, or its policies, backend, and frontend. OSAC deploys these
  components unchanged.
- Adding imported clusters to the AI Grid through OSAC-6488, or redesigning the
  import flow.
- Routing tenants from OSAC into the AI Grid — redirects, proxies, deep links,
  or authentication handoff from the OSAC console. Ownership of that handoff
  is an API-surface question expected to be covered by OSAC-6432.
- Enforcing tenant isolation for model access, subscriptions, and usage; the
  AI Grid/MaaS components own that enforcement.
- Removing the existing `ocp_4_20_ai_maas` template as part of this work; it is
  slated for removal once the replacement path works.
- Dedicated per-tenant AI Grid hubs, tenant-specific inference clusters, or
  private inference capacity.
- Detailed OSAC UI/API surface design for these workflows; OSAC-6432 owns it.
- Replacing ACM and GitOps for in-grid configuration and day-2 operations.
  OSAC does not manage resources inside the grid after spokes are attached.
  Grouping attached spokes for placement and isolation is owned by the AI
  Grid/ACM layer.
- Deprovisioning: removing a spoke from the grid, or tearing the hub down.
  This increment covers standing capacity up; teardown is a later increment.
- Detailed bootstrap sequencing, policy values, and application configuration
  for the AI Grid Hub; those belong in the design phase.

## User Stories

### Cloud Provider Admin

- As a Cloud Provider Admin, I want to provision the AI Grid Hub through OSAC
  so that ACM, GitOps, and the AI Grid MVP components are installed for me
  instead of by hand.

- As a Cloud Provider Admin, I want to provision spoke clusters with
  GPU-equipped worker nodes and have them attached to the hub automatically so
  that I can grow inference capacity in one step.

- As a Cloud Provider Admin, I want to see the hub and spoke lifecycle states
  so that I know when a spoke has joined the grid, and when one was provisioned
  but failed to attach.

- As a Cloud Provider Admin, I want to provision the hub and spokes and check
  status through both the OSAC UI and API/CLI so that the workflow supports
  interactive and automated operation.

### Cloud Infrastructure Admin

- As a Cloud Infrastructure Admin, I want the prerequisites a spoke cluster
  must meet to be explicit, so that I can prepare storage, networking and GPU
  capacity before clusters are provisioned.

### Tenant Admin / Tenant User

These confirm that the AI Grid OSAC deploys serves tenants as the existing MVP
does. OSAC does not build these capabilities.

- As a Tenant Admin, I want to assign model subscriptions to my users on an
  OSAC-provisioned AI Grid so that my organization can consume shared
  inference capacity.

- As a Tenant User, I want to run inference against my organization's models
  on an OSAC-provisioned AI Grid so that I can use shared capacity without
  knowing which spoke serves me.

## Assumptions

- The AI Grid is shared cloud-provider infrastructure serving multiple
  tenants.
- ACM and GitOps are required in order to reuse the existing AI Grid MVP and
  its day-2 management model.
- The Cloud Infrastructure Admin prepares the underlying storage, networking
  and GPU capacity outside OSAC. The Cloud Provider Admin then selects from
  the supported options OSAC offers when provisioning a spoke on it. OSAC
  reports unmet prerequisites to the Cloud Provider Admin, who raises them
  with the infrastructure admin; OSAC does not provision that capacity.

## Dependencies

- **Existing AI Grid MVP:** assumed to exist and be deployable — its GitOps
  applications, ACM policies, backend, and frontend. OSAC deploys it unchanged
  and does not own its development or release.
- **AI Grid backend:** registers a spoke with ACM and attaches it to the grid,
  on request. OSAC makes that request automatically once a spoke is
  provisioned. OSAC does not register clusters with ACM itself.
- **ACM and GitOps:** the multicluster management layer the hub depends on, and
  the owner of AI software installation on attached spokes.
- **OSAC-6488:** introduces the provider-level `WorkloadCluster` resource for
  clusters serving AI workloads, and anticipates CaaS-provisioned clusters
  using the same shape. Whether an attached spoke becomes a `WorkloadCluster`
  is a design decision shared with that Feature. Attaching imported clusters
  to the AI Grid is deferred to a follow-up; owner TBD.
- **OSAC-6432:** delivers the Cloud Provider Admin UI/API surfaces, including
  status reporting and the tenant endpoint and authentication handoff. The
  user stories here depend on it, so OSAC-6432 must land first or alongside;
  this work cannot be delivered to a Cloud Provider Admin without it.
- **GPU capacity:** a supported CaaS path supplying worker nodes with the
  required GPU hardware.

## Open Questions

Inference-readiness visibility and deprovisioning are deferred and recorded in
Out of Scope.

### 1. Tenant endpoint and authentication handoff

OSAC-6432 is expected to cover the tenant endpoint and authentication handoff
into the AI Grid. That has not been confirmed with the Feature's owner.

- **Owner:** OSAC-6432
- **Impact:** If it is not covered there, no Feature owns the handoff and
  tenants have no supported route from OSAC into the grid.

---

## Provenance

Authored: draft @ prd 0.11.5 - e2b0d87, workspace main @ f0a8211
Final: respond @ prd 0.11.5 - 7b2b8de, workspace main @ f0a8211

> Context changed between draft and respond.

<!-- ai-workflow-provenance:{"schema_version":1,"provenance_kind":"session","workflow":"prd","workflow_version":"0.11.5","ai_workflows":"7b2b8de","source_repo":"f0a8211","source_repo_branch":"main","commits_behind_main":0,"commits_ahead_main":0,"main_ref":"main","phases":["draft","revise","revise","revise","revise","revise","revise","revise","revise","revise","revise","revise","revise","revise","revise","revise","revise","revise","revise","revise","revise","revise","revise","revise","revise","revise","revise","revise","respond","respond","respond"],"authoring_modes":["skill"],"context_changed":true,"origin_untracked":false} -->
