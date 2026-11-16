# Testplan — OSAC-7318

## Overview

- **Feature:** OSAC-7318 — Volume ownership and disk lifecycle for VMaaS ComputeInstances (Feature 1: create-VM-with-volumes)
- **Total test cases:** 20
- **Requirements covered:** 11 of 11
- **Interface changes covered:** 12 of 12

Implementation phasing: cases exercising IC-12 (runtime attach/detach/move)
run against the OSAC-5888/5889 implementation tracks; the model decisions
they verify are final in this design. All other cases run against Feature 1.

## Test Case Index

| ID | Scenario | IC | Priority |
|----|----------|----|----------|
| TC-FR1-01 | CI-created volumes record owner and termination policy | IC-1, IC-7 | critical |
| TC-FR1-02 | Cross-tenant owner reference rejected | IC-1 | high |
| TC-FR2-01 | Owner change to a second ComputeInstance rejected | IC-1 | high |
| TC-FR3-01 | Create-time disks usable inside the guest | IC-3, IC-7, IC-8 | critical |
| TC-FR3-02 | VM start waits for still-importing DataVolume | IC-8 | high |
| TC-FR3-03 | Runtime add to a running VM hotplugs the disk | IC-12 | high |
| TC-FR4-01 | Remove from a running VM preserves the volume and data | IC-12 | high |
| TC-FR5-01 | Volume moves between ComputeInstances with data intact | IC-12 | medium |
| TC-FR6-01 | Delete refused while a ComputeInstance uses the volume | IC-10 | critical |
| TC-FR6-02 | Delete removes backing storage end to end | IC-6, IC-10 | critical |
| TC-FR6-03 | Failed delete is visible and retryable | IC-10 | medium |
| TC-FR7-01 | Volume reaches BOUND when the DataVolume succeeds | IC-4, IC-5, IC-6 | critical |
| TC-FR7-02 | DataVolume import failure surfaces as FAILED with reason | IC-4 | high |
| TC-FR8-01 | Blank data disk presents the full requested size | IC-3 | high |
| TC-FR8-02 | Volume create without source behaves as before | IC-3 | critical |
| TC-FR8-03 | Explicit CAAS type with a source rejected | IC-3 | medium |
| TC-FR9-01 | ComputeInstance deletion removes born volumes and storage | IC-2, IC-9 | critical |
| TC-FR9-02 | Attached volumes survive ComputeInstance deletion | IC-2, IC-9 | high |
| TC-FR10-01 | Tenant-visible states and progress events | IC-4 | high |
| TC-FR11-01 | CLI volume create source flags | IC-11 | medium |

## Test Cases

### FR-1: Every volume records the owning/using ComputeInstance

##### Shared Preconditions

- A tenant with a Ready storage tier and a usable subnet exists
- The fulfillment API and `osac` CLI are authenticated for that tenant

#### TC-FR1-01: CI-created volumes record owner and termination policy

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-1, IC-7 | critical | automated |

**Steps:** 1. Create a ComputeInstance with one boot disk and one data disk → 2. `osac get volumes` and `osac get volume <id> -o yaml` for each disk's volume
**Expected:** Both volumes list and get show `type` `VOLUME_TYPE_VMAAS`, `owner.compute_instance` equal to the ComputeInstance ID, and `termination_policy` `VOLUME_TERMINATION_POLICY_DELETE`; tenant and project match the instance.

#### TC-FR1-02: Cross-tenant owner reference rejected

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-1 | high | automated |

**Steps:** 1. Via the private API (the CI provisioning path, which is allowed to write `owner`), create a volume whose `owner.compute_instance` references a ComputeInstance of tenant B → 2. Via the same path, create a volume whose owner references a ComputeInstance of tenant A (same-tenant control)
**Expected:** The cross-tenant request is rejected with `INVALID_ARGUMENT` and a message identifying the tenant mismatch, and no volume is created; the same-tenant control succeeds with the owner recorded.

### FR-2: A volume is used by at most one ComputeInstance

#### TC-FR2-01: Owner change to a second ComputeInstance rejected

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-1 | high | automated |

