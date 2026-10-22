# Testplan — OSAC-1415

## Overview

- **Feature:** Cluster Upgrade CaaS, Phase 1
- **Use cases:** 31 plain-language behaviors, grouped into the cases below
- **Test cases:** 25 (22 local checks; 3 proposed deployed E2E journeys)
- **Requirement coverage:** FR-7, FR-8, FR-10, FR-11, FR-12, FR-13, and NFR-1 have cases; NFR-2 has a documented gap.
- **Interface coverage:** IC-1 through IC-9 have cases.

The numbered list is the behavior to review; several related use cases can share one test case. Each case keeps the required preconditions, steps, expected results, tier, and owner. Versions in examples are OpenShift semver; the API stores desired `ClusterVersionReference` values. A public node-set name selects one NodePool, even when the node-set, resource-class, and NodePool names differ. The API rejects unknown node-set names; AAP checks whether the selected HyperShift NodePool exists when it applies an accepted upgrade.

## Use cases

1. A new cluster starts with node-set versions matching its control-plane version.
2. An existing ready cluster gains observed versions and becomes eligible during migration.
3. An existing cluster stays ineligible until HyperShift is ready and its versions can be resolved.
4. A target version must exist, be enabled, and not be obsolete; a deprecated version remains usable.
5. A control-plane target must be newer and keep every node pool within the allowed version skew.
6. A node-pool target must be newer, no newer than the control plane, and within the allowed skew.
7. Failed or deleting clusters cannot accept an upgrade.
8. A HyperShift cluster that has not become ready cannot accept an upgrade.
9. A ready HyperShift cluster can accept an upgrade while post-install work keeps the ClusterOrder `PROGRESSING`.
10. Later guest control-plane unavailability does not by itself close an otherwise open upgrade gate.
11. Only one upgrade request can be active per cluster, including competing control-plane and node-pool requests.
12. A control-plane upgrade changes only the selected HostedCluster image through AAP.
13. A node-pool upgrade changes only the NodePool selected by its public node-set name.
14. The API rejects a request for a missing or inaccessible cluster, or an unknown node set in that cluster.
15. If a selected HyperShift resource is missing or belongs to another ClusterOrder after acceptance, AAP fails before patching.
16. Retryable AAP failures recover without rerunning installation or launching duplicate work.
17. Create, scale, and upgrade jobs do not run concurrently for the same cluster.
18. An image-only upgrade does not trigger cluster creation or scaling.
19. A temporary catalog lookup failure leaves an accepted upgrade Pending until projection can resume.
20. An accepted upgrade stays Pending after the AAP patch until HyperShift starts the upgrade.
21. Success is reported only when the selected control plane or node pool reaches the accepted target version.
22. A terminal failure reports the error, preserves the observed version, records history, and releases the upgrade gate.
23. A timeout is a warning: it keeps the gate closed and adds no history until a later terminal result.
24. The API reports upgrade state, timestamps, and independent observed control-plane and node-pool versions.
25. History retains successful and failed attempts across restarts, ignores replay, and records a separately accepted retry.
26. Later scaling preserves each node pool's selected image, including the fallback for older ClusterOrders.
27. A version referenced by an active node set cannot be deleted.
28. Tenant permissions apply, and OSAC resolves a supplied catalog name or semver string to the release image.
29. The CLI requires exactly one target, reports server errors, and displays status and history.
30. The UI offers eligible choices, explains blocked actions, and shows progress and history.
31. Deployed API, CLI, and UI journeys cover successful upgrades and the specified retry, timeout, and failure paths.

## Coverage and execution

Each case names its **primary** tier and owner. The matrix adds boundaries that the same behavior also needs. Proposed tests have not run. A lower-tier check does not establish a deployed or real-AAP result.

