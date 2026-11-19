# Test Plan — OSAC-46 VM instance types

## Overview

- **Feature:** OSAC-46 — VM instance types
- **Source:** [README.md](README.md), [ui-design.md](ui-design.md)
- **Total test cases:** 4

#### TC-VIT-01: A VM is created with an instance type

| Priority | Automation |
|---|---|
| critical | automated |

- **Tier:** E2E
- **Execution:** `tests/e2e/vmaas/sanity/test_compute_instance_instance_type.py`

#### TC-VIT-02: An unknown instance type is rejected

| Priority | Automation |
|---|---|
| critical | automated |

- **Tier:** Unit
- **Gap:** no reference-validation case exists.

#### TC-VIT-03: Instance type resources surface in the UI

| Priority | Automation |
|---|---|
| medium | automated |

- **Tier:** E2E
- **Gap:** no UI journey exists.

#### TC-VIT-04: Changing an instance type after creation is rejected

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Unit
- **Gap:** no immutability test exists.
