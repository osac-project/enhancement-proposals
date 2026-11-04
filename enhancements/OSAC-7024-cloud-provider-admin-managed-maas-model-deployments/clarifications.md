# Clarification Log — OSAC-7024

## Status

- Rounds completed: 12
- Open gaps: 0
- Resolved inventory scope: The model list includes AI Grid catalog entries
  added through the Models API or Git; AI Grid has no day-0 models.
- Deferred to design: Exact readiness status labels and remaining aggregation
  details.
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

### R1.Q5: Removing a referenced model placement

If a model is referenced by an active MaaS subscription, what should happen
when an admin tries to remove it from a cluster?

#### Answer

Allow removal from one or more selected clusters when no active MaaS
subscription references the model; retain the model identity in the catalog.
If an active subscription references it, block removal from every cluster and
explain why.

#### Impact

The PRD should state that per-cluster deployment removal is supported while
the model remains in the catalog, and that active subscription references
block removal from any cluster with a clear explanation.

#### Decision (D5)

Admins can remove deployments from selected clusters while retaining the model
identity in the catalog. Any active MaaS subscription reference blocks removal
from every cluster.

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

## Round 3 — Final v1 scope decision

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

Serving-scale and per-instance capacity changes are in scope. Serving-scale
changes do not interrupt inference; per-instance capacity changes may restart
the model and interrupt inference. The selected serving profile and topology
cannot be changed after creation; changing them requires a new deployment.
The design defines the specific supported settings.

#### Impact

FR-2 should distinguish supported serving-scale and per-instance capacity
updates and their user-visible impact from the immutable serving profile and
topology, without enumerating CRD fields or exact controls.

---

## Round 7 — Model identity and metadata updates

### R7.Q1: Mutable model metadata

Which model details can a Cloud Provider Admin change after creation?

#### Answer

Descriptive metadata that does not change model identity can be updated.
Model identity, including the inference name, is fixed after creation so
existing subscription references remain valid.

#### Impact

FR-2 should limit editable metadata to non-identity descriptive attributes and
state that the model's identity cannot be changed after creation. Exact
metadata fields remain for the design to define.

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

---

## Round 9 — V1 serving-option boundaries

### R9.Q1: Immutable and advanced model settings

Which model settings are immutable after creation, and which advanced options
are not separate admin controls in v1?

#### Answer

Model source, serving runtime, model identity (including the inference name),
and the selected serving profile and topology are fixed after creation;
changing the profile or topology requires a new deployment. Non-identity
descriptive metadata can be updated. Advanced capabilities such as LoRA
adapters, confidential compute, and KV-cache offloading are not independently
configurable per-model options in v1.

#### Impact

FR-2 should distinguish immutable source, serving runtime, identity, and
serving profile/topology from editable non-identity metadata, and state that
advanced capabilities are not separate admin controls in v1, without
specifying resource schemas or field mappings.

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

## Consolidated v1 model configuration and update scope

#### Decision (D18)

At creation, Cloud Provider Admins select a model source and inference name,
choose a supported serving profile, and configure supported serving-scale and
per-instance capacity settings. After creation, the model source, serving
runtime, identity (including inference name), and selected serving profile and
topology cannot be changed; changing the profile or topology requires a new
deployment. Admins can update non-identity descriptive metadata, serving-scale
settings, and per-instance capacity settings. Serving-scale changes do not
interrupt inference; per-instance capacity changes may restart the model and
interrupt inference. Advanced capabilities such as LoRA adapters, confidential
compute, and KV-cache offloading are not independently configurable per-model
options in v1. Routing, scheduling, and rollout behavior remain
platform-managed. The design defines the supported profiles and capacity
settings.

---

## Round 11 — Partial placement availability

### R11.Q1: MaaS availability with partial cluster readiness

If a model is ready on some, but not all, selected clusters, should tenants be
able to use it through MaaS on the ready placements or should availability
wait until every selected cluster is ready?

#### Answer

A selected cluster is ready only when the inference deployment is ready and
the model is available through MaaS on that cluster. Tenants can discover and
use the model through MaaS on ready placements while other selected clusters
are not ready. Overall placement remains partial until all selected clusters
are ready; the Cloud Provider Admin can see readiness and a reason for each
selected cluster.

#### Impact

FR-5 and FR-6 should define partial-readiness status and MaaS usability without
prescribing status field names or recovery mechanics.

#### Decision (D19)

Per-cluster readiness includes both inference deployment readiness and MaaS
availability. Subscribed Tenant Users can discover and use the model through
MaaS on ready placements while other selected clusters are not ready. Overall
placement remains partial until every selected cluster is ready, and
Cloud Provider Admins see each cluster's readiness and reason.

---

## Round 12 — Subscription and placement-removal consistency

### R12.Q1: Concurrent subscription save and placement removal

What must happen if saving a subscription that references a model overlaps with
removing one of its cluster placements?

#### Answer

The model identity remains in the catalog. Subscription saves must verify the
referenced model exists, and placement removal must be blocked when an active
subscription references the model. Concurrent saves and placement removals
must not bypass that guard; if the operations conflict, the operation that
cannot proceed must fail with a clear conflict response. The Subscription PRD
covers save validation; this PRD covers placement removal. The design defines
how the operations are coordinated.

#### Impact

FR-4 must state that active subscriptions block placement removal and describe
the user-visible conflict behavior without prescribing the coordination
mechanism.

#### Decision (D20)

OSAC must coordinate subscription saves and placement removals so an active
subscription reference blocks removal from any cluster. If concurrent
operations conflict, the operation that cannot proceed is rejected with a
clear conflict response. The Subscription PRD owns save validation; this PRD
owns the placement-removal guard. The design defines the coordination
mechanism.

---

## Remaining Gaps

No unresolved PRD questions remain. Exact readiness status labels and
remaining aggregation details, the exact RHOAI version mapping, and
resource-level compatibility details are deferred to the design.
