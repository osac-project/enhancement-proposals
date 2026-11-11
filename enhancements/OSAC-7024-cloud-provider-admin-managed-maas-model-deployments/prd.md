# MaaS Model Management Through OSAC

| Field       | Value |
|-------------|-------|
| Author(s)   | Ganesh Murthy |
| Jira        | [OSAC-7024](https://redhat.atlassian.net/browse/OSAC-7024) |
| Date        | 2026-10-29 |

## 1. Problem Statement

An AI Grid starts with no models in the OSAC-managed MaaS model list. OSAC needs to provide a governed UI, CLI, and API workflow for Cloud Provider Admins to manage these models. [Jira: OSAC-7024]

## 2. Goals and Non-Goals

### 2.1 Goals

- Cloud Provider Admins can manage MaaS models through the OSAC UI, CLI, and API on OpenShift clusters that host the models' inference workloads. [Clarify: R1.Q1, R1.Q2]
- Cloud Provider Admins can place models on selected AI Grid inference clusters and see deployment status for each placement and MaaS status on ingress clusters. [Clarify: R4.Q1, R4.Q2, R10.Q1, R11.Q1]

### 2.2 Non-Goals

- Provisioning or importing clusters, or installing the AI Grid, RHOAI, or MaaS. This feature manages models on already-onboarded clusters. [Jira: OSAC-7024] [Clarify: R5.Q1]
- Managing MaaS subscriptions, authorization policies, API keys, or inference requests. [Jira: OSAC-7024]
- Tenant-facing model discovery and access; existing MaaS subscription behavior continues to govern which models tenants can use. [Clarify: R11.Q1]
- V1 does not support registering or managing externally hosted models; it manages models deployed to AI Grid inference clusters. [Clarify: R1.Q2, R2.Q1]
- Maintaining a historical model list after a model and all its deployments are deleted. Whole-model deletion removes the model from the OSAC-managed model list and is blocked while any subscription references it. [Clarify: R1.Q5]
- Per-cluster validation that a selected cluster has sufficient compute resources for a model's requested per-replica resources. V1 presents inference-capable, available, and provisioned AI Grid clusters as placement candidates and reports observed deployment status after saving. Administrators may use GitOps directly for heterogeneous placements outside this managed workflow. [Clarify: R10.Q1]

## 3. User Stories

### Cloud Provider Admin

- As a Cloud Provider Admin, I want to view a model's configuration, selected
  cluster placements, and current deployment and MaaS status, so that I can
  understand what is running and where it is available.

- As a Cloud Provider Admin, I want to deploy a MaaS model to specific
  inference-capable AI Grid clusters that I select, so that I can choose where
  the model runs.
- As a Cloud Provider Admin, I want to see a model's overall status, deployment
  status on selected inference clusters, and MaaS status on ingress clusters,
  so that I can understand where it runs and is available.
- As a Cloud Provider Admin, I want to add or remove compute resources for a
  running model, so that I can adjust its serving scale and resource allocation.
- As a Cloud Provider Admin, I want to remove a model deployment from one or
  more selected clusters where it is installed, so that I can adjust its
  placement while the model remains deployed on at least one cluster.
- As a Cloud Provider Admin, I want to delete a model and all its deployments
  when no subscription references it, so that I can retire the model offering.

## 4. Requirements

### 4.1 Functional Requirements

Cloud Provider Admin model-management capabilities in FR-1 through FR-5 must be available through the UI, CLI, and API. [Clarify: R1.Q1]

- **FR-1:** Cloud Provider Admins must be able to list MaaS model deployments and view model details. [Clarify: R1.Q1, R1.Q2]
- **FR-2:** Cloud Provider Admins must be able to select a model source and inference name, configure supported serving-scale and per-replica compute resources, and create a deployment on existing clusters. After creation, the model source, serving runtime, and model identity (including the inference name) cannot be changed; changing them requires a new deployment. Admins must be able to add or remove compute resources for a running model, including supported serving-scale changes (such as replica count) and changes to per-replica CPU, memory, or GPU resources. Serving-scale changes do not interrupt inference; changes to per-replica resources may restart the model and interrupt inference. Advanced capabilities such as LoRA adapters, confidential compute, and KV-cache offloading are not independently configurable per-model options in v1. Request routing follows the existing MaaS configuration. The platform determines workload placement within each selected cluster and applies changes using its default rollout behavior; CPAs cannot configure per-model routing policies, pod-placement rules, or rollout strategies in v1. The design doc defines the compute-resource options. [Jira: OSAC-7024, Clarify: R1.Q3, R6.Q1, R8.Q1, R9.Q1]
- **FR-3:** Cloud Provider Admins must be able to retrieve AI Grid placement-cluster candidates and select one or more clusters for a model. Candidates are onboarded AI Grid clusters configured to run inference (inference or combined role) and reported as available and provisioned. This platform-readiness list does not assess whether requested compute resources fit a selected cluster; V1 does not perform that per-cluster validation before saving. After saving, OSAC reports the observed deployment status on each selected cluster (FR-5). The model is deployed only to selected clusters; locations may provide context but do not determine placement. [Clarify: R4.Q1, R5.Q1, R10.Q1]
- **FR-4:** Cloud Provider Admins must be able to remove a model deployment from one or more selected clusters where it is installed, provided at least one deployment remains. From the Admin's perspective, the removed placements are removed immediately; a subscription reference does not block removing an individual placement. Removing the final deployment requires deleting the whole model, which removes it and all its deployments from the OSAC-managed model list. OSAC must block whole-model deletion while any subscription references the model and explain why. Subscription saves and whole-model deletions must be coordinated so a concurrent save cannot leave a subscription referencing a deleted model; if the operations conflict, the operation that cannot proceed must return a clear conflict response. [Clarify: R1.Q5, R12.Q1]
- **FR-5:** Cloud Provider Admins must be able to see overall model status, deployment status for each selected inference cluster, and MaaS publication/routing status for each ingress cluster. Status reflects observed platform reports after saving and includes any available reason or message; it is not a pre-save model-to-cluster compatibility assessment. Overall status is ready when every selected deployment and every ingress-cluster MaaS registration is ready, with at least one ingress cluster. Overall status is partial when every ingress-cluster MaaS registration is ready and at least one, but not all, selected deployments are ready. [Clarify: R4.Q2, R10.Q1, R11.Q1]

**Partial-placement scenario:** A Cloud Provider Admin selects inference clusters A and B. If A's inference deployment is ready and B's is not, while MaaS is ready on the ingress cluster or clusters, the Admin sees each deployment's status and the separate ingress status; overall status is partial. The scenario covers provider-facing model status only; tenant discovery and access follow existing MaaS subscription behavior and are outside this feature.

### 4.2 Non-Functional Requirements

- **NFR-2:** Model-management operations must be restricted to authorized Cloud Provider Admins. [Jira: OSAC-7024]

## 5. Dependencies

- Target clusters are already provisioned or imported and onboarded to the AI Grid, with RHOAI and MaaS installed and available. [Jira: OSAC-7024] [Clarify: R5.Q1]
- AI Grid provides placement-cluster candidates based on onboarding, inference-capable role, and reported availability and provisioning readiness. [Clarify: R4.Q1, R5.Q1, R10.Q1]

---

## Provenance

Authored: revise @ prd 0.11.5 - 7b2b8de, workspace main @ 2753cc412
Phases: draft, respond, respond, respond, respond, respond, respond, respond, respond, respond, respond, respond, respond, respond, respond, respond, respond, respond, respond, respond, respond, respond, respond, respond, respond, respond, respond, respond, respond, respond, respond, respond, respond, respond, respond, respond, respond, respond, respond, respond, respond, respond, respond, respond, respond, respond, respond, respond, respond, respond, respond, respond, revise, revise, revise, revise, revise, revise, revise

<!-- ai-workflow-provenance:{"schema_version":1,"provenance_kind":"session","workflow":"prd","workflow_version":"0.11.5","ai_workflows":"7b2b8de","source_repo":"2753cc412","source_repo_branch":"main","commits_behind_main":0,"commits_ahead_main":579,"main_ref":"main","phases":["draft","respond","respond","respond","respond","respond","respond","respond","respond","respond","respond","respond","respond","respond","respond","respond","respond","respond","respond","respond","respond","respond","respond","respond","respond","respond","respond","respond","respond","respond","respond","respond","respond","respond","respond","respond","respond","respond","respond","respond","respond","respond","respond","respond","respond","respond","respond","respond","respond","respond","respond","respond","revise","revise","revise","revise","revise","revise","revise"],"authoring_modes":["skill"],"context_changed":false,"origin_untracked":false} -->
