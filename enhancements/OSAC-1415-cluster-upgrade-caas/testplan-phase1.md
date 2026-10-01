# Testplan — OSAC-1415

## Overview

- **Feature:** OSAC-1415 — Cluster Upgrade CaaS (Stage 1)
- **Total test cases:** 42
- **Requirements covered:** 7 of 8 (FR-7, FR-8, FR-10, FR-11, FR-12, FR-13, NFR-1); NFR-2 is documentation
- **Interface changes covered:** 9 of 9 (IC-1 through IC-9)

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

- Cluster in `CLUSTER_STATE_READY`. `status.observed_cp_version = "4.16.5"`. ClusterVersion `4.17.3` is ACTIVE.

##### Steps

1. `PATCH /clusters/{id}` with `spec.version = "4.17.3"`.
2. `GET /clusters/{id}` immediately after.
3. Simulate operator setting `upgradeStatus.state = Progressing` and signaling to fulfillment-service.
4. Simulate operator completing upgrade: sets `upgradeStatus.state = Succeeded`, `completionTime`, `observedVersion = "4.17.3"`, signals CLUSTER_STATE_READY.
5. `GET /clusters/{id}`.

##### Expected Results

- After step 1: HTTP 200, cluster state unchanged (READY), `conditions[CAN_UPGRADE].status = False`.
- After step 2: `status.upgrade.state = CLUSTER_UPGRADE_PROGRESS_STATE_PROGRESSING`, `from_version = "4.16.5"`, `to_version = "4.17.3"`, `started_at` is non-zero, `completed_at` is absent.
- After step 5: `status.upgrade.state = CLUSTER_UPGRADE_PROGRESS_STATE_SUCCEEDED`, `completed_at` is non-zero, `conditions[CAN_UPGRADE].status = True`, `status.observed_cp_version = "4.17.3"`.

---

#### TC-FR7-01b: CP upgrade completion requires version match in HC history

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-1, IC-3 | critical | automated |

##### Preconditions

- CP upgrade to `4.17.3` in progress (`conditions[CAN_UPGRADE].status = False`). `HC.status.controlPlaneVersion.history[0].state = "Partial"` (upgrade in progress).

##### Steps

1. Simulate `HC.status.controlPlaneVersion.history[0].state = "Completed"` but `history[0].version = "4.17.2"` (version mismatch — different version completed).
2. `GET /clusters/{id}`.
3. Simulate `HC.status.controlPlaneVersion.history[0].version = "4.17.3"` (correct version) AND `history[0].state = "Completed"` AND all eligibility conditions hold.
4. `GET /clusters/{id}`.

##### Expected Results

- After step 2: `conditions[CAN_UPGRADE].status = False` — completion not declared while `history[0].version != "4.17.3"`.
- After step 4: `conditions[CAN_UPGRADE].status = True`, `status.upgrade.state = CLUSTER_UPGRADE_PROGRESS_STATE_SUCCEEDED`, `status.observed_cp_version = "4.17.3"`.

---

#### TC-FR7-02: Upgrade status reflects Failed state

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-1, IC-3 | critical | automated |

##### Preconditions

- Cluster in `CLUSTER_STATE_READY`. `observed_cp_version = "4.16.5"`. ClusterVersion `4.17.3` ACTIVE.

##### Steps

1. `PATCH /clusters/{id}` `spec.version = "4.17.3"`.
2. Simulate operator detecting HostedCluster upgrade failure; sets `upgradeStatus.state = Failed`, `message = "HostedCluster condition Degraded=True: etcd not available"`, signals CLUSTER_STATE_FAILED.
3. `GET /clusters/{id}`.

##### Expected Results

- Step 3: `status.upgrade.state = CLUSTER_UPGRADE_PROGRESS_STATE_FAILED`, `message = "HostedCluster condition Degraded=True: etcd not available"`, `status.state = CLUSTER_STATE_FAILED`, `status.observed_cp_version` remains `"4.16.5"`.

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

#### TC-FR7-03b: NP upgrade completion requires NodePool.status.version match and eligibility conditions

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-2, IC-4 | critical | automated |

##### Preconditions

- NP `workers` upgrade to `4.17.3` in progress (`conditions[CAN_UPGRADE].status = False`). `NodePool["workers"].status.conditions[UpdatingVersion].status = True`.

##### Steps

1. Simulate `NodePool["workers"].status.conditions[UpdatingVersion].status = False` but `NodePool["workers"].status.version = "4.17.2"` (version mismatch).
2. `GET /clusters/{id}`.
3. Simulate `NodePool["workers"].status.version = "4.17.3"` AND all eligibility conditions hold.
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

- Cluster in `CLUSTER_STATE_FAILED` (previous upgrade or provisioning failed). ClusterVersion `4.17.3` ACTIVE.

##### Steps

1. `PATCH /clusters/{id}` `spec.version = "4.17.3"`.

##### Expected Results

- gRPC `FAILED_PRECONDITION`, message = `"cluster is in state FAILED and cannot be upgraded"`. No `ClusterOrder.spec.ReleaseImage` change.

