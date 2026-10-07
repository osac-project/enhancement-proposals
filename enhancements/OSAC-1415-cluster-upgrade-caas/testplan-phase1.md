# Testplan — OSAC-1415

## Overview

- **Feature:** OSAC-1415 — Cluster Upgrade CaaS (Stage 1)
- **Total test cases:** 47
- **Requirements with test cases:** 7 of 8 (FR-7, FR-8, FR-10, FR-11, FR-12, FR-13, NFR-1); NFR-2 is documentation
- **Interface changes covered:** 9 of 9 (IC-1 through IC-9)

PATCH steps below use semantic versions as shorthand; CP and NP desired versions are both `ClusterVersionReference` values on the wire, while observed versions are semver strings.

For NP cases, the public target is a CaaS node-set name. Fulfillment maps it to a `NodeRequest` by resource class; the operator selects the HyperShift NodePool by name, as introduced by [PR #1418](https://github.com/osac-project/osac/pull/1418). Targeting cases use different node-set, resource-class, and NodePool names and assert the selected NodePool name.

### Upgrade-path coverage and ownership

| Behavior / cases | Tier and owner | Boundary and execution evidence |
|---|---|---|
| Terminal history append, replay, and persistence (`TC-FR13-01`, `TC-FR13-02`, `TC-FR13-03`, `TC-IC2-01`) | Unit and component integration, fulfillment-service `[DEV]` | `ginkgo run -r internal` in `fulfillment-service/` for history logic; proposed case under `fulfillment-service/it/`, run by `make -C ../osac-installer test PLATFORM=kind PROFILE=dev NS=osac SUITE=fulfillment` from `fulfillment-service/`. The deployed service, PostgreSQL, and public/private APIs are real; operator feedback and HyperShift status are simulated. AAP and HyperShift reconciliation are omitted. |
| Upgrade-mode routing, NodePool name selection, job idempotency, feedback (`TC-IC1-01`, `TC-IC1-01c`, `TC-IC2-01`, `TC-FR7-01`, `TC-FR7-03b`) | Envtest, osac-operator `[DEV]` | `make test` in `osac-operator/`; real Kubernetes API and controller, fake AAP client and simulated HyperShift status. This does not prove the AAP service boundary. |
| Shared HC/NP image patch, unique target validation, later scale preserving per-NP image (`TC-IC1-01`, `TC-IC2-01`, `TC-IC2-01b`, `TC-IC2-01c`) | Component integration, osac-aap `[DEV]` | Proposed target under `osac-aap/tests/integration/targets/`, run by `make test` in `osac-aap/`; real Kind API and Ansible tasks, no real AAP controller or HyperShift reconciliation. |
| AAP template launch, polling, and retry (`TC-IC1-01c`) | Contract, osac-operator/osac-aap `[DEV]` | No qualifying real-AAP contract suite is currently identified; follow [OSAC-4843](https://redhat.atlassian.net/browse/OSAC-4843). A fake AAP client in Envtest covers caller logic only. |
| Deployed CP/NP upgrade and later scale (`TC-IC1-01`, `TC-IC2-01`, `TC-IC2-01b`) | E2E, `[QE]` | Proposed cases under `tests/e2e/` require deployed fulfillment-service, operator, AAP, and HyperShift; execution command and environment are unresolved pending the provider test setup in [OSAC-4843](https://redhat.atlassian.net/browse/OSAC-4843). |

---

## Test Cases

---

### FR-7: Upgrade status surfaced

FR-7 requires upgrade state (progressing/succeeded/failed), source and target versions, and transition timestamps in cluster status.

#### TC-FR7-01: Upgrade status transitions Progressing → Succeeded

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-1, IC-3 | critical | automated |

##### Preconditions

- Cluster in `CLUSTER_STATE_READY`. `status.observed_cp_version = "4.16.5"`. Target ClusterVersion has `metadata.name = "4-17-3"`, `spec.version = "4.17.3"`, and is ACTIVE.

##### Steps

1. `PATCH /clusters/{id}` with `spec.version = "4.17.3"`.
2. `GET /clusters/{id}` immediately after.
3. Simulate successful completion of the AAP patch job, then `GET /clusters/{id}`.
4. Simulate HyperShift signaling upgrade start; operator sets `upgradeStatus.state = Progressing` and sends private status feedback.
5. `GET /clusters/{id}`.
6. Simulate HyperShift completion; operator sets `upgradeStatus.state = Succeeded`, `completionTime`, `observedVersion = "4.17.3"`, and sends private status feedback.
7. `GET /clusters/{id}`.

##### Expected Results

- After step 1: HTTP 200, cluster state unchanged (READY), `conditions[CAN_UPGRADE].status = False`.
- After step 2: `status.upgrade.state = CLUSTER_UPGRADE_PROGRESS_STATE_PENDING` and `conditions[CAN_UPGRADE].status = False`.
- After step 3: `status.upgrade.state` is still `CLUSTER_UPGRADE_PROGRESS_STATE_PENDING`; AAP job success alone does not indicate HyperShift progress.
- After step 5: `status.upgrade.state = CLUSTER_UPGRADE_PROGRESS_STATE_PROGRESSING`, `from_version = "4.16.5"`, `to_version = "4.17.3"`, `started_at` is non-zero, `completed_at` is absent.
- After step 7: `status.upgrade.state = CLUSTER_UPGRADE_PROGRESS_STATE_SUCCEEDED`, `completed_at` is non-zero, `conditions[CAN_UPGRADE].status = True`, `status.observed_cp_version = "4.17.3"`, and Cluster/ClusterOrder provisioning status is unchanged.

---

#### TC-FR7-01b: CP upgrade completion requires target image and semver in HC history

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-1, IC-3 | critical | automated |

##### Preconditions

- CP upgrade to `4.17.3` in progress (`conditions[CAN_UPGRADE].status = False`). `HC.status.controlPlaneVersion.desired.image = ClusterOrder.spec.ReleaseImage`, `desired.version = "4.17.3"`, and `history[0].state = "Partial"`.

##### Steps

1. Simulate `HC.status.controlPlaneVersion.history[0].state = "Completed"` but `history[0].image` still names the previous release image.
2. `GET /clusters/{id}`.
3. Simulate `HC.status.controlPlaneVersion.history[0].image = ClusterOrder.spec.ReleaseImage`, but `version = "4.17.2"` and `state = "Completed"`; GET the Cluster.
4. Simulate `HC.status.controlPlaneVersion.history[0].version = "4.17.3"`.
5. `GET /clusters/{id}`.

##### Expected Results

- After step 2: `conditions[CAN_UPGRADE].status = False` — completion is not declared while the completed history image differs from the requested target.
- After step 3: `conditions[CAN_UPGRADE].status = False` while the completed history version differs from HyperShift's `desired.version = "4.17.3"`.
- After step 5: `conditions[CAN_UPGRADE].status = True`, `status.upgrade.state = CLUSTER_UPGRADE_PROGRESS_STATE_SUCCEEDED`, `status.observed_cp_version = "4.17.3"`.

---

#### TC-FR7-02: Terminal upgrade failure releases the upgrade lock

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-1, IC-3 | critical | automated |

##### Preconditions

- Cluster in `CLUSTER_STATE_READY`. `observed_cp_version = "4.16.5"`. ClusterVersions `4.17.3` and `4.17.4` ACTIVE.

##### Steps

1. `PATCH /clusters/{id}` `spec.version = "4.17.3"`.
2. Simulate the operator reporting a terminal upgrade failure (detection criteria TBD): set `upgradeStatus.state = Failed`, `completionTime`, and an upgrade-specific message; send private status feedback.
3. `GET /clusters/{id}`.
4. `PATCH /clusters/{id}` with `spec.version = "4.17.4"`, replay the failed result for `4.17.3`, then `GET /clusters/{id}`.

##### Expected Results

- Step 3: `status.upgrade.state = CLUSTER_UPGRADE_PROGRESS_STATE_FAILED`, `completed_at` and the upgrade-specific message are set, one `status.version_history` entry records `success = false`, `conditions[CAN_UPGRADE].status = True`, Cluster state remains READY, ClusterOrder provisioning status is unchanged, and `status.observed_cp_version` remains `"4.16.5"`.
- Step 4: the new request is accepted; stale feedback does not release its lock or duplicate the failed history entry. `status.upgrade.state = CLUSTER_UPGRADE_PROGRESS_STATE_PENDING` for `4.17.4` and `conditions[CAN_UPGRADE].status = False`.

---

#### TC-FR7-03: Upgrade timestamps are non-zero and ordered

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-3 | medium | automated |

##### Preconditions

- Completed upgrade scenario (TC-FR7-01 completed).

##### Steps

1. `GET /clusters/{id}` after upgrade completes.

##### Expected Results

- `status.upgrade.started_at` < `status.upgrade.completed_at`.
- Both timestamps are valid RFC 3339 / protobuf Timestamp values with non-zero seconds.

---

#### TC-FR7-03b: NP upgrade completion requires NodePool.status.version match

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-2, IC-4 | critical | automated |

##### Preconditions

- NP upgrade for node set `workers` to `4.17.3` is in progress (`conditions[CAN_UPGRADE].status = False`). Its resource class is `gpu` and its desired reference name is `4-17-3`. The `NodeRequest` with `ResourceClass="gpu"` has `Version="4.17.3"`; the selected NodePool is named `pool-a` and has `status.conditions[UpdatingVersion].status = True`.

##### Steps

1. Simulate `pool-a.status.conditions[UpdatingVersion].status = False` but `pool-a.status.version = "4.17.2"` (version mismatch).
2. `GET /clusters/{id}`.
3. Simulate `pool-a.status.version = "4.17.3"` with `UpdatingVersion=False`.
4. `GET /clusters/{id}`.

##### Expected Results

- After step 2: `conditions[CAN_UPGRADE].status = False` — completion not declared while `status.version != "4.17.3"`.
- After step 4: `conditions[CAN_UPGRADE].status = True`, `status.node_sets["workers"].observed_version = "4.17.3"`.

---

### FR-10: One active upgrade per cluster

FR-10 requires that only one upgrade can be in progress at a time per cluster.

#### TC-FR10-01: Upgrade request rejected when upgrade already in progress

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-1, IC-9 | critical | automated |

##### Preconditions

- Upgrade to `4.17.3` in progress; `conditions[CAN_UPGRADE].status = False`. ClusterVersion `4.17.4` ACTIVE.

##### Steps

1. `PATCH /clusters/{id}` `spec.version = "4.17.4"`.

##### Expected Results

- gRPC `FAILED_PRECONDITION`, message includes upgrade-in-progress reason from `CanUpgrade` condition. No change to `ClusterOrder.spec.ReleaseImage`.

---

---

#### TC-FR10-03: NP upgrade rejected when CP upgrade already in progress

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-2, IC-9 | critical | automated |

##### Preconditions

- CP upgrade to `4.17.3` in progress; `conditions[CAN_UPGRADE].status = False`. ClusterVersion `4.16.5` ACTIVE. Node pool `workers` at `4.15.5`.

##### Steps

1. `PATCH /clusters/{id}` `spec.node_sets["workers"].version = "4.16.5"`.

##### Expected Results

- gRPC `FAILED_PRECONDITION`, message includes upgrade-in-progress reason from `CanUpgrade` condition. No `ClusterOrder.spec.nodeRequests` change.

---

#### TC-FR10-04: Upgrade rejected on FAILED cluster

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-1, IC-9 | critical | automated |

##### Preconditions

- Cluster in `CLUSTER_STATE_FAILED` because provisioning failed. ClusterVersion `4.17.3` ACTIVE.

##### Steps

1. `PATCH /clusters/{id}` `spec.version = "4.17.3"`.

##### Expected Results

- gRPC `FAILED_PRECONDITION`, message = `"cluster is in state FAILED and cannot be upgraded"`. No `ClusterOrder.spec.ReleaseImage` change.

---

### FR-13: Upgrade history

FR-13 requires a record of every upgrade attempt that reached a terminal result.

#### TC-FR13-01: Completed upgrade appears in version history

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-3, IC-5 | critical | automated |

##### Preconditions

- Cluster in `CLUSTER_STATE_READY`. `observed_cp_version = "4.16.5"`. ClusterVersion `4.17.3` ACTIVE.

##### Steps

1. Complete an upgrade from `4.16.5` to `4.17.3` (TC-FR7-01 scenario completed).
2. `GET /clusters/{id}`.

##### Expected Results

- `status.version_history` contains one entry: `from_version = "4.16.5"`, `to_version = "4.17.3"` (OpenShift semver, not catalog name `4-17-3`), `success = true`, `completed_at` is non-zero and matches `status.upgrade.completed_at`.

---

#### TC-FR13-02: Control-plane and node-pool history survives later upgrades and feedback replay

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-5 | medium | automated |

##### Preconditions

- Cluster `READY`, with control plane at `4.17.3`, node set `workers` at `4.16.5`, `CanUpgrade=True`, and an empty `status.version_history`. Versions `4.17.3` and `4.17.5` are ACTIVE.

##### Steps

1. Upgrade `workers` from `4.16.5` to `4.17.3`. Send successful node-pool completion feedback and `GET /clusters/{id}`.
2. Replay the same completion feedback and `GET /clusters/{id}` again.
3. Upgrade the control plane from `4.17.3` to `4.17.5`. Send success feedback after HyperShift reports completion and `GET /clusters/{id}`.
4. Upgrade `workers` from `4.17.3` to `4.17.5`. Send successful node-pool completion feedback, restart fulfillment-service, and `GET /clusters/{id}`.

##### Expected Results

- After step 2, replay has not added a duplicate; one entry has `component = "node_pool:workers"`, `from_version = "4.16.5"`, `to_version = "4.17.3"`, and `success = true`.
- After step 3, the node-pool entry remains alongside the new `control_plane` entry; control-plane feedback has not replaced it.
- After step 4, the persisted `status.version_history` has exactly three upgrade entries ordered by `completed_at` ascending: the first node-pool transition, the control-plane transition, and `node_pool:workers` from `4.17.3` to `4.17.5`. Every entry has a nonzero completion time and `success = true`.

---

#### TC-FR13-03: Failed control-plane and node-pool attempts appear in history

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-5 | medium | automated |

##### Preconditions

- A control-plane attempt from `4.16.5` to `4.17.3` fails (TC-FR7-02 scenario). On a separate Cluster whose control plane is at `4.17.3`, a node-pool attempt from `4.16.5` to `4.17.3` also fails.

##### Steps

1. `GET /clusters/{id}` after each failure, then replay its terminal feedback and GET again.

##### Expected Results

- Each Cluster has exactly one history entry for its failed attempt, with the public component, `from_version = "4.16.5"`, `to_version = "4.17.3"`, `success = false`, and a nonzero `completed_at` matching `status.upgrade.completed_at`.
- `status.upgrade.state = CLUSTER_UPGRADE_PROGRESS_STATE_FAILED`; replay adds no entry and the observed version remains `"4.16.5"`.

---

### NFR-1: UI support — version selection, status monitoring, history

NFR-1 requires that the API surface supports UI display of upgrade state, history, and version selection.

---

### IC-1: `PATCH /clusters/{id}` spec.version — CP upgrade trigger and validation

#### TC-IC1-01: CP upgrade on READY cluster patches HC through AAP only

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-1 | critical | automated |

##### Preconditions

- Cluster `READY`. `observed_cp_version = "4.16.5"`. Node pools at `observed_version = "4.15.5"`. ClusterVersion `4.17.3` ACTIVE. Cluster has two node pools.

##### Steps

1. `PATCH /clusters/{id}` `spec.version = "4.17.3"`.
2. Reconcile the ClusterOrder and run the existing cluster AAP job in upgrade mode against the HC.

##### Expected Results

- HTTP 200. `ClusterOrder.spec.ReleaseImage` is updated to the image from ClusterVersion `4.17.3`. The operator launches the configured create-hosted-cluster AAP template once in upgrade mode and does not patch HC itself. The playbook finds the existing HC, patches only `HostedCluster.spec.release.image`, and reads it back to confirm the target image; its install/post-install tasks do not run, and `NodePool.spec.release.image` values and other HC fields do not change. Cluster state is unchanged; `conditions[CAN_UPGRADE].status = False` is written in the acceptance transaction.

---

#### TC-IC1-01b: Only one concurrent upgrade request succeeds

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-1, IC-9 | critical | automated |

##### Preconditions

- Cluster in `CLUSTER_STATE_READY` with `CAN_UPGRADE=True` and `observed_cp_version = "4.16.5"`. ClusterVersions `4.17.3` and `4.17.4` are ACTIVE. Do not deliver upgrade completion feedback during the test.

##### Steps

1. Use a barrier to start two `PATCH /clusters/{id}` requests at the same time, for `spec.version = "4.17.3"` and `spec.version = "4.17.4"`.
2. Read the stored Cluster after both requests finish; reconcile it and read the derived `ClusterOrder.spec.ReleaseImage`.

##### Expected Results

- One request returns HTTP 200; the other returns `FAILED_PRECONDITION` with the `CanUpgrade` reason.
- The stored Cluster version matches the successful request and has no stored release image; `CanUpgrade=False`. The reconciled `ClusterOrder.spec.ReleaseImage` matches that version's `ClusterVersion.spec.image`. The rejected request changes nothing.

---

#### TC-IC1-01c: AAP upgrade-mode run failure retries without cluster reprovisioning

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-1 | critical | automated |

##### Preconditions

- A CP upgrade to `4.17.3` is Pending. The existing HC still has the old image, and no upgrade job has succeeded for this target.

##### Steps

1. Reconcile once with the configured cluster AAP template unavailable; restore it and reconcile again.
2. Fail the launched AAP job before it patches HC; reconcile through the configured retry backoff.
3. Let the retried job patch HC successfully; restart the operator and reconcile again before HyperShift reports progress.

##### Expected Results

- Launch and patch failures retain `status.upgrade.state = Pending`, keep `CanUpgrade=False`, and expose an upgrade-specific message. The operator retries the configured AAP template in upgrade mode with backoff; its installation branch does not run.
- The recorded job ID prevents a duplicate launch while the job is active. After the image matches, restart does not launch another job. AAP job success alone leaves the upgrade Pending until HyperShift signals a start; ClusterOrder provisioning status is unchanged.

---

#### TC-IC1-02: Upgrade with OBSOLETE target version is rejected

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-1, IC-9 | critical | automated |

##### Preconditions

- ClusterVersion `4.17.3` exists with `state = OBSOLETE`. Cluster in `READY`.

##### Steps

1. `PATCH /clusters/{id}` `spec.version = "4.17.3"`.

##### Expected Results

- gRPC `INVALID_ARGUMENT`, message = `"version 4.17.3 is obsolete and cannot be used as an upgrade target"`. No `ClusterOrder.spec.ReleaseImage` change.

---

#### TC-IC1-03: Upgrade with DEPRECATED target version is accepted

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-1 | high | automated |

##### Preconditions

- ClusterVersion `4.17.3` with `state = DEPRECATED`. `observed_cp_version = "4.16.5"`. Cluster `READY`.

##### Steps

1. `PATCH /clusters/{id}` `spec.version = "4.17.3"`.

##### Expected Results

- HTTP 200. `ClusterOrder.spec.ReleaseImage` updated to DEPRECATED version's image (DEPRECATED is allowed as upgrade target).

---

#### TC-IC1-04: Downgrade is rejected

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-1, IC-9 | critical | automated |

##### Preconditions

- `observed_cp_version = "4.17.3"`. ClusterVersion `4.16.5` ACTIVE. Cluster `READY`.

##### Steps

1. `PATCH /clusters/{id}` `spec.version = "4.16.5"`.

##### Expected Results

- gRPC `INVALID_ARGUMENT`, message = `"target version 4.16.5 is not greater than current version 4.17.3"`.

---

#### TC-IC1-05: Same-version upgrade is rejected

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-1, IC-9 | high | automated |

##### Preconditions

- `observed_cp_version = "4.17.3"`. ClusterVersion `4.17.3` ACTIVE. Cluster `READY`.

##### Steps

1. `PATCH /clusters/{id}` `spec.version = "4.17.3"`.

##### Expected Results

- gRPC `INVALID_ARGUMENT`, message = `"target version 4.17.3 is not greater than current version 4.17.3"`.

---

#### TC-IC1-06: Upgrade rejected when PROGRESSING + HC not yet available (CanUpgrade=False)

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-1, IC-9 | high | automated |

##### Preconditions

- Cluster in `CLUSTER_STATE_PROGRESSING` (initial provisioning in progress). HC `Available=False` and Cluster `READY=False`. Fulfillment created the Cluster with `CAN_UPGRADE=False`. ClusterVersion `4.17.3` ACTIVE.

##### Steps

1. `PATCH /clusters/{id}` `spec.version = "4.17.3"`.

##### Expected Results

- gRPC `FAILED_PRECONDITION`, message identifies missing Cluster `READY=True` feedback. No `ClusterOrder.spec.ReleaseImage` change. Blocking rule: DB `CAN_UPGRADE=False`.

---

#### TC-IC1-07: Upgrade allowed on PROGRESSING cluster (AAP tasks running)

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-1 | high | automated |

##### Preconditions

- A new Cluster with two node sets and selected ClusterVersion `spec.version="4.16.5"` was stored with `CAN_UPGRADE=False` in its creation transaction. `CLUSTER_STATE_PROGRESSING` persists while AAP post-provisioning tasks run. `ClusterOrder.conditions[ClusterAvailable]=True`, but Cluster `READY=True` feedback has not yet been stored. Observed versions are empty. ClusterVersion `4.17.3` ACTIVE.

##### Steps

1. Deliver Cluster `READY=True` through private status feedback while `ClusterOrder.phase=Progressing`.
2. `PATCH /clusters/{id}` `spec.version = "4.17.3"`.

##### Expected Results

- Create stored both desired node-set version references equal to the selected CP reference with `CAN_UPGRADE=False` in one transaction.
- Step 1 stores `READY=True`, the CP and both node-set observed semver baselines (`"4.16.5"`), and `CAN_UPGRADE=True` in one transaction while Cluster state remains `PROGRESSING`.
- Step 2 returns HTTP 200 and stores the upgrade target with `CAN_UPGRADE=False` in one transaction.

---

#### TC-IC1-07b: Upgrade allowed on PROGRESSING cluster (failed AAP post-provisioning)

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-1 | high | automated |

##### Preconditions

- Cluster in `CLUSTER_STATE_PROGRESSING` with `READY=True` and DB `CAN_UPGRADE=True`; AAP post-provisioning tasks subsequently failed. `observed_cp_version = "4.16.5"`. ClusterVersion `4.17.3` ACTIVE.

##### Steps

1. `PATCH /clusters/{id}` `spec.version = "4.17.3"`.

##### Expected Results

- HTTP 200, cluster state unchanged (PROGRESSING), `conditions[CAN_UPGRADE].status = False`. Failed AAP post-provisioning does not block the upgrade at the API level.

---

#### TC-IC1-08: Upgrade rejected when HC Available but Cluster READY=False

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-1, IC-9 | high | automated |

##### Preconditions

- Cluster in `CLUSTER_STATE_PROGRESSING` (initial provisioning; HC created and Available=True) with Cluster `READY=False` and DB `CAN_UPGRADE=False`. ClusterVersion `4.17.3` ACTIVE.

##### Steps

1. `PATCH /clusters/{id}` `spec.version = "4.17.3"`.

##### Expected Results

- gRPC `FAILED_PRECONDITION`, message identifies missing Cluster `READY=True` feedback. No `ClusterOrder.spec.ReleaseImage` change. Blocking rule: DB `CAN_UPGRADE=False`.

---

#### TC-IC1-09: CP upgrade rejected when target version is not in the catalog

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-1, IC-9 | critical | automated |

##### Preconditions

- No ClusterVersion with name or version string `"4.99.0"` exists in the catalog.
  Cluster in `READY`. `observed_cp_version = "4.16.5"`.

##### Steps

1. `PATCH /clusters/{id}` `spec.version = "4.99.0"`.

##### Expected Results

- gRPC `INVALID_ARGUMENT`, message = `"version 4.99.0 not found in the ClusterVersion catalog"`.
  No DB write. No `ClusterOrder.spec.ReleaseImage` change.

---

#### TC-IC2-05: NP upgrade rejected before Cluster READY feedback (CanUpgrade=False)

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-2, IC-9 | high | automated |

##### Preconditions

- Cluster in `CLUSTER_STATE_PROGRESSING` (initial provisioning) with Cluster `READY=False` and DB `CAN_UPGRADE=False`. Node pool `workers` has not reached its requested version. ClusterVersion `4.17.0` ACTIVE.

##### Steps

1. `PATCH /clusters/{id}` `spec.node_sets["workers"].version = "4.17.0"`.

##### Expected Results

- gRPC `FAILED_PRECONDITION`, message identifies missing Cluster `READY=True` feedback. No `ClusterOrder.spec.nodeRequests` change. Blocking rule: DB `CAN_UPGRADE=False`.

---

#### TC-IC1-10: Upgrade accepted when ControlPlaneAvailable=False (cluster-internal state, not an API gate)

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-1 | high | automated |

##### Preconditions

- Cluster in `CLUSTER_STATE_READY`. HC `Available=True`, version converged. **`ControlPlaneAvailable=False`** (cluster-internal: CP temporarily unreachable). `CAN_UPGRADE=True` (ControlPlaneAvailable is not included in CanUpgrade). ClusterVersion `4.17.3` ACTIVE.

##### Steps

1. `PATCH /clusters/{id}` `spec.version = "4.17.3"`.

##### Expected Results

- HTTP 200, cluster state unchanged (READY), `conditions[CAN_UPGRADE].status = False`. `ControlPlaneAvailable=False` is a cluster-internal state not captured by `CanUpgrade` — the upgrade is accepted and the operator launches the AAP patch job. Whether HyperShift progresses depends on its responsiveness.

---

#### TC-IC1-11: CP upgrade rejected when target version violates N-3 skew against existing node pool

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-1, IC-9 | critical | automated |

##### Preconditions

- `observed_cp_version = "4.17.3"`. Node pool `workers` at `observed_version = "4.14.5"` (CP-NP skew = 3, at the limit). ClusterVersion `4.18.0` ACTIVE. Cluster `READY`.

##### Steps

1. `PATCH /clusters/{id}` `spec.version = "4.18.0"`.

##### Expected Results

- gRPC `INVALID_ARGUMENT`, message = `"target control plane version 4.18.0 would leave node pool workers at 4.14.5 more than 3 minor versions behind"`. No `ClusterOrder.spec.ReleaseImage` change.

---

### IC-2: `PATCH /clusters/{id}` spec.node_sets[*].version — NP upgrade trigger and validation

#### TC-IC2-01: NP upgrade on READY cluster patches the target NodePool through AAP only

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-2 | critical | automated |

##### Preconditions

- Cluster `READY`. `observed_cp_version = "4.17.3"`. Node set `workers` uses resource class `gpu` and has `observed_version = "4.16.5"`; the other node set uses `cpu`. Their existing NodePools are named `pool-a` and `pool-b`, deliberately different from the node-set and resource-class names. `pool-a` is the named target for `workers`. ClusterVersion `4.17.3` is ACTIVE.

##### Steps

1. `PATCH /clusters/{id}` `spec.node_sets["workers"].version = "4.17.3"`.
2. Reconcile the ClusterOrder and run the existing cluster AAP job in upgrade mode for the NP upgrade.
3. Simulate `pool-a` completing at `4.17.3`, deliver private status feedback, and read the public Cluster.

##### Expected Results

- After step 1: HTTP 200, cluster state unchanged, and `conditions[CAN_UPGRADE].status = False` written in the acceptance transaction.
- After step 2: The `NodeRequest` with `ResourceClass="gpu"` receives the image from ClusterVersion `4.17.3`; the `cpu` request is unchanged. The operator selects `pool-a` by name and launches the configured create-hosted-cluster AAP template once in upgrade mode with internal component `node_pool:pool-a`. The playbook confirms that the named NodePool belongs to this `ClusterOrder`, patches only `pool-a.spec.release.image`, and reads it back. Install/post-install tasks do not run, and the HostedCluster image, `pool-b` image, and other NP fields do not change.
- After step 3: Public `status.upgrade.component` and the new history entry use `node_pool:workers`; that entry has `from_version = "4.16.5"`, `to_version = "4.17.3"`, `success = true`, and a nonzero `completed_at`. Only `status.node_sets["workers"].observed_version` advances to `4.17.3`. `conditions[CAN_UPGRADE].status = True`, and cluster provisioning state is unchanged.

---

#### TC-IC2-01b: Later scaling preserves an independently upgraded NodePool image

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-2 | high | automated |

##### Preconditions

- The CP and another NP are at `4.18.0`; `workers` completed an independent upgrade from `4.16.5` to `4.17.3`, and its `NodeRequest` contains the `4.17.3` image.

##### Steps

1. Change only `workers` desired node count to trigger the existing scaling/create-hosted-cluster AAP path.
2. Run the scaling playbook and read the HC and both NodePool specs.

##### Expected Results

- Scaling changes the replica count without resetting the NodePool matched to `workers` from the `4.17.3` image to the CP's `4.18.0` image. The HC and other NP images remain unchanged, and no upgrade job is launched for the scale-only change.

---

#### TC-IC2-01c: Shared upgrade patch fails for missing or mismatched targets

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-1, IC-2 | high | automated |

##### Preconditions

- A component-integration environment has the cluster working namespace, a `ClusterOrder`, and a valid CP or NP upgrade-mode payload.

##### Steps

1. Run the shared upgrade patch with the selected HC absent; repeat with the selected NP absent.
2. Create HC and NP resources with a mismatched ClusterOrder association, then repeat each patch.
3. For an NP upgrade, restore the correctly associated named target and add another associated NodePool with a different name; run the patch, then repeat after removing the selected named target while the other remains.
4. Run the CP and NP patches against correctly associated resources with the selected named NP present, then read both resources.

##### Expected Results

- Each missing or mismatched target fails the AAP playbook without creating a resource or changing an image. A different NodePool cannot satisfy a missing named target; a `state: patched` missing-resource warning alone is not accepted as success.
- A target-validation failure is reported as a terminal upgrade failure rather than retried indefinitely; fulfillment releases `CanUpgrade` while Cluster and ClusterOrder provisioning state remain unchanged.
- Each valid run changes only its selected resource's `spec.release.image`, confirms the value by readback, and leaves the other resource and all unrelated spec fields unchanged. Installation and post-install tasks do not run.

---

#### TC-IC2-02: NP upgrade rejected when target version exceeds CP version

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-2, IC-9 | critical | automated |

##### Preconditions

- `observed_cp_version = "4.16.5"`. Node pool `workers` at `4.16.5`. ClusterVersion `4.17.3` ACTIVE. Cluster `READY`.

##### Steps

1. `PATCH /clusters/{id}` `spec.node_sets["workers"].version = "4.17.3"`.

##### Expected Results

- gRPC `INVALID_ARGUMENT`, message = `"target node pool version 4.17.3 exceeds control plane version 4.16.5"`. No `ClusterOrder` change.

---

#### TC-IC2-03: NP upgrade rejected when version skew would exceed N-3 minor versions

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-2, IC-9 | critical | automated |

##### Preconditions

- `observed_cp_version = "4.17.3"`. Node pool `workers` at `4.13.9` (already at N-4 skew). ClusterVersion `4.14.5` ACTIVE. Cluster `READY`.

##### Steps

1. `PATCH /clusters/{id}` `spec.node_sets["workers"].version = "4.14.5"`.

##### Expected Results

- gRPC `INVALID_ARGUMENT`, message = `"target node pool version 4.14.5 exceeds maximum allowed skew of 3 minor versions behind control plane 4.17.3"`. No `ClusterOrder` change.

---

#### TC-IC2-04: NP downgrade is rejected

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-2, IC-9 | critical | automated |

##### Preconditions

- `observed_cp_version = "4.17.3"`. Node pool `workers` at `observed_version = "4.16.5"`. ClusterVersion `4.15.9` ACTIVE. Cluster `READY`.

##### Steps

1. `PATCH /clusters/{id}` `spec.node_sets["workers"].version = "4.15.9"`.

##### Expected Results

- gRPC `INVALID_ARGUMENT`, message = `"target version 4.15.9 is not greater than current node pool version 4.16.5"`. No `ClusterOrder` change.

---

#### TC-IC2-06: NP upgrade rejected when target version is not in the catalog

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-2, IC-9 | critical | automated |

##### Preconditions

- No ClusterVersion with name or version string `"4.99.0"` exists in the catalog.
  Cluster `READY`. `observed_cp_version = "4.17.3"`. Node pool `workers` at `observed_version = "4.16.5"`.

##### Steps

1. `PATCH /clusters/{id}` `spec.node_sets["workers"].version = "4.99.0"`.

##### Expected Results

- gRPC `INVALID_ARGUMENT`, message = `"version 4.99.0 not found in the ClusterVersion catalog"`.
  No `ClusterOrder` change.

---

### IC-3: `GET /clusters/{id}` — observed version and upgrade state

#### TC-IC3-01: observed_cp_version populated after upgrade completes

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-3 | high | automated |

##### Preconditions

- CP upgrade from `4.16.5` to `4.17.3` completed.

##### Steps

1. `GET /clusters/{id}`.

##### Expected Results

- `status.observed_cp_version = "4.17.3"`.

---

#### TC-IC3-02: Upgrade progress visible in GET response while upgrade is in progress

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-3 | high | automated |

##### Preconditions

- Upgrade in progress; operator signaled `upgradeStatus={state:Progressing, ...}` to fulfillment-service. `conditions[CAN_UPGRADE].status = False`.

##### Steps

1. `GET /clusters/{id}`.

##### Expected Results

- `conditions[CAN_UPGRADE].status = False`. `status.upgrade.state = CLUSTER_UPGRADE_PROGRESS_STATE_PROGRESSING`. `status.upgrade.from_version` and `to_version` are non-empty.

---

### IC-4: `GET /clusters/{id}` — per-NP observed version

#### TC-IC4-01: Node set observed_version populated after upgrade

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-4 | medium | automated |

##### Preconditions

- Upgrade from `4.16.5` to `4.17.3` completed. Cluster has one node set `workers`.

##### Steps

1. `GET /clusters/{id}`.

##### Expected Results

- `status.node_sets["workers"].observed_version = "4.17.3"`.

---

#### TC-IC4-02: Node set observed_version reflects its own upgrade, independent of CP version

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-4 | medium | automated |

##### Preconditions

- Cluster with two node sets: `workers` (upgraded from `4.15.5` to `4.16.5`) and `gpu-nodes` (still at `4.15.5`). CP is at `4.17.3`.

##### Steps

1. `GET /clusters/{id}`.

##### Expected Results

- `status.observed_cp_version = "4.17.3"`.
- `status.node_sets["workers"].observed_version = "4.16.5"`.
- `status.node_sets["gpu-nodes"].observed_version = "4.15.5"`.
- Node set observed versions reflect their own individual upgrade history, independent of the CP version.

---

### IC-5: `GET /clusters/{id}` — version history

#### TC-IC5-01: Completed upgrade appears in version_history

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-5 | medium | automated |

##### Preconditions

- Upgrade from `4.16.5` to `4.17.3` completed successfully.

##### Steps

1. `GET /clusters/{id}`.

##### Expected Results

- `status.version_history` contains one entry: `from_version = "4.16.5"`, `to_version = "4.17.3"`, `success = true`, `completed_at` is non-zero.

---

#### TC-IC5-02: History entries are ordered by completed_at ascending

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-5 | low | automated |

##### Preconditions

- Three completed sequential upgrades (TC-FR13-02 scenario).

##### Steps

1. `GET /clusters/{id}`.

##### Expected Results

- `status.version_history[0].completed_at` < `status.version_history[1].completed_at` < `status.version_history[2].completed_at`.

---

### IC-6: `osac upgrade cluster <name> --version <version>`

#### TC-IC6-01: CLI issues correct CP PATCH and prints upgrade accepted response

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-6 | high | automated |

##### Preconditions

- Mock server returns HTTP 200 with cluster state unchanged and `conditions[CAN_UPGRADE].status = False`.

##### Steps

1. `osac upgrade cluster my-cluster --version 4.17.3`.

##### Expected Results

- Exit code 0. Stdout shows the cluster resource (state unchanged, `can_upgrade: false`). PATCH request body contains `spec.version.name = "4-17-3"`.

---

#### TC-IC6-02: CLI exits non-zero on server error

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-6 | high | automated |

##### Preconditions

- Mock server returns `FAILED_PRECONDITION`.

##### Steps

1. `osac upgrade cluster my-cluster --version 4.17.3`.

##### Expected Results

- Exit code 1. Stderr contains the `FAILED_PRECONDITION` error message from the server.

---

### IC-7: `osac upgrade cluster <name> --node-set <node_set_name> --version <version>`

#### TC-IC7-01: CLI issues correct NP PATCH and prints upgrade accepted response

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-7 | high | automated |

##### Preconditions

- Mock server returns HTTP 200 with cluster state unchanged and `conditions[CAN_UPGRADE].status = False`.

##### Steps

1. `osac upgrade cluster my-cluster --node-set workers --version 4.17.3`.

##### Expected Results

- Exit code 0. Stdout shows the cluster resource (state unchanged, `can_upgrade: false`). PATCH request body contains `spec.node_sets["workers"].version.name = "4-17-3"`, the same reference type used for CP upgrades.

---

#### TC-IC7-02: CLI exits non-zero on NP server error

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-7 | high | automated |

##### Preconditions

- Mock server returns `INVALID_ARGUMENT` (e.g., target version exceeds CP version).

##### Steps

1. `osac upgrade cluster my-cluster --node-set workers --version 4.19.0`.

##### Expected Results

- Exit code 1. Stderr contains the `INVALID_ARGUMENT` error message from the server.

---

### IC-8: Enhanced `osac describe cluster <name>`

#### TC-IC8-01: describe output includes observed version and upgrade state

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-8 | low | automated |

##### Preconditions

- Mock `GET /clusters/{id}` response with `observed_cp_version = "4.17.3"`, `upgrade.state = SUCCEEDED`.

##### Steps

1. `osac describe cluster my-cluster`.

##### Expected Results

- Stdout contains `Observed Version: 4.17.3` and `Upgrade State: Succeeded`.

---

#### TC-IC8-02: describe output includes version history table

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-8 | low | automated |

##### Preconditions

- Mock response with 2 history entries in `status.version_history`.

##### Steps

1. `osac describe cluster my-cluster`.

##### Expected Results

- Stdout contains a table with columns `From`, `To`, `Completed`, `Result` and 2 data rows with the correct version strings.

---

### IC-9: Validation rejection errors

#### TC-IC9-01: All rejection codes are structured gRPC errors

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-9 | critical | automated |

##### Preconditions

- Setup for each of the 3 rejection conditions defined in IC-9: OBSOLETE target, downgrade, non-READY state.

##### Steps

1. Trigger each rejection condition.

##### Expected Results

- Each response is a gRPC Status error with the code specified in IC-9 (`INVALID_ARGUMENT` or `FAILED_PRECONDITION`) and the matching message pattern. No `INTERNAL` (status code 13) error is returned for any of these conditions.

---

#### TC-IC9-02: Error messages include the actual version strings

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-9 | medium | automated |

##### Preconditions

- `observed_cp_version = "4.17.3"`. Target version `"4.16.5"` is a downgrade.

##### Steps

1. `PATCH /clusters/{id}` `spec.version = "4.16.5"`.

##### Expected Results

- Error message is `"target version 4.16.5 is not greater than current version 4.17.3"` — contains both version strings verbatim so operators can diagnose without additional lookups.

---

## Gaps

### Requirement Coverage Gaps

| Requirement | Gap |
|-------------|-----|
| FR-8 (NP version capped at CP version) | Tested by TC-IC2-02 (NP upgrade rejected when target version exceeds CP version). |
| FR-11 (NP version cap follows CP; no concurrent CP+NP upgrade) | NP version cap: tested by TC-IC2-02. TC-FR10-03 rejects an NP request during a CP upgrade; TC-FR10-01 rejects a CP request during an unspecified active upgrade. A CP request during an NP upgrade is not explicitly covered. |
| FR-12 (unsupported version skews blocked) | Tested by TC-IC2-03 (NP upgrade N-3 skew rejection) and TC-IC1-11 (CP upgrade N-3 skew rejection against existing NPs). |
| NFR-2 (user documentation) | Documentation requirement; no automated test applicable. Documentation must be produced as a separate deliverable. |

### Interface Change Coverage Gaps

All 9 interface changes are covered by test cases. No gaps.

---

## Summary

| Metric | Count |
|--------|-------|
| Total test cases | 47 |
| Critical | 21 |
| High | 16 |
| Medium | 7 |
| Low | 3 |
| Automated | 47 |
| Manual | 0 |
| Requirements with test cases | 7 / 8 |
| Interface changes with test cases | 9 / 9 |
