# Testplan — OSAC-3702

## Overview

- **Feature:** OSAC-3702 — LVMS Node-Local Storage Backend for VMaaS (single-node)
- **Total test cases:** 21
- **Requirements covered:** 9 of 9 (R1–R9)
- **Interface changes covered:** 8 of 8 (IC-1–IC-8)

Requirement IDs are R1–R9 as assigned in `01-context.md` (the house-style PRD
has no FR-N/NFR-N IDs). Interface Changes are numbered from the design's
§API Extensions / §Implementation Details in `03-design.md`, in T-order:

| IC | Interface surface | Design ref | Ticket |
|----|-------------------|-----------|--------|
| IC-1 | Private proto: optional `VolumeTopology{node}` on `VolumeSpec` + `CreateVolumeRequest` | §API Extensions, §Impl (Topology proto) | T1 / OSAC-4357 |
| IC-2 | Fulfillment: local-tier node guard (`FailedPrecondition`) + carry topology into Volume CR | §Impl (Fulfillment guard + carry) | T2 / OSAC-4358 |
| IC-3 | Operator Volume CRD: optional `topology` field | §API Extensions | T3 / OSAC-4359 |
| IC-4 | Operator: `LvmsVendorProvisioner` + provider-keyed routing + `VendorCreateVolumeRequest.Topology` | §Impl (Provider-keyed routing) | T4 / OSAC-4360 (OSAC-4221 first) |
| IC-5 | CSI: `VOLUME_ACCESSIBILITY_CONSTRAINTS` capability + controller topology extract + `AccessibleTopology` | §API Extensions, §Impl (CSI controller) | T5 / OSAC-4361 |
| IC-6 | CSI: `NodeGetInfo` `osac.io/node` segment + topolvm-node socket mount routing | §Impl (CSI node) | T6 / OSAC-4362 |
| IC-7 | Operator Helm: RBAC for `topolvm.io/LogicalVolume` | §API Extensions (RBAC) | T7 / OSAC-4363 |
| IC-8 | AAP: `osac-csi` local-tier StorageClass (WFC) + VMaaS onboarding wiring | §Impl (AAP StorageClass) | T8 / OSAC-4364 |

## Test Cases

### R1: Opaque `local` tier — LVMS presented like any remote backend

#### TC-R1-01: Provider-keyed routing selects the LVMS provisioner for a `provider: lvms` backend

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-4 | critical | automated |

##### Preconditions

- A `StorageBackend { provider: lvms }` named `local` and a `local` tier are registered.
- A `StorageBackend { provider: vast }` is also registered.

##### Steps

1. Create a Volume against the `local` tier (with a topology node set).
2. Inspect which provisioner the operator Volume controller dispatches to.

##### Expected Results

- The controller dispatches to `LvmsVendorProvisioner` (not `VastVendorProvisioner`); a `LogicalVolume` CR is created and no VAST endpoint/secret lookup occurs.

#### TC-R1-02: Tenant sees only the opaque tier, no LVMS internals

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-8 | high | automated |

##### Preconditions

- The `local` tier and its `osac-csi` StorageClass exist.

##### Steps

1. List storage tiers / StorageClasses available to a tenant user.

##### Expected Results

- The tenant sees a `local` tier served by provisioner `osac.csi.openshift.io`; no `topolvm.io` provisioner name, device-class, or VG detail is exposed on the tenant-facing tier.

### R2: Automatic setup during single-node VMaaS onboarding

#### TC-R2-01: VMaaS onboarding creates the `local`-tier osac-csi StorageClass end-to-end

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-8 | critical | automated |

##### Preconditions

- A single-node cluster with LVMS installed (OSAC-3011) and `OSAC_ENABLE_STORAGE_CONTROLLER=true` **and** `lvms.enabled` set.

##### Steps

1. Run VMaaS onboarding.
2. Inspect the resulting StorageClass.

##### Expected Results

- A StorageClass with `provisioner: osac.csi.openshift.io`, `volumeBindingMode: WaitForFirstConsumer`, `reclaimPolicy: Delete`, and **no** `topolvm.io/device-class` parameter exists after onboarding, with no manual steps.

#### TC-R2-02: The native `topolvm.io` OSAC-managed StorageClass is retired; the LVMS-operator default is untouched

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-8 | high | automated |

##### Preconditions

- OSAC-3011's per-tenant `provisioner: topolvm.io` StorageClass previously existed on the control-plane path.

##### Steps

1. Complete VMaaS onboarding with the control plane enabled.
2. List StorageClasses.

##### Expected Results

- No OSAC-managed per-tenant `provisioner: topolvm.io` StorageClass is emitted on the control-plane path; the separate LVMS-operator default StorageClass (from `LVMCluster`) is still present and unmodified.

### R3: Node-local provisioning behavior (WaitForFirstConsumer, node-pinned)

#### TC-R3-01: CSI advertises the accessibility capability so external-provisioner sends topology

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-5 | critical | automated |

##### Preconditions

- The OSAC CSI driver is deployed.

##### Steps

1. Call `GetPluginCapabilities`.

##### Expected Results