---

### FR-13: Upgrade history

FR-13 requires a record of past version transitions surfaced in cluster status.

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

- `status.version_history` contains one entry: `from_version = "4.16.5"`, `to_version = "4.17.3"`, `success = true`, `completed_at` is non-zero and matches `status.upgrade.completed_at`.

---

#### TC-FR13-02: Sequential upgrades accumulate history entries

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-5 | medium | automated |

##### Preconditions

- Cluster with two completed sequential upgrades: `4.16.5 → 4.17.3`, then `4.17.3 → 4.17.5`.

##### Steps

1. `GET /clusters/{id}`.

##### Expected Results

- `status.version_history` contains 2 entries ordered by `completed_at` ascending.
- Entry 0: `from_version = "4.16.5"`, `to_version = "4.17.3"`, `success = true`.
- Entry 1: `from_version = "4.17.3"`, `to_version = "4.17.5"`, `success = true`.

---

#### TC-FR13-03: Failed upgrade does not appear in history

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-5 | medium | automated |

##### Preconditions

- Cluster upgrade from `4.16.5` to `4.17.3` fails (TC-FR7-02 scenario).

##### Steps

1. `GET /clusters/{id}` after failure.

##### Expected Results

- `status.version_history` is empty (no entry for the failed upgrade attempt).

---

### NFR-1: UI support — version selection, status monitoring, history

NFR-1 requires that the API surface supports UI display of upgrade state, history, and version selection.

---

### IC-1: `PATCH /clusters/{id}` spec.version — CP upgrade trigger and validation

#### TC-IC1-01: CP upgrade on READY cluster patches HC only

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-1 | critical | automated |

##### Preconditions

- Cluster `READY`. `observed_cp_version = "4.16.5"`. Node pools at `observed_version = "4.15.5"`. ClusterVersion `4.17.3` ACTIVE. Cluster has two node pools.

##### Steps

1. `PATCH /clusters/{id}` `spec.version = "4.17.3"`.

##### Expected Results

- HTTP 200. `ClusterOrder.spec.ReleaseImage` updated to the image from ClusterVersion `4.17.3`. Operator patches `HostedCluster.spec.release.image` only. `NodePool.spec.release.image` values are not changed by this operation. Cluster state unchanged; `conditions[CAN_UPGRADE].status = False` written in the same transaction.

---

#### TC-IC1-01b: Only one concurrent upgrade request succeeds

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-1, IC-9 | critical | automated |

##### Preconditions

- Cluster in `CLUSTER_STATE_READY` with `CAN_UPGRADE=True` and `observed_cp_version = "4.16.5"`. ClusterVersions `4.17.3` and `4.17.4` are ACTIVE. Do not deliver an operator Signal during the test.

##### Steps

1. Use a barrier to start two `PATCH /clusters/{id}` requests at the same time, for `spec.version = "4.17.3"` and `spec.version = "4.17.4"`.
2. Read the stored Cluster and resolved ReleaseImage after both requests finish.

##### Expected Results

- One request returns HTTP 200; the other returns `FAILED_PRECONDITION` with the `CanUpgrade` reason.
- The stored version and ReleaseImage match the successful request, and `CanUpgrade=False`. The rejected request changes nothing.

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

- Cluster in `CLUSTER_STATE_PROGRESSING` (initial provisioning in progress). HC `Available=False` (HostedCluster not yet ready). `CAN_UPGRADE=False`, `reason=HostedClusterNotAvailable`. ClusterVersion `4.17.3` ACTIVE.

##### Steps

1. `PATCH /clusters/{id}` `spec.version = "4.17.3"`.

##### Expected Results

- gRPC `FAILED_PRECONDITION`, message includes `"HostedCluster not yet Available"` (from the `CanUpgrade` condition reason). No `ClusterOrder.spec.ReleaseImage` change. Blocking rule: `CAN_UPGRADE=False`.

---

#### TC-IC1-07: Upgrade allowed on PROGRESSING cluster (AAP tasks running)

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-1 | high | automated |

##### Preconditions

- Cluster in `CLUSTER_STATE_PROGRESSING` (AAP post-provisioning tasks still running). `observed_cp_version = "4.16.5"`. ClusterVersion `4.17.3` ACTIVE.

##### Steps

1. `PATCH /clusters/{id}` `spec.version = "4.17.3"`.

##### Expected Results

- HTTP 200, cluster state unchanged (PROGRESSING), `conditions[CAN_UPGRADE].status = False`. OSAC state `PROGRESSING` is not a blocked state; upgrades are accepted when `CanUpgrade=True`.

---

#### TC-IC1-07b: Upgrade allowed on PROGRESSING cluster (failed AAP post-provisioning)

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-1 | high | automated |

##### Preconditions

- Cluster in `CLUSTER_STATE_PROGRESSING`. HC was successfully provisioned; AAP post-provisioning tasks subsequently failed. `observed_cp_version = "4.16.5"`. ClusterVersion `4.17.3` ACTIVE.

