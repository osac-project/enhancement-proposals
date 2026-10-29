# Clarification Log — OSAC-7024

## Status

- Rounds completed: 2
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

## Remaining Gaps

None identified for PRD drafting. The exact RHOAI version mapping and resource-level compatibility details remain design considerations, not PRD clarification blockers.
