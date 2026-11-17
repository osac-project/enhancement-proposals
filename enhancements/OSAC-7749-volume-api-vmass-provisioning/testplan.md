# Testplan — OSAC-7749

## Overview

- **Feature:** OSAC-7749 — Volume API owns VMaaS volume provisioning end-to-end
- **Total test cases:** 16
- **Requirements covered:** 6 of 7 (REQ-7 is a scope constraint with no
  separate behavioral surface — see Gaps; the PRD does not define FR/NFR
  IDs, so requirements use the `REQ-N` keys derived in the architectural
  context and referenced by the design)
- **Interface changes covered:** 6 of 7 (IC-6 is deployment configuration
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
| TC-REQ3-01 | DataVolume lands in the VM namespace on the target cluster | IC-3 | critical |
| TC-REQ4-01 | Volume reports AVAILABLE when the DataVolume import succeeds | IC-2 | critical |
| TC-REQ4-02 | Import failure reports FAILED with the DataVolume failure reason | IC-2 | critical |
| TC-REQ4-03 | WFFC storage: AVAILABLE reflects DV Succeeded, not PVC Bound | IC-2 | medium |
| TC-REQ4-04 | Volume starts PENDING and moves to CREATING when the operator picks it up | IC-2 | high |
| TC-REQ5-01 | Deleting a ComputeInstance deletes its volumes and DataVolumes | IC-4 | critical |
| TC-REQ5-02 | Deleting a running ComputeInstance tears down the VM before the DataVolumes | IC-4 | high |
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
volume.
**Expected:** Both the list entries and the get response show
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
   `spec.diskVolumeIDs` is populated.
**Expected:** The workflow creates the VirtualMachine, Secrets, and any
configured Service; the target namespace contains no DataVolumes created
by the workflow (DataVolumes, when present, were created by the operator
and carry the `DataVolumeProvisioned`-owning controller's annotations),
and the run reports no DataVolume or StorageClass-resolution tasks.

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

**Steps:** 1. Create a ComputeInstance whose boot image references an
   inaccessible registry URL (or a source that fails import) → 2. wait
   for the DataVolume to reach phase `Failed` → 3. `osac volumes get`.
**Expected:** The volume reports `status.state = FAILED` and
`status.message` contains the DataVolume condition's reason and message
(for example the importer's exit reason), not the generic
"volume provisioning failed".

#### TC-REQ4-03: WFFC storage: AVAILABLE reflects DV Succeeded, not PVC Bound

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-2 | medium | automated |

**Steps:** 1. Create a ComputeInstance whose disks use a
   WaitForFirstConsumer StorageClass → 2. read the volume state once the
   DataVolume reports `Succeeded` while the PVC is still `Pending`
   (before/without the VM consuming it).
**Expected:** The volume reports `AVAILABLE` (DataVolume `Succeeded`
drives the state), demonstrating the state definition does not depend on
PVC binding.

#### TC-REQ4-04: Volume starts PENDING and moves to CREATING when the operator picks it up (parameterized)

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-2 | high | automated |

##### Steps

1. Create a volume through the `{creation flow}` (a ComputeInstance with
   a disk, or a standalone volume through the CSI/public path).
2. Immediately after the volume appears in `osac volumes list`, run
   `osac volumes get` and record `status.state`.
3. Wait for provisioning to start, then run `osac volumes get` again.

##### Expected Results

| Creation flow | Expected Result |
|---------------|-----------------|
| CI-owned disk volume | The first observed state is `PENDING` (the record exists, no DataVolume activity yet); after the operator picks up the Volume CR, the state is `CREATING` and stays `CREATING` on subsequent gets until it settles — the transition is persisted, not transient |
| CaaS/CSI volume | Same: `PENDING` at creation, `CREATING` once the operator starts vendor provisioning — the initial state applies to every creation flow |

### REQ-5: Deleting a ComputeInstance deletes its volumes

##### Shared Preconditions

- A ComputeInstance with a boot disk and an additional disk has reached
  `RUNNING`.

#### TC-REQ5-01: Deleting a ComputeInstance deletes its volumes and DataVolumes

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-4 | critical | automated |

**Steps:** 1. Delete the ComputeInstance → 2. wait for the instance to
   be gone → 3. `osac volumes list` and inspect the target namespace.
**Expected:** `osac volumes list` no longer shows the instance's
volumes; the DataVolumes `<ci-name>-root-disk` and `<ci-name>-disk-1`
no longer exist in the VM namespace; no volume remains in `DELETING`.

#### TC-REQ5-02: Deleting a running ComputeInstance tears down the VM before the DataVolumes

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-4 | high | automated |

**Steps:** 1. Delete the running ComputeInstance → 2. observe teardown
   ordering and completion within the reconciliation timeout window.
**Expected:** The VirtualMachine and VMI are deleted first (the AAP
deprovision job no longer deletes DataVolumes), the PVCs release, and
the DataVolumes are then deleted by the Volume controller; the volumes
end `DELETED` without operator intervention (retry loop absorbs the
PVC-in-use window).

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

## Summary

| Metric | Count |
|--------|-------|
| Total test cases | 16 |
| Critical | 8 |
| High | 6 |
| Medium | 2 |
| Low | 0 |
| Automated | 16 |
| Manual | 0 |
| Requirements with test cases | 6 / 7 |
| Interface changes with test cases | 6 / 7 |