- The response includes `VOLUME_ACCESSIBILITY_CONSTRAINTS`.

#### TC-R3-02: Scheduler-selected node threads through to the LogicalVolume and PV nodeAffinity

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-5 | critical | automated |

##### Preconditions

- A `local`-tier PVC with `WaitForFirstConsumer`; a pod that consumes it.

##### Steps

1. Create the PVC (stays Pending) and the pod.
2. Let the scheduler pick node N.
3. Inspect the `LogicalVolume` CR, the `CreateVolumeResponse`, and the bound PV.

##### Expected Results

- `LogicalVolume.spec.nodeName == N`; the `CreateVolumeResponse.AccessibleTopology` contains `{osac.io/node: N}`; the bound PV's `nodeAffinity` requires `osac.io/node in [N]`.

#### TC-R3-03: `NodeGetInfo` topology value equals the Kubernetes Node name

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-6 | high | automated |

##### Preconditions

- The node plugin runs on node N.

##### Steps

1. Call `NodeGetInfo` on node N.

##### Expected Results

- `AccessibleTopology` returns segment `osac.io/node=<N>` where `<N>` equals the Node's `.metadata.name` (not `os.Hostname()`).

#### TC-R3-04: Local-tier create via direct API with no topology node is rejected

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-2 | high | automated |

##### Preconditions

- A `local` tier resolving to `provider: lvms`.

##### Steps

1. Call `CreateVolume` for the `local` tier with an empty `topology.node`.

##### Expected Results

- The call fails with `codes.FailedPrecondition`; no Volume record is persisted.

#### TC-R3-05: Network-tier create ignores topology and is unaffected (regression)

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-2 | high | automated |

##### Preconditions

- A network tier (e.g. VAST).

##### Steps

1. Create a network-tier Volume with no topology node.
2. Inspect the resulting PV.

##### Expected Results

- The Volume is created normally; its PV has no `nodeAffinity`; its StorageClass stays `volumeBindingMode: Immediate` — advertising the accessibility capability does not change network provisioning.

### R4: ComputeInstance consumption (boot + additional disks)

#### TC-R4-01: A ComputeInstance backs its `local`-tier disk end-to-end and data round-trips

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-8 | critical | automated |

##### Preconditions

- Single-node VMaaS with the `local` tier configured.

##### Steps

1. Create a ComputeInstance with a `tier=local` disk.
2. Wait for the VM to run.
3. Write data to the disk, then read it back.

##### Expected Results

- The PVC binds after scheduling; an LV is carved on the scheduled node; the VM reaches Running; written data reads back identically.

#### TC-R4-02: The LogicalVolume topology matches the node the ComputeInstance is pinned to

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-4 | high | automated |

##### Preconditions

- A running ComputeInstance with a `local`-tier disk from TC-R4-01.

##### Steps

1. Compare `LogicalVolume.spec.nodeName`, the PV `nodeAffinity`, and the node the VM pod runs on.

##### Expected Results

- All three name the same node; the volume does not migrate across nodes.

### R5: Full lifecycle + cleanup (no capacity leak)

#### TC-R5-01: Deleting the ComputeInstance releases both the LV and the inventory record

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-4 | critical | automated |

##### Preconditions

- A running ComputeInstance with a `local`-tier disk.

##### Steps

1. Delete the ComputeInstance (and thereby its PVC).
2. Inspect the `LogicalVolume` CR, the node VG, and the fulfillment Volume record.

##### Expected Results

- The `LogicalVolume` CR is deleted, topolvm-node reclaims the LV (VG free space returns), and the fulfillment Volume record is removed — no orphaned LV or inventory row.

#### TC-R5-02: Delete is idempotent when the LogicalVolume is already gone

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-4 | medium | automated |

##### Preconditions

- A Volume whose `LogicalVolume` CR has already been deleted out of band.

##### Steps

1. Invoke `DeleteVolume` for that Volume.

##### Expected Results

- The call succeeds (treated as already-deleted); the Volume record is still cleaned up; no error is returned for the missing CR.

#### TC-R5-03: LogicalVolume that never becomes ready drives the Volume to an error state

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-4 | medium | automated |

##### Preconditions

- A `LogicalVolume` whose `status.volumeID` is never set within the provisioner's bounded poll timeout.

##### Steps

1. Create a `local`-tier Volume and hold the LV in a non-ready state past the timeout.

##### Expected Results

- The Volume transitions to an error state carrying a message; the reconciler retries; no duplicate LV is carved on retry (idempotent by `LogicalVolume` name).

### R6: Inventory tracking

#### TC-R6-01: A `local`-tier Volume is persisted with tenant, tier, state, size, and vendor volume ID

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-2 | high | automated |

##### Preconditions

- A `local` tier configured; a scheduled consumer.

##### Steps

1. Provision a `local`-tier Volume through the PVC path.
2. Read the fulfillment Volume record.

##### Expected Results

- The record carries the tenant, `tier=local`, `status.backend=local`, requested size, `state` transitioning `CREATING → AVAILABLE`, and `vendor_volume_id == LogicalVolume.status.volumeID`.

#### TC-R6-02: The topolvm volume handle is surfaced for the node mount

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-4 | high | automated |