| Behavior / cases | Required tier and owner | Location, command, and boundary |
|---|---|---|
| Admission, status, history, migration, catalog guard: `TC-FR7-01`–`06`, `10`, `13`, `14`, `TC-FR8-01`, `TC-FR10-01`, `TC-FR11-01`, `TC-FR12-01`, `TC-FR13-01` | Unit, fulfillment-service `[DEV]`; component integration for persistence, migration, and public/private API behavior | `ginkgo run -r internal` from `fulfillment-service/` runs logic with test-controlled catalog, Cluster, and feedback. Proposed `fulfillment-service/it/` cases run with `make -C ../osac-installer test PLATFORM=kind PROFILE=dev NS=osac SUITE=fulfillment` from `fulfillment-service/`; service, PostgreSQL, and API are real; HyperShift and AAP are simulated or omitted. Migration needs a pre-upgrade database fixture. The deployed API must reject downgrade and N-3 skew without persisting intent. |
| Upgrade routing, observation, retries, and job serialization: `TC-FR7-03`–`05`, `07`–`11` | Envtest, osac-operator `[DEV]` | `make test` from `osac-operator/`; Kubernetes API and controller are real, AAP client is fake, and HyperShift behavior is test-controlled. This does not prove AAP launch or a real HyperShift upgrade. |
| Selected image patch, target validation, and later scaling: `TC-FR7-07`–`09`, `12` | Component integration, osac-aap `[DEV]` | Proposed `osac-aap/tests/integration/targets/`, run by `make test` from `osac-aap/`; Kind API and Ansible tasks are real, deployed AAP controller and HyperShift reconciliation are absent. |
| AAP template launch, polling, and retry: `TC-FR7-07`–`10` | Contract, osac-operator/osac-aap `[DEV]` | No qualifying real-AAP contract suite or command is identified. Follow [OSAC-4843](https://redhat.atlassian.net/browse/OSAC-4843); Envtest's fake AAP client covers only caller logic. |
| CLI target selection, errors, and display: `TC-FR7-15`–`16` | Component integration, fulfillment-service CLI `[DEV]` | Proposed cases in `fulfillment-service/it/`, using the fulfillment Kind command above. CLI, deployed API, and PostgreSQL are real; AAP and HyperShift are omitted. Unit CLI checks may also run with `ginkgo run -r internal` and a mocked API. |
| UI choices, blocked actions, status, and history: `TC-NFR1-01` | Unit, osac-ui `[DEV]` | `pnpm test` from `osac-ui/`; rendered UI and interactions are real, Connect replies are mocked. |
| Tenant API/CLI, UI, and recovery journeys: `TC-FR7-17`–`18`, `TC-NFR1-02` | E2E, `[QE]` | Proposed `tests/e2e/` scenarios need deployed fulfillment-service, operator, AAP, and HyperShift. Provider setup and command are unresolved under [OSAC-4843](https://redhat.atlassian.net/browse/OSAC-4843). The browser runner has no identified owner/ticket; retry, timeout, and terminal-failure injection also need definition. |

## Test Cases

### FR-7: Upgrade state and lifecycle

#### TC-FR7-01: Initialize version baselines on creation

| Interface Change | Priority | Automation |
|---|---|---|
| IC-2, IC-3, IC-4 | critical | automated |

**Tier/owner:** Component integration, fulfillment-service `[DEV]`.

##### Preconditions

- An enabled catalog version `4.16.5` and a new cluster with two node sets.

##### Steps

1. Create the cluster at `4.16.5`; read its Cluster and ClusterOrder, then supply initial HyperShift readiness feedback and read it again.

##### Expected Results

- Both desired node-set versions equal the control-plane version. The accepted version and `CanUpgrade=False` are stored together until HyperShift is ready; readiness records observed control-plane and node-pool baselines with `CanUpgrade=True`. Initial installation creates no upgrade-history entry.

#### TC-FR7-02: Migrate versions and apply the HyperShift readiness gate

| Interface Change | Priority | Automation |
|---|---|---|
| IC-2, IC-3, IC-4, IC-9 | critical | automated |

**Tier/owner:** Component integration, fulfillment-service `[DEV]`.

##### Preconditions

- Pre-upgrade records include a ready HyperShift cluster with post-install work unfinished (including a failed task), one not yet ready, and one whose catalog baseline cannot be resolved.

##### Steps

1. Run the numbered migration, supply initial readiness feedback, and try an upgrade on each Cluster.
2. For the ready cluster, leave post-install work unfinished and later make its guest control plane unavailable; try another upgrade when `CanUpgrade=True`.

##### Expected Results

- Node-set references are backfilled from the control-plane reference. The ready, resolvable cluster stores observed control-plane and node-pool semver with `CanUpgrade=True` and accepts an upgrade even while its ClusterOrder is `PROGRESSING`. The not-yet-ready and unresolved clusters reject upgrades. Later guest control-plane unavailability does not itself close an open `CanUpgrade` gate. The migration adds no installation history and needs no new table.

#### TC-FR7-03: Accept and complete a selected upgrade

| Interface Change | Priority | Automation |
|---|---|---|
| IC-1, IC-2, IC-3, IC-4 | critical | automated |

**Tier/owner:** Envtest, osac-operator `[DEV]`, with fulfillment component integration for persisted status.

##### Preconditions

- HyperShift is ready, `CanUpgrade=True`, and an allowed target `4.17.3` exists for a control plane at `4.16.5`; repeat for one eligible node pool.

##### Steps

1. Accept an upgrade, complete the AAP image patch, and read the Cluster.
2. Report that the selected HyperShift component has started, then completed at `4.17.3`; read the Cluster after each change.

##### Expected Results

- Acceptance closes `CanUpgrade` and reports Pending. AAP patch success alone leaves Pending. HyperShift start reports Progressing; only completion of the **selected** component at `4.17.3` reports Succeeded, advances its observed version, and opens `CanUpgrade`. ClusterOrder upgrade status and public Cluster status follow those transitions. A different version or component cannot complete the attempt. Cluster and ClusterOrder provisioning states stay unchanged.

#### TC-FR7-04: Record a terminal failure without changing the observed version

| Interface Change | Priority | Automation |
|---|---|---|
| IC-3, IC-5 | critical | automated |

**Tier/owner:** Component integration, fulfillment-service `[DEV]`, with operator Envtest feedback.

##### Preconditions

- A control-plane or node-pool upgrade is active at observed version `4.16.5`.

##### Steps

1. Report a terminal HyperShift failure with an upgrade-specific message; read the Cluster and retry with a separately accepted target.

##### Expected Results

- The first attempt is Failed with completion time and message; observed version remains `4.16.5`, one failed history entry appears, and `CanUpgrade=True` is stored with the result. Provisioning state is unchanged. A new accepted request closes the gate; replay of the old failure cannot reopen it or duplicate history.

#### TC-FR7-05: Treat timeout as a warning until a terminal result

| Interface Change | Priority | Automation |
|---|---|---|
| IC-3, IC-5, IC-9 | critical | automated |

**Tier/owner:** Component integration, fulfillment-service `[DEV]`, with operator Envtest observation.

##### Preconditions

- An active attempt has no terminal result; a controlled clock can pass the implementation-defined timeout.

##### Steps

1. Pass the timeout and try another upgrade; then report a later successful or failed terminal result.

##### Expected Results

- TimedOut shows a warning, keeps `CanUpgrade=False`, rejects the second request, and adds no history. The operator keeps observing. The later terminal result replaces TimedOut, adds exactly one matching history entry, and opens the gate; only success advances the observed version.

#### TC-FR7-06: Return independent observed versions and upgrade timing

| Interface Change | Priority | Automation |
|---|---|---|
| IC-3, IC-4, IC-5 | high | automated |

**Tier/owner:** Component integration, fulfillment-service `[DEV]`.

##### Preconditions

- A control-plane upgrade has finished and one node pool is still at its earlier version; a second node pool can upgrade independently afterward.

##### Steps

1. Read the public Cluster during Progressing and after each terminal result.

##### Expected Results

- The response identifies component, source and target semver, state, message, and start/completion timestamps; completion follows start. `observed_cp_version` and each node set's `observed_version` change only with that component's success. History is returned through the public API.

#### TC-FR7-07: Patch only the selected control-plane image through AAP

| Interface Change | Priority | Automation |
|---|---|---|
| IC-1 | critical | automated |

**Tier/owner:** Component integration, osac-aap `[DEV]`, with operator Envtest routing.

##### Preconditions

- A ready ClusterOrder has a selected HostedCluster, two NodePools, and a newly resolved control-plane release image.

##### Steps

1. Reconcile the image-only intent through the AAP upgrade operation; inspect the three live resources and provisioning job count.
2. Inspect the operator's HostedCluster and NodePool RBAC verbs.

##### Expected Results

- Only the selected HostedCluster's `spec.release.image` changes to the catalog image. Both NodePools stay unchanged; no create, scale, installation, readiness, or post-install job runs. Image-only intent does not change the creation/scaling config hash, and the operator needs no HostedCluster write permission.

#### TC-FR7-08: Patch only the NodePool selected by node-set name

| Interface Change | Priority | Automation |
|---|---|---|
| IC-2 | critical | automated |

**Tier/owner:** Component integration, osac-aap `[DEV]`, with operator Envtest routing.

##### Preconditions

- Public node set `workers`, resource class `gpu`, and selected NodePool `pool-a` have distinct names; a second NodePool exists.

##### Steps

1. Upgrade `workers` and inspect the ClusterOrder mapping and both live NodePools.

##### Expected Results

- Fulfillment updates only the matching NodeRequest image, and AAP changes only `pool-a.spec.release.image`. The HostedCluster and other NodePool images are unchanged; public status and history identify `node_pool:workers`.

#### TC-FR7-09: Fail an accepted upgrade if its HyperShift resource is missing or foreign

| Interface Change | Priority | Automation |
|---|---|---|
| IC-1, IC-2 | high | automated |

**Tier/owner:** Component integration, osac-aap `[DEV]`.

##### Preconditions

- A request for an existing Cluster and node set has been accepted. Before AAP patches it, the selected HyperShift resource disappears or is found to belong to another ClusterOrder.

##### Steps

1. Run the AAP upgrade path for each target and inspect live images and Cluster status.

##### Expected Results

- Each job fails before changing any image. The already accepted attempt reports terminal Failed with a target-validation message, retains provisioning state, and can be retried through a new request after the resource is repaired.

#### TC-FR7-10: Recover from temporary AAP or catalog failure

| Interface Change | Priority | Automation |
|---|---|---|
| IC-1, IC-2, IC-3 | high | automated |

**Tier/owner:** Envtest, osac-operator `[DEV]`, with fulfillment Unit projection checks.

##### Preconditions

- An accepted attempt has a target catalog reference; separately induce a temporary catalog lookup failure and a retryable AAP error.

##### Steps

1. Reconcile during each failure, restore the dependency, and reconcile again, including after an operator restart.

##### Expected Results

- The accepted attempt stays Pending with an upgrade-specific message and `CanUpgrade=False`. Projection resumes from the stored intent. AAP retry uses backoff and does not run installation, start duplicate jobs, or repeat an already applied image patch.

#### TC-FR7-11: Serialize upgrade with create and scale work

| Interface Change | Priority | Automation |
|---|---|---|
| IC-1, IC-2 | high | automated |

**Tier/owner:** Envtest, osac-operator `[DEV]`.

##### Preconditions

- A create or scale job is active; repeat with an upgrade job active first.

##### Steps

1. Present the other job type, finish the active job, and reconcile the latest ClusterOrder.

##### Expected Results

- Only one job runs for the cluster at a time under the per-cluster lease. The waiting job begins after the active job ends and uses the latest desired state.

#### TC-FR7-12: Preserve component images during later scaling

| Interface Change | Priority | Automation |
|---|---|---|
| IC-1, IC-2 | high | automated |

**Tier/owner:** Component integration, osac-aap `[DEV]`.

##### Preconditions

- The control plane and one node pool use different selected images; another older ClusterOrder lacks a NodeRequest image.

##### Steps

1. Render and apply a later scale for both ClusterOrders.

##### Expected Results

- The HostedCluster uses the control-plane image; each NodePool keeps its own NodeRequest image. The older order's NodePool uses the control-plane image fallback, and scaling does not revert an independently upgraded pool.

#### TC-FR7-13: Protect a catalog version used only by a node set

| Interface Change | Priority | Automation |
|---|---|---|
| IC-2 | high | automated |

**Tier/owner:** Component integration, fulfillment-service `[DEV]`.

##### Preconditions

- An active Cluster references a catalog version only through a node set; include canonical-ID and legacy name-only references.

##### Steps

1. Try to soft-delete that version, then remove the last active reference and retry.

##### Expected Results

- Deletion is blocked while either reference exists and succeeds after none remain. Existing template and catalog-item protection stays in effect.

#### TC-FR7-14: Reject missing or inaccessible clusters and unknown node sets

| Interface Change | Priority | Automation |
|---|---|---|
| IC-1, IC-2, IC-9 | critical | automated |

**Tier/owner:** Component integration, fulfillment-service `[DEV]`.

##### Preconditions

- A tenant has Update permission on its own Cluster but not another tenant's Cluster. The tenant's Cluster has node set `workers` but not `missing`; an eligible version exists.

##### Steps

1. Request an upgrade for a nonexistent Cluster, the inaccessible Cluster, and node set `missing` on the tenant's Cluster.
2. Request an upgrade of the tenant's existing Cluster and node set using the eligible version.

##### Expected Results

- The first three requests are rejected before Pending status, desired version, gate, history, or projected image changes. The request for the accessible Cluster and its existing node set is accepted. ClusterOrder retains its tenant annotation.

#### TC-FR7-15: Use exactly one CLI upgrade target

| Interface Change | Priority | Automation |
|---|---|---|
| IC-6, IC-7 | high | automated |

**Tier/owner:** Component integration, fulfillment-service CLI `[DEV]`.

##### Preconditions

- Separate ready Cluster fixtures have an eligible control plane and node set `workers`.

##### Steps

1. Run `osac upgrade cluster c --control-plane --version 4.17.3` and `osac upgrade cluster c --node-set workers --version 4.17.3` as separate attempts.
2. Run the command with both targets, neither target, and a server-rejected request.

##### Expected Results

- Each valid command patches only its selected public field and prints acceptance. Both-target and no-target forms fail before an API request. A server rejection exits nonzero and displays the server's reason. The supplied `--version` string reaches the API unchanged.

#### TC-FR7-16: Display status and history in the CLI

| Interface Change | Priority | Automation |
|---|---|---|
| IC-8 | medium | automated |

**Tier/owner:** Component integration, fulfillment-service CLI `[DEV]`.

##### Preconditions

- The API returns one completed control-plane attempt and one node-pool attempt.

##### Steps

1. Run `osac describe cluster c`.

##### Expected Results

- Output shows control-plane and per-node-set observed versions, current or last upgrade state, source and target versions, component, timestamps, and both history outcomes.

#### TC-FR7-17: Upgrade control plane and named node pool through deployed API and CLI

| Interface Change | Priority | Automation |
|---|---|---|
| IC-1, IC-2, IC-3, IC-4, IC-5, IC-6, IC-7, IC-8 | critical | automated |

**Tier/owner:** E2E, `[QE]`; proposed.

##### Preconditions

- A deployed OSAC stack with AAP, HyperShift, a ready tenant HCP cluster, two distinct node sets, and eligible sequential targets.

##### Steps

1. Start a control-plane upgrade by CLI and observe it through the API; after its terminal result, upgrade one named node set through the API and observe it by CLI.

##### Expected Results

- Each attempt moves Pending → Progressing → Succeeded without changing provisioning state. The selected control plane, then only the selected NodePool, reaches its target; the other pool is unchanged. API and CLI show independent observed versions and two ordered history entries.

#### TC-FR7-18: Observe deployed retry, timeout, and failure

| Interface Change | Priority | Automation |
|---|---|---|
| IC-1, IC-2, IC-3, IC-5 | critical | automated |

**Tier/owner:** E2E, `[QE]`; proposed.

##### Preconditions

- A deployed test environment can induce a retryable AAP error, delay beyond the timeout, and a terminal HyperShift failure without fabricating a terminal result.

##### Steps

1. Run separate eligible attempts for each condition; restore AAP for the retry and allow a later terminal result after timeout.

##### Expected Results

- AAP retry keeps Pending and the gate closed until recovery. Timeout warns without history or gate release. Later terminal feedback replaces the warning. Terminal failure leaves the observed version unchanged, records one failed entry, opens the gate, and does not change provisioning state.

### FR-8: Node-pool version cannot exceed the control plane

#### TC-FR8-01: Reject a node-pool target above the observed control plane

| Interface Change | Priority | Automation |
|---|---|---|
| IC-2, IC-9 | critical | automated |

**Tier/owner:** Component integration, fulfillment-service `[DEV]`.

##### Preconditions

- Observed control plane is `4.17.3`; a node pool is at `4.16.5`; target `4.18.1` exists.

##### Steps

1. Request the node-pool upgrade to `4.18.1`.

##### Expected Results

- The API rejects the target and identifies its relationship to the observed control-plane version; desired versions, upgrade gate, and projected images do not change.

### FR-10: One active upgrade per cluster

#### TC-FR10-01: Admit only one of two concurrent requests for the same target

| Interface Change | Priority | Automation |
|---|---|---|
| IC-1, IC-2, IC-9 | critical | automated |

**Tier/owner:** Component integration, fulfillment-service `[DEV]`.

##### Preconditions

- A ready Cluster has `CanUpgrade=True` and two eligible control-plane targets; repeat with two eligible versions for one node set.

##### Steps

1. Submit the two requests for the same component concurrently; read stored intent and gate.

##### Expected Results

- Exactly one request succeeds in each run. The other is rejected with the active-upgrade reason. The winning desired version, Pending status, and `CanUpgrade=False` are stored in one transaction; only that image is projected.

### FR-11: No concurrent control-plane and node-pool upgrades

#### TC-FR11-01: Block control-plane and node-pool overlap

| Interface Change | Priority | Automation |
|---|---|---|
| IC-1, IC-2, IC-9 | critical | automated |

**Tier/owner:** Unit, fulfillment-service `[DEV]`.

##### Preconditions

- First a control-plane upgrade, then in a separate run a node-pool upgrade, holds `CanUpgrade=False`.

##### Steps

1. Request an upgrade of the other target during each active attempt.

##### Expected Results

- Each cross-target request is rejected with the active-upgrade reason; the active attempt and both desired versions remain unchanged. FR-10 covers simultaneous requests for the same target, and FR-8 covers the node-pool version cap.

### FR-12: Block unsupported versions and skew

#### TC-FR12-01: Validate catalog targets, upgrade direction, and version skew

| Interface Change | Priority | Automation |
|---|---|---|
| IC-1, IC-2, IC-9 | critical | automated |

**Tier/owner:** Component integration, fulfillment-service `[DEV]`, with Unit validation checks.

##### Preconditions

- The catalog has enabled, disabled, DEPRECATED, and OBSOLETE versions with known images; observed component version is `4.16.5`. One catalog name matches a different entry's version string.
- CP skew fixtures have pools at `4.17` and `4.16`, with targets `4.20` and `4.19`.
- NP skew fixtures have CP at `4.20`: a `4.15` pool targets `4.16`, and a `4.16` pool targets `4.17`.

##### Steps

1. Try absent, disabled, OBSOLETE, same-version, and older targets for both components.
2. On separate eligible fixtures, submit a newer DEPRECATED target by catalog name and a newer target by semver string; test the name/version collision and inspect projected images.
3. Request each CP and NP skew variant through the public API.
4. Repeat an otherwise valid request on FAILED, DELETING, and DELETE_FAILED Clusters.

##### Expected Results

- Invalid catalog, same-version, older-version, and blocked-state requests are rejected with the target or state reason and no new intent, gate change, or image projection.
- Both four-minor skew requests are rejected; both three-minor requests are accepted.
- The newer DEPRECATED target is accepted. Accepted name and semver inputs project their catalog images; a matching catalog name takes precedence over a different entry's version string.

### FR-13: Keep upgrade history

#### TC-FR13-01: Persist one entry per terminal attempt

| Interface Change | Priority | Automation |
|---|---|---|
| IC-3, IC-5 | critical | automated |

**Tier/owner:** Component integration, fulfillment-service `[DEV]`.

##### Preconditions

- A ready Cluster can run a successful CP attempt, a failed NP attempt, and a separately accepted retry.

##### Steps

1. Complete the three attempts, replay their terminal feedback, restart fulfillment-service, and read the Cluster.

##### Expected Results

- History retains exactly three entries in completion order with public component names, source/target semver, completion time, and success/failure outcome. Replays add none; the accepted retry adds its own entry even for repeated versions. Installation adds none.

### NFR-1: UI version choice, progress, and history

#### TC-NFR1-01: Offer eligible upgrades and explain blocked actions

| Interface Change | Priority | Automation |
|---|---|---|
| IC-1, IC-2, IC-3, IC-4, IC-5 | high | automated |

**Tier/owner:** Unit, osac-ui `[DEV]`.

##### Preconditions

- Mocked Cluster and catalog responses include an eligible target, invalid targets, active upgrade, and independently observed node-pool versions.

##### Steps

1. Open each control-plane and node-set choice; select an eligible upgrade, then inspect progress and history.

##### Expected Results

- Only eligible choices can submit; blocked actions show the admission reason and send no request. The UI shows target component, source/target versions, state, observed versions, and history.

#### TC-NFR1-02: Use the deployed UI to start and monitor an upgrade

| Interface Change | Priority | Automation |
|---|---|---|
| IC-1, IC-2, IC-3, IC-4, IC-5 | high | automated |

**Tier/owner:** E2E, `[QE]`; proposed.

##### Preconditions

- Deployed UI and upgrade stack, tenant login, eligible and blocked choices, and a persisted browser runner.

##### Steps

1. Select an eligible target in the UI, monitor it to a terminal result, and open its history; try a blocked choice.

##### Expected Results

- The selected component progresses to a visible terminal outcome and history entry. A blocked choice displays the reason and sends no upgrade request.

## Gaps

### Requirement Coverage Gaps

- **NFR-2, user documentation:** The local Phase 1 design does not specify a user-documentation deliverable or acceptance check. Confirm the intended documentation scope before adding a test case; the seven other requirements have cases.

### Interface Change Coverage Gaps

All nine interface changes are exercised by cases above.

### Execution Readiness Gaps

- **Real AAP contract:** Template launch, polling, and retry lack a qualifying contract suite and command; [OSAC-4843](https://redhat.atlassian.net/browse/OSAC-4843) tracks the provider test setup.
- **Deployed upgrades and recovery:** `TC-FR7-17`–`18` need provider environment, command, and controlled failure injection under [OSAC-4843](https://redhat.atlassian.net/browse/OSAC-4843). Their behavior is planned, not yet execution-ready.
- **Deployed browser journey:** `TC-NFR1-02` needs a persisted runner, command, owner, and follow-up ticket; none is identified. `pnpm test` proves UI component behavior only.

## Summary

| Metric | Count |
|---|---:|
| Use cases | 31 |
| Total test cases | 25 |
| Critical | 15 |
| High | 9 |
| Medium | 1 |
| Low | 0 |
| Automated, including proposed cases | 25 |
| Manual | 0 |
| Requirements with cases | 7 / 8 |
| Interface changes with cases | 9 / 9 |