**Steps:** 1. Create a volume owned by ComputeInstance A → 2. Update the volume setting `owner.compute_instance` to ComputeInstance B (same tenant)
**Expected:** The update is rejected with `INVALID_ARGUMENT`; the owner remains ComputeInstance A.

### FR-3: Add as a disk, at creation time or later while running

##### Shared Preconditions

- A published registry image reachable by node pull (e.g. `quay.io/containerdisks/fedora:41`)

#### TC-FR3-01: Create-time disks usable inside the guest

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-3, IC-7, IC-8 | critical | automated |

**Steps:** 1. Create a ComputeInstance with a boot disk (registry image) and a blank data disk → 2. Wait for state RUNNING → 3. Verify disks inside the guest (SSH/console)
**Expected:** The VM reaches RUNNING; the guest boots the registry image's OS; the guest sees both disks, the data disk empty with the full requested capacity.

#### TC-FR3-02: VM start waits for still-importing DataVolume

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-8 | high | automated |

**Steps:** 1. Create a ComputeInstance whose boot image is a large registry image (≥ 2 GiB, so import takes at least tens of seconds) → 2. Inspect the VM and VMI while the DataVolume is importing → 3. Wait for import completion
**Expected:** While importing, the VMI is Pending with `FailedPvcNotFound` and the ComputeInstance does not report provisioning failure; after the DataVolume reaches Succeeded the VM reaches RUNNING with no intervention.

#### TC-FR3-03: Runtime add to a running VM hotplugs the disk

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-12 | high | automated |

##### Additional Preconditions

- A BOUND volume with no owner exists in the same tenant and cluster

**Steps:** 1. Add the volume to the running ComputeInstance's additional disks → 2. Verify the disk inside the guest
**Expected:** The volume's owner is set to the ComputeInstance; the disk appears in the running guest without a VM restart.

### FR-4: Remove as a disk while running; volume and data survive

#### TC-FR4-01: Remove from a running VM preserves the volume and data

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-12 | high | automated |

**Steps:** 1. Write a marker file to a volume attached to a running ComputeInstance → 2. Remove the disk from the ComputeInstance → 3. Re-add the volume to another ComputeInstance and read the marker
**Expected:** After removal the disk is gone from the guest, the volume is BOUND with no owner and is listed as available; the marker file is intact after re-add.

### FR-5: A volume moves between ComputeInstances by remove then add

#### TC-FR5-01: Volume moves between ComputeInstances with data intact

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-12 | medium | automated |

**Steps:** 1. Remove a data volume from ComputeInstance A → 2. Add it to ComputeInstance B on the same cluster → 3. Read the previously written data
**Expected:** The volume's owner transitions A → (none) → B; the data written under A is readable inside B's guest.

### FR-6: Delete is a distinct action, refused while used, retryable on failure

#### TC-FR6-01: Delete refused while a ComputeInstance uses the volume

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-10 | critical | automated |

**Steps:** 1. Delete a volume that has `owner` set
**Expected:** The API responds `FAILED_PRECONDITION` with a message directing the tenant to remove the disk from the ComputeInstance first; the volume and its storage are unchanged.

#### TC-FR6-02: Delete removes backing storage end to end

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-6, IC-10 | critical | automated |

**Steps:** 1. Delete an unowned BOUND volume → 2. Inspect the target cluster and the volume API
**Expected:** The DataVolume, its PVC, and the PV are removed from the target cluster; the volume API no longer returns the volume; deletion completes without manual cleanup.

#### TC-FR6-03: Failed delete is visible and retryable

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-10 | medium | automated |

**Steps:** 1. Create a ComputeInstance whose boot image registry URL does not resolve (fault injection) → 2. Delete one of its volumes after the import fails → 3. Point the boot image to a resolvable URL (fault cleared) and retry the delete
**Expected:** The volume enters FAILED with a reason naming the storage failure; after the fault clears, the retried delete completes and the backing storage is removed.

### FR-7: Volume state and the storage the VM runs on stay in step

#### TC-FR7-01: Volume reaches BOUND when the DataVolume succeeds

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-4, IC-5, IC-6 | critical | automated |