##### Preconditions

- An AVAILABLE `local`-tier Volume.

##### Steps

1. Inspect the `CreateVolumeResponse.volume_context`.

##### Expected Results

- `volume_context` includes `osac.backend`, `osac.volume-id`, `osac.topolvm-volume-id` (equal to `status.volumeID`), and `osac.protocol`, so the node plugin can mount via topolvm-node.

### R7: Predictable capacity failure

#### TC-R7-01: Insufficient VG capacity returns ResourceExhausted with no partial volume

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-4 | high | automated |

##### Preconditions

- A node whose VG cannot satisfy the requested size.

##### Steps

1. Create a `local`-tier Volume larger than free VG space on the selected node.

##### Expected Results

- `LvmsVendorProvisioner` returns `codes.ResourceExhausted` (not a generic error), propagated by the CSI controller and surfaced as a PVC provisioning event; no LV is carved and no partial inventory record remains.

### R8: Interfaces via the same console/CLI channels (no LVMS-specific UI)

#### TC-R8-01: The topology field is private and produces no tenant-facing UI diff

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-1 | medium | automated |

##### Preconditions

- The private proto with `VolumeTopology` is generated.

##### Steps

1. Regenerate public/tenant-facing types (`pnpm gen-types`) and inspect the tenant-facing storage resources.

##### Steps note

- `VolumeTopology.node` lives only on `private.v1.VolumeSpec`.

##### Expected Results

- No new tenant-facing field appears on `block-volumes` / `compute-instance-disk`; the tenant sees the `local` tier through the same console/CLI channels as other tiers, with no LVMS-specific control.

#### TC-R8-02: The topology proto message is additive and optional (round-trip)

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-1 | medium | automated |

##### Preconditions

- The generated proto types.

##### Steps

1. Marshal/unmarshal a `VolumeSpec` with `topology` set and with `topology` absent.

##### Expected Results

- Both round-trip cleanly; the field defaults to empty when absent; `buf lint`/`buf generate` succeed with a fresh field number (not the removed `pvc_ref` slot).

### R9: Test + docs

#### TC-R9-01: Single-node VMaaS E2E covers provision → mount → data round-trip → cleanup with node-pinning

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| — | critical | automated |

##### Preconditions

- A single-node VMaaS cluster with the `local` tier configured (the full chain: IC-1 through IC-8 deployed).

##### Steps

1. Create a ComputeInstance with a `local`-tier disk.
2. Verify the LV is carved on the scheduled node and the PV `nodeAffinity` pins it there.
3. Write and read back data.
4. Delete the ComputeInstance and verify LV + inventory cleanup.

##### Expected Results

- The full flow passes: the volume provisions on the scheduled node, mounts, round-trips data, and on deletion leaves no LV or inventory record — matching the Dev Preview graduation criterion.

### IC-3 / IC-7 coverage

#### TC-R3-06: Operator Volume CRD carries the optional topology field through to the provisioner

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-3 | high | automated |

##### Preconditions

- The operator CRD with the additive `topology` field is installed.

##### Steps

1. Create a `local`-tier Volume with a topology node.
2. Inspect the Volume CR and what the `LvmsVendorProvisioner` receives.

##### Expected Results

- The Volume CR persists `spec.topology.node`; the provisioner's `VendorCreateVolumeRequest.Topology.Node` equals that value; network-backend Volumes leave it empty.

#### TC-R6-03: Operator ServiceAccount can manage LogicalVolume resources

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-7 | high | automated |

##### Preconditions

- The operator Helm chart with the new RBAC is deployed.

##### Steps

1. As the operator ServiceAccount, `create`/`get`/`list`/`watch`/`delete` a `topolvm.io/LogicalVolume`.

##### Expected Results

- All verbs succeed within the operator's cluster; without the RBAC grant, `LogicalVolume` create is forbidden (provisioning would fail closed).

## Gaps

### Requirement Coverage Gaps

- **R9 (docs portion):** the admin + user documentation deliverable has no behavioral test case — it is validated by a `[DOCS]` story in decomposition, not by an automated test. The E2E portion of R9 is covered by TC-R9-01.
- All other PRD requirements (R1–R8) have at least one behavioral test case.

### Interface Change Coverage Gaps

- All eight interface changes (IC-1 through IC-8) are exercised by at least one test case:
  IC-1 → TC-R8-01/02; IC-2 → TC-R3-04/05, TC-R6-01; IC-3 → TC-R3-06; IC-4 → TC-R1-01, TC-R4-02, TC-R5-01/02/03, TC-R6-02, TC-R7-01; IC-5 → TC-R3-01/02; IC-6 → TC-R3-03; IC-7 → TC-R6-03; IC-8 → TC-R1-02, TC-R2-01/02, TC-R4-01.

## Summary

| Metric | Count |
|--------|-------|
| Total test cases | 21 |
| Critical | 7 |
| High | 10 |
| Medium | 4 |
| Low | 0 |
| Automated | 21 |
| Manual | 0 |
| Requirements with test cases | 9 / 9 |
| Interface changes with test cases | 8 / 8 |
