# Test Plan — OSAC-2917 GPU instance types

## Overview

- **Feature:** OSAC-2917 — GPU instance types
- **Design:** [design.md](design.md) (§Test Plan)
- **Total test cases:** 5

#### TC-GPU-01: GPU field validation rejects zero, negative, and empty values

| Priority | Automation |
|---|---|
| critical | automated |

- **Tier:** Unit
- **Gap:** no InstanceType validation test exists.

#### TC-GPU-02: An InstanceType without GPU is accepted

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Unit
- **Gap:** no non-GPU case exists.

#### TC-GPU-03: A valid PCI selector and resource name are accepted

| Priority | Automation |
|---|---|
| critical | automated |

- **Tier:** Unit
- **Gap:** no positive validation case exists.

#### TC-GPU-04: A VM requests a GPU instance type

| Priority | Automation |
|---|---|
| critical | automated |

- **Tier:** E2E
- **Execution:** `tests/e2e/vmaas/sanity/test_compute_instance_gpu.py`

#### TC-GPU-05: A VM with no GPU type cannot claim a GPU device

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** E2E
- **Gap:** no negative journey exists.
