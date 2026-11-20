# Test Plan — OSAC-1270 Base OS management for BMaaS

## Overview

- **Feature:** OSAC-1270 — Base OS management for BMaaS
- **Design:** [design.md](design.md) (§Test Plan)
- **Total test cases:** 6

#### TC-BOS-01: Create requires a DiskImage from the user or a CatalogItem

| Priority | Automation |
|---|---|
| critical | automated |

- **Tier:** Unit
- **Gap:** no BMI server test covers the requirement.

#### TC-BOS-02: A missing, obsolete, or deprecated DiskImage is handled

| Priority | Automation |
|---|---|
| critical | automated |

- **Tier:** Unit
- **Gap:** no test covers the three states.

#### TC-BOS-03: Tenant visibility of the DiskImage is enforced

| Priority | Automation |
|---|---|
| critical | automated |

- **Tier:** Unit
- **Gap:** no cross-tenant test exists.

#### TC-BOS-04: The CatalogItem default is applied before validation

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Unit
- **Gap:** no defaulting test exists.

#### TC-BOS-05: disk_image is immutable on Update

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Unit
- **Gap:** no update-mask test exists.

#### TC-BOS-06: A bare-metal instance boots the selected image

| Priority | Automation |
|---|---|
| critical | automated |

- **Tier:** E2E
- **Execution:** `tests/e2e/bmaas/sanity/test_baremetal_disk_image_architecture.py`
