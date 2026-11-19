# Test Plan — OSAC-3141 Metering for Block Storage

## Overview

- **Feature:** OSAC-3141 — Metering for block storage
- **Design:** [design.md](design.md) (§Test Plan)
- **Total test cases:** 5

#### TC-S-01: A Volume bills gibibyte-seconds

| Priority | Automation |
|---|---|
| critical | automated |

- **Tier:** E2E
- **Execution:** `tests/e2e/vmaas/sanity/test_volume_metering.py`

#### TC-S-02: Volume deletion closes usage and retains history

| Priority | Automation |
|---|---|
| critical | automated |

- **Tier:** E2E
- **Gap:** no case covers deletion boundaries or retention.

#### TC-S-03: Correction apply and reverse reach the provider once

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Contract
- **Gap:** Echo replay and DLQ are not covered by a test.

#### TC-S-04: Fixed-point quantity and interval semantics

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Unit
- **Gap:** the volume quantity rules have no unit test.

#### TC-S-05: The gate can be disabled, restarted, and re-enabled

| Priority | Automation |
|---|---|
| medium | automated |

- **Tier:** Component integration
- **Gap:** no test covers the documented outage gap.
