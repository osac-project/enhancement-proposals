# Test Plan — OSAC-1034 VM API fields

## Overview

- **Feature:** OSAC-1034 — Well-defined attributes for VM and Cluster creation
- **Source:** [README.md](README.md)
- **Total test cases:** 4

#### TC-VMF-01: A compute instance exposes the documented fields

| Priority | Automation |
|---|---|
| critical | automated |

- **Tier:** E2E
- **Execution:** `tests/e2e/vmaas/sanity/test_compute_instance_cli_fields.py`

#### TC-VMF-02: A cluster exposes the documented fields

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** E2E
- **Gap:** no case asserts the cluster field set.

#### TC-VMF-03: Invalid field values are rejected with field paths

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Unit
- **Gap:** no validation test exists.

#### TC-VMF-04: Public responses omit private fields

| Priority | Automation |
|---|---|
| critical | automated |

- **Tier:** Unit
- **Gap:** no schema guard exists for these messages.
