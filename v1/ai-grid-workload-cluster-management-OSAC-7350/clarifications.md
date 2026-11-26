# Clarification Log — OSAC-7350

## Status

- Rounds completed: 4
- Open gaps: 0
- Exit criteria met: Yes

## Round 1 — Hub selection and workload-cluster operations

### R1.Q1: Eligible OSAC hubs

The Jira says the CPA selects an existing OSAC hub to establish the AI Grid.
Which hubs are eligible?

#### Answer

All registered OSAC hubs are available for selection.

#### Impact

The selection workflow offers all registered OSAC hubs, rather than limiting
the candidates to hubs already identified as ACM hubs with imported spokes.
When no hubs are registered, the API/CLI returns an empty list (R2.Q1).

#### Decision (D1)

All registered OSAC hubs are eligible for CPA selection as the AI Grid hub.

---

### R1.Q2: Hub replacement or removal

Can the CPA change or remove the selected hub after establishing the AI Grid?

#### Answer

No. The selected hub is fixed after selection.

#### Impact

The v1 workflow does not support replacing the hub or removing its AI Grid
association.

#### Decision (D2)

An AI Grid's selected hub cannot be changed or removed after selection.

This initial decision was superseded by D11 in Round 4.

---

### R1.Q3: Workload-cluster location

How is location provided when adding a workload cluster to AI Grid?

#### Answer

The CPA provides a required free-text location and can update it later.

#### Impact

The API and CLI must accept and return the CPA-managed placement location.

#### Decision (D3)

Adding a workload cluster requires a CPA-entered free-text location, which
the CPA can update later.

---

### R1.Q4: Role-change safeguards

Should the model and subscription safeguards that apply to removal also block
role changes that stop a cluster serving inference or ingress?

#### Answer

Yes. Apply the same relevant safeguards to those role changes.

#### Impact

Changing a role must be blocked when it would stop inference while models are
placed on the cluster, or stop ingress while subscriptions exist or remaining
Grid members would have no ingress-capable cluster.

#### Decision (D4)

The AIGMVP model-placement and subscription safeguards apply to both AI Grid
removal and role changes that stop inference or ingress.

---

### R1.Q5: CLI scope

Should CPA CLI operations accompany the API?

#### Answer

Yes. Include API and CLI support; UI work remains out of scope.

#### Impact

The PRD must cover the same in-scope workload-cluster management capabilities
through the API and CLI.

#### Decision (D5)

All in-scope API operations are also available through the CPA CLI. No UI is
implemented in this Feature.

---

## Round 2 — Empty hub inventory, versions, and personas

### R2.Q1: No registered OSAC hubs

What should the CPA experience if no OSAC hubs are registered?

#### Answer

The API/CLI returns an empty list.

#### Impact

The workload-cluster Feature does not register a hub when no candidates are
available.

#### Decision (D6)

When no OSAC hubs are registered, the hub-list operation returns an empty
list; hub registration is not added to this Feature.

---

### R2.Q2: Cluster version reporting

Which cluster versions should the API/CLI expose?

#### Answer

Expose both OpenShift and Kubernetes versions. If the OpenShift version is
unavailable, report "Not reported".

#### Impact

The PRD should distinguish OpenShift and Kubernetes version information and
define the unavailable OpenShift-version display.

#### Decision (D7)

Return OpenShift and Kubernetes versions separately; report "Not reported"
when the OpenShift version is unavailable.

---

### R2.Q3: Cloud Infrastructure Admin impact

Is Cloud Infrastructure Admin affected by this Feature?

#### Answer

No. Cloud Provider Admin is the affected persona.

#### Impact

The PRD can state that Cloud Infrastructure Admin is not affected.

#### Decision (D8)

Cloud Infrastructure Admin is not affected by this Feature.

---

## Round 3 — Hub setup and readiness feedback

### R3.Q1: Hub selection action

Does selecting an OSAC hub install/configure AI Grid hub components, or does
it only designate the hub?

#### Answer

Selection designates the hub. A separate process installs/configures AI Grid
hub components.

#### Impact

The API/CLI must treat hub selection and hub setup as separate user-visible
steps. The setup process is a dependency; this Feature does not install the
hub components.

#### Decision (D9)

Selecting a hub designates it as the AI Grid hub but does not install or
configure its AI Grid components.

---

### R3.Q2: Hub setup status

What should the CPA see while AI Grid hub setup is underway or if it fails?

#### Answer

Report setup status.

#### Impact

The API/CLI should expose whether the selected hub is pending setup, ready, or
failed, with an actionable reason for failure.

#### Decision (D10)

Report hub setup as Pending, Ready, or Failed, with an actionable failure
reason.

---

## Round 4 — Hub replacement and removal

### R4.Q1: Replacing the designated hub

Can the CPA remove and re-add the selected hub or designate a different
hub after selection?

#### Answer

Yes. Only one hub is designated at a time, but the CPA can remove it, re-add
it, or designate another hub.

#### Impact

Hub designation is replaceable rather than immutable. Removing the designated
hub also removes its workload clusters from AI Grid membership.

#### Decision (D11)

The AI Grid has one designated hub at a time. The CPA can remove or replace
that hub after selection.

---

### R4.Q2: Workload clusters after hub removal

What happens to the hub's workload clusters when the hub is removed or
replaced?

#### Answer

Workload clusters remain imported into OSAC but leave AI Grid. Hub removal is
allowed even if those clusters have model placements or subscriptions.

#### Impact

Hub removal is distinct from individually removing a spoke. It detaches the
associated workload clusters from AI Grid without deleting them or
automatically cleaning up model placements or subscriptions.

#### Decision (D12)

Removing a hub detaches its workload clusters from AI Grid but keeps them
imported into OSAC. Hub removal is not blocked by model placements or
subscriptions and does not automatically move/delete them.

---

### R4.Q3: Hub-removal warning

Should the CPA receive a warning and explicitly confirm before removing a hub
that has workload clusters with model placements or subscriptions?

#### Answer

Yes. Warn the CPA about the impact and require explicit confirmation.

#### Impact

The API/CLI hub-removal flow must make the potential effect on model
placements and subscriptions visible before completing the removal.

#### Decision (D13)

Hub removal warns about detaching workload clusters with model placements or
subscriptions and requires explicit CPA confirmation.

---

## Remaining Gaps

None identified for the current v1 scope.
