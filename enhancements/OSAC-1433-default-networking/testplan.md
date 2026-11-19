# Test Plan — OSAC-1433 Default networking

## Overview

- **Feature:** OSAC-1433 — Default networking
- **Design:** [design.md](design.md) (§Test Plan)
- **Total test cases:** 5

#### TC-DN-01: NetworkClass defaults are validated and named on failure

| Priority | Automation |
|---|---|
| critical | automated |

- **Tier:** Unit
- **Gap:** no defaults validation test exists.

#### TC-DN-02: Attachment resolution covers omitted, empty, partial, complete

| Priority | Automation |
|---|---|
| critical | automated |

- **Tier:** Unit
- **Gap:** no resolution test exists.

#### TC-DN-03: The default ExternalIP pool is the lowest ready pool with capacity

| Priority | Automation |
|---|---|
| critical | automated |

- **Tier:** Unit
- **Gap:** no pool-selection test exists.

#### TC-DN-04: A VM gets external access through the default attachment

| Priority | Automation |
|---|---|
| critical | automated |

- **Tier:** E2E
- **Execution:** `tests/e2e/networking/vmaas/test_vmaas_networking.py`

#### TC-DN-05: A shared subnet connects a BMI and a VM

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** E2E
- **Execution:** `tests/e2e/networking/stretched/test_shared_subnet_bmi_compute_instance.py`
