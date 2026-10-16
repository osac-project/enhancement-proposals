# Testplan — OSAC-6040

## Overview

- **Feature:** [OSAC-6037](https://redhat.atlassian.net/browse/OSAC-6037) — Storage API integration for ComputeInstance volume lifecycle management.
- **Design:** [design.md](design.md), proposed dynamic OSAC CSI path.
- **Total test cases:** 26.
- **Requirements covered:** backend portions of all 4 PRD behavioral/dependency groups have cases. The visibility group is partial at feature level: UI behavior and tests belong to separate design/work. Deletion-policy assertions remain conditional.
- **Interface changes covered:** 9 of 9 active interface changes in this backend design.
- **Execution:** No implementation tests or cluster experiments run for this draft. These are planned cases, not claims of existing assertions or passing coverage.
- **Baseline:** OSAC `d30e35d27bcda4d55097323f5bc3ccb313a4c390`; [merged PRD at its pinned revision](https://github.com/osac-project/enhancement-proposals/blob/3da4e31a12a626f0571a42f076c89333c11a3e01/enhancements/OSAC-6037-storage-api-volume-lifecycle/prd.md).

The PRD has no FR/NFR identifiers. C, D, V, P and S below are **local test-ID aliases**, not invented published requirements. C/D/V refer to its three behavioral In Scope bullets; P refers to Dependencies; S groups Out of Scope protections. OSAC 0.4 is release metadata, not a separate behavioral test. Persona stories restate these behaviors.

| Local alias | Actual source | Design | Planned cases |
|-------------|---------------|--------|---------------|
| C | In Scope — create a Storage API Volume for every boot/additional disk from provisioning | Sections 4.1–4.3, Section 4.6, Section 8; IC-1/2/3/7/8/10 | TC-C-01–13 |
| D | In Scope — delete all associated Volumes through Storage API; Out of Scope standalone-deletion wording | Sections 4.1–4.3, Section 4.6, Section 9.1; IC-3/5/6/7/10 | TC-D-01–08 |
| V | In Scope — IDs in ComputeInstance status and UI | Backend status/API: Sections 4.2–4.3, Section 7; IC-3/4. UI is separately owned. | TC-V-01, TC-V-04; UI coverage outside this plan |
| P | Dependencies — private Storage API, no separate attach/detach prerequisite | Sections 4.1–4.3, Section 4.7, Section 8; IC-1/2/3/5/8 | TC-P-01–02 |
| S | Out of Scope — one-way correlation, no independent attachment lifecycle, resize/migration, sharing or snapshots/backups | Section 2.2, Section 4.8; IC-4 | TC-S-01; deletion policy in TC-D-06 |

## Planning evidence and ownership

Unit, Envtest, component integration and Contract cases belong to **DEV** implementation work. Only deployed cross-component user journeys belong to **QE**. Decomposition must carry each case's harness, command, prerequisites, real/fake boundary and unresolved gap into its owning Task. No implementation/QE Tasks have been created by this draft. Per user direction, UI design, implementation and UI testing are separate work; this plan covers the backend API and installer-schema handoff, and records the external dependency without defining UI behavior.

Commands below are planned invocations from the stated working directory. Paths are relative to the monorepo unless a harness says otherwise. Existing runner availability does not mean its new scenarios already exist.

### Harness registry

| Harness | Existing evidence / planned files | Command and working directory | Prerequisites and real/fake boundary | Execution readiness |
|---------|-----------------------------------|-------------------------------|--------------------------------------|---------------------|
| H1 — CSI unit | Existing `osac-csi-driver/pkg/driver/controller_test.go`, `pkg/fulfillment/grpc_client_test.go`; proposed `pkg/driver/managed_claim_test.go` | `make test` in `osac-csi-driver/` | Go toolchain; real handler/client code, fake Kubernetes/fulfillment/provider dependencies | Existing runner; new assertions needed. Does not prove private wire, hub RBAC or CDI integration. |
| H2 — fulfillment database | Existing `fulfillment-service/internal/servers/servers_suite_test.go`, private Volume/ComputeInstance tests; proposed `internal/servers/managed_volume_allocation_test.go` | `ginkgo run --timeout 10m internal/servers` in `fulfillment-service/` | Go/Ginkgo, Docker/Podman and PostgreSQL container; real migrations/transactions/server code, mocked auth/attribution and no vendor. Concurrency cases need independent committed transactions, not the suite's shared transaction. | Existing runner; new migration fixtures, transaction barriers and assertions needed. Classified as component integration, not unit. |
| H3 — fulfillment reconciler unit | Existing `fulfillment-service/internal/controllers/computeinstance/` and `internal/controllers/volume/` tests; extend cleanup fixtures | `ginkgo run --timeout 20m -r internal` in `fulfillment-service/` | Go/Ginkgo and suite dependencies; target reconciler behavior with controlled clients/events, no deployed hub/vendor. The broader command also includes other internal suites. | Existing runner; new managed cleanup cases needed. |
| H4 — operator Envtest | Existing `osac-operator/internal/controller/computeinstance_feedback_controller_test.go`, `volume_controller_test.go`, `lvms_vendor_provisioner_envtest_test.go`; proposed managed cleanup/prerequisite fixtures | `make test` in `osac-operator/` | Go, Envtest API-server/etcd assets and generated CRDs; real Kubernetes API/etcd, fake fulfillment/vendor/KubeVirt/CDI progress. Minimal TopoLVM CRD exists; fixture controls status/finalizers. | Existing runner; assertions/fixtures needed. Does not prove physical disk removal, scheduler convergence or guest I/O. |
| H5 — AAP Kind | Existing `osac-aap/tests/integration/targets/compute_instance_create/` and `compute_instance_delete/`; proposed managed-storage scenario under those targets | `make test` in `osac-aap/` | Ansible dependencies, container engine, Kind/kubectl; real role task execution and Kubernetes object persistence, minimal VM/CDI CRDs, no real CDI/import/vendor. | Existing create baseline overrides resource creation/waits with no-ops. Add and register a scenario executing real `create_resources.yaml`; baseline alone provides no DV contract evidence. G1. |
| H6 — deployed fulfillment Kind | Existing `fulfillment-service/it/it_volume_lifecycle_test.go`, `it_public_volumes_test.go`; proposed `it_managed_compute_volumes_test.go` | `make -C osac-installer test PLATFORM=kind PROFILE=dev NS=osac SUITE=fulfillment` from repo root | Kind, Helm, container engine, built images and CLI; real fulfillment/database/auth boundary/Kubernetes. This suite disables operator/sync; fixture drives provider status. | Existing runner; managed fixtures/assertions needed. Two Hub records on one Kind cluster prove record/namespace routing only. |
| H7 — installer/schema contract | Existing Helm/schema files under `osac-installer/charts/osac/`; proposed managed VM render assertions and installer schema contract fixtures | Existing `make helm-validate` in `osac-installer/`; **proposed** `make managed-vm-storage-render-test` for new assertions | Helm/schema tooling and pinned profile/schema fixtures; rendered manifests are real output, all cluster/provider readiness simulated. Plugin/Wizard verification belongs to the separate UI/Enclave design and work. | New assertion target does not yet exist; helm-validate alone does not cover this behavior. G5. |
| H8 — CSI/private API and installation contract | Proposed `osac-csi-driver/test/integration/managed_compute/` using real driver/server and fault proxy; extend operator Kind RBAC fixture where applicable | No combined command exists. Add/document a runner in the owning DEV Task; existing `make test` in CSI and `make integration-tests` in operator are **not** substitutes for the combined boundary. | Kind, migrated fulfillment, compatible CSI image, generated CRDs, TLS/auth and real ServiceAccounts; fake provider completion allowed; no guest or real vendor required. | Harness missing; G2 / OSAC-4845. Operator's current Kind suite alone does not deploy the full service/CSI path. |
| H9 — deployed VM lifecycle | Existing `tests/e2e/vmaas/regression/test_compute_instance_storage_tier.py`, `test_compute_instance_delete_during_provision.py`; extend them and add deterministic fault fixtures | `uv run pytest tests/e2e/vmaas/regression/test_compute_instance_storage_tier.py tests/e2e/vmaas/regression/test_compute_instance_delete_during_provision.py` from repo root | Full real fulfillment/operator/AAP/CDI/KubeVirt/OSAC CSI/vendor stack, tenant/infra credentials, provider inventory and guest I/O access; multiple LVMS nodes for C-10 and two actual hubs for C-11. | Existing runner; ID/backend assertions and controlled fault harness absent. Current storage helper has a commented-out call; delete test does not prove backend cleanup. G3/G4. |

### Boundary-to-case ownership

| Changed boundary | Tier / owner | Cases | Harness / known gap |
|------------------|--------------|-------|---------------------|
| AAP → DataVolume / managed StorageClass, legacy routing | Component integration / DEV | C-02 | H5; G1 |
| Claim owner resolution, topology and CSI translation | Unit / DEV | C-03, C-04 | H1 |
| Private Create transaction, races, status ownership and archival | Component integration / DEV | C-05, C-07, D-03, D-07, V-04 | H2 |
| Fulfillment API → hub CR, tenant-visible status / deletion policy | Component integration / DEV | C-06, D-06, V-01 | H6; policy G6 |
| Public descriptor and excluded lifecycle surface | Contract / DEV | S-01 | H6; generated descriptors plus real responses |
| Reconciler cleanup during hub/API failures | Unit / DEV | D-04 | H3 |
| Operator readiness, provider identity/completion, cleanup UIDs | Envtest / DEV | C-08, C-12, C-13, D-05, D-08 | H4 |
| Installer values/schema → release configuration and downstream contract | Contract / DEV | C-09 | H7; G5 |
| CSI → real private gRPC/API; installed hub service permissions | Contract + component integration / DEV | P-01, P-02 | H8; G2 |
| Full VM storage create, placement, I/O and cleanup | E2E / QE | C-01, C-10, C-11, D-01, D-02 | H9; G3/G4 |

### Timing and fault evidence

These are proposed **test budgets**, not product SLAs. Each asynchronous case records its trigger, expected observable condition, elapsed time and diagnostic snapshots on timeout.

- **Unit/transaction cases:** drive fake clocks or explicit transaction/provider barriers. Release an identified barrier and assert the resulting call/commit/state. Do not create ordering with arbitrary sleeps. The enclosing suite timeout catches deadlocks.
- **Kind/Envtest asynchronous projection:** trigger the API write or reconcile event, observe the named CR/status/finalizer change every 100 ms for up to 10 seconds in the focused fixture. Disable long periodic fallback in event-path fixtures so success demonstrates the intended watch/signal. Adjust only with recorded environment evidence.
- **Negative cleanup assertions:** hold a known consumer/provider/UID barrier, reconcile and observe retained state for a bounded 10-second window; release it and assert the next transition. A negative polling timeout alone is not proof of correct fencing.
- **Deployed matrix:** start timing at the public Create/Delete response; poll every 5 seconds with initial creation/import budget 1,800 seconds and deletion budget 900 seconds. Record provider-specific values in the qualification matrix. Failure to reach the named state is a failed/incomplete run, not automatic evidence of a product latency defect.
- **Deletion evidence:** query the saved provider operation/volume IDs and saved Kubernetes UIDs, including allocations without PVs. An accepted Delete, absent VM, empty response field or timed-out request is not a cleanup oracle.

## Test Cases

### C: In Scope — creation of every required disk

#### TC-C-01: Boot and additional disks are the same volumes tracked by Storage API

| Interface Change | Priority | Automation |
|------------------|----------|------------|
| IC-1, IC-2, IC-3, IC-7, IC-8, IC-10 | critical | automated |

**Tier / owner / harness:** E2E / QE / H9 (registry above).

##### Preconditions

- Qualified runtime/provider matrix row from Section 9.2; one boot disk and two additional disks; provider inventory baseline captured; tenant credentials and guest I/O access available.

##### Steps

1. Create the ComputeInstance through the public API and capture all managed DataVolumes, PVCs, PVs and Volume records as they appear.
2. Wait for import/binding and VM Ready; write and read a distinct marker on each guest disk.
3. Match each disk key to its public Volume ID, PV CSI handle and provider resource using privileged test inspection; delete the instance through the API.

##### Expected Results

- Exactly three parent allocations and three Storage API Volumes exist; each is recorded before the corresponding provider create begins.
- All disk PVCs select the managed OSAC CSI class; each PV's CSI handle equals its disk's OSAC Volume ID; imported boot and guest I/O succeed.
- StorageReady becomes true after binding/population; guest readiness still follows the existing VM checks. Cleanup meets TC-D-01.
- Repeat for every required tier/protocol combination. An unimplemented required VAST NFS route is a failing matrix row, not a skipped success.

#### TC-C-02: AAP emits the managed workload contract and keeps scratch claims separate

| Interface Change | Priority | Automation |
|------------------|----------|------------|
| IC-1 | critical | automated |

**Tier / owner / harness:** Component integration / DEV / H5 (registry above).

##### Preconditions

- New AAP scenario registered with real create_resources tasks and minimal CDI/KubeVirt CRDs; managed and legacy ComputeInstance inputs; managed tier mappings; explicit scratch class.

##### Steps

1. Render/create boot and two additional DataVolumes for a managed instance using both tenant-resolved and JIT-resolved classes.
2. Inspect sources, annotations, class selection and apply behavior; attempt a missing managed tier.
3. Run the legacy fixture and inspect its existing class selection.

##### Expected Results

- Managed disks carry tenant/owner and parent/disk/lifecycle annotations, deterministic disk keys, direct-import annotation false and their managed classes; boot uses registry and additional disks use blank sources.
- Managed classes use the OSAC driver, WFFC and Retain with explicit tenant/project/tier. The root DataVolume retains its existing non-apply behavior.
- A missing managed tier fails without a vendor fallback; scratch configuration names a separate class and does not assign a parent disk key. Legacy input keeps its original flow.
- This fixture proves object construction only; real CDI propagation and scratch behavior are covered by TC-C-01.

#### TC-C-03: CSI rejects forged or incomplete managed claim identity

| Interface Change | Priority | Automation |
|------------------|----------|------------|
| IC-2 | critical | automated |

**Tier / owner / harness:** Unit / DEV / H1 (registry above).

##### Preconditions

- Fake Kubernetes owner chain and fulfillment client with call counters; a valid managed PVC→DataVolume→ComputeInstance fixture.

##### Steps

1. Exercise valid metadata, then missing claim metadata, wrong DataVolume UID, wrong parent ID, temporary claim, wrong namespace/tenant and absent managed marker.
2. For each invalid fixture invoke CSI CreateVolume.

##### Expected Results

- Valid input makes one managed private Create call with the expected parent/disk/source UIDs and no default-tenant substitution.
- Missing/malformed request metadata returns INVALID_ARGUMENT; a stale or unsupported owner chain returns FAILED_PRECONDITION; unauthorized tenant context returns PERMISSION_DENIED. All are rejected before private Create, whose call count stays zero; none falls back to standalone Create.

#### TC-C-04: CSI preserves selected topology and the existing allocation identity

| Interface Change | Priority | Automation |
|------------------|----------|------------|
| IC-2, IC-3 | high | automated |

**Tier / owner / harness:** Unit / DEV / H1 (registry above).

##### Preconditions

- Two preferred topology entries; fake private API returns a stored LVMS allocation on the first node and exposes its persisted topology.

##### Steps

1. Create with preferred nodes A then B; inspect the private request and CSI response.
2. Retry with identical identity; then retry offering only an incompatible node B.

##### Expected Results

- The first request carries osac.io/node=A, and returned AccessibleTopology agrees with the stored allocation.
- Identical retries return the same OSAC Volume ID; incompatible placement yields FAILED_PRECONDITION and no second allocation.
- VolumeId remains the OSAC ID; vendor identity remains in the existing backend context, not public disk status.

#### TC-C-05: Allocation, Volume and public ID commit atomically under retries

| Interface Change | Priority | Automation |
|------------------|----------|------------|
| IC-3 | critical | automated |

**Tier / owner / harness:** Component integration (database) / DEV / H2 (registry above).

##### Preconditions

- Real PostgreSQL; independent committed request transactions/connections; immutable parent disk specification and a barrier inside the transaction; no backend calls in the transaction.

##### Steps

1. Run two simultaneous matching managed Creates; drop the first response after commit and retry.
2. Inject failures between Volume insert, allocation insert and parent projection; inspect committed rows and outbox.
3. Retry with changed capacity/tier/source PVC UID and then inspect the original allocation.

##### Expected Results

- Matching committed requests return one Volume ID, one slot row and one parent correlation; no duplicate Volume/outbox create survives.
- Each pre-commit failure rolls back all three writes and their outbox effects; a later retry can create once.
- Changed immutable inputs return ALREADY_EXISTS without replacing the original disk or correlation.

#### TC-C-06: Managed Volume follows the ComputeInstance hub

| Interface Change | Priority | Automation |
|------------------|----------|------------|
| IC-3 | critical | automated |

**Tier / owner / harness:** Component integration / DEV / H6 (registry above).

##### Preconditions

- Kind fulfillment fixture with two registered Hub records, separately observable hub namespaces and a parent pinned to hub A; operator/provider execution disabled.

##### Steps

1. Call private Create with the managed context for hub A; wait for Volume CR projection.
2. Repeat with hub B, empty hub and cross-tenant parent contexts.

##### Expected Results

- Persisted Volume.status.hub and the emitted Volume CR select hub A; no Volume CR is emitted into hub B's fixture namespace.
- Mismatched/empty hub returns FAILED_PRECONDITION; unauthorized tenant context returns PERMISSION_DENIED without revealing the parent.
- This proves routing between registered records on the fixture cluster; TC-C-11 supplies actual two-cluster evidence.

#### TC-C-07: Parent Delete and managed Create cannot leave an untracked late allocation

| Interface Change | Priority | Automation |
|------------------|----------|------------|
| IC-3 | critical | automated |

**Tier / owner / harness:** Component integration (database) / DEV / H2 (registry above).

##### Preconditions

- Real PostgreSQL; separate request transactions; explicit barriers immediately after acquiring the shared parent row lock.

##### Steps

1. Hold Create's lock, issue parent Delete, commit Create, and allow Delete to proceed.
2. On another parent, commit Delete first, then issue both a new allocation and a retry for an existing slot.

##### Expected Results

- Create-first commits one allocation visible to cleanup before deletion proceeds.
- Delete-first rejects both Creates with FAILED_PRECONDITION; no late Volume/allocation row or create outbox event is committed.
- The test waits on transaction barriers and observes commit order; it does not infer ordering from sleeps.

#### TC-C-08: Partial disk failure cannot produce a ready VM

| Interface Change | Priority | Automation |
|------------------|----------|------------|
| IC-10 | high | automated |

**Tier / owner / harness:** Envtest / DEV / H4 (registry above).

##### Preconditions

- Real API server/etcd; fake fulfillment/provider; two managed required disks and controllable DataVolume/PVC conditions.

##### Steps

1. Make one Volume AVAILABLE and its DataVolume populated; fail the second Volume and reconcile.
2. Recover the same second allocation; then advance binding/population and existing VM readiness separately.

##### Expected Results

- StorageReady remains false while any required allocation or population is incomplete; failure reason identifies the unresolved disk without exposing provider credentials.
- Successful allocation IDs remain unchanged. StorageReady turns true only after both disk conditions are met; VM Ready still waits for its existing checks.

#### TC-C-09: Managed deployment configuration is rendered and delivered consistently

| Interface Change | Priority | Automation |
|------------------|----------|------------|
| IC-1, IC-8 | high | automated |

**Tier / owner / harness:** Contract / DEV / H7 (registry above).

##### Preconditions

- Proposed Helm/schema assertion target and release-profile fixtures; installer schema available for contract inspection.

##### Steps

1. Render VMaaS and non-VMaaS profiles with a canonical hub ID; validate schema and CSI controller arguments, permissions and values.
2. Exercise absent hub ID, allowStub=true and unsupported release-image combinations.
3. Compare the new hub-ID value with its installer schema type, default, description and validation constraints.

##### Expected Results

- VMaaS output enables hub CSI with allowStub=false, the registered hub ID and the required metadata/RBAC settings; unrelated profiles retain their declared behavior.
- Invalid managed configurations cannot enable class resolution; complete rollout is a deployment prerequisite.
- Installer values and schema agree on the field name/type/default and reject invalid managed inputs. Downstream plugin/Wizard adoption and UI verification belong to separate design/work (G7).

#### TC-C-10: Multiple LVMS disks and the VM use one eligible node

| Interface Change | Priority | Automation |
|------------------|----------|------------|
| IC-1, IC-2, IC-7 | critical | automated |

**Tier / owner / harness:** E2E / QE / H9 (registry above).

##### Preconditions

- At least two eligible LVMS nodes, real CDI/KubeVirt/TopoLVM and OSAC CSI; one boot plus two additional disks; no manual PV prebinding.

##### Steps

1. Create the ComputeInstance and record selected-node annotations and CSI preferred topology for each disk.
2. Wait for VM Ready, inspect LogicalVolume node placement and VM/VMI node, then perform guest I/O on each disk.

##### Expected Results

- Every disk backend and bound PV has topology compatible with the final VM node; all disks are usable from that VM.
- Node selection is observed before backend/PV creation for each delayed claim; no independent random storage-node selection occurs.
- If the actual multi-disk CDI scheduling path cannot converge, record a blocking matrix failure requiring design revision.

#### TC-C-11: Two real hubs do not provision each other's managed disks

| Interface Change | Priority | Automation |
|------------------|----------|------------|
| IC-2, IC-3, IC-8 | critical | automated |

**Tier / owner / harness:** E2E / QE / H9 (registry above).

##### Preconditions

- Two distinct Kubernetes workload clusters registered as hubs, each with real managed CSI/provider setup and non-overlapping observable provider inventory.

##### Steps

1. Create a ComputeInstance pinned to each hub and wait for boot/I/O.
2. Compare parent hub, Volume hub, driver clusterID, PV and provider resources; delete both instances.

##### Expected Results

- Each allocation/PV/backend exists only on its parent hub; each guest can use its own disks.
- Deletion removes only that parent's resources on its recorded hub; the other live instance remains usable.

#### TC-C-12: Missing or incompatible managed prerequisites block provisioning

| Interface Change | Priority | Automation |
|------------------|----------|------------|
| IC-8, IC-10 | high | automated |

**Tier / owner / harness:** Envtest / DEV / H4 (registry above).

##### Preconditions

- Operator prerequisite evaluator fixtures for rollout status/image versions, driver readiness, hub identity and required class availability.

##### Steps

1. Set one prerequisite at a time to missing, mismatched or an incomplete rollout with old replicas remaining; reconcile a new managed instance.
2. Restore all prerequisites and reconcile; retain a legacy instance as a control.

##### Expected Results

- Managed provisioning reports the missing prerequisite and does not submit managed create work or select vendor fallback classes.
- Current observed generation, compatible ready replicas with no old replicas, canonical hub ID and required storage setup permit the managed path.
- Legacy resources retain their original lifecycle. Fake readiness fixtures do not count as deployed readiness evidence (TC-P-02).

#### TC-C-13: Lost provider-create responses reuse a durable operation identity

| Interface Change | Priority | Automation |
|------------------|----------|------------|
| IC-7 | critical | automated |

**Tier / owner / harness:** Envtest / DEV / H4 (registry above).

##### Preconditions

- Real API server with minimal TopoLVM LogicalVolume CRD; fake provider response faults; reconciler restart hook and stored operation context.

##### Steps

1. Interrupt before provider Create after operation identity is persisted; restart and reconcile.
2. Create the LogicalVolume, lose its response before status update, restart and reconcile again.
3. Repeat the response-loss contract against a fake VAST CSI endpoint recording request names.

##### Expected Results

- The same LVMS operation name is reused; exactly one owned LogicalVolume exists and UID validation remains active.
- VAST retries carry the same stable create name. An unresolved outcome remains recorded until reconciled.
- Parent deletion cannot declare cleanup from an empty vendor-ID field. These fixtures prove controller identity behavior, not real vendor idempotency (TC-D-02).

### D: In Scope — deletion of all associated Volumes

#### TC-D-01: Parent deletion waits for workload, backend and retained PV cleanup

| Interface Change | Priority | Automation |
|------------------|----------|------------|
| IC-5, IC-6, IC-7, IC-10 | critical | automated |

**Tier / owner / harness:** E2E / QE / H9 (registry above).

##### Preconditions

- Ready managed VM with boot and additional disks from TC-C-01; saved allocation/PV/provider identities and privileged inventory access.

##### Steps

1. Delete the ComputeInstance through its public API; observe workload-release, private Volume deletion, backend removal and retained PV cleanup.
2. Poll parent lifecycle/finalizers and compare provider inventory to its baseline.

##### Expected Results

- VM/VMI and consuming pods are absent and matching VolumeAttachments released before backend deletion is authorized.
- Every recorded Volume reaches authoritative deletion; all saved backend resources and managed retained PV UIDs are absent.
- Parent completion follows both backend and PV cleanup acknowledgements; no allocation is silently dropped or left orphaned.

#### TC-D-02: Deletion recovers committed allocations with no PV and uncertain backend creates

| Interface Change | Priority | Automation |
|------------------|----------|------------|
| IC-3, IC-6, IC-7 | critical | automated |

**Tier / owner / harness:** E2E / QE / H9 (registry above).

##### Preconditions

- Deterministic fault proxy/barriers at private Create response and provider Create response, real full stack, durable inventory observation; harness gap G3 must be closed.

##### Steps

1. Commit private Create, drop its response and block PV persistence; delete the parent and release the barrier.
2. Repeat with a successful provider Create whose response is lost; restart the responsible controller before allowing cleanup.
3. Inspect all allocation and provider identities during and after deletion.

##### Expected Results

- Parent correlation exists even when no PV does; cleanup includes that allocation and no retry creates an extra disk.
- An uncertain provider outcome keeps cleanup pending until the stable operation is reconciled and removed.
- Final provider inventory returns to baseline before parent completion. A timeout cannot be interpreted as proof that no disk exists.

#### TC-D-03: Private Delete requires the recorded deleting parent and release acknowledgement

| Interface Change | Priority | Automation |
|------------------|----------|------------|
| IC-5 | critical | automated |

**Tier / owner / harness:** Component integration (database) / DEV / H2 (registry above).

##### Preconditions

- Allocated managed Volume; authenticated service request fixtures; live/deleting parents and UID-qualified cleanup acknowledgement variants.

##### Steps

1. Call private Delete without managed authorization, with the wrong parent, with a live parent, and with a missing/stale release acknowledgement.
2. Persist the valid deleting-parent acknowledgement and repeat Delete, including a matching retry.

##### Expected Results

- Unauthorized lifecycle context is denied; live/wrong-parent/unreleased requests do not set deletion intent and return FAILED_PRECONDITION where authorization permits inspection.
- Authorized matching cleanup sets deletion intent once; repeated requests preserve that identity and cannot affect another allocation.
- A CSI-originated Delete cannot bypass the same ownership and release checks.

#### TC-D-04: Hub loss and API outages retain cleanup ownership

| Interface Change | Priority | Automation |
|------------------|----------|------------|
| IC-6, IC-7, IC-10 | critical | automated |

**Tier / owner / harness:** Unit / DEV / H3 (registry above).

##### Preconditions

- Fulfillment reconciler fixtures with a deleting managed parent, recorded allocations and unavailable/decommissioned hub or failing API client.

##### Steps

1. Reconcile each unavailable dependency; include a Volume whose create outcome is unresolved.
2. Restore the dependency and provide authoritative cleanup progress, then reconcile again.

##### Expected Results

- Managed parent and Volume cleanup finalizers remain while evidence is unavailable; allocated IDs remain queryable and cleanup-pending/failure reasons are emitted.
- Hub-absence shortcuts do not archive the managed parent or mark allocations cleaned.
- After evidence arrives, reconciliation resumes the same IDs and reaches the normal cleanup boundary.

#### TC-D-05: LVMS deletion submission does not equal completion

| Interface Change | Priority | Automation |
|------------------|----------|------------|
| IC-7 | critical | automated |

**Tier / owner / harness:** Envtest / DEV / H4 (registry above).

##### Preconditions

- Owned LogicalVolume with a fixture finalizer that holds Kubernetes deletion; persisted expected UID and managed Volume CR.

##### Steps

1. Request cleanup and reconcile while the LogicalVolume has deletionTimestamp but remains present.
2. Remove the fixture finalizer; wait for actual object absence and reconcile.
3. Exercise an already recorded legacy generated name and a replacement object with a different UID.

##### Expected Results

- Volume remains DELETING and its finalizer stays while the expected LogicalVolume exists.
- DELETED is reported only after the expected backend object is absent; existing recorded generated names remain usable.
- A replacement UID is not deleted as though it were the original. Envtest absence is not proof of physical device cleanup; deployed evidence is TC-D-01.

#### TC-D-06: Managed deletion protection and standalone compatibility follow the agreed policy

| Interface Change | Priority | Automation |
|------------------|----------|------------|
| IC-5 | high | automated |

**Tier / owner / harness:** Component integration / DEV / H6 (registry above).

##### Preconditions

- Real public/private fulfillment APIs and database; one live managed allocation and one standalone Volume; design Section 9.1 policy resolved.

##### Steps

1. Attempt public Delete on the managed Volume as its tenant user.
2. Delete the standalone Volume using its existing public API; then initiate valid parent cleanup for the managed allocation.

##### Expected Results

- Under the proposed policy, public managed Delete returns FAILED_PRECONDITION with no deletion intent; parent cleanup is allowed through the private contract.
- Standalone Delete retains its existing asynchronous behavior.
- These policy assertions are conditional on Section 9.1. Change the case if the PRD owner chooses a different scope; do not report a passing policy contract before that decision.

#### TC-D-07: Allocation records survive until parent cleanup and archival complete

| Interface Change | Priority | Automation |
|------------------|----------|------------|
| IC-3, IC-6 | critical | automated |

**Tier / owner / harness:** Component integration (database) / DEV / H2 (registry above).

##### Preconditions

- Real PostgreSQL; deleting parent with multiple allocations, archived Volume fixture and controlled cleanup acknowledgements.

##### Steps

1. Complete cleanup for only one disk, attempt parent archival, and inspect allocation rows/status.
2. Complete all backend removals but withhold PV cleanup acknowledgement; retry archival.
3. Provide all acknowledgements and archive the parent within the intended transaction.

##### Expected Results

- Partial/backend-only cleanup retains the parent and every allocation needed for recovery; Volume archival does not break lookup by ID.
- Only complete backend and PV evidence permits parent archival and atomic retirement of live allocation rows.
- Archived parent status retains its disk IDs; rollback preserves both parent and ownership records.

#### TC-D-08: Cleanup waits for release and uses UID-qualified PV deletion

| Interface Change | Priority | Automation |
|------------------|----------|------------|
| IC-6 | critical | automated |

**Tier / owner / harness:** Envtest / DEV / H4 (registry above).

##### Preconditions

- ComputeInstance CR deletion fixture; recorded PVC/PV UIDs; controllable pods/VolumeAttachments; fake fulfillment acknowledgement sink.

##### Steps

1. Keep a consuming pod or VolumeAttachment present while AAP completion is reported.
2. Remove consumers and record workload release; withhold backend completion.
3. After backend completion, replace a retained PV with a same-name/different-UID object before cleanup; then exercise the matching-UID case.

##### Expected Results

- No release acknowledgement is issued while references remain; missing CR alone is not release evidence.
- No retained PV is removed before backend completion.
- UID conflict keeps storage cleanup pending and preserves the replacement PV; matching cleanup is acknowledged before the managed finalizer is released.

### V: In Scope — Volume IDs in status and UI (backend status/API portion)

#### TC-V-01: Public status exposes only committed tenant-visible disk IDs

| Interface Change | Priority | Automation |
|------------------|----------|------------|
| IC-3, IC-4 | high | automated |

**Tier / owner / harness:** Component integration / DEV / H6 (registry above).

##### Preconditions

- Deployed fulfillment API/database; two tenants, managed and legacy parents; known committed allocations; public credentials and normal CLI binary.

##### Steps

1. Get/List the managed parent and inspect CLI JSON/YAML; attempt public status mutation.
2. Query using the other tenant; fetch a legacy parent.

##### Expected Results

- Managed status lists boot then disk-N with exactly the committed OSAC Volume IDs; provider IDs, credentials, hub/claim UIDs and private cleanup fields are absent.
- Public mutation cannot replace IDs; cross-tenant requests reveal neither parent nor disk correlations.
- Legacy status has no adopted disk IDs; CLI serialization agrees with public API fields.

#### TC-V-04: Feedback updates cannot erase fulfillment-owned correlations

| Interface Change | Priority | Automation |
|------------------|----------|------------|
| IC-3, IC-4 | critical | automated |

**Tier / owner / harness:** Component integration (database) / DEV / H2 (registry above).

##### Preconditions

- Real PostgreSQL; a parent with managed IDs; independently committed transactions for allocation and feedback-shaped masked updates.

##### Steps

1. Race an allocation update with an ordinary operator status update using its explicit field mask.
2. Attempt a broad/private status replacement by the feedback principal; invoke projection repair against a controlled inconsistent status fixture.

##### Expected Results

- Ordinary state/condition feedback preserves every committed disk ID.
- Unauthorized broad replacement is rejected without removing IDs; projection repair restores the ledger's immutable ordered correlations.
- No duplicate allocation is created to repair a display/status inconsistency.

### P: Dependencies — private Storage API

#### TC-P-01: Real CSI uses the private managed Create/Delete wire contract

| Interface Change | Priority | Automation |
|------------------|----------|------------|
| IC-2, IC-3, IC-5 | critical | automated |

**Tier / owner / harness:** Contract / DEV / H8 (registry above).

##### Preconditions

- Proposed real-driver/real-fulfillment Kind harness; migrated database and generated matching private protos; real Kubernetes owner-chain fixtures, controlled provider completion and fault proxy.

##### Steps

1. Drive CSI CreateVolume through a real gRPC connection with claim metadata and topology; observe the private API request and persisted allocation.
2. Drop a post-commit response and repeat; exercise unauthorized tenant context and a parent already deleting.
3. Drive managed CSI Delete while the parent is live and after authorized release.

##### Expected Results

- The real wire request carries private managed context and uses the correct authenticated identity; one durable OSAC ID survives response loss.
- Cross-tenant and deleting-parent cases match Section 4.3 without standalone fallback.
- Live-parent deletion is refused; authorized cleanup enters the private lifecycle. Public API descriptors do not expose managed request context.
- This harness proves service/driver protocol compatibility, not CDI import or real provider I/O.

#### TC-P-02: Installed hub CSI prerequisites and service permissions are sufficient

| Interface Change | Priority | Automation |
|------------------|----------|------------|
| IC-8 | high | automated |

**Tier / owner / harness:** Component integration / DEV / H8 (registry above).

##### Preconditions

- Proposed installed hub CSI fixture with real ServiceAccounts/RBAC, generated CRDs and TLS/auth to a compatible real fulfillment service; fake vendor endpoint permitted.

##### Steps

1. Install the declared release profile and inspect rollout completion, driver registration and hub-ID configuration.
2. As the CSI account read only required owner-chain resources and call the private API; as cleanup account inspect/remove only fixture managed PVs using runtime UID checks.
3. Remove a required permission, use a wrong hub ID or leave an old replica; evaluate the provisioning gate.

##### Expected Results

- Ready compatible installation permits managed resolution and authenticated private requests; no stub volume is returned.
- Missing permissions, wrong hub identity and incomplete/incompatible rollout keep managed provisioning disabled with a concrete prerequisite reason.
- Cluster-scoped access is explicitly documented; runtime tenant/UID checks prevent deletion of unrelated PV fixtures. This is not vendor qualification.

### S: Out of Scope — public contract boundaries

#### TC-S-01: Public contracts retain the one-way correlation and excluded lifecycle boundaries

| Interface Change | Priority | Automation |
|------------------|----------|------------|
| IC-4 | high | automated |

**Tier / owner / harness:** Contract / DEV / H6 (registry above).

##### Preconditions

- Generated public descriptors and deployed public response fixtures from the changed build; baseline API descriptors available.

##### Steps

1. Inspect ComputeInstance/Volume Get responses and generated public API descriptor changes.
2. Compare added methods and fields against the baseline and exercise existing disk-immutability validation.

##### Expected Results

- Only the planned ComputeInstance correlation/condition fields appear publicly; Volume has no new parent/reverse-link or independent attachment-state field.
- The feature adds no attach/detach, resize/migration, sharing, snapshot or backup operation; existing immutable-disk validation is retained.
- Standalone-deletion policy is assessed in TC-D-06, not inferred from descriptor inspection.

## Gaps

### Requirement Coverage Gaps

All four behavioral/dependency groups have cases for their backend portion. The PRD visibility requirement also includes UI display; that portion is explicitly outside this design/test plan and must be covered by separate UI design/work (G7), as directed by the user. This plan does not claim complete feature-level visibility coverage. Scope constraints have a contract case and explicit non-goals. The standalone-deletion policy is mapped but unresolved: TC-D-06 is conditional, not an approved acceptance criterion. The PRD specifies no performance SLA. Runtime/backend coverage cannot be called complete until the required matrix is agreed and executed.

### Interface Change Coverage Gaps

All nine active interface changes in this backend design have planned cases:

| Interface | Cases |
|-----------|-------|
| IC-1 | TC-C-01, TC-C-02, TC-C-09, TC-C-10 |
| IC-2 | TC-C-01, TC-C-03, TC-C-04, TC-C-10, TC-C-11, TC-P-01 |
| IC-3 | TC-C-01, TC-C-04, TC-C-05, TC-C-06, TC-C-07, TC-C-11, TC-D-02, TC-D-07, TC-V-01, TC-V-04, TC-P-01 |
| IC-4 | TC-V-01, TC-V-04, TC-S-01 |
| IC-5 | TC-D-01, TC-D-03, TC-D-06, TC-P-01 |
| IC-6 | TC-D-01, TC-D-02, TC-D-04, TC-D-07, TC-D-08 |
| IC-7 | TC-C-01, TC-C-10, TC-C-13, TC-D-01, TC-D-02, TC-D-04, TC-D-05 |
| IC-8 | TC-C-01, TC-C-09, TC-C-11, TC-C-12, TC-P-02 |
| IC-10 | TC-C-01, TC-C-08, TC-C-12, TC-D-01, TC-D-04 |

### Execution and decision gaps

| Gap | Missing evidence / required action | Owner and tracking |
|-----|------------------------------------|--------------------|
| G1 | AAP baseline bypasses real resource creation. Implement/register H5 scenario using actual create/delete resource tasks; separately qualify CDI annotation propagation and scratch behavior in H9. | DEV AAP; existing integration gap [OSAC-4843](https://redhat.atlassian.net/browse/OSAC-4843). Carry feature cases into implementation Tasks. |
| G2 | No executable real CSI→fulfillment managed contract or combined installed hub CSI/RBAC harness exists. Build H8 and document its command, fault injection, images/auth and provider boundary. | DEV CSI/fulfillment/operator; [OSAC-4845](https://redhat.atlassian.net/browse/OSAC-4845). |
| G3 | Existing deployed VM tests lack durable allocation/provider inventory assertions and deterministic lost-response/no-PV barriers. Add them; VM absence and fixture provider success are insufficient. | QE deployed journeys; [OSAC-4850](https://redhat.atlassian.net/browse/OSAC-4850); coordinate fault fixture with DEV contract work under [OSAC-4845](https://redhat.atlassian.net/browse/OSAC-4845). |
| G4 | Required CDI/KubeVirt/CSI/backend/version matrix, multi-disk LVMS convergence, VAST protocol support, scratch configuration, guest I/O and real backend deletion are unqualified. Current VAST provisioner rejects non-block protocols; required NFS support is implementation work. | Storage/VMaaS/deployment owners of design Section 9.2; [OSAC-4845](https://redhat.atlassian.net/browse/OSAC-4845), [OSAC-4850](https://redhat.atlassian.net/browse/OSAC-4850); existing LVMS mount gap [OSAC-3711](https://redhat.atlassian.net/browse/OSAC-3711). |
| G5 | New installer assertion target and managed-release gate are proposed. Implement H7 and its values/schema assertions. The downstream UI/Enclave dependency is tracked separately in G7. | DEV installer; planning follow-up [OSAC-6040](https://redhat.atlassian.net/browse/OSAC-6040), feature [OSAC-6037](https://redhat.atlassian.net/browse/OSAC-6037). Assign the concrete Component-bearing installer Task during decomposition. |
| G6 | Design Section 9.1 deletion-policy scope and Section 9.3 internal allocation bookkeeping boundary need maintainer/PRD review. Retain conditional behavior until resolved. | Storage/VMaaS / PRD owner; [OSAC-6040](https://redhat.atlassian.net/browse/OSAC-6040), [OSAC-6037](https://redhat.atlassian.net/browse/OSAC-6037). |
| G7 | The PRD's UI visibility requirement and downstream Enclave plugin/Wizard delivery are owned by separate UI design/work. This backend plan supplies `status.volumes` and installer-schema contracts; it defines no UI behavior or tests. The separate design/Task links were not supplied and must be linked for feature-level delivery tracking. | UI/Enclave owners; parent feature [OSAC-6037](https://redhat.atlassian.net/browse/OSAC-6037). User-directed scope split; no UI Task is created or specified by this revision. |

Harness-gap tickets above are existing coverage follow-ups, not claims that this feature's implementation Tasks have already been assigned to them. Decomposition must preserve the distinctions among planned behavior coverage, runnable assertions, and executed runtime evidence.

## Summary

| Metric | Count |
|--------|-------|
| Total test cases | 26 |
| Critical | 18 |
| High | 8 |
| Medium | 0 |
| Low | 0 |
| Automated (planned) | 26 |
| Manual | 0 |
| PRD groups with backend test cases | 4 / 4 |
| PRD groups with all portions covered by this plan | 3 / 4; visibility requires separate UI coverage |
| Additional scope-constraint group | 1 / 1 |
| Active backend interface changes with test cases | 9 / 9 |
| Cases executed during drafting/revision | 0 |