**Steps:** 1. Create a ComputeInstance with a registry boot image (owned volume) → 2. Observe the Volume CR on the hub and the volume API while the DataVolume imports → 3. Wait for DataVolume Succeeded
**Expected:** The volume is PENDING with the Volume CR in phase Pending while importing; when the DataVolume reaches Succeeded the volume is BOUND and `provisioned_size_gib` equals the bound PVC's capacity.

#### TC-FR7-02: DataVolume import failure surfaces as FAILED with reason

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-4 | high | automated |

**Steps:** 1. Create a ComputeInstance whose boot image registry URL does not resolve (e.g. `docker://quay.io/nonexistent/osac-test:latest`) → 2. Wait for the DataVolume to fail
**Expected:** The volume is FAILED with a reason containing the DataVolume's failure condition message; the ComputeInstance provisioning reports the failure.

### FR-8: Disk source options are preserved for OSAC-volume-backed disks

#### TC-FR8-01: Blank data disk presents the full requested size

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-3 | high | automated |

**Steps:** 1. Create a ComputeInstance with a blank data disk of 50 GiB → 2. Check the disk size inside the guest
**Expected:** The guest sees a disk of exactly 50 GiB (consumer-presented sizing); the PVC request on the cluster is larger by the filesystem overhead.

#### TC-FR8-02: Volume create without source behaves as before

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-3 | critical | automated |

**Steps:** 1. Run the existing Volume API creation suites (server tests, CLI tests, CSI-driver contract tests) unchanged
**Expected:** All existing tests pass; volumes created without `type` or `source` default to the CAAS realization path and state vocabulary (CREATING/AVAILABLE).

#### TC-FR8-03: Explicit CAAS type with a source rejected

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-3 | medium | automated |

**Steps:** 1. Create a volume with `type` `VOLUME_TYPE_CAAS` and a registry `source`
**Expected:** The API rejects the request with `INVALID_ARGUMENT` naming the type/source conflict; no volume is created.

### FR-9: Deleting a ComputeInstance deletes the volumes provisioned with it

#### TC-FR9-01: ComputeInstance deletion removes born volumes and storage

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-2, IC-9 | critical | automated |

**Steps:** 1. Delete a ComputeInstance created with boot and data disks → 2. Inspect the target cluster, the hub, and the volume API during and after deletion
**Expected:** The VirtualMachine manifest is removed first, then each born volume's DataVolume, PVC and PV, and the volume records; ComputeInstance deletion completes only after all volumes are cleaned up.

#### TC-FR9-02: Attached volumes survive ComputeInstance deletion

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-2, IC-9 | high | automated |

**Steps:** 1. Attach a user-created volume to a ComputeInstance → 2. Delete the ComputeInstance
**Expected:** The born disks are removed with the instance; the attached volume survives, its owner is cleared, and it remains BOUND and available for reuse.

### FR-10: Tenant-visible states with progress as events

#### TC-FR10-01: Tenant-visible states and progress events

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-4 | high | automated |

**Steps:** 1. Drive a volume through create → in-use → remove → delete → 2. Observe the volume API states and events at each step
**Expected:** The tenant-visible state is always one of available-and-unused, in-use by the named ComputeInstance, being deleted, or failed with a reason; intermediate progress (import percentage, phase changes) appears as events, not as additional states.

### FR-11: Fulfillment API and `osac` CLI expose the operations

#### TC-FR11-01: CLI volume create source flags

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-11 | medium | automated |

**Steps:** 1. `osac create volume --name v2 --blank …` → 2. `osac create volume --name v3` (no new flags) → 3. `osac get volume v2 -o yaml`
**Expected:** v2 is created with `type` `VOLUME_TYPE_VMAAS` and no source (blank disk); v3 succeeds exactly as before (CAAS default, no source); the from-image flag is not exposed on the CLI in this slice [Locked: D14].

## Coverage Matrix

Tier ownership and suite mapping per `docs/INTEGRATION-TESTING.md` in
the osac mono-repo. [DEV] cases execute in the owning story's
validation; [QE] cases execute in the deployed e2e suite. Cases marked
*deferred* execute against the OSAC-5888/5889 tracks.

