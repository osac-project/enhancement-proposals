# Clarification Log — OSAC-7024

## Status

- Rounds completed: 10
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

### R1.Q2: V1 model scope

What should Cloud Provider Admins be able to manage in the first release? The Jira describes deployments published through MaaS; the existing provisioning template also has a separate external-model path.

#### Answer

For v1, external models are not allowed.

#### Impact

The PRD must state that external model management is out of scope for this
feature; see D9.

#### Decision (D2)

The initial answer included external models. This decision was superseded by
D9, which excludes them from v1.

---

### R1.Q3: Supported updates

After creating a model, what changes should an admin be able to make without deleting and recreating it?

#### Answer

Cloud Provider Admins can update non-identity descriptive metadata and settings
for serving scale, per-instance capacity, and serving topology. Serving-scale
changes do not interrupt inference; per-instance capacity or serving-topology
changes may restart the model and interrupt inference. Model source, serving
runtime, and model identity, including the inference name, cannot be changed
after creation.

#### Impact

The PRD should include updates to model metadata and capacity. It should not imply that model source or serving runtime can be changed in place.

#### Decision (D3)

In-place model updates in the first release cover capacity and metadata.

---

### R1.Q4: Placement selection

How should an admin choose where a model runs in the first release?

#### Answer

Cloud Provider Admins select one or more specific eligible clusters.
Location may be shown as context, but it does not determine placement; the
model is made available only on the selected clusters. This supersedes the
initial location-based answer and is formalized in D10.

#### Impact

The PRD should describe direct cluster selection and per-selected-cluster
placement, rather than location-based placement. See D10.

#### Decision (D4)

The initial decision was location-based placement. It was superseded by D10,
which requires direct selection of eligible clusters.

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

Day-2 Models API v1 does not manage external model registration. See D9.

#### Impact

External model registration is not managed in v1; see D9.

#### Decision (D6)

The initial decision covered MaaS registration for an existing external
endpoint. It was superseded by D9, which excludes external model registration
from v1.

---

### R2.Q2: Placement within selected locations

If an admin selects one or more locations, where should OSAC make the model available?

#### Answer

On the clusters selected by the Cloud Provider Admin.

#### Impact

The PRD should describe deployment only to the clusters selected by the Cloud
Provider Admin, rather than implicitly targeting all eligible clusters in a
selected location. See D10.

#### Decision (D7)

Cloud Provider Admins select individual eligible clusters directly; location
may provide context but does not determine placement. This is formalized in
D10.

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

Day-2 Models API v1 does not manage external model registration. This
supersedes D2 and D6.

---

## Round 4 — Cluster placement and status

### R4.Q1: Placement targets

When multiple eligible clusters share a location, should a Cloud Provider Admin
select the location or the specific cluster or clusters where a model
will run?

#### Answer

The admin selects specific eligible clusters. A model is deployed to each
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

## Round 6 — Capacity update impact

### R6.Q1: Capacity update classes and impact

Which capacity updates should Cloud Provider Admins be able to make, and what
impact should they expect?

#### Answer

Both serving-scale changes and per-instance capacity or serving-topology
changes are in scope. Serving-scale changes do not interrupt inference;
per-instance capacity or serving-topology changes may restart the model and
interrupt inference. The design defines the specific supported settings.

#### Impact

FR-4 should distinguish serving-scale changes from per-instance capacity or
serving-topology changes, and state their user-visible impact without
enumerating CRD fields or exact controls.

#### Decision (D13)

Cloud Provider Admins can update supported serving-capacity settings. Changes
to serving scale do not interrupt inference; changes to per-instance capacity
or serving topology may restart the model and interrupt inference. The design
defines the specific supported settings and CRD mapping.

---

## Round 7 — Model identity and metadata updates

### R7.Q1: Mutable model metadata

Which model details can a Cloud Provider Admin change after creation?

#### Answer

Descriptive metadata that does not change model identity can be updated.
Model identity, including the inference name, is fixed after creation so
existing subscription references remain valid.

#### Impact

FR-4 should limit editable metadata to non-identity descriptive attributes and
state that the model's identity cannot be changed after creation. Exact
metadata fields remain for the design to define.

#### Decision (D14)

Cloud Provider Admins can update non-identity descriptive metadata, but cannot
change a model's identity, including its inference name, after creation. This
keeps existing subscription references valid; the design defines the exact
editable metadata fields.

---

## Round 8 — Admin-configurable serving settings

### R8.Q1: Serving settings exposed to administrators

Which serving settings should Cloud Provider Admins choose when creating a
local model, and which remain platform-managed?

#### Answer

Admins choose the model source, a supported serving profile that determines
the model's serving topology, and supported capacity settings. Routing,
scheduling, and rollout behavior remain
platform-managed and are not configurable per model. The design defines the
available profiles and exact settings.

#### Impact

FR-2 should bound administrator-configurable settings at the user-facing level
and identify platform-managed behavior without prescribing CRD fields or
preset implementation.

#### Decision (D15)

Cloud Provider Admins can choose a model source and supported serving profile
that determines the model's serving topology, and configure supported capacity
settings. Routing, scheduling, and rollout
behavior are platform-managed rather than per-model administrator settings.
The design defines the supported profiles and exact settings.

---

## Round 9 — V1 serving-option boundaries

### R9.Q1: Admin-configurable serving options

Which serving options are Cloud Provider Admins able to configure in v1, and
which remain fixed or platform-managed?

#### Answer

Admins select the model source and inference name at creation, choose a
supported serving profile that determines topology, and configure supported
capacity settings. Model source, serving runtime, and identity cannot be
changed after creation.
Advanced capabilities such as LoRA adapters, confidential compute, and
KV-cache offloading are not separate per-model admin controls in v1. Routing,
scheduling, and rollout behavior remain platform-managed. Non-identity
descriptive metadata can be updated. Exact profile contents and capacity
settings are defined in the design.

#### Impact

FR-2 should enumerate the v1 user-facing configuration categories and
distinguish them from immutable source, serving runtime, and identity and from
platform-managed behavior, without specifying resource schemas or field
mappings.

#### Decision (D16)

V1 exposes model source and identity at creation, supported serving-profile
selection, and supported capacity settings. Source, serving runtime, and
identity are immutable after creation; non-identity descriptive metadata can
be updated. Advanced
capabilities are not separate per-model admin controls, and routing,
scheduling, and rollout remain platform-managed. The design defines exact
profile contents and capacity settings. This supplements D14 and D15.

---

## Round 10 — Model-specific cluster eligibility

### R10.Q1: Model-specific cluster compatibility

Beyond platform prerequisites, what makes a cluster eligible for a particular
model configuration?

#### Answer

A cluster must support the selected model configuration's hardware,
serving-profile, and capacity requirements. OSAC must explain when a cluster
is incompatible. Operational readiness issues on selected clusters are
reported through per-cluster status.

#### Impact

FR-3 should distinguish the platform prerequisites in D12 from
model-specific compatibility. The PRD should state the user-visible
eligibility and explanation behavior without naming CRD fields, presets, or
health-check mechanisms.

#### Decision (D17)

A cluster is eligible for a model only if it meets the platform prerequisites
and is compatible with the selected model configuration's hardware,
serving-profile, and capacity requirements. OSAC explains incompatibility;
operational readiness issues after selection are reported through
per-selected-cluster status. Specific checks and enforcement mechanisms are
defined in the design.

---

## Remaining Gaps

None identified for PRD drafting. The exact RHOAI version mapping and resource-level compatibility details remain design considerations, not PRD clarification blockers.
