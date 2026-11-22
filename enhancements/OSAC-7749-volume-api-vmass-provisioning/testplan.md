# Testplan — OSAC-7749

## Overview

- **Feature:** OSAC-7749 — Volume API owns VMaaS volume provisioning end-to-end
- **Total test cases:** 21
- **Requirements covered:** 6 of 7 (REQ-7 is a scope constraint with no
  separate behavioral surface — see Gaps; the PRD does not define FR/NFR
  IDs, so requirements use the `REQ-N` keys derived in the architectural
  context and referenced by the design)
- **Interface changes covered:** 7 of 8 (IC-6 is deployment configuration
  implicitly exercised by every deployed case — see Gaps)

## Test Case Index

| ID | Scenario | IC | Priority |
|----|----------|----|----------|
| TC-REQ1-01 | Volume get/list shows the owning ComputeInstance | IC-1 | critical |
| TC-REQ1-02 | Public volume create with `owner` is rejected | IC-1 | high |
| TC-REQ1-03 | Volume update cannot change or clear `owner` | IC-1 | medium |
| TC-REQ2-01 | CI disks provision as DataVolumes via the operator, AAP creates the VM only | IC-3 | critical |
| TC-REQ2-02 | Ownerless (CaaS) volume still provisions through vendor CSI | — | critical |
| TC-REQ2-03 | Unmapped tier gets a JIT StorageClass from the operator | IC-5 | high |
| TC-REQ2-04 | `ocp_virt_vm` create workflow creates no DataVolumes | IC-7 | high |
| TC-REQ2-05 | Repeated identical Volumes.Create stores exactly one volume | IC-8 | high |
| TC-REQ2-06 | Orphaned volume with deleted owner is cleaned up by reconciler | IC-8 | high |
| TC-REQ2-07 | Out-of-band Volume CR — controller reconciles self-contained CR; finalizer chain cleans up | IC-8 | medium |
| TC-REQ3-01 | DataVolume lands in the VM namespace on the target cluster | IC-3 | critical |
| TC-REQ4-01 | Volume reports AVAILABLE when the DataVolume import succeeds | IC-2 | critical |
| TC-REQ4-02 | Import failure reports FAILED with the DataVolume failure reason | IC-2 | critical |
| TC-REQ4-03 | WFFC storage: CREATING while the PVC waits, AVAILABLE on DV Succeeded | IC-2 | medium |
| TC-REQ4-04 | PENDING → CREATING transition — deterministic mapping (integration tier) | IC-2 | high |
| TC-REQ4-05 | Volume creation flows start at PENDING, never further (deployed, order-tolerant) | IC-2 | high |
| TC-REQ5-01 | Deleting a ComputeInstance deletes its volumes and DataVolumes | IC-4 | critical |
| TC-REQ5-02 | Deleting a running ComputeInstance releases PVCs and completes DataVolume cleanup | IC-4 | high |
| TC-REQ6-01 | OCI registry boot disk works unchanged through the new path | IC-3 | critical |

## Test Cases

### REQ-1: Every VMaaS volume records exactly one owning ComputeInstance

##### Shared Preconditions

- A deployed OSAC installation (fulfillment, operator, AAP, CDI on the
  target cluster) with a tenant whose storage tiers are mapped and ready.
- A ComputeInstance with one boot disk and one additional disk has been
  created and reached `RUNNING`.

#### TC-REQ1-01: Volume get/list shows the owning ComputeInstance

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-1 | critical | automated |

**Steps:** 1. `osac volumes list` for the tenant (or `Volumes.List` via
the public API) → 2. `osac volumes get <volume-id>` for the boot-disk
volume → 3. `osac volumes get <volume-id>` for the data-disk volume.
**Expected:** Both the list entries and both get responses show
`spec.owner = {type: "COMPUTE_INSTANCE", reference: "<the CI's id>"}` for the
instance's boot-disk and data-disk volumes; a volume created through the
CaaS CSI path in the same tenant shows no `owner` field.

#### TC-REQ1-02: Public volume create with `owner` is rejected

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-1 | high | automated |

