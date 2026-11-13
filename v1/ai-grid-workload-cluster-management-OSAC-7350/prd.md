# Cloud Provider API for AI Grid Hub Selection and Workload Cluster Management

| Field       | Value |
|-------------|-------|
| Author(s)   | Ganesh Murthy |
| Jira        | [OSAC-7350](https://redhat.atlassian.net/browse/OSAC-7350) |
| Date        | 2026-11-06 |

## Problem Statement

OSAC's CaaS Cluster API represents tenant-owned clusters and does not provide
Cloud Provider Admins a provider-scoped way to establish or manage AI Grid on
provider-owned workload clusters. These clusters host inference services
offered to tenants, who consume them through endpoints rather than accessing
the clusters. For v1, the CPA establishes an empty AI Grid by designating an
existing OSAC hub and onboarding its already-imported workload clusters.
Without this workflow, CPAs cannot use OSAC to organize and manage the
provider clusters used for tenant inference. [Jira: OSAC-7350]

## In Scope

- **Service:** MaaS, for provider-managed AI Grid workload clusters that host
  inference for tenants. Tenant CaaS cluster resources remain separate.
  [Jira: OSAC-7350] [User]
- **Hub designation and replacement:** Through the API and CLI, the CPA can
  list all registered OSAC hubs and designate one as the AI Grid hub. If none
  are registered, the list is empty. Only one hub is designated at a time,
  but the CPA can remove it, re-add it, or designate another hub. V1
  establishes one Grid; the API and CLI associate workload clusters and
  operations with a Grid so they can address one or more Grids.
  [Jira: OSAC-7350] [Clarify: R1.Q1, R1.Q2, R2.Q1, R1.Q5, R4.Q1]
- **Hub setup visibility:** Hub designation does not install AI Grid
  components. A separate setup process performs installation; the CPA can
  see whether setup is pending, ready, or failed, with an actionable reason
  for failure. [Clarify: R3.Q1, R3.Q2]
- **Workload inventory:** The CPA can list the workload clusters already
  imported into OSAC and associated with the designated hub, including
  clusters not yet enrolled in AI Grid. The CPA can see each cluster's name,
  location, connection state, AI Grid membership, role, provisioning state,
  OpenShift and Kubernetes versions, and available compute and GPU
  information. An unavailable OpenShift version is shown as “Not reported.”
  [Jira: OSAC-7350] [Clarify: R2.Q2]
- **AI Grid membership and roles:** The CPA can add a workload cluster to
  AI Grid and update its role and location. Adding a cluster requires a
  CPA-entered free-text location. Clusters need not be Ready to be added;
  connection state and AI Grid provisioning are shown separately. The CPA
  can use Ingress, Inference, or Combined roles. [Jira: OSAC-7350]
  [Clarify: R1.Q3]
- **Provisioning and placement readiness:** The CPA can see whether a
  workload cluster's AI Grid setup is still in progress or needs attention.
  Only Available, fully provisioned Inference or Combined clusters are
  eligible for model placement; Ingress-only clusters are not model targets.
  [Jira: OSAC-7350]
- **Safe workload-cluster role changes and removal:** Changing a workload
  cluster's role or removing that cluster from AI Grid is blocked with a
  clear explanation when existing model placements or subscriptions make
  the change unsafe. A cluster with placed models cannot leave AI Grid or
  stop serving inference until the models are moved, even if a model has
  another placement. An Ingress or Combined cluster cannot stop serving
  ingress while subscriptions exist, or leave the remaining Grid without an
  ingress-capable cluster. [Jira: OSAC-7350] [Clarify: R1.Q4]
- **Removal behavior:** Removing a cluster removes its AI Grid membership,
  but does not delete the OSAC workload-cluster resource or underlying
  provider-owned cluster, and does not uninstall OpenShift AI. Model
  placements and subscriptions are not automatically moved or deleted;
  whole-model deletion remains blocked while a subscription references it.
  [Jira: OSAC-7350]
- **Hub removal behavior:** The CPA can remove or replace the designated hub
  even when its workload clusters have model placements or subscriptions.
  Those workload clusters remain imported into OSAC but leave AI Grid. Model
  placements and subscriptions are not automatically moved or deleted. The
  CPA sees a warning and must explicitly confirm hub removal because Grid
  workloads may be disrupted. [Clarify: R4.Q1, R4.Q2, R4.Q3]
- **Access:** Only authorized Cloud Provider Admins can use these API and
  CLI capabilities. Tenant access to the CaaS Cluster API does not grant
  access to provider-owned workload clusters. [Jira: OSAC-7350]

## Out of Scope

- Implementing a UI for these capabilities. [Jira: OSAC-7350]
- Installing AI Grid hub components; this is handled by the separate hub
  setup process. [Clarify: R3.Q1]
- Importing OSAC hubs or workload clusters, or importing a hub whose workload
  clusters are already AI Grid members. [Jira: OSAC-7350]
- Provisioning or deleting the underlying provider-owned workload-cluster
  infrastructure. [Jira: OSAC-7350]
- Automatically moving or deleting model placements or subscriptions when
  roles change, workload clusters leave AI Grid, or a hub is removed.
  [Jira: OSAC-7350] [Clarify: R4.Q2]
- Changing the tenant-facing CaaS Cluster API or giving tenants direct access
  to provider-owned workload clusters. [Jira: OSAC-7350]
- Uninstalling OpenShift AI when a workload cluster leaves AI Grid.
  [Jira: OSAC-7350]

## User Stories

### Cloud Provider Admin

- As a Cloud Provider Admin, I want to select an existing OSAC hub and see
  whether AI Grid setup succeeds, so that I can establish the v1 Grid and
  begin onboarding its workload clusters. [Jira: OSAC-7350]
- As a Cloud Provider Admin, I want to remove and re-add or replace the
  designated hub, so that I can redirect Grid management to another OSAC hub.
  [Clarify: R4.Q1]
- As a Cloud Provider Admin, I want to review the imported workload clusters
  and their membership, role, location, availability, and provisioning
  status and version information, so that I can identify which clusters are
  ready for AI Grid use. [Jira: OSAC-7350]
- As a Cloud Provider Admin, I want to add workload clusters to AI Grid with
  the appropriate role and location, so that provider clusters can serve
  their intended inference or ingress functions. [Jira: OSAC-7350]
- As a Cloud Provider Admin, I want unsafe workload-cluster role changes and
  removals to be blocked with a clear explanation, so that existing model
  deployments, subscriptions, and inference access are protected.
  [Jira: OSAC-7350]
- As a Cloud Provider Admin, I want a clear warning and confirmation before
  removing a hub whose workload clusters have model placements or
  subscriptions, so that I understand the impact before their Grid membership
  is detached. [Clarify: R4.Q2, R4.Q3]

## Requirements

### Functional Requirements

- **FR-1:** CPAs must be able to list registered OSAC hubs and designate one
  as the AI Grid hub. When none are registered, the list is empty. V1 has one
  active Grid; the API scopes operations by Grid so it can support one or
  more Grids. The CPA can remove and re-add or replace the designated hub.
  [Jira: OSAC-7350] [Clarify: R1.Q1, R1.Q2, R2.Q1, R4.Q1]
- **FR-2:** After hub designation, CPAs must be able to see whether hub setup
  is pending, ready, or failed, including an actionable reason on failure.
  [Clarify: R3.Q1, R3.Q2]
- **FR-3:** CPAs must be able to list the workload clusters associated with
  the selected hub, including clusters not yet enrolled in AI Grid, and view
  their name, location, connection state, membership, role, provisioning
  status, versions, and reported compute/GPU information. [Jira: OSAC-7350]
- **FR-4:** CPAs must be able to add workload clusters with a role and
  required free-text location, then update their role and location. Adding
  is allowed regardless of connection readiness. [Jira: OSAC-7350]
  [Clarify: R1.Q3]
- **FR-5:** AI Grid roles are Ingress, Inference, and Combined. Only Available,
  fully provisioned Inference or Combined clusters are eligible for model
  placement; Ingress-only clusters are not model targets. [Jira: OSAC-7350]
- **FR-6:** Unsafe role changes and spoke removals must be blocked with a
  clear explanation when models, subscriptions, or the Grid's remaining
  ingress capability would be affected. Admins must resolve placements or
  subscriptions first; the API does not automatically clean them up.
  [Jira: OSAC-7350] [Clarify: R1.Q4]
- **FR-7:** CPAs can remove or replace the designated hub after an impact
  warning and explicit confirmation. Its workload clusters remain imported
  into OSAC but leave AI Grid, even if they have model placements or
  subscriptions; those are not automatically moved or deleted.
  [Clarify: R4.Q1, R4.Q2, R4.Q3]

### Non-Functional Requirements

- **NFR-1:** Workload-cluster management operations are restricted to
  authorized Cloud Provider Admins. [Jira: OSAC-7350]

## Dependencies

- OSAC has registered hubs and imported workload clusters available for the
  CPA to select and manage. [Jira: OSAC-7350]
- A separate hub-setup process installs/configures AI Grid components and
  provides setup status and failure reasons that the CPA can view.
  [Clarify: R3.Q1, R3.Q2]
- AI Grid model-placement and subscription information is available so the
  API and CLI can block unsafe workload-cluster role changes/removals and warn
  before hub removal. [Jira: OSAC-7350] [Clarify: R4.Q2, R4.Q3]

---

## Provenance

Authored: draft @ prd 0.11.5 - 7b2b8de, workspace main @ 2753cc412
Final: revise @ prd 0.11.5 - 7b2b8de, workspace main @ 28ec02f8d

> Context changed between draft and revise.

<!-- ai-workflow-provenance:{"schema_version":1,"provenance_kind":"session","workflow":"prd","workflow_version":"0.11.5","ai_workflows":"7b2b8de","source_repo":"28ec02f8d","source_repo_branch":"main","commits_behind_main":0,"commits_ahead_main":861,"main_ref":"main","phases":["draft","revise","revise","revise","revise","revise","revise","revise","revise","revise"],"authoring_modes":["skill"],"context_changed":true,"origin_untracked":false} -->
