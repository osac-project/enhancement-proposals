# Clarification Log — OSAC-7024

## Status

- Rounds completed: 5
- Open gaps: 0
- Exit criteria met: Yes

## Round 1 — Initial release scope

### R1.Q1: Supported interfaces

Which user-facing surfaces should the first release support for model management?

#### Answer

API, UI, and CLI.

#### Impact

The PRD should include model-management workflows through all three surfaces.

#### Decision (D1)

The first release includes API, UI, and CLI support for model management.

---

### R1.Q2: Local and external models

What should Cloud Provider Admins be able to manage in the first release? The Jira describes deployments published through MaaS; the existing provisioning template also has a separate external-model path.

#### Answer

Local and external models.

#### Impact

The PRD must cover both locally deployed inference models and externally hosted models. The user-visible lifecycle for external models still needs clarification.

#### Decision (D2)

The first release includes management of both local and external models.

---

### R1.Q3: Supported updates

After creating a model, what changes should an admin be able to make without deleting and recreating it?

#### Answer

Capacity and metadata.

#### Impact

The PRD should include updates to model metadata and capacity. It should not imply that model source or serving runtime can be changed in place.

#### Decision (D3)

In-place model updates in the first release cover capacity and metadata.

---

### R1.Q4: Placement selection

How should an admin choose where a model runs in the first release?

#### Answer

Locations.

#### Impact

The PRD should describe location-based placement from the administrator's perspective. The behavior that maps selected locations to clusters remains to be clarified.

#### Decision (D4)

Administrators select locations for model placement in the first release.

---

### R1.Q5: Deleting an in-use model

If a model is referenced by an active MaaS subscription, what should happen when an admin tries to delete it?

#### Answer

Block deletion.

#### Impact

The PRD should require a clear explanation that the model cannot be deleted while active subscription references remain.

#### Decision (D5)

Deletion is rejected while the model is referenced by an active MaaS subscription.

---

## Round 2 — External models and placement behavior

### R2.Q1: External model management

For external models, what should the Cloud Provider Admin manage?

#### Answer

MaaS registration for an already-running external endpoint. OSAC does not deploy or operate the endpoint's serving infrastructure.

#### Impact

The first release includes managing external model registration and discovery through MaaS, but not provisioning or operating the external model endpoint.

#### Decision (D6)

External model management is limited to MaaS registration for an existing endpoint; the serving infrastructure remains outside OSAC.

---

### R2.Q2: Placement within selected locations

If an admin selects one or more locations, where should OSAC make the local model available?

#### Answer

On all eligible clusters in each selected location.

#### Impact

The PRD should describe deployment to all eligible clusters in the selected locations rather than requiring the administrator to select individual clusters.

#### Decision (D7)

Local models are deployed to all eligible clusters in the selected locations.

---

### R2.Q3: Placement status visibility

What placement status should administrators be able to see for a model deployed across locations?

#### Answer

Overall readiness and readiness for each selected location, with a useful reason when a location is not ready.

#### Impact

The PRD should require both an overall model status and location-level status with an explanation for locations that are not ready.

#### Decision (D8)

Model status includes overall readiness and per-selected-location readiness with a reason for locations that are not ready.

---

## Round 3 — Day-2 model scope

### R3.Q1: External model registration in v1

Should the day-2 Models API v1 include registration of externally hosted models,
or focus on locally deployed models?

#### Answer

Focus on locally deployed models. Existing day-0 external-model provisioning
workflows remain unchanged.

#### Impact

The v1 Models API does not include registering external endpoints for MaaS.
Local deployments remain manageable after cluster provisioning.

#### Decision (D9)

V1 of the day-2 Models API manages locally deployed models only. External model
registration is out of scope for this feature; existing day-0 workflows are
unchanged. This supersedes D2 and D6.

---

## Round 4 — Cluster placement and status

### R4.Q1: Placement targets

When multiple eligible clusters share a location, should a Cloud Provider Admin
select the location or the specific cluster or clusters where a local model
will run?

#### Answer

The admin selects specific eligible clusters. A local model is deployed to each
selected cluster; location can be shown as context but does not determine
placement.

#### Impact

The PRD should describe explicit cluster selection and per-selected-cluster
placement, rather than selecting a location and implicitly targeting all
eligible clusters there.

#### Decision (D10)

Cloud Provider Admins select one or more eligible clusters directly, and local
models are placed on those selected clusters. This supersedes D4's location
selection and D7's all-eligible-clusters-in-selected-locations behavior.

---

### R4.Q2: Placement readiness detail

What placement readiness should Cloud Provider Admins see for a model deployed
to multiple clusters?

#### Answer

Overall readiness and readiness for each selected cluster, with a useful reason
when a cluster is not ready.

#### Impact

The PRD should report readiness at the selected-cluster level, not the
location level.

#### Decision (D11)

Model status includes overall readiness and per-selected-cluster readiness with
a reason when a selected cluster is not ready. This supersedes D8's
per-location status decision.

---

## Round 5 — Target cluster prerequisites

### R5.Q1: Cluster and platform readiness

What must be in place before a Cloud Provider Admin can manage models on a
target cluster?

#### Answer

The cluster must already be provisioned or imported, connected to ACM and
onboarded to the AI Grid, with AI Grid, RHOAI, and MaaS installed.

#### Impact

Cluster provisioning/import and initial AI Grid/RHOAI/MaaS installation are
prerequisites, not deliverables of this day-2 model-management Feature.

#### Decision (D12)

Model management targets clusters that are already provisioned or imported and
onboarded to the AI Grid, with AI Grid, RHOAI, and MaaS installed. This Feature
does not provision/import clusters or install these platforms.

---

## Remaining Gaps

None identified for PRD drafting. The exact RHOAI version mapping and resource-level compatibility details remain design considerations, not PRD clarification blockers.
