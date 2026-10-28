# OSAC Provisioning for Multi-Tenant AI Grid Infrastructure

| Field       | Value |
|-------------|-------|
| Author(s)   | Yuval Turgeman |
| Jira        | [OSAC-6435](https://redhat.atlassian.net/browse/OSAC-6435) |
| Date        | 2026-10-26 |

## Problem Statement

Today OSAC can provision a MaaS cluster from its existing template, but it does
not provide an AI Grid — the multi-cluster fabric that serves models to tenants
for inference, built as a hub with attached spoke clusters. The AI Grid MVP
exists outside OSAC and requires the Cloud Provider Admin to separately create
the hub, register clusters with ACM, install the AI Grid, and attach inference
capacity. None of it is represented in an OSAC provisioning workflow, so every
AI Grid deployment is a bespoke manual exercise and the provider cannot add
inference capacity on demand.

OSAC is the platform that provisions the clusters; the AI Grid MVP is deployed
on top of them and keeps everything it provides today, including its
tenant-facing experiences.

## In Scope

- Cloud Provider Admin provisioning of the AI Grid Hub — the single ACM/GitOps
  hub shared across tenants — installing ACM, GitOps, and the existing AI Grid
  MVP GitOps applications, ACM policies, backend, and frontend as one
  OSAC-initiated operation.
- OSAC provisioning of spoke clusters — CaaS clusters with GPU-equipped worker
  nodes — attached to the hub automatically as a post-install step, with no
  separate operator action.
- Cloud Provider Admin access to provisioning and status through both the OSAC
  UI and API/CLI.
- ACM and GitOps installation and reconciliation of the AI software stack on
  attached spokes, reusing the existing MVP day-2 model.
- OSAC lifecycle visibility: hub provisioned, spoke provisioned, and spoke
  attached.

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

- As a Cloud Provider Admin, I want to see whether the hub and each attached
  spoke are ready so that I know when the spoke has joined the grid.

- As a Cloud Provider Admin, I want to provision the hub and spokes and check
  status through both the OSAC UI and API/CLI so that the workflow supports
  interactive and automated operation.

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

## Dependencies

- **Existing AI Grid MVP:** assumed to exist and be deployable — its GitOps
  applications, ACM policies, backend, and frontend. OSAC deploys it unchanged
  and does not own its development or release.
- **AI Grid backend:** performs the attachment workflow and accepts
  OSAC-provisioned spokes; OSAC calls it as a post-install step once a spoke
  is provisioned.
- **ACM and GitOps:** the multicluster management layer the hub depends on, and
  the owner of AI software installation on attached spokes.
- **OSAC-6488:** introduces the provider-level `WorkloadCluster` resource for
  clusters serving AI workloads, and anticipates CaaS-provisioned clusters
  using the same shape. Whether an attached spoke becomes a `WorkloadCluster`
  is a design decision shared with that Feature. Attaching imported clusters
  to the AI Grid is deferred to a follow-up; owner TBD.
- **OSAC-6432:** delivers the Cloud Provider Admin UI/API surfaces, including
  status reporting and the tenant endpoint and authentication handoff.
- **GPU capacity:** a supported CaaS path supplying worker nodes with the
  required GPU hardware.

## Open Questions

### 1. AI software readiness signal

Should OSAC expose an `AI software ready` state beyond `spoke attached`, and
which AI Grid MVP signals would establish it?

- **Owner:** OSAC-6432 / AI Grid integration
- **Impact:** Whether the Cloud Provider Admin can tell from OSAC that an
  attached spoke can serve inference, or only that it was attached.

### 2. Attachment failure and retry behavior

When the post-install attachment step fails or the AI Grid backend rejects the
spoke, what does OSAC report and what recovery is available? The spoke exists
and is provisioned, but is not part of the grid.

- **Owner:** AI Grid backend and OSAC integration
- **Impact:** Failure visibility, and whether attachment is retryable without
  re-provisioning the spoke.

### 3. Spoke cluster prerequisites

Which storage, networking, GPU driver and runtime, and related prerequisites
must be present on a GPU spoke cluster before ACM/GitOps can make it an AI
workload cluster?

- **Owner:** OSAC CaaS and AI Grid integration
- **Impact:** Whether these are provided by CaaS, configured by the hub's
  ACM/GitOps policies, or added to OSAC scope.

### 4. Where the AI Grid Hub runs

Does OSAC provision a new cluster for the AI Grid Hub, or install ACM, GitOps,
and the MVP components onto an existing OSAC cluster?

- **Owner:** OSAC architecture and AI Grid integration
- **Impact:** Whether the Cloud Provider Admin orders a new cluster or enables
  the AI Grid on one that already exists, and whether a spoke ends up
  registered with two management planes or one.

---

## Provenance

Authored: draft @ prd 0.11.5 - e2b0d87, workspace main @ f0a8211
Final: revise @ prd 0.11.5 - 7b2b8de, workspace main @ f0a8211

> Context changed between draft and revise.

<!-- ai-workflow-provenance:{"schema_version":1,"provenance_kind":"session","workflow":"prd","workflow_version":"0.11.5","ai_workflows":"7b2b8de","source_repo":"f0a8211","source_repo_branch":"main","commits_behind_main":0,"commits_ahead_main":0,"main_ref":"main","phases":["draft","revise","revise","revise","revise","revise","revise","revise","revise","revise","revise","revise","revise","revise","revise","revise","revise","revise","revise","revise","revise","revise","revise","revise","revise","revise","revise","revise"],"authoring_modes":["skill"],"context_changed":true,"origin_untracked":false} -->