**Steps:** 1. Call `Volumes.Create` on the public API with a spec that
sets `spec.owner = {type: "COMPUTE_INSTANCE", reference: "ci-..."}`.
**Expected:** The call fails with `InvalidArgument` and message
"owner is system-managed"; no volume is created (`Volumes.List` does not
show it).

#### TC-REQ1-03: Volume update cannot change or clear `owner`

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-1 | medium | automated |

**Steps:** 1. `Volumes.Update` on an owned volume with an update mask
covering `spec.owner`, setting a different CI id → 2. repeat with
`spec.owner` cleared.
**Expected:** Both calls fail with `InvalidArgument` (owner is immutable
and system-managed); a subsequent `Volumes.Get` still returns the
original owner.

### REQ-2: The Volume API is the single provisioning path for VMaaS disks

##### Shared Preconditions

- Same deployed installation as REQ-1; no ComputeInstances exist yet.
- The tenant has at least one mapped storage tier and access to a second
  tier with no tenant StorageClass mapping (for TC-REQ2-03).

#### TC-REQ2-01: CI disks provision as DataVolumes via the operator, AAP creates the VM only

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-3 | critical | automated |

##### Steps

1. Create a ComputeInstance with a boot disk (OCI registry image) and one
   additional disk on the mapped tier.
2. Wait for the instance to reach `RUNNING`.
3. On the target cluster, inspect the DataVolumes in the VM namespace and
   the AAP job's executed tasks.

##### Expected Results

- A DataVolume `<ci-name>-root-disk` exists with
  `spec.source.registry.url = "docker://<image>"`, `pullMethod: node`,
  `accessModes: [ReadWriteOnce]`, the tenant-resolved StorageClass, and
  annotations `osac.openshift.io/storage-volume-id` (the fulfillment
  volume ID) and `osac.openshift.io/tenant`.
- A DataVolume `<ci-name>-disk-1` exists with `spec.source.blank: {}`,
  the requested size, and the same annotations.
- The AAP provision job's task log shows no DataVolume-create or
  StorageClass-resolution tasks; the VirtualMachine exists and references
  both DataVolumes by name.

#### TC-REQ2-02: Ownerless (CaaS) volume still provisions through vendor CSI

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| — | critical | automated |

**Steps:** 1. Create a volume through the CaaS CSI path (or public
`Volumes.Create` without owner) on a vendor-backed tier → 2. wait for
provisioning.
**Expected:** The volume reports `AVAILABLE` with `status.vendor_volume_id`
set, the `osacv1alpha1.Volume` CR is handled by the `VendorProvisioner`
path (no DataVolume exists for it), and its `spec.owner` is absent —
the pre-existing CaaS flow is unchanged by the feature.

#### TC-REQ2-03: Unmapped tier gets a JIT StorageClass from the operator

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-5 | high | automated |

**Steps:** 1. Create a ComputeInstance whose additional disk uses a tier
   with no tenant StorageClass mapping → 2. wait for `RUNNING`.
**Expected:** A new StorageClass for the tier exists on the target
cluster (created by the operator before DataVolume creation — no AAP job
created it), the disk's DataVolume uses it, and the volume reports
`AVAILABLE`.

#### TC-REQ2-04: `ocp_virt_vm` create workflow creates no DataVolumes

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-7 | high | automated |

**Steps:** 1. Run the published `ocp_virt_vm` create workflow (component
   integration target on Kind) with a ComputeInstance payload whose
   disks are described in the CR spec (boot disk + additional disks).