##### Steps

1. `PATCH /clusters/{id}` `spec.version = "4.17.3"`.

##### Expected Results

- HTTP 200, cluster state unchanged (PROGRESSING), `conditions[CAN_UPGRADE].status = False`. Failed AAP post-provisioning does not block the upgrade at the API level.

---

#### TC-IC1-08: Upgrade rejected when PROGRESSING + CP version not yet converged (CanUpgrade=False)

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-1, IC-9 | high | automated |

##### Preconditions

- Cluster in `CLUSTER_STATE_PROGRESSING` (initial provisioning; HC created and Available=True). `HC.status.controlPlaneVersion.history[0].image != ClusterOrder.spec.ReleaseImage` — version not yet confirmed by HyperShift history. `CAN_UPGRADE=False`, `reason=ControlPlaneVersionNotConverged`. ClusterVersion `4.17.3` ACTIVE.

##### Steps

1. `PATCH /clusters/{id}` `spec.version = "4.17.3"`.

##### Expected Results

- gRPC `FAILED_PRECONDITION`, message includes the version mismatch (e.g. `"control plane version not yet converged"`). No `ClusterOrder.spec.ReleaseImage` change. Blocking rule: `CAN_UPGRADE=False`.

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

#### TC-IC2-05: NP upgrade rejected when PROGRESSING + NP version not yet converged (CanUpgrade=False)

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-2, IC-9 | high | automated |

##### Preconditions

- Cluster in `CLUSTER_STATE_PROGRESSING` (initial provisioning). Node pool `workers`: `UpdatingVersion=False`, but `NodePool.status.version ("4.16.4") != ClusterOrder.spec.nodeRequests["workers"].Version ("4.16.5")` — NP version not yet confirmed by HyperShift. `CAN_UPGRADE=False`, `reason=NodePoolVersionNotConverged`. ClusterVersion `4.17.0` ACTIVE.

##### Steps

1. `PATCH /clusters/{id}` `spec.node_sets["workers"].version = "4.17.0"`.

##### Expected Results

- gRPC `FAILED_PRECONDITION`, message includes the NP version mismatch. No `ClusterOrder.spec.nodeRequests` change. Blocking rule: `CAN_UPGRADE=False`.

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

- HTTP 200, cluster state unchanged (READY), `conditions[CAN_UPGRADE].status = False`. `ControlPlaneAvailable=False` is a cluster-internal state not captured by `CanUpgrade` — the upgrade is accepted and the operator attempts to patch HC. Whether the patch succeeds depends on HyperShift's responsiveness.

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

#### TC-IC2-01: NP upgrade on READY cluster patches the target NodePool only

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-2 | critical | automated |

##### Preconditions

- Cluster `READY`. `observed_cp_version = "4.17.3"`. Node pool `workers` at `observed_version = "4.16.5"`. ClusterVersion `4.17.3` ACTIVE. Cluster has two node pools.

##### Steps

1. `PATCH /clusters/{id}` `spec.node_sets["workers"].version = "4.17.3"`.

##### Expected Results

- HTTP 200. `ClusterOrder.spec.nodeRequests["workers"].ReleaseImage` updated to the image from ClusterVersion `4.17.3`. Operator patches `NodePool["workers"].spec.release.image` only. `HostedCluster.spec.release.image` and the other `NodePool.spec.release.image` are not changed. Cluster state unchanged; `conditions[CAN_UPGRADE].status = False` written in the same transaction.

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

- Two completed sequential upgrades (TC-FR13-02 scenario).

##### Steps

1. `GET /clusters/{id}`.

##### Expected Results

- `status.version_history[0].completed_at` < `status.version_history[1].completed_at`.

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

- Exit code 0. Stdout shows the cluster resource (state unchanged, `can_upgrade: false`). PATCH request body contains `spec.version.name = "4.17.3"`.

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

- Exit code 0. Stdout shows the cluster resource (state unchanged, `can_upgrade: false`). PATCH request body contains `spec.node_sets["workers"].version = "4.17.3"`.

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
| FR-11 (NP version cap follows CP; no concurrent CP+NP upgrade) | NP version cap: tested by TC-IC2-02. No concurrent CP+NP: tested by TC-FR10-01, TC-FR10-02, TC-FR10-03. |
| FR-12 (unsupported version skews blocked) | Tested by TC-IC2-03 (NP upgrade N-3 skew rejection) and TC-IC1-11 (CP upgrade N-3 skew rejection against existing NPs). |
| NFR-2 (user documentation) | Documentation requirement; no automated test applicable. Documentation must be produced as a separate deliverable. |

### Interface Change Coverage Gaps

All 9 interface changes are covered by test cases. No gaps.

---

## Summary

| Metric | Count |
|--------|-------|
| Total test cases | 44 |
| Critical | 19 |
| High | 18 |
| Medium | 6 |
| Low | 3 |
| Automated | 38 |
| Manual | 0 |
| Requirements with test cases | 7 / 8 |
| Interface changes with test cases | 9 / 9 |
