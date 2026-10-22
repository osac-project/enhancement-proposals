# Testplan — OSAC-1415

## Overview

- **Feature:** Cluster Upgrade CaaS
- **Use cases:** 31 plain-language behaviors, grouped into the cases below
- **Test cases:** 25 (22 local checks; 3 proposed deployed E2E journeys)
- **Requirement coverage:** FR-7, FR-8, FR-10, FR-11, FR-12, FR-13, and NFR-1 have cases; NFR-2 has a documented gap.
- **Interface coverage:** IC-1 through IC-9 have cases.

The numbered list is the behavior to review; several related use cases can share one test case. Each case keeps the required preconditions, steps, expected results, tier, and owner. Versions in examples are OpenShift semver; the API stores desired `ClusterVersionReference` values. One tenant request selects a target for the whole cluster. OSAC applies separate control-plane and NodePool image changes in order, and reports per-component history and observed versions. The public node-set spec has no version selector in the intended contract; its current presence is an implementation gap.

## Use cases

1. A new cluster starts with node-set versions matching its control-plane version.
2. A newly created ready cluster gains observed versions and becomes eligible after HyperShift readiness feedback.
3. A new cluster stays ineligible until HyperShift is ready and its versions can be resolved.
4. A target version must exist, be enabled, and not be obsolete; a deprecated version remains usable.
5. A cluster target must advance at least one component without an unsupported control-plane/node-pool skew.
6. Node pools never advance above the completed control-plane version.
7. Failed or deleting clusters cannot accept an upgrade.
8. A HyperShift cluster that has not become ready cannot accept an upgrade.
9. A ready HyperShift cluster can accept an upgrade while post-install work keeps the ClusterOrder `PROGRESSING`.
10. Later guest control-plane unavailability does not by itself close an otherwise open upgrade gate.
11. Only one whole-cluster upgrade request can be active at a time.
12. The first stage changes the HostedCluster image through the existing AAP job.
13. After control-plane success, one batch changes every eligible NodePool image.
14. The API rejects a request for a missing or inaccessible cluster and does not expose a node-set version selector.
15. AAP errors are reported for the affected component without changing another cluster's resources.
16. Retryable AAP failures recover without rerunning installation or launching duplicate work.
17. AAP jobs for a ClusterOrder are serialized, and an active upgrade blocks node-set additions and size increases.
18. A changed release image changes the `ClusterOrder.spec` hash and dispatches the existing AAP job; an ID-only annotation edit does not.
19. A temporary catalog lookup failure leaves an accepted upgrade Pending until projection can resume.
20. An accepted upgrade stays Pending after the AAP patch until HyperShift starts the upgrade.
21. A component succeeds only when HyperShift observes its accepted target version; the cluster gate stays closed until all participating components finish.
22. A terminal failure updates its existing history entry and preserves the observed version; other node pools continue after one fails.
23. A timeout updates the existing entry as a warning and keeps the gate closed while observation continues.
24. The API reports request acceptance and last state-transition times with independent observed component versions.
25. History retains current and previous attempts newest first across restarts, ignores replay, and creates no attempt for an unchanged stored target.
26. Later reconciliation preserves each node pool's image; scale-out is blocked during an active upgrade.
27. A version referenced by a control plane or any node set cannot be deleted.
28. Tenant permissions apply, and CLI catalog-name/semver resolution matches new-cluster creation.
29. The CLI accepts one cluster target version, reports server errors, and displays status and history.
30. The UI offers eligible choices, explains blocked actions, and shows progress and history.
31. Deployed API, CLI, and UI journeys cover successful upgrades and the specified retry, timeout, and failure paths.

## Coverage and execution

Each case names its **primary** tier and owner. The matrix adds boundaries that the same behavior also needs. Proposed tests have not run. A lower-tier check does not establish a deployed or real-AAP result.

