# MaaS Model Management Through OSAC

| Field       | Value |
|-------------|-------|
| Author(s)   | Ganesh Murthy |
| Jira        | [OSAC-7024](https://redhat.atlassian.net/browse/OSAC-7024) |
| Date        | 2026-10-29 |

## 1. Problem Statement

An AI Grid starts with no MaaS models registered in its catalog. OSAC needs to provide a governed UI, CLI, and API workflow for Cloud Provider Admins to manage these models. [Jira: OSAC-7024]

## 2. Goals and Non-Goals

### 2.1 Goals

- Cloud Provider Admins can manage MaaS models through the OSAC UI, CLI, and API on OpenShift clusters that host the models' inference workloads. [Clarify: R1.Q1, R3.Q1]
- Cloud Provider Admins can place models on selected eligible clusters and see overall and per-cluster readiness. [Clarify: R4.Q1, R4.Q2]
- Tenant users can discover and use models made available to them under existing MaaS subscription rules. [Jira: OSAC-7024]

### 2.2 Non-Goals

- Provisioning or importing clusters, or installing the AI Grid, RHOAI, or MaaS. This feature manages models on already-onboarded clusters. [Jira: OSAC-7024] [Clarify: R5.Q1]
- Managing MaaS subscriptions, authorization policies, API keys, or inference requests. [Jira: OSAC-7024]
- Registering externally hosted models through this day-2 Models API. Existing day-0 external-model provisioning workflows are unchanged. [Clarify: R2.Q1, R3.Q1]

## 3. User Stories

### Cloud Provider Admin

- As a Cloud Provider Admin, I want to list and inspect MaaS model
  deployments, so that I can review the models in my environment.

- As a Cloud Provider Admin, I want to deploy a MaaS model to specific
  eligible clusters that I select, so that I can choose where the model is
  offered.
- As a Cloud Provider Admin, I want to see a model's overall readiness and
  readiness on its selected clusters, so that I can understand where it is
  ready. The exact status labels and aggregation rules remain under discussion.
- As a Cloud Provider Admin, I want to update a model's metadata and
  capacity, so that I can maintain its offering.
- As a Cloud Provider Admin, I want to remove a model when it is not
  referenced by an active MaaS subscription, so that I can retire offerings
  that are no longer needed.

### Tenant User

- As a Tenant User, I want to discover and use models available under my
  MaaS subscription, so that I can access the models I'm authorized to use.

## 4. Requirements

### 4.1 Functional Requirements

Cloud Provider Admin model-management capabilities in FR-1 through FR-6 must be available through the UI, CLI, and API. [Clarify: R1.Q1]

- **FR-1:** Cloud Provider Admins must be able to list model deployments and view model details. [Clarify: R1.Q1, R3.Q1]
- **FR-2:** Cloud Provider Admins must be able to select a model source and inference name, choose a supported serving profile that determines the model's serving topology, configure supported capacity settings, and create a deployment on existing clusters that becomes available through MaaS. Model source, serving runtime, and model identity, including the inference name, are set at creation and cannot be changed afterward. Advanced capabilities such as LoRA adapters, confidential compute, and KV-cache offloading are not separate per-model admin controls in v1. Routing, scheduling, and rollout behavior remain platform-managed. The design doc defines the supported profiles and capacity settings. [Jira: OSAC-7024, Clarify: R8.Q1, R9.Q1]
- **FR-3:** Cloud Provider Admins must be able to select one or more eligible clusters for a model. A cluster is eligible only if it meets the platform prerequisites and is compatible with the selected model configuration's hardware, serving-profile, and capacity requirements; OSAC must explain when a cluster is incompatible. For this deployment, OSAC makes the model available only on those selected clusters; locations may be shown as context but models are placed only in selected clusters. [Clarify: R4.Q1, R10.Q1]
- **FR-4:** Cloud Provider Admins must be able to update non-identity descriptive metadata and settings for serving scale, per-instance capacity, and serving topology for MaaS model deployments. Serving-scale changes do not interrupt inference; changes to per-instance capacity or serving topology may restart the model and interrupt inference. A model's identity, including its inference name, cannot be changed after creation. The design defines the specific editable metadata and capacity settings. [Clarify: R1.Q3, R6.Q1, R7.Q1]
- **FR-5:** Cloud Provider Admins must be able to delete a model when it is not referenced by an active MaaS subscription. If it is referenced, OSAC must block deletion and explain that the references must be resolved first. [Clarify: R1.Q5]
- **FR-6:** Cloud Provider Admins must be able to see overall model readiness and readiness for each selected cluster, including a useful reason when a cluster is not ready. [Clarify: R4.Q2]
- **FR-7:** Tenant users must be able to discover and use models made available to them through MaaS, with access governed by their existing subscriptions. [Jira: OSAC-7024]

### 4.2 Non-Functional Requirements

- **NFR-1:** Model capabilities and configurations presented to Cloud Provider Admins must be compatible with the RHOAI and MaaS capabilities available on the target clusters. [Jira: OSAC-7024]
- **NFR-2:** Model-management operations must be restricted to authorized Cloud Provider Admins, and tenant model access must remain governed by MaaS subscription rules. [Jira: OSAC-7024]

## 5. Dependencies

- Target clusters are already provisioned or imported and onboarded to the AI Grid, with RHOAI and MaaS installed and available. [Jira: OSAC-7024] [Clarify: R5.Q1]
- OSAC can identify eligible clusters so administrators can select individual model-placement targets. [Clarify: R4.Q1]

---

## Provenance

Authored: respond @ prd 0.11.5 - 7b2b8de, workspace main @ 2753cc412
Phases: draft, respond, respond, respond, respond, respond, respond, respond, respond, respond, respond, respond, respond, respond, respond, respond, respond, respond, respond, respond, respond, respond, respond

<!-- ai-workflow-provenance:{"schema_version":1,"provenance_kind":"session","workflow":"prd","workflow_version":"0.11.5","ai_workflows":"7b2b8de","source_repo":"2753cc412","source_repo_branch":"main","commits_behind_main":0,"commits_ahead_main":579,"main_ref":"main","phases":["draft","respond","respond","respond","respond","respond","respond","respond","respond","respond","respond","respond","respond","respond","respond","respond","respond","respond","respond","respond","respond","respond","respond"],"authoring_modes":["skill"],"context_changed":false,"origin_untracked":false} -->
