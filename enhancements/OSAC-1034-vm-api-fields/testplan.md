# Test Plan — OSAC-1034 VM API fields

## Overview

- **Public requirements:** [README.md](README.md)
- **Total test cases:** 4

Execution identifies matching assertions on OSAC main. Gaps describe remaining coverage for
the named work owner. No individual assignee or follow-up ticket is recorded here.

## Test cases

#### TC-VMF-01: A tenant VM request projects compute, disk, run strategy and user data to the hub

| Priority | Automation |
|---|---|
| critical | automated |

- **Tier:** E2E
- **Owner:** [QE]
- **References:** [README.md, lines 59-104](https://github.com/osac-project/enhancement-proposals/blob/84a28b6b9865f71684304e9fd1e1665835807bfc/enhancements/OSAC-1034-vm-api-fields/README.md#L59-L104)
- **Dependencies:** Real deployed fulfillment, hub API and controller; fixture template, instance type, network and synthetic user data; guest readiness omitted.
- **Execution:** `tests/e2e/vmaas/sanity/test_compute_instance_cli_fields.py`
- **Evidence:** `test_compute_instance_cli_explicit_fields` ([source](https://github.com/osac-project/osac/blob/b778b3abffc55bad57edcd5e82d37b82a1280c90/tests/e2e/vmaas/sanity/test_compute_instance_cli_fields.py#L29)).
- **Selector:** `uv run pytest -n 0 tests/e2e/vmaas/sanity/test_compute_instance_cli_fields.py::test_compute_instance_cli_explicit_fields` from OSAC root. Source reviewed, test not run.

**Preconditions.** Use the suite's default instance type, fixture template, a 20 GiB boot disk and synthetic user data.

1. Create using the tenant CLI with run strategy Always.
2. Compare hub spec and generated user-data Secret with the inputs.

**Expected results.** Hub spec has fixture vCPUs/memory, a nonempty instance-type label, 20 GiB and Always. Its user-data reference resolves to the ComputeInstance-owned fixture Secret.

#### TC-VMF-02: Registry image source and SSH identity project into the private VM spec

| Priority | Automation |
|---|---|
| medium | automated |

- **Tier:** Component integration
- **Owner:** [DEV]
- **References:** [README.md, lines 59-73](https://github.com/osac-project/enhancement-proposals/blob/84a28b6b9865f71684304e9fd1e1665835807bfc/enhancements/OSAC-1034-vm-api-fields/README.md#L59-L73)
- **Dependencies:** Real fulfillment and PostgreSQL with an isolated hub controller. The image and SSH identity are fixture records, and no guest or provider is used.
- **Gap:** The CLI projection spec covers compute, boot disk, run strategy and user data. No matching assertion was found in the pinned ComputeInstance CLI or fulfillment suites for the resolved registry source and SSH identity together.

**Preconditions.** Prepare a registry DiskImage named fixture-image and a registered synthetic SSH public key named fixture-key.

1. Create a VM with the supported typed references.
2. Inspect the private object and the corresponding hub resource for each resolved value.

**Expected results.** The image resolves to the fixture registry type and source reference, and the SSH identity matches fixture-key in the applicable private and hub projections.

#### TC-VMF-03: Invalid disk size or run strategy fails validation at its field

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Unit
- **Owner:** [DEV]
- **References:** [README.md, lines 63-79](https://github.com/osac-project/enhancement-proposals/blob/84a28b6b9865f71684304e9fd1e1665835807bfc/enhancements/OSAC-1034-vm-api-fields/README.md#L63-L79)
- **Dependencies:** In-process ComputeInstance validators with synthetic disks and run strategy; no provider.
- **Gap:** The deployed explicit-field test covers positive projection. No exact local negative matrix for both legacy fields was verified in ComputeInstance tests.

**Preconditions.** Use a valid fixture spec with a 20 GiB disk and Always.

1. Validate separate invalid disk and unsupported run-strategy fixtures.
2. Check the field paths in validation results.

**Expected results.** Each invalid value fails at its own field. The baseline passes.

#### TC-VMF-04: Additional VM disks retain their distinct requested sizes

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Component integration
- **Owner:** [DEV]
- **References:** [README.md, lines 70-79](https://github.com/osac-project/enhancement-proposals/blob/84a28b6b9865f71684304e9fd1e1665835807bfc/enhancements/OSAC-1034-vm-api-fields/README.md#L70-L79)
- **Dependencies:** Real fulfillment and PostgreSQL with the hub projection controller in Kind. Fixture disk and tier inputs, recording AAP and no guest.
- **Gap:** The storage-tier handoff tests prove disk identity and classes. The legacy explicit size projection for two additional disks still needs a focused mapping.

**Preconditions.** Prepare a VM fixture with a 20 GiB boot disk and two valid additional disks of 30 and 40 GiB.

1. Create the VM through the public API.
2. Read the corresponding private spec and hub spec and compare sizes in disk order.

**Expected results.** The private and hub specs retain a 20 GiB boot disk and distinguish the 30 GiB and 40 GiB additional disks.