**Expected:** The workflow creates the VirtualMachine, Secrets, and any
configured Service; the target namespace contains no DataVolumes created
by the workflow (DataVolumes, when present, were created by the operator
and carry the `DataVolumeProvisioned`-owning controller's annotations),
and the run reports no DataVolume or StorageClass-resolution tasks.

#### TC-REQ2-05: Repeated and concurrent Volumes.Create stores exactly one volume

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-8 | high | automated |

**Steps:** 1. Issue the private `Volumes.Create` for a CI disk twice
   with the identical request (same deterministic name, owner, source,
   target, and spec) → 2. issue it a third time with the same name and
   owner but a different `sizeGiB` → 3. issue two synchronized
   concurrent identical Create calls (same name, owner, spec) and
   verify both return the same volume ID.
**Expected:** The two identical sequential calls both return the same
volume id (get-or-adopt; `Volumes.List` shows exactly one volume with
that name); the mismatched call fails with `AlreadyExists` naming
`sizeGiB` as the conflicting field; the concurrent identical calls both
return the same volume ID and `Volumes.List` still shows exactly one
volume with that name.

#### TC-REQ2-06: Orphaned volume with deleted owner is cleaned up by Volume controller

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-8 | high | automated |

##### Steps

1. Create a volume record with a valid owner via the private
   `Volumes.Create` (or directly in Postgres), then delete the owner
   ComputeInstance record without running normal volume cleanup —
   the volume record must exist in fulfillment and be visible via
   `Volumes.List`. Then create the corresponding Volume CR on the hub
   referencing the deleted owner. The Volume controller is not yet
   running (in envtest: create the objects before starting the
   manager), so the orphan cannot be cleaned up during setup.
2. Precheck: assert the volume is listed via `Volumes.List` (state
   `PENDING`) with the controller still held.
3. Start (release) the Volume controller.
4. Poll `Volumes.List` and the hub for the Volume CR until the volume
   is no longer listed and the CR is removed. Fail the case if a
   bounded timeout expires first.

##### Expected Results

- The precheck (step 2) shows the volume listed before
  reconciliation.
- The Volume controller detects the orphan (the `ComputeInstances.Get`
  call for the owner returns `NotFound`) and calls `Volumes.Delete`;
  the volume is no longer listed via `Volumes.List`, and the Volume CR
  is removed.

#### TC-REQ2-07: Out-of-band Volume CR — controller reconciles self-contained CR; finalizer chain cleans up

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-8 | medium | automated |

##### Steps

1. Manually create a Volume CR on the hub for a fulfillment record
   that does not exist (simulating an out-of-band or late-arriving
   CR). Per design §4.5, stale-CR cleanup is not an automated
   mechanism — this case verifies the operator behavior that is
   real: the CR is self-contained, and the finalizer chain cleans
   up its storage when the CR is deleted.
2. Let the Volume controller reconcile the CR and wait for the
   DataVolume at `spec.target` to exist — the finalizer-path
   assertions below require it.
3. Delete the Volume CR (as an operator would when cleaning up an
   out-of-band CR).
4. Negative assertion: with the DataVolume and its PVC still present,
   verify (with a bounded wait) that the Volume CR remains
   Terminating and still carries its finalizer — the finalizer must
   not be released while the storage exists.
5. Simulate the garbage collector (see note): delete the PVC and
   remove the DataVolume's `foregroundDeletion` finalizer.
6. Wait for the Volume CR's finalizer to be removed and the CR to be
   gone.

Note: envtest does not run the Kubernetes garbage collector or CDI
controllers. The fixture creates a PVC owned by the DataVolume
(nothing else would) and asserts it exists before the Volume CR is
deleted. When the controller issues the foreground delete, the
fixture simulates the GC's part (step 5): it deletes the PVC and
removes the DataVolume's `foregroundDeletion` finalizer, letting the
Volume finalizer complete. The real GC path — including PVC-in-use
release — is covered end-to-end by TC-REQ5-02 on the deployed stack.

##### Expected Results

- The Volume controller reconciles the CR without consulting the
  fulfillment record (the CR is self-contained).
- While the DataVolume and its PVC exist, the Volume CR remains
  Terminating with its finalizer — the finalizer is not released
  before the storage is gone (step 4).
- When the GC simulation completes (step 5), the DataVolume and its
  PVC are deleted via the finalizer chain, and the Volume CR's
  finalizer is removed (step 6).
- No DataVolume or PVC remains for the deleted CR.

### REQ-3: The volume is provisioned in the same location as its owning ComputeInstance

#### TC-REQ3-01: DataVolume lands in the VM namespace on the target cluster

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-3 | critical | automated |

##### Steps

1. Create a ComputeInstance with disks and wait for `RUNNING`.
2. Read the CI's `status.virtualMachineReference.namespace` (or the
   running VM's namespace) and the DataVolumes' namespace.
3. Check the `osacv1alpha1.Volume` CR's cluster placement.

##### Expected Results

- Every DataVolume named above exists in the same namespace as the
  VirtualMachine on the target cluster.
- The Volume CR exists on the same hub cluster as the ComputeInstance CR
  (operator-observable: the CR is found in the CI CR's cluster and
  namespace scope, not on a randomly selected hub).

### REQ-4: Volume lifecycle and failure reasons derive from the DataVolume

##### Shared Preconditions

- Same deployed installation; a ComputeInstance with disks exists or is
  being created per case.

#### TC-REQ4-01: Volume reports AVAILABLE when the DataVolume import succeeds

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-2 | critical | automated |

**Steps:** 1. Create a ComputeInstance with a registry boot image →
2. poll `osac volumes get` until the boot-disk volume settles.
**Expected:** The volume's `status.state` sequence ends at `AVAILABLE`
(with `status.message` empty) at the same time the DataVolume reports
phase `Succeeded`; the volume never reports `FAILED` during import.

#### TC-REQ4-02: Import failure reports FAILED with the DataVolume failure reason

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-2 | critical | automated |

##### Steps

1. Create a ComputeInstance whose boot image references an
   inaccessible registry URL (or a source that fails import).
2. Poll (with a bound) for the DataVolume to reach phase `Failed` —
   the feedback update is asynchronous, so an immediate volume read
   may still return `CREATING`. Note: CDI may keep retrying the
   import (importer pod in `CrashLoopBackOff` with the DataVolume
   remaining in `ImportInProgress`) without setting `Failed`; the
   poll bound must account for this, and the CDI version under test
   should be recorded.
3. If the DataVolume reached `Failed` within the bound, poll (with a
   bound) for the volume to reach `FAILED`, then read
   `status.message`. Otherwise, read the volume state and record the
   CDI version and timeout outcome, as the expected results require.

##### Expected Results

- The volume reports `status.state = FAILED` and
  `status.message` contains the DataVolume condition's reason and message
  (for example the importer's exit reason), not the generic
  "volume provisioning failed".
- If the poll bound expires with the DataVolume still in
  `ImportInProgress` (CDI retry loop), the volume reports `CREATING`
  (per the state-mapping table — ImportInProgress maps to CREATING);
  the test records the CDI version and the timeout outcome for
  investigation. The FAILED assertion applies only when the DataVolume
  reaches `Failed` within the bound.

#### TC-REQ4-03: WFFC storage: CREATING while the PVC waits, AVAILABLE on DV Succeeded

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-2 | medium | automated |

##### Preconditions

- The deployed CDI has `HonorWaitForFirstConsumer` enabled — the
  expected states depend on it (CDI does not schedule the import worker
  for a Pending WFFC PVC).
- The WFFC StorageClass exercises the legacy import path: either a
  non-CSI provisioner, or the DataVolume is annotated
  `cdi.kubevirt.io/storage.usePopulator: "false"`. On the populator
  path (CSI-provisioned WFFC StorageClass without the annotation),
  CDI reports `PendingPopulation` instead of
  `WaitForFirstConsumer`; that phase maps to `CREATING` through the
  fallback row with the phase name in `status.message`, so the
  expected volume state is identical — but step 2's stated
  observation holds only on the legacy path.

##### Steps

1. Create a ComputeInstance whose disks use a WaitForFirstConsumer
   StorageClass, with the AAP provision job template suspended (the
   job will not execute; the VM is not created and the PVC is not
   consumed).
2. Poll (with a bound) for the volume state while the DataVolume
   reports `WaitForFirstConsumer` and its PVC is still `Pending` —
   the feedback update is asynchronous, so `PENDING` may briefly
   precede `CREATING`.
3. Resume the AAP provision job template. After the VM's
   virt-launcher pod binds the PVC and the import
   completes (DataVolume `Succeeded`, PVC `Bound`), poll (with a
   bound) for the volume to reach `AVAILABLE` — the feedback update is
   asynchronous, so a single read may still return `CREATING`.

##### Expected Results

- During the wait (step 2): the volume reports `CREATING` — the DV's
  `WaitForFirstConsumer` phase maps to CREATING; the volume is waiting,
  not stuck and not failed.
- After binding and import (step 3): the volume reports `AVAILABLE`,
  driven by the DataVolume reaching `Succeeded` — the state definition
  tracks data readiness, not PVC binding.

#### TC-REQ4-04: PENDING → CREATING transition — deterministic mapping (integration tier) (parameterized)

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-2 | high | automated |

##### Steps

1. At the integration tier (deployed fulfillment and operator
   components, Volume CR under test control), create a volume record
   and its Volume CR through the `{creation flow}` — an owned volume
   (owner + source + target) or an ownerless CaaS/CSI volume — holding
   the Volume controller's pickup (CR present, no phase set).
2. Read the volume state through the API.
3. Set the Volume CR phase to `Progressing` (simulating the operator's
   pickup) and let the feedback loop run.
4. Poll (with a bound) until the volume reports `CREATING` — the
   feedback update is asynchronous, so an immediate single read may
   still show `PENDING` — then read once more.

##### Expected Results

| Creation flow | Expected Result |
|---------------|-----------------|
| Owned volume (CI disk) | Step 2: `PENDING` (record exists, no CR activity); step 4: `CREATING`, persisted on the subsequent read — the transition is carried by the feedback loop, not transient |
| Ownerless (CaaS/CSI) | Same: `PENDING` at step 2 and `CREATING` persisted at step 4 — the initial state and the feedback-driven transition apply to every creation flow, including CaaS/CSI |

#### TC-REQ4-05: Volume creation flows start at PENDING, never further (deployed, order-tolerant) (parameterized)

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-2 | high | automated |

The deployed operator cannot be suspended per-controller, so the
deployed assertion is order-tolerant by design: the design allows a fast
pickup to move the volume to `CREATING` before the first read, and that
is not a failure. The deterministic `PENDING → CREATING` observation is
TC-REQ4-04.

##### Steps

1. Create a volume through the `{creation flow}` (a ComputeInstance
   with a disk, or a standalone volume through the CSI/public path).
2. As soon as the volume appears in `osac volumes list`, run
   `osac volumes get` and record `status.state`.
3. Poll until the volume settles (`AVAILABLE` or `FAILED`), recording
   every observed state, then run `osac volumes get` once more.

##### Expected Results

| Creation flow | Expected Result |
|---------------|-----------------|
| CI-owned disk volume | The observed state sequence is monotonic — it never moves backward — and every observation is a valid lifecycle state. `PENDING`, `CREATING`, or (for a fast-settling volume, e.g. a blank disk) `AVAILABLE` may be the first observation; once `CREATING` is observed it persists until the volume settles; if the volume settles before `CREATING` is ever observed, that is recorded, not failed — the deterministic `PENDING → CREATING` order proof is TC-REQ4-04's, at the integration tier |
| CaaS/CSI volume | Same monotonicity, persistence, and first-observation tolerance — the initial state applies to every creation flow |

### REQ-5: Deleting a ComputeInstance deletes its volumes

##### Shared Preconditions

- A ComputeInstance with a boot disk and an additional disk has reached
  `RUNNING`.

#### TC-REQ5-01: Deleting a ComputeInstance deletes its volumes and DataVolumes

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-4 | critical | automated |

**Steps:** 1. Delete the ComputeInstance → 2. poll (with a bound) for
   the instance to be gone → 3. poll (with a bound) for: the volumes
   leaving `osac volumes list`, the DataVolumes
   `<ci-name>-root-disk` and `<ci-name>-disk-1` being absent from the
   VM namespace, and no volume remaining in `DELETING`. Cleanup is
   asynchronous — bounded polls, not immediate checks.
**Expected:** `osac volumes list` no longer shows the instance's
volumes; the DataVolumes `<ci-name>-root-disk` and `<ci-name>-disk-1`
no longer exist in the VM namespace; no volume remains in `DELETING`.

#### TC-REQ5-02: Deleting a running ComputeInstance releases PVCs and completes DataVolume cleanup

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-4 | high | automated |

##### Steps

1. Suspend the AAP deprovision job template for the target
   ComputeInstance (the job will not execute; the VM stays running and
   the PVC stays held by the virt-launcher pod).
2. Delete the ComputeInstance. The volume-side deletion proceeds
   (fulfillment + Volume controller) even though the VM is not
   deprovisioned.
3. Poll (with a bound) for the volume to reach `DELETING` while the
   PVC is still held — the feedback update is asynchronous, so the
   state may briefly remain `PENDING` or `CREATING` after the delete
   request returns. Once `DELETING` is observed, inspect the Volume CR.
4. Resume the AAP deprovision job template; the job halts the VM,
   the virt-launcher pod terminates, the PVC releases, and teardown
   completes within the reconciliation timeout window.

##### Expected Results

- Step 3 (PVC held): the volume shows `DELETING` — not `DELETED` —
  and the Volume CR still carries the `volume-datavolume` finalizer;
  the record and finalizer persist until the PVC is gone, proving the
  invariant that no storage outlives the volume record.
- Step 4 (after PVC release): each DataVolume completes its foreground
  deletion once its PVC is released (PVC protection tracks the
  consuming pod, which terminates when the deprovision job halts the
  VM — this may precede VM-object deletion, which is not asserted); the
  volumes end `DELETED` without operator intervention; and no
  DataVolume or PVC remains in the target namespace.

### REQ-6: OCI registry disk sources keep working

#### TC-REQ6-01: OCI registry boot disk works unchanged through the new path

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-3 | critical | automated |

**Steps:** 1. Create a ComputeInstance with a boot disk sourced from an
   OCI registry image (e.g. `quay.io/containerdisks/fedora:latest`) →
   2. wait for `RUNNING` → 3. verify the disk inside the guest.
**Expected:** The VM reaches `RUNNING` with the boot disk attached
(e.g. `vda` visible via guest-agent or console); the DataVolume uses
`source.registry.url = "docker://<image>"` with `pullMethod: node` —
identical to the pre-feature AAP-created shape.

## Gaps

### Requirement Coverage Gaps

**REQ-7 (new ComputeInstances only; no backfill)** — a scope constraint,
not a behavioral surface: the deployment model is full install with no
in-flight instances at cutover, and no migration path exists to test.
The observable coexistence requirement (ownerless volumes unaffected) is
covered by TC-REQ2-02. No separate test case is applicable.

### Interface Change Coverage Gaps

**IC-6 (operator RBAC and installer target-cluster configuration)** —
deployment configuration with no independent behavioral assertion: every
deployed test case above (TC-REQ2-01, TC-REQ3-01, TC-REQ4-*, TC-REQ5-*)
runs only if the RBAC and kubeconfig wiring are correct, so the
configuration is exercised end-to-end by the REQ-2/REQ-3/REQ-5 cases. A
standalone RBAC assertion would duplicate suite setup. Recommendation:
cover the chart value shape through installer chart linting in the
owning implementation task.

## Coverage Matrix

Each test case is mapped to its canonical tier, work owner, suite
location, command, and dependency disclosure, per
[docs/INTEGRATION-TESTING.md](../../docs/INTEGRATION-TESTING.md).
Tiers: Unit (Go tests, no cluster), Envtest (controller against
kube-apiserver/etcd), Component-integration (real components on Kind),
E2E (deployed cross-component journeys).

| TC | Tier | Owner | Suite / Location | Command | Dependencies (real vs. faked) |
|----|------|-------|------------------|---------|-------------------------------|
| TC-REQ1-01 | E2E | [QE] | `tests/e2e/vmaas/regression/test_compute_instance_storage_tier.py` | deployed suite via osac-test-infra | Real fulfillment, operator, AAP, CDI; real target cluster |
| TC-REQ1-02 | Component-integration | [DEV] | `fulfillment-service/it/it_public_volumes_test.go` | `go test ./it/ -run TestPublicVolumesCreate` | Real fulfillment-service + Postgres; no Kubernetes |
| TC-REQ1-03 | Component-integration | [DEV] | `fulfillment-service/it/it_public_volumes_test.go` | `go test ./it/ -run TestPublicVolumesUpdate` | Real fulfillment-service + Postgres |
| TC-REQ2-01 | E2E | [QE] | `tests/e2e/vmaas/regression/test_compute_instance_storage_tier.py` | deployed suite | Real fulfillment, operator, AAP, CDI, target cluster |
| TC-REQ2-02 | E2E | [QE] | `tests/e2e/` (existing CaaS/CSI suite or new file) | deployed suite | Real fulfillment, operator, vendor CSI driver |
| TC-REQ2-03 | E2E | [QE] | `tests/e2e/vmaas/regression/` (extends storage-tier test) | deployed suite | Real fulfillment, operator, AAP, CDI, target cluster |
| TC-REQ2-04 | Component-integration | [DEV] | `osac-aap/tests/integration/targets/compute_instance_create/` | `uv run ansible-playbook targets/compute_instance_create/tasks/baseline.yml -e '@common_vars.yml'` | Real playbook on Kind; no AAP server, no VM controllers |
| TC-REQ2-05 | Component-integration | [DEV] | `fulfillment-service/it/it_volume_lifecycle_test.go` (extended) | `go test ./it/ -run TestVolumeIdempotentCreate` | Real fulfillment-service + Postgres |
| TC-REQ2-06 | Envtest | [DEV] | `osac-operator` envtest (extends volume controller tests) | `make -C osac-operator test` | Real Volume controller reconcile logic, envtest kube-apiserver; fulfillment Volumes API simulated by a fake client wired into the controller — Create stores the record, List returns it, Delete removes it; the fulfillment-side record→CR deletion step is simulated by the test setting the CR's deletionTimestamp; fulfillment ComputeInstances API stubbed (owner returns NotFound); the real record→CR→storage chain is covered end-to-end by TC-REQ5-01/02 (E2E) |
| TC-REQ2-07 | Envtest | [DEV] | `osac-operator` envtest (extends volume controller tests) | `make -C osac-operator test` | Real Volume controller reconcile logic, envtest kube-apiserver; CR created and deleted by the test (out-of-band CR — per design §4.5 there is no automated stale-CR mechanism to invoke); DataVolume creation and finalizer-chain cleanup verified; dependent PVC created by the fixture (envtest runs no CDI); Kubernetes garbage collector simulated by the fixture (PVC deletion + `foregroundDeletion` finalizer removal — envtest runs no GC); the real GC path is covered by TC-REQ5-02 (E2E) |
| TC-REQ3-01 | E2E | [QE] | `tests/e2e/vmaas/regression/test_compute_instance_storage_tier.py` | deployed suite | Real fulfillment, operator, AAP, CDI, target cluster |
| TC-REQ4-01 | E2E | [QE] | `tests/e2e/vmaas/regression/test_compute_instance_storage_tier.py` | deployed suite | Real fulfillment, operator, AAP, CDI, target cluster |
| TC-REQ4-02 | E2E | [QE] | `tests/e2e/vmaas/regression/` (new: unreachable-registry scenario) | deployed suite | Real stack; registry URL pointed at an unreachable host |
| TC-REQ4-03 | E2E | [QE] | `tests/e2e/vmaas/regression/` (WFFC StorageClass scenario) | deployed suite | Real CDI with HonorWaitForFirstConsumer; WFFC StorageClass |
| TC-REQ4-04 | Component-integration (deployed fulfillment + operator, CDI faked) | [DEV] | `fulfillment-service/it/` with the osac-operator running alongside; supplementary: `osac-operator` integration test on Kind (CR-side state only) | `go test ./it/ -run TestVolumePendingToCreating` (fulfillment side); supplementary: `make -C osac-operator integration-tests` | Real fulfillment-service + Postgres; real Volume controller reconcile loop; CDI faked (DataVolume CRs driven directly, no CDI controllers). The supplementary operator-side test checks CR-level state only and cannot verify persisted API state |
| TC-REQ4-05 | E2E | [QE] | `tests/e2e/vmaas/regression/test_compute_instance_storage_tier.py` (extended) | deployed suite | Real fulfillment, operator, AAP, CDI, target cluster |
| TC-REQ5-01 | E2E | [QE] | `tests/e2e/vmaas/regression/test_compute_instance_storage_tier.py` (existing delete assertions) | deployed suite | Real fulfillment, operator, AAP, CDI, target cluster |
| TC-REQ5-02 | E2E | [QE] | `tests/e2e/vmaas/regression/` (new: delete-with-held-PVC scenario) | deployed suite | Real stack; AAP job template suspended/resumed |
| TC-REQ6-01 | E2E | [QE] | `tests/e2e/vmaas/regression/test_compute_instance_storage_tier.py` (existing OCI assertions) | deployed suite | Real fulfillment, operator, AAP, CDI, target cluster |

### Dependency disclosure

- **E2E cases** run against a deployed OSAC stack via
  [osac-test-infra](https://redhat.atlassian.net/browse/OSAC-4843)
  (real fulfillment-service, osac-operator, AAP, CDI on a target
  cluster). No components are faked.
- **Component-integration cases** in `fulfillment-service/it/` use a
  real fulfillment-service with real Postgres (compose-based); no
  Kubernetes or AAP.
- **osac-aap targets** run real Ansible playbooks against Kind; no AAP
  server, no VM controllers, no storage data plane.
- **osac-operator envtest** runs controller reconcile logic against a
  real kube-apiserver/etcd (envtest binaries); DataVolume CRs are
  created but CDI controllers are not running — the test drives the
  CRs directly (faked CDI).
- **Cases extending existing suites** (TC-REQ4-02, TC-REQ4-03,
  TC-REQ5-02, TC-REQ2-02, TC-REQ2-03) add scenarios to the named
  files; the harness work is part of the [QE] story that implements
  them — no separate follow-up ticket needed.

## Graduation Criteria

The feature is considered production-ready when all of the following
measurable conditions are met:

1. **All 8 critical test cases pass** in CI (TC-REQ1-01, TC-REQ2-01,
   TC-REQ2-02, TC-REQ3-01, TC-REQ4-01, TC-REQ4-02, TC-REQ5-01,
   TC-REQ6-01) on a deployed OSAC stack.
2. **All remaining test cases pass** (high and medium priority) in
   their respective tiers: component-integration cases in
   `fulfillment-service/it/` and `osac-aap` targets; E2E cases on the
   deployed suite.
3. **No regressions** in existing volume or ComputeInstance suites:
   `it_volume_lifecycle_test.go`, `it_public_volumes_test.go`,
   `it_compute_instance_volume_records_test.go`,
   `it_compute_instance_storage_handoff_test.go`,
   `test_compute_instance_storage_tier.py`, and the
   `compute_instance_create` AAP targets.
4. **Idempotency verified** under repeated sequential Create calls AND
   synchronized concurrent requests (TC-REQ2-05) — exactly one stored
   volume per deterministic name, both callers receive the same volume
   ID.
5. **Orphan detection verified** (TC-REQ2-06, TC-REQ2-07) —
   volumes whose owner has been deleted are cleaned up by the
   reconciler; the Volume controller reconciles a self-contained
   out-of-band CR and the finalizer chain removes its DataVolume
   and PVC when the CR is deleted.
6. **Error paths produce visible failure reasons** — volumes in
   `FAILED` state carry a descriptive `status.message` from the
   DataVolume condition (TC-REQ4-02), not the generic "volume
   provisioning failed".

## Summary

| Metric | Count |
|--------|-------|
| Total test cases | 21 |
| Critical | 8 |
| High | 10 |
| Medium | 3 |
| Low | 0 |
| Automated | 20 |
| Manual | 0 |
| Requirements with test cases | 6 / 7 |
| Interface changes with test cases | 7 / 8 |

---

## Provenance

Authored: draft @ design 0.15.0 - 922de34, workspace feat/OSAC-7749 @ 0e8e9f1f6 (87 behind origin/main)
Final: respond @ design 0.15.0 - 922de34, workspace feat/OSAC-7749 @ 0e8e9f1f6 (101 behind origin/main)

> Context changed between draft and respond.

<!-- ai-workflow-provenance:{"schema_version":1,"provenance_kind":"session","workflow":"design","workflow_version":"0.15.0","ai_workflows":"922de34","source_repo":"0e8e9f1f6","source_repo_branch":"feat/OSAC-7749","commits_behind_main":101,"commits_ahead_main":0,"main_ref":"main","phases":["draft","revise","revise","revise","revise","revise","revise","revise","revise","revise","revise","respond","respond","respond","revise","revise","revise","revise","revise","revise","respond","revise","revise","revise","revise","respond","respond","respond","respond","respond","respond"],"authoring_modes":["skill"],"context_changed":true,"origin_untracked":false} -->