| TC | Tier | Owner | Suite / command | Dependencies |
|----|------|-------|-----------------|--------------|
| TC-FR1-01 | Component integration (deployed) | [QE] Story 1.04 | `it/` via `make -C ../osac-installer test SUITE=fulfillment` | Real fulfillment + Postgres; no operator |
| TC-FR1-02 | Component integration (deployed) | [QE] Story 1.04 | `it/` via `make -C ../osac-installer test SUITE=fulfillment` | Real fulfillment + Postgres; private-API client for the owner-write path |
| TC-FR2-01 | Unit (server, DB-backed) + deployed | [DEV] Story 1.02, [QE] Story 1.04 | `ginkgo run internal/servers`; `it/` | Real Postgres; real fulfillment |
| TC-FR3-01 | E2E | [QE] Story 3.04 | `tests/e2e/` (deployed Kind profile) | Real CNV/KubeVirt, CDI, operator, fulfillment; guest access via console/SSH |
| TC-FR3-02 | E2E | [QE] Story 3.04 | `tests/e2e/` | Real CNV; large (≥ 2 GiB) registry image |
| TC-FR3-03 | E2E | [QE] *deferred* (OSAC-5889) | `tests/e2e/` | Real CNV hotplug |
| TC-FR4-01 | E2E | [QE] *deferred* (OSAC-5889) | `tests/e2e/` | Real CNV hotplug |
| TC-FR5-01 | E2E | [QE] *deferred* (OSAC-5889) | `tests/e2e/` | Real CNV hotplug |
| TC-FR6-01 | Unit (server, DB-backed) + deployed | [DEV] Story 1.02, [QE] Story 4.02 | `ginkgo run internal/servers`; `it/` | Real Postgres |
| TC-FR6-02 | E2E | [QE] Story 4.02 | `tests/e2e/` | Real operator + Kind; unowned-BOUND precondition constructed via the private API (test fixture) |
| TC-FR6-03 | E2E | [QE] Story 4.02 | `tests/e2e/` | Real operator + Kind; fault injected via unresolvable registry URL |
| TC-FR7-01 | Envtest + E2E | [DEV] Story 2.02, [QE] Story 3.04 | `make test` (osac-operator); `tests/e2e/` | Envtest: real K8s API/etcd, faked multicluster; E2E: real CDI |
| TC-FR7-02 | Envtest + E2E | [DEV] Story 2.02, [QE] Story 3.04 | `make test`; `tests/e2e/` | Same as TC-FR7-01 |
| TC-FR8-01 | E2E | [QE] Story 3.04 | `tests/e2e/` | Real CDI + storage class with filesystem overhead |
| TC-FR8-02 | Contract + regression | [DEV] Story 1.02 | Existing fulfillment server suites, CLI suites, CSI-driver contract suites — run unchanged | Real Postgres; proto regeneration check |
| TC-FR8-03 | Unit (server, DB-backed) | [DEV] Story 1.02 | `ginkgo run internal/servers` | Real Postgres |
| TC-FR9-01 | E2E | [QE] Story 4.02 | `tests/e2e/` | Real operator, CDI, fulfillment |
| TC-FR9-02 | E2E | [QE] *deferred* (OSAC-5889) | `tests/e2e/` | Real attach flow |
| TC-FR10-01 | E2E | [QE] Story 3.04 | `tests/e2e/` | Real fulfillment events |
| TC-FR11-01 | Component integration (deployed CLI) | [QE] Story 1.04 | `it/` CLI harness | Real fulfillment; real `osac` binary |

## Gaps

### Requirement Coverage Gaps

All PRD requirements have test cases. The Jira Feature definition-of-done
additionally requires Volume API and osac-operator documentation describing
the model, lifecycle, and DataVolume naming contract — a documentation-only
deliverable with no behavioral test case.

### Interface Change Coverage Gaps

All interface changes are exercised by test cases.

## Summary

| Metric | Count |
|--------|-------|
| Total test cases | 20 |
| Critical | 7 |
| High | 9 |
| Medium | 4 |
| Low | 0 |
| Automated | 20 |
| Manual | 0 |
| Requirements with test cases | 11 / 11 |
| Interface changes with test cases | 12 / 12 |
