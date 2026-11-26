# Test Plan — OSAC-1710 Storage tier selection

## Overview

- **Public requirements:** [design.md](design.md), [prd.md](prd.md)
- **Total test cases:** 13

Execution identifies matching assertions on OSAC main. Gaps describe remaining coverage for
the named work owner. No individual assignee or follow-up ticket is recorded here.

## Test cases

#### TC-VT-01: Boot disk defaults merge with and without a tier

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Unit
- **Owner:** [DEV]
- **References:** [design.md, lines 525-528](https://github.com/osac-project/enhancement-proposals/blob/71a6101a18a06a832695adefc5c505f20f5e24b4/enhancements/OSAC-1710-storage-tier-selection/design.md#L525-L528)
- **Dependencies:** In-process merge helper with synthetic defaults; no storage client.
- **Gap:** No exact merge fixture identified in the fulfillment ComputeInstance server and controller test inventory for both rows.

**Preconditions.** Use a 20 GiB boot disk and template defaults with and without shared tier fast.

1. Merge with no user tier and compare the resolved boot disks.
2. Repeat with explicit tier standard.

**Expected results.** Fast is inherited when present, remains unset when no source supplies a tier, and explicit standard wins.

#### TC-VT-02: Unit validation distinguishes missing and empty tiers on both disk types

| Priority | Automation |
|---|---|
| critical | automated |

- **Tier:** Unit
- **Owner:** [DEV]
- **References:** [design.md, lines 525-528](https://github.com/osac-project/enhancement-proposals/blob/71a6101a18a06a832695adefc5c505f20f5e24b4/enhancements/OSAC-1710-storage-tier-selection/design.md#L525-L528)
- **Dependencies:** Local validation and synthetic disks; no API server.
- **Gap:** Deployed gRPC tests cover inputs on both disks. The focused validateDisk matrix remains unresolved in fulfillment server tests.

**Preconditions.** Prepare a valid boot disk and additional disk fixture.

1. For each disk, validate absent and empty tier forms independently.
2. Repeat with a valid reference.

**Expected results.** Invalid forms fail at their documented validation boundary. The valid references pass.

#### TC-VT-03: Unit tier lookup handles found, absent and backend errors

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Unit
- **Owner:** [DEV]
- **References:** [design.md, lines 527-529](https://github.com/osac-project/enhancement-proposals/blob/71a6101a18a06a832695adefc5c505f20f5e24b4/enhancements/OSAC-1710-storage-tier-selection/design.md#L527-L529)
- **Dependencies:** StorageTier lookup client is a test double; no network.
- **Gap:** Deployed unknown-tier rejection exists, but the three mock client outcomes were not identified in the focused fulfillment server tests.

**Preconditions.** Stub three lookups for tier fast: present, absent and temporary error.

1. Validate the same tier against each outcome.
2. Compare the returned decision/error.

**Expected results.** Present succeeds, absent is reported as invalid and lookup failure remains distinguishable from absence.

#### TC-VT-04: Catalog defaults and field editability follow the schema

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Unit
- **Owner:** [DEV]
- **References:** [design.md, lines 529-531](https://github.com/osac-project/enhancement-proposals/blob/71a6101a18a06a832695adefc5c505f20f5e24b4/enhancements/OSAC-1710-storage-tier-selection/design.md#L529-L531)
- **Dependencies:** Local CatalogItem field and schema fixtures; no deployed stack.
- **Gap:** Deployed default and override scenarios do not assert the focused schema/editability rules.

**Preconditions.** Build FieldDefinitions for boot_disk.storage_tier with a fast default in editable and fixed forms.

1. Resolve each with and without user tier standard.
2. Validate the resulting configuration against the CatalogItem schema.

**Expected results.** Omission inherits fast, editable accepts standard, and fixed cannot be changed by the tenant request.

#### TC-VT-05: The explicit boot tier reaches the hub CR and DataVolume class

| Priority | Automation |
|---|---|
| critical | automated |

- **Tier:** E2E
- **Owner:** [QE]
- **References:** [design.md, lines 541-545](https://github.com/osac-project/enhancement-proposals/blob/71a6101a18a06a832695adefc5c505f20f5e24b4/enhancements/OSAC-1710-storage-tier-selection/design.md#L541-L545)
- **Dependencies:** Real deployed fulfillment, hub and virtualization APIs, storage controllers and AAP; no guest-level readback in this case.
- **Execution:** `tests/e2e/vmaas/sanity/test_compute_instance_storage_tier.py`
- **Evidence:** `test_compute_instance_explicit_boot_disk_tier` ([source](https://github.com/osac-project/osac/blob/b778b3abffc55bad57edcd5e82d37b82a1280c90/tests/e2e/vmaas/sanity/test_compute_instance_storage_tier.py#L59)).
- **Selector:** `uv run pytest -n 0 tests/e2e/vmaas/sanity/test_compute_instance_storage_tier.py::test_compute_instance_explicit_boot_disk_tier` from OSAC root. Source reviewed, test not run.

**Preconditions.** Use the deployed VMaaS fixture's template and default storage tier.

1. Create a VM with that explicit boot tier and wait for the hub ComputeInstance.
2. Compare its bootDisk storageTier and the corresponding DataVolume StorageClass.

**Expected results.** The hub spec contains the selected tier and the DataVolume uses its resolved StorageClass.

#### TC-VT-06: The deployed API rejects missing and empty boot disk tiers

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** E2E
- **Owner:** [QE]
- **References:** [design.md, lines 537-545](https://github.com/osac-project/enhancement-proposals/blob/71a6101a18a06a832695adefc5c505f20f5e24b4/enhancements/OSAC-1710-storage-tier-selection/design.md#L537-L545)
- **Dependencies:** Real deployed fulfillment, PostgreSQL and public gRPC; fixture templates and references; provider provisioning is not expected to start.
- **Execution:** `tests/e2e/vmaas/sanity/test_compute_instance_storage_tier.py`
- **Evidence:** `test_compute_instance_boot_disk_tier_required` ([source](https://github.com/osac-project/osac/blob/b778b3abffc55bad57edcd5e82d37b82a1280c90/tests/e2e/vmaas/sanity/test_compute_instance_storage_tier.py#L284)).
- **Selector:** `uv run pytest -n 0 tests/e2e/vmaas/sanity/test_compute_instance_storage_tier.py::test_compute_instance_boot_disk_tier_required` from OSAC root. Source reviewed, test not run.

**Preconditions.** Use the VMaaS fixture with a 20 GiB boot disk and a template that supplies no tier.

1. Submit absent and empty boot disk tier requests.
2. Inspect gRPC status and diagnostic for each.

**Expected results.** Both fail with InvalidArgument. Absence names the required tier, while the empty reference requires an ID or name.

#### TC-VT-07: The deployed API rejects missing and empty additional disk tiers

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** E2E
- **Owner:** [QE]
- **References:** [design.md, lines 537-545](https://github.com/osac-project/enhancement-proposals/blob/71a6101a18a06a832695adefc5c505f20f5e24b4/enhancements/OSAC-1710-storage-tier-selection/design.md#L537-L545)
- **Dependencies:** Real deployed fulfillment, PostgreSQL and public gRPC; fixture references; provider provisioning is not expected to start.
- **Execution:** `tests/e2e/vmaas/sanity/test_compute_instance_storage_tier.py`
- **Evidence:** `test_compute_instance_additional_disk_tier_required` ([source](https://github.com/osac-project/osac/blob/b778b3abffc55bad57edcd5e82d37b82a1280c90/tests/e2e/vmaas/sanity/test_compute_instance_storage_tier.py#L328)).
- **Selector:** `uv run pytest -n 0 tests/e2e/vmaas/sanity/test_compute_instance_storage_tier.py::test_compute_instance_additional_disk_tier_required` from OSAC root. Source reviewed, test not run.

**Preconditions.** Use a valid fixture boot tier and a 50 GiB additional disk.

1. Submit absent and empty tiers on the additional disk.
2. Inspect gRPC status and diagnostic for each.

**Expected results.** Both fail with InvalidArgument. Absence identifies additional_disks[0].storage_tier, while an empty reference requires an ID or name.

#### TC-VT-08: The deployed API rejects an unknown storage tier

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** E2E
- **Owner:** [QE]
- **References:** [design.md, lines 537-545](https://github.com/osac-project/enhancement-proposals/blob/71a6101a18a06a832695adefc5c505f20f5e24b4/enhancements/OSAC-1710-storage-tier-selection/design.md#L537-L545)
- **Dependencies:** Real deployed fulfillment, PostgreSQL and public gRPC; no provider is reached for rejected requests.
- **Execution:** `tests/e2e/vmaas/sanity/test_compute_instance_storage_tier.py`
- **Evidence:** `test_compute_instance_nonexistent_tier_rejected` ([source](https://github.com/osac-project/osac/blob/b778b3abffc55bad57edcd5e82d37b82a1280c90/tests/e2e/vmaas/sanity/test_compute_instance_storage_tier.py#L191)).
- **Selector:** `uv run pytest -n 0 tests/e2e/vmaas/sanity/test_compute_instance_storage_tier.py::test_compute_instance_nonexistent_tier_rejected` from OSAC root. Source reviewed, test not run.

**Preconditions.** Use a valid VM fixture and an unused synthetic tier name.

1. Submit the VM create with the unused tier on its boot disk.
2. Capture the gRPC result and diagnostic.

**Expected results.** Create fails with InvalidArgument and the error names the missing tier.

#### TC-VT-09: The mapper populates each disk tier and CRD validation keeps it immutable

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Envtest
- **Owner:** [DEV]
- **References:** [design.md, lines 530-534](https://github.com/osac-project/enhancement-proposals/blob/71a6101a18a06a832695adefc5c505f20f5e24b4/enhancements/OSAC-1710-storage-tier-selection/design.md#L530-L534)
- **Dependencies:** Real envtest API server and CRD admission, in-process mapping helper; no AAP or storage provider.
- **Gap:** Fulfillment handoff tests assert selected class behavior. No exact admission matrix found in the operator test inventory.

**Preconditions.** Use a ComputeInstance proto with boot fast and additional standard.

1. Map and create the CR, then submit distinct fixtures with missing/invalid tier and an update to the boot tier.
2. Read the persisted spec.

**Expected results.** The mapped fields retain their respective tiers, invalid creates and the tier edit are rejected, and original tiers remain.

#### TC-VT-10: Kind resolves catalog and template defaults and rejects unresolved tiers

| Priority | Automation |
|---|---|
| critical | automated |

- **Tier:** Component integration
- **Owner:** [DEV]
- **References:** [design.md, lines 536-539](https://github.com/osac-project/enhancement-proposals/blob/71a6101a18a06a832695adefc5c505f20f5e24b4/enhancements/OSAC-1710-storage-tier-selection/design.md#L536-L539)
- **Dependencies:** Real disposable Kind, fulfillment, PostgreSQL, hub controller and StorageClass lookup; recording AAP; no VM execution.
- **Gap:** Canonical compute-storage handoff covers explicit shared-tier resolution. No single verified Kind selector covers catalog default, template default, override and both missing-tier paths.

**Preconditions.** Create shared tiers fast and standard and synthetic CatalogItems and templates with distinct defaults.

1. Create VMs with explicit, catalog, template and omitted tiers, plus an unknown tier.
2. Read admitted specs or return diagnostics.

**Expected results.** Explicit wins over catalog, catalog wins over template, and unresolved or nonexistent tiers fail with a tier-specific diagnostic.

#### TC-VT-13: Kind resolves a visible shared tier name to its canonical ID

| Priority | Automation |
|---|---|
| critical | automated |

- **Tier:** Component integration
- **Owner:** [DEV]
- **References:** [design.md, lines 536-539](https://github.com/osac-project/enhancement-proposals/blob/71a6101a18a06a832695adefc5c505f20f5e24b4/enhancements/OSAC-1710-storage-tier-selection/design.md#L536-L539)
- **Dependencies:** Real Kind, authenticated fulfillment, PostgreSQL, and storage/operator fixtures. Recording AAP, no actual provider or guest.
- **Execution:** `fulfillment-service/it/it_compute_instance_storage_handoff_test.go`
- **Evidence:** `resolves a visible shared StorageTier name for a tenant-scoped instance` ([source](https://github.com/osac-project/osac/blob/b778b3abffc55bad57edcd5e82d37b82a1280c90/fulfillment-service/it/it_compute_instance_storage_handoff_test.go#L116)).
- **Selector:** Ginkgo focus `resolves a visible shared StorageTier name for a tenant-scoped instance` in the installer SUITE=compute-storage phase from OSAC root. Source reviewed, test not run.

**Preconditions.** Use the compute-storage fixture with two shared tiers, both class fixtures, and an authorized tenant identity.

1. List the selected shared tier and request it by name on a 30 GiB boot disk.
2. Compare the created VM tier reference with the fixture ID and name.

**Expected results.** The user sees the shared tier and the create response resolves it to the selected canonical ID and name.

#### TC-VT-11: A deployed CatalogItem default stamps the boot tier

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** E2E
- **Owner:** [QE]
- **References:** [design.md, lines 529-545](https://github.com/osac-project/enhancement-proposals/blob/71a6101a18a06a832695adefc5c505f20f5e24b4/enhancements/OSAC-1710-storage-tier-selection/design.md#L529-L545)
- **Dependencies:** Real VMaaS deployment and hub API; fixture CatalogItem, template and tier.
- **Execution:** `tests/e2e/vmaas/sanity/test_compute_instance_storage_tier.py`
- **Evidence:** `test_compute_instance_boot_disk_tier_from_catalog_item_default` ([source](https://github.com/osac-project/osac/blob/b778b3abffc55bad57edcd5e82d37b82a1280c90/tests/e2e/vmaas/sanity/test_compute_instance_storage_tier.py#L373)).
- **Selector:** `uv run pytest -n 0 tests/e2e/vmaas/sanity/test_compute_instance_storage_tier.py::test_compute_instance_boot_disk_tier_from_catalog_item_default` from OSAC root. Source reviewed, test not run.

**Preconditions.** Prepare the suite CatalogItem with a default boot tier, and no request override.

1. Create a VM from that CatalogItem.
2. Read the resolved boot tier from its hub CR.

**Expected results.** The recorded tier is the CatalogItem default.

#### TC-VT-12: A deployed editable CatalogItem accepts a tier override

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** E2E
- **Owner:** [QE]
- **References:** [design.md, lines 529-545](https://github.com/osac-project/enhancement-proposals/blob/71a6101a18a06a832695adefc5c505f20f5e24b4/enhancements/OSAC-1710-storage-tier-selection/design.md#L529-L545)
- **Dependencies:** Real VMaaS deployment and hub API; fixture CatalogItem and two distinct tiers.
- **Execution:** `tests/e2e/vmaas/sanity/test_compute_instance_storage_tier.py`
- **Evidence:** `test_compute_instance_user_tier_overrides_catalog_item_default` ([source](https://github.com/osac-project/osac/blob/b778b3abffc55bad57edcd5e82d37b82a1280c90/tests/e2e/vmaas/sanity/test_compute_instance_storage_tier.py#L464)).
- **Selector:** `uv run pytest -n 0 tests/e2e/vmaas/sanity/test_compute_instance_storage_tier.py::test_compute_instance_user_tier_overrides_catalog_item_default` from OSAC root. Source reviewed, test not run.

**Preconditions.** Use the suite's editable CatalogItem with a boot default and a different fixture tier.

1. Create a VM with the different tier.
2. Read the hub CR.

**Expected results.** The boot disk contains the explicitly selected tier.
