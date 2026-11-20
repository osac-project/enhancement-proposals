# Test Plan — OSAC-1710 Storage tier selection

## Overview

- **Feature:** OSAC-1710 — Storage tier selection for VMs
- **Design:** [design.md](design.md) (§Test Plan)
- **Total test cases:** 5

#### TC-VT-01: Boot disk defaults merge with and without a tier

| Priority | Automation |
|---|---|
| critical | automated |

- **Tier:** Unit
- **Gap:** no unit test covers the merge.

#### TC-VT-02: An empty storage tier is rejected on boot and additional disks

| Priority | Automation |
|---|---|
| critical | automated |

- **Tier:** Unit
- **Gap:** no validation test exists.

#### TC-VT-03: A non-existent tier is rejected before creation

| Priority | Automation |
|---|---|
| critical | automated |

- **Tier:** Unit
- **Gap:** no tier-existence test exists.

#### TC-VT-04: The CatalogItem default applies and is editable per the schema

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Unit
- **Gap:** no CatalogItem field test exists.

#### TC-VT-05: A VM boots from the selected tier

| Priority | Automation |
|---|---|
| critical | automated |

- **Tier:** E2E
- **Execution:** `tests/e2e/vmaas/sanity/test_compute_instance_storage_tier.py`