| Behavior / cases | Required tier and owner | Location, command, and boundary |
|---|---|---|
| Admission, status, history, creation baseline, catalog guard: `TC-FR7-01`–`06`, `10`, `13`, `14`, `TC-FR8-01`, `TC-FR10-01`, `TC-FR11-01`, `TC-FR12-01`, `TC-FR13-01` | Unit, fulfillment-service `[DEV]`; component integration for persistence and public/private API behavior | `ginkgo run -r internal` from `fulfillment-service/` runs logic with test-controlled catalog, Cluster, and feedback. Proposed `fulfillment-service/it/` cases run with `make -C ../osac-installer test PLATFORM=kind PROFILE=dev NS=osac SUITE=fulfillment` from `fulfillment-service/`; service, PostgreSQL, and API are real; HyperShift and AAP are simulated or omitted. The deployed API must reject downgrade and N-3 skew without persisting intent. |
| Upgrade routing, observation, retries, and job serialization: `TC-FR7-03`–`05`, `07`–`11` | Envtest, osac-operator `[DEV]` | `make test` from `osac-operator/`; Kubernetes API and controller are real, AAP client is fake, and HyperShift behavior is test-controlled. This does not prove AAP launch or a real HyperShift upgrade. |
| Component image application and later reconciliation: `TC-FR7-07`–`09`, `12` | Component integration, osac-aap `[DEV]` | Proposed `osac-aap/tests/integration/targets/`, run by `make test` from `osac-aap/`; Kind API and Ansible tasks are real, deployed AAP controller and HyperShift reconciliation are absent. |
| AAP template launch, polling, and retry: `TC-FR7-07`–`10` | Contract, osac-operator/osac-aap `[DEV]` | No qualifying real-AAP contract suite or command is identified. Follow [OSAC-4843](https://redhat.atlassian.net/browse/OSAC-4843); Envtest's fake AAP client covers only caller logic. |
| CLI version selection, errors, and display: `TC-FR7-15`–`16` | Component integration, fulfillment-service CLI `[DEV]` | Proposed cases in `fulfillment-service/it/`, using the fulfillment Kind command above. CLI, deployed API, and PostgreSQL are real; AAP and HyperShift are omitted. Unit CLI checks may also run with `ginkgo run -r internal` and a mocked API. |
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

#### TC-FR7-02: Establish observed versions and the HyperShift readiness gate

| Interface Change | Priority | Automation |
|---|---|---|
| IC-2, IC-3, IC-4, IC-9 | critical | automated |

**Tier/owner:** Component integration, fulfillment-service `[DEV]`.

##### Preconditions

- Clusters created with OSAC-1415 include one ready HyperShift cluster whose post-install work is unfinished, one not yet ready, and one whose observed node-pool version has not yet been reported.

##### Steps

1. Supply initial readiness and version feedback, then try a whole-cluster upgrade on each Cluster.
2. For the ready cluster, leave post-install work unfinished and later make its guest control plane unavailable; try another upgrade when `CanUpgrade=True`.

##### Expected Results

- The ready cluster with complete observed versions stores control-plane and node-pool semver with `CanUpgrade=True` and accepts one cluster upgrade even while its ClusterOrder is `PROGRESSING`. The not-yet-ready cluster and the one missing an observed version reject upgrades. Later guest control-plane unavailability does not itself close an open `CanUpgrade` gate. Initial installation adds no upgrade-history entries.

#### TC-FR7-03: Accept one request and complete its component upgrades

| Interface Change | Priority | Automation |
|---|---|---|
| IC-1, IC-2, IC-3, IC-4 | critical | automated |

**Tier/owner:** Envtest, osac-operator `[DEV]`, with fulfillment component integration for persisted status.

##### Preconditions

- HyperShift is ready, `CanUpgrade=True`, and an allowed target `4.17.3` exists for a control plane and two node pools at `4.16.5`.

##### Steps

1. Accept one cluster request and read its history before any AAP job runs.
2. Apply and observe the control-plane image and result; read the Cluster before and after control-plane success.
3. Apply both NodePool images, report separate start and completion observations, and read the Cluster after each result.

##### Expected Results

- Acceptance closes `CanUpgrade` and immediately creates the control plane's Pending history entry. AAP success alone leaves that entry Pending. HyperShift observations update only the matching component entry and observed version. NodePool images are not projected before control-plane success; both are then accepted as Pending component attempts and projected together before their AAP job. The gate opens only after all started components reach a definitive result. A different version, component, or attempt ID cannot complete an entry. Cluster and ClusterOrder provisioning states stay unchanged.

#### TC-FR7-04: Record a terminal failure without changing the observed version

| Interface Change | Priority | Automation |
|---|---|---|
| IC-3, IC-5 | critical | automated |

**Tier/owner:** Component integration, fulfillment-service `[DEV]`, with operator Envtest feedback.

##### Preconditions

- One cluster request has active component entries at observed version `4.16.5`.

##### Steps

1. Report a terminal control-plane failure in one run and a node-pool failure after control-plane success in another; read the Cluster after each.
2. Repeat the stored target reference after failure, then select a different eligible catalog target in a separate run.

##### Expected Results

- Each failed component's existing entry changes to Failed with a message and last-state time; its observed version remains `4.16.5`. Control-plane failure prevents node-pool work and creates no node-pool entries; a failed node pool does not stop other pools. The gate opens after the applicable definitive results. Repeating the stored target creates no new entry or AAP job, even while an observed version lags. A later accepted changed target creates new entries; replay of old feedback cannot mutate them or duplicate history. Provisioning state is unchanged.

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

- The already present component entry changes to TimedOut with a warning and last-state time. `CanUpgrade=False` rejects the second request; no new entry is added. The operator keeps observing. A later definitive result updates that same entry and contributes to gate release; only success advances the observed version.

#### TC-FR7-06: Return independent observed versions and upgrade timing

| Interface Change | Priority | Automation |
|---|---|---|
| IC-3, IC-4, IC-5 | high | automated |

**Tier/owner:** Component integration, fulfillment-service `[DEV]`.

##### Preconditions

- Within one accepted cluster request, the control plane has finished and two node pools report progress independently.

##### Steps

1. Read the public Cluster during Progressing and after each terminal result.

##### Expected Results

- The response identifies each component's source and target semver, state, message, request acceptance time, and last state-transition time. Every entry is present at acceptance; its last-state time changes only on a newly observed state, including a later result after TimedOut. `observed_cp_version` and each node set's `observed_version` change only when that component reaches the accepted target. History remains newest first by acceptance, even when an older entry changes state.

#### TC-FR7-07: Dispatch the existing AAP job for a changed control-plane image

| Interface Change | Priority | Automation |
|---|---|---|
| IC-1 | critical | automated |

**Tier/owner:** Component integration, osac-aap `[DEV]`, with operator Envtest routing.

##### Preconditions

- A ready ClusterOrder has a selected HostedCluster, two NodePools, and a newly resolved control-plane release image.

##### Steps

1. Reconcile the changed `ClusterOrder.spec.releaseImage` through the existing AAP cluster job; inspect the three live resources and provisioning job count.
2. Change only the internal attempt-ID annotation on the order and reconcile again.
3. Inspect the operator's HostedCluster and NodePool RBAC verbs.

##### Expected Results

- The changed release image changes the spec hash and launches the existing AAP cluster job. AAP applies the HostedCluster image and stamps its attempt ID; both NodePool images stay unchanged until control-plane success. The annotation-only edit changes no hash and launches no job. The operator needs no HostedCluster write permission. AAP job success does not by itself complete the component history entry.

#### TC-FR7-08: Upgrade every eligible NodePool after control-plane success

| Interface Change | Priority | Automation |
|---|---|---|
| IC-2 | critical | automated |

**Tier/owner:** Component integration, osac-aap `[DEV]`, with operator Envtest routing.

##### Preconditions

- Public node sets `workers` and `batch` map to NodePools `pool-a` and `pool-b`, with different resource-class and NodePool names. A third pool is already at target.

##### Steps

1. Accept one cluster upgrade and inspect all NodeRequest images before control-plane success.
2. Report control-plane success, then inspect the ClusterOrder mapping, the AAP job, and all live NodePools.

##### Expected Results

- No NodePool image changes before control-plane success. Fulfillment then projects the target to both eligible NodeRequests in one batch; AAP applies it to `pool-a` and `pool-b` and stamps their own attempt IDs. The already-target pool is skipped. Public history identifies the OSAC node-set names, and each pool can report progress independently.

#### TC-FR7-09: Isolate an AAP reconciliation error to the affected component

| Interface Change | Priority | Automation |
|---|---|---|
| IC-1, IC-2 | high | automated |

**Tier/owner:** Component integration, osac-aap `[DEV]`.

##### Preconditions

- A whole-cluster request has been accepted; AAP can be made to fail while applying one component without modifying another cluster's resources.

##### Steps

1. Run the existing AAP cluster job with a controlled error for the control plane and, separately, for one node pool; inspect the live resources and component history.

##### Expected Results

- The job reports its actual reconciliation error; another cluster's resources are unchanged. The corresponding accepted component entry is updated through the normal failure path, without creating a second entry or changing provisioning state. A retryable AAP error follows the existing job backoff rather than a repeated tenant request for the same stored target.

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

- The accepted component entry stays Pending with an upgrade-specific message and `CanUpgrade=False`. Projection resumes from stored intent. AAP retry uses the existing backoff and does not start duplicate jobs for an unchanged desired config.

#### TC-FR7-11: Block scale-out and serialize AAP work during an upgrade

| Interface Change | Priority | Automation |
|---|---|---|
| IC-1, IC-2 | high | automated |

**Tier/owner:** Envtest, osac-operator `[DEV]`.

##### Preconditions

- A create or scale job is active; repeat with an upgrade job active first and an active cluster upgrade gate.

##### Steps

1. Present the other desired update, finish the active AAP job, and reconcile the latest ClusterOrder.
2. During the active cluster upgrade, request a new node set, a size increase, a size reduction, and removal of an upgrading node set.

##### Expected Results

- Only one AAP job runs for the ClusterOrder at a time; the next job uses the latest desired spec. Node-set additions and size increases are rejected during the active upgrade. Scale-in and removal follow normal update rules. A removed participant's existing entry becomes NodeSetRemoved after its NodePool is deleted; it does not keep the cluster gate open indefinitely.

#### TC-FR7-12: Preserve component images during later reconciliation

| Interface Change | Priority | Automation |
|---|---|---|
| IC-1, IC-2 | high | automated |

**Tier/owner:** Component integration, osac-aap `[DEV]`.

##### Preconditions

- The control plane and one node pool use different selected images; a NodeRequest without its own image exercises the existing fallback.

##### Steps

1. Render and apply a later allowed update for both ClusterOrders.

##### Expected Results

- The HostedCluster uses the control-plane image; each NodePool keeps its own NodeRequest image. A NodeRequest with no image uses the control-plane image fallback, and later reconciliation does not revert an independently upgraded pool.

#### TC-FR7-13: Protect catalog versions used by control planes or node sets

| Interface Change | Priority | Automation |
|---|---|---|
| IC-2 | high | automated |

**Tier/owner:** Component integration, fulfillment-service `[DEV]`.

##### Preconditions

- Active Clusters reference distinct catalog versions through a control plane and through a node set.

##### Steps

1. Try to soft-delete each referenced version, then remove its last active reference and retry.

##### Expected Results

- Deletion is blocked while any control-plane or node-set reference exists and succeeds after none remain. Existing template and catalog-item protection stays in effect.

#### TC-FR7-14: Enforce tenant access and the single public version selector

| Interface Change | Priority | Automation |
|---|---|---|
| IC-1, IC-2, IC-9 | critical | automated |

**Tier/owner:** Component integration, fulfillment-service `[DEV]`.

##### Preconditions

- A tenant has Update permission on its own Cluster but not another tenant's Cluster. Its Cluster has node set `workers`, and an eligible version exists.

##### Steps

1. Request an upgrade for a nonexistent Cluster and the inaccessible Cluster.
2. Inspect the public Cluster node-set contract, then request one upgrade of the accessible Cluster using its cluster-level version selector.

##### Expected Results

- The first two requests are rejected before desired version, gate, history, or projected image changes. The public node-set spec has no writable version field. The accessible Cluster's single request is accepted for the entire cluster; ClusterOrder retains its tenant annotation.

#### TC-FR7-15: Resolve one CLI cluster target like new-cluster creation

| Interface Change | Priority | Automation |
|---|---|---|
| IC-6, IC-7 | high | automated |

**Tier/owner:** Component integration, fulfillment-service CLI `[DEV]`.

##### Preconditions

- A ready Cluster has a control plane and node set `workers`. Catalog fixtures include a version name, a semver string, and a name/version collision.

##### Steps

1. Run `osac upgrade cluster c --version 4.17.3` with catalog-name and semver inputs on separate fixtures; repeat the name/version collision used by `osac create cluster`.
2. Run the command without a version and with a server-rejected version.

##### Expected Results

- Each valid command resolves the version with the same name-first rules as new-cluster creation, sends the canonical catalog reference through the single cluster-level update, and prints acceptance. Missing version fails before an API request. A server rejection exits nonzero and displays the server's reason. No CLI control-plane or node-set target flag is exposed.

#### TC-FR7-16: Display status and history in the CLI

| Interface Change | Priority | Automation |
|---|---|---|
| IC-8 | medium | automated |

**Tier/owner:** Component integration, fulfillment-service CLI `[DEV]`.

##### Preconditions

- The API returns component entries from one cluster request, including a completed control plane and a still-running node set, plus older history.

##### Steps

1. Run `osac describe cluster c`.

##### Expected Results

- Output shows control-plane and per-node-set observed versions and component history newest first, including current and older states, source and target versions, acceptance and last-transition times.

#### TC-FR7-17: Upgrade a whole cluster through one deployed CLI request

| Interface Change | Priority | Automation |
|---|---|---|
| IC-1, IC-2, IC-3, IC-4, IC-5, IC-6, IC-7, IC-8 | critical | automated |

**Tier/owner:** E2E, `[QE]`; proposed.

##### Preconditions

- A deployed OSAC stack with AAP, HyperShift, a ready tenant HCP cluster, two distinct node sets, and an eligible cluster target.

##### Steps

1. Start one cluster upgrade by CLI and observe it through the API and CLI as the control plane and both NodePools progress.

##### Expected Results

- The control plane reaches the target before either NodePool image advances; both eligible NodePools then upgrade without another user request. Their component entries move independently from Pending through Progressing to Succeeded, while the gate opens only after all finish. API and CLI show independent observed versions and newest-first history; provisioning state stays unchanged.

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

- AAP retry keeps the existing Pending entry and the gate closed until recovery. Timeout updates the existing entry without creating another or releasing the gate; later definitive feedback updates it again. Terminal failure leaves the component's observed version unchanged, updates its existing entry, and releases the gate only when the cluster request has finished; provisioning state stays unchanged.

### FR-8: Node-pool version cannot exceed the control plane

#### TC-FR8-01: Keep node pools at or below the completed control plane

| Interface Change | Priority | Automation |
|---|---|---|
| IC-2, IC-9 | critical | automated |

**Tier/owner:** Component integration, fulfillment-service `[DEV]`.

##### Preconditions

- Observed control plane and one node pool are `4.16.5`; an eligible whole-cluster target `4.17.3` exists.

##### Steps

1. Accept one cluster upgrade to `4.17.3` and report AAP control-plane patch success before HyperShift control-plane completion.
2. Report control-plane completion and observe the subsequent NodePool image and status.

##### Expected Results

- The NodePool stays at `4.16.5` until the control plane is observed at `4.17.3`. It may then advance to `4.17.3`, never above the completed control-plane version. No separate node-pool request is required.

### FR-10: One active upgrade per cluster

#### TC-FR10-01: Admit only one of two concurrent cluster requests

| Interface Change | Priority | Automation |
|---|---|---|
| IC-1, IC-2, IC-9 | critical | automated |

**Tier/owner:** Component integration, fulfillment-service `[DEV]`.

##### Preconditions

- A ready Cluster has `CanUpgrade=True` and two eligible whole-cluster targets.

##### Steps

1. Submit the two cluster requests concurrently; read stored intent, history, and gate.

##### Expected Results

- Exactly one request succeeds. The other is rejected with the active-upgrade reason. The winning desired version, initial Pending component history, and `CanUpgrade=False` are stored in one transaction; only that request's image is projected.

### FR-11: No concurrent control-plane and node-pool upgrades

#### TC-FR11-01: Sequence component upgrades within one cluster request

| Interface Change | Priority | Automation |
|---|---|---|
| IC-1, IC-2, IC-9 | critical | automated |

**Tier/owner:** Unit, fulfillment-service `[DEV]`.

##### Preconditions

- One cluster request has been accepted with a control plane and two node pools below target.

##### Steps

1. Observe the AAP job and NodePool images before control-plane success, then report control-plane success and observe the next AAP job and both NodePools.

##### Expected Results

- No NodePool image advances while the control plane is still upgrading. After control-plane success, both eligible NodePools are scheduled without a second tenant request and may progress concurrently. `CanUpgrade` remains False until the cluster request has finished. FR-10 covers concurrent tenant requests, and FR-8 covers the version cap.

### FR-12: Block unsupported versions and skew

#### TC-FR12-01: Validate catalog targets, upgrade direction, and version skew

| Interface Change | Priority | Automation |
|---|---|---|
| IC-1, IC-2, IC-9 | critical | automated |

**Tier/owner:** Component integration, fulfillment-service `[DEV]`, with Unit validation checks.

##### Preconditions

- The catalog has enabled, disabled, DEPRECATED, and OBSOLETE versions with distinct known images; observed component version is `4.16.5`. One catalog name matches a different entry's version string.
- CP skew fixtures have pools at `4.17` and `4.16`, with targets `4.20` and `4.19`.
- Node-pool skew fixtures have one pool more than three minor versions behind the proposed completed control plane and one within the limit.

##### Steps

1. Try absent, disabled, OBSOLETE, unchanged stored-reference, and older whole-cluster targets.
2. On separate eligible fixtures, submit a newer DEPRECATED target by catalog name and a newer target by semver string; test the name/version collision and inspect projected images.
3. Request each control-plane and node-pool skew variant through the public API's single cluster target.
4. Repeat an otherwise valid request on FAILED, DELETING, and DELETE_FAILED Clusters.

##### Expected Results

- Invalid catalog, older-version, and blocked-state requests are rejected with the target or state reason and no new intent, gate change, history entry, or image projection. Repeating the stored reference creates no new attempt or job even if observed status lags.
- Both four-minor skew requests are rejected; both three-minor requests are accepted.
- The newer DEPRECATED target is accepted. Accepted name and semver inputs project their catalog images; a matching catalog name takes precedence over a different entry's version string.

### FR-13: Keep upgrade history

#### TC-FR13-01: Persist current and previous component attempts newest first

| Interface Change | Priority | Automation |
|---|---|---|
| IC-3, IC-5 | critical | automated |

**Tier/owner:** Component integration, fulfillment-service `[DEV]`.

##### Preconditions

- A ready Cluster can accept a target for its control plane and two node sets, then later accept a different eligible target. Controlled feedback can arrive out of order.

##### Steps

1. Accept the first cluster request; read history before AAP and again after control-plane success schedules both node sets.
2. Fail one node set while the other progresses, then complete the other; accept a changed later target. Replay older feedback, restart fulfillment-service, and read the Cluster.

##### Expected Results

- Every component entry appears as Pending when that component upgrade is accepted, before a terminal result. Each entry retains its public component name, source and target semver, acceptance time, latest state time, state, and message. Entries stay newest first by acceptance even when an older entry changes after a newer one; observations update only the matching attempt. Replays and unchanged-target requests add none. Installation adds none.

### NFR-1: UI version choice, progress, and history

#### TC-NFR1-01: Offer eligible upgrades and explain blocked actions

| Interface Change | Priority | Automation |
|---|---|---|
| IC-1, IC-2, IC-3, IC-4, IC-5 | high | automated |

**Tier/owner:** Unit, osac-ui `[DEV]`.

##### Preconditions

- Mocked Cluster and catalog responses include an eligible target, invalid targets, active upgrade, and independently observed node-pool versions.

##### Steps

1. Open the cluster version choice; select an eligible target once, then inspect control-plane and node-set progress and history.

##### Expected Results

- Only eligible cluster targets can submit; blocked actions show the admission reason and send no request. The UI exposes no separate node-set version choice and shows each component's source/target versions, state, observed version, acceptance time, last-transition time, and newest-first history.

#### TC-NFR1-02: Use the deployed UI to start and monitor an upgrade

| Interface Change | Priority | Automation |
|---|---|---|
| IC-1, IC-2, IC-3, IC-4, IC-5 | high | automated |

**Tier/owner:** E2E, `[QE]`; proposed.

##### Preconditions

- Deployed UI and upgrade stack, tenant login, eligible and blocked choices, and a persisted browser runner.

##### Steps

1. Select one eligible cluster target in the UI, monitor the control plane and node pools to their results, and open history; try a blocked choice.

##### Expected Results

- One user action starts the cluster request. The control plane and then eligible node pools show independent progress and results in history. A blocked choice displays the reason and sends no upgrade request.

## Gaps

### Requirement Coverage Gaps

- **NFR-2, user documentation:** The design does not specify a user-documentation deliverable or acceptance check. Confirm the intended documentation scope before adding a test case; the seven other requirements have cases.

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
