# MaaS Model Management Through OSAC

| Field       | Value |
|-------------|-------|
| Author(s)   | Ganesh Murthy |
| Jira        | [OSAC-7024](https://redhat.atlassian.net/browse/OSAC-7024) |
| Date        | 2026-10-29 |

## 1. Problem Statement

OSAC configures MaaS during cluster provisioning and seeds a local model, but Cloud Provider Admins do not have a governed way to manage local model deployments on existing clusters afterward. MaaS model listing lets consumers discover models; it does not let administrators manage those deployments through OSAC. Administrators therefore depend on provisioning automation or direct cluster-resource management to add or change local model offerings, and cannot manage their lifecycle through OSAC without reprovisioning. [Jira: OSAC-7024]

## 2. Goals and Non-Goals

### 2.1 Goals

- Cloud Provider Admins can manage locally deployed MaaS models through the OSAC UI, CLI, and API after cluster provisioning. [Clarify: R1.Q1, R3.Q1]
- Cloud Provider Admins can place local models on selected eligible clusters and see overall and per-cluster readiness. [Clarify: R4.Q1, R4.Q2]
- Tenant users can discover and use models made available to them under existing MaaS subscription rules. [Jira: OSAC-7024]

### 2.2 Non-Goals

- Provisioning or importing clusters, or installing the AI Grid, RHOAI, or MaaS. This feature manages models on already-onboarded clusters. [Jira: OSAC-7024] [Clarify: R5.Q1]
- Managing MaaS subscriptions, authorization policies, API keys, or inference requests. [Jira: OSAC-7024]
- Registering externally hosted models through this day-2 Models API. Existing day-0 external-model provisioning workflows are unchanged. [Clarify: R2.Q1, R3.Q1]

## 3. Requirements

### 3.1 Functional Requirements

- **FR-1:** Cloud Provider Admins must be able to list and inspect local model deployments through the UI, CLI, and API. [Clarify: R1.Q1, R3.Q1]
- **FR-2:** Cloud Provider Admins must be able to select a model source and inference name, configure supported serving settings, and create a local deployment on existing clusters that becomes available through MaaS when ready. [Jira: OSAC-7024]
- **FR-3:** Cloud Provider Admins must be able to select one or more eligible clusters for a local model. OSAC makes the model available on those selected clusters; locations may be shown as context but do not determine placement. [Clarify: R4.Q1]
- **FR-4:** Cloud Provider Admins must be able to update metadata and capacity for local model deployments. [Clarify: R1.Q3]
- **FR-5:** Cloud Provider Admins must be able to delete a local model when it is not referenced by an active MaaS subscription. If it is referenced, OSAC must block deletion and explain that the references must be resolved first. [Clarify: R1.Q5]
- **FR-6:** Cloud Provider Admins must be able to see overall model readiness and readiness for each selected cluster, including a useful reason when a cluster is not ready. [Clarify: R4.Q2]
- **FR-7:** Tenant users must be able to discover and use local models made available to them through MaaS, with access governed by their existing subscriptions. [Jira: OSAC-7024]

### 3.2 Non-Functional Requirements

- **NFR-1:** Model capabilities and configurations presented to Cloud Provider Admins must be compatible with the RHOAI and MaaS capabilities available on the target clusters. [Jira: OSAC-7024]
- **NFR-2:** Model-management operations must be restricted to authorized Cloud Provider Admins, and tenant model access must remain governed by MaaS subscription rules. [Jira: OSAC-7024]

## 4. Acceptance Criteria

- [ ] A Cloud Provider Admin can create, list, view, update, and delete models through the UI, CLI, and API, subject to the stated update and deletion constraints.
- [ ] A Cloud Provider Admin can list and inspect local model deployments.
- [ ] A Cloud Provider Admin can select a model source and inference name, configure supported serving settings, deploy the local model to selected eligible clusters, and see it become available through MaaS when ready.
- [ ] A local model selected for multiple clusters is made available on each selected cluster.
- [ ] A Cloud Provider Admin can update metadata and capacity for local model deployments.
- [ ] A Cloud Provider Admin can see overall readiness and per-cluster readiness, including a reason for a selected cluster that is not ready.
- [ ] An attempt to delete a model referenced by an active MaaS subscription is blocked with a clear explanation; a model without such references can be deleted.
- [ ] A Tenant User can discover and use only the models available under their MaaS subscription rules.

## 5. Dependencies

- Target clusters are already provisioned or imported and onboarded to the AI Grid, with RHOAI and MaaS installed and available. [Jira: OSAC-7024] [Clarify: R5.Q1]
- OSAC can identify eligible clusters so administrators can select individual model-placement targets. [Clarify: R4.Q1]

---

## Provenance

Authored: respond @ prd 0.11.5 - 7b2b8de, workspace main @ 2753cc412
Phases: draft, respond, respond, respond

<!-- ai-workflow-provenance:{"schema_version":1,"provenance_kind":"session","workflow":"prd","workflow_version":"0.11.5","ai_workflows":"7b2b8de","source_repo":"2753cc412","source_repo_branch":"main","commits_behind_main":0,"commits_ahead_main":579,"main_ref":"main","phases":["draft","respond","respond","respond"],"authoring_modes":["skill"],"context_changed":false,"origin_untracked":false} -->
