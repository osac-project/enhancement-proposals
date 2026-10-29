# MaaS Model Management Through OSAC

| Field       | Value |
|-------------|-------|
| Author(s)   | Ganesh Murthy |
| Jira        | [OSAC-7024](https://redhat.atlassian.net/browse/OSAC-7024) |
| Date        | 2026-10-29 |

## 1. Problem Statement

OSAC configures MaaS during cluster provisioning and seeds a local model, but Cloud Provider Admins do not have a governed way to manage model offerings on existing clusters afterward. MaaS model listing lets consumers discover models; it does not give administrators a way to manage local deployments or register external models. Administrators therefore depend on provisioning automation or direct cluster-resource management to add or change offerings, and cannot manage their lifecycle through OSAC without reprovisioning. [Jira: OSAC-7024]

## 2. Goals and Non-Goals

### 2.1 Goals

- Cloud Provider Admins can manage local and external MaaS model offerings through the OSAC UI, CLI, and API after cluster provisioning. [Clarify: R1.Q1, R1.Q2]
- Cloud Provider Admins can place local models in selected locations and see overall and per-location readiness. [Clarify: R1.Q4, R2.Q2, R2.Q3]
- Tenant users can discover and use models made available to them under existing MaaS subscription rules. [Jira: OSAC-7024]

### 2.2 Non-Goals

- Installing RHOAI or MaaS, or provisioning OpenShift clusters. [Jira: OSAC-7024]
- Managing MaaS subscriptions, authorization policies, API keys, or inference requests. [Jira: OSAC-7024]
- Deploying or operating the serving infrastructure for externally hosted models. External model management is limited to registering an already-running endpoint for MaaS. [Clarify: R2.Q1]

## 3. Requirements

### 3.1 Functional Requirements

- **FR-1:** Cloud Provider Admins must be able to list and inspect local model deployments and external models registered for MaaS through the UI, CLI, and API. [Clarify: R1.Q1, R1.Q2]
- **FR-2:** Cloud Provider Admins must be able to select a model source and inference name, configure supported serving settings, and create a local deployment on existing clusters that becomes available through MaaS when ready. [Jira: OSAC-7024]
- **FR-3:** Cloud Provider Admins must be able to select one or more locations for a local model. OSAC makes the model available on all eligible clusters in the selected locations. [Clarify: R1.Q4, R2.Q2]
- **FR-4:** Cloud Provider Admins must be able to register an already-running external model endpoint for discovery through MaaS. [Clarify: R1.Q2, R2.Q1]
- **FR-5:** Cloud Provider Admins must be able to update model metadata and capacity. Capacity updates apply to locally deployed models; external endpoint serving capacity remains outside OSAC management. [Clarify: R1.Q3, R2.Q1]
- **FR-6:** Cloud Provider Admins must be able to delete a model when it is not referenced by an active MaaS subscription. If it is referenced, OSAC must block deletion and explain that the references must be resolved first. [Clarify: R1.Q5]
- **FR-7:** Cloud Provider Admins must be able to see overall model readiness and readiness for each selected location, including a useful reason when a location is not ready. [Clarify: R2.Q3]
- **FR-8:** Tenant users must be able to discover and use models made available to them through MaaS, with access governed by their existing subscriptions. [Jira: OSAC-7024]

### 3.2 Non-Functional Requirements

- **NFR-1:** Model capabilities and configurations presented to Cloud Provider Admins must be compatible with the RHOAI and MaaS capabilities available on the target clusters. [Jira: OSAC-7024]
- **NFR-2:** Model-management operations must be restricted to authorized Cloud Provider Admins, and tenant model access must remain governed by MaaS subscription rules. [Jira: OSAC-7024]

## 4. Acceptance Criteria

- [ ] A Cloud Provider Admin can create, list, view, update, and delete models through the UI, CLI, and API, subject to the stated update and deletion constraints.
- [ ] A Cloud Provider Admin can list and inspect local model deployments and external MaaS registrations.
- [ ] A Cloud Provider Admin can select a model source and inference name, configure supported serving settings, deploy the local model to existing clusters in selected locations, and see it become available through MaaS when ready.
- [ ] A local model selected for multiple locations is made available on all eligible clusters in those locations.
- [ ] A Cloud Provider Admin can register an already-running external model endpoint for MaaS discovery without OSAC deploying or operating its serving infrastructure.
- [ ] A Cloud Provider Admin can update model metadata and capacity; capacity changes are available for local deployments.
- [ ] A Cloud Provider Admin can see overall readiness and per-location readiness, including a reason for a location that is not ready.
- [ ] An attempt to delete a model referenced by an active MaaS subscription is blocked with a clear explanation; a model without such references can be deleted.
- [ ] A Tenant User can discover and use only the models available under their MaaS subscription rules.

## 5. Dependencies

- RHOAI and MaaS are installed and available on the existing clusters where local models will run. [Jira: OSAC-7024]
- External model endpoints are already running and available for MaaS registration; their serving infrastructure is managed outside OSAC. [Clarify: R2.Q1]
- OSAC can identify eligible clusters and their locations so administrators can place local models by location. [Clarify: R2.Q2]

---

## Provenance

Authored: draft @ prd 0.11.5 - 7b2b8de, workspace main @ 2753cc412

<!-- ai-workflow-provenance:{"schema_version":1,"provenance_kind":"session","workflow":"prd","workflow_version":"0.11.5","ai_workflows":"7b2b8de","source_repo":"2753cc412","source_repo_branch":"main","commits_behind_main":0,"commits_ahead_main":579,"main_ref":"main","phases":["draft"],"authoring_modes":["skill"],"context_changed":false,"origin_untracked":false} -->
