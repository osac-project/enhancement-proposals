# Test Plan — OSAC-985 Metering and usage tracking

## Overview

- **Feature:** OSAC-985 — Metering and usage tracking
- **Design:** [design.md](design.md) (§Test Plan)
- **Total test cases:** 6

#### TC-MU-01: A VM creation produces a heartbeat

| Priority | Automation |
|---|---|
| critical | automated |

- **Tier:** E2E
- **Execution:** `tests/e2e/vmaas/sanity/test_metering_billing.py`
- **Covers:** `test_metering_heartbeat_envelope`

#### TC-MU-02: Stopping a VM ends billing

| Priority | Automation |
|---|---|
| critical | automated |

- **Tier:** E2E
- **Execution:** `tests/e2e/vmaas/sanity/test_metering_billing.py`
- **Covers:** `test_metering_stop_ends_billing`

#### TC-MU-03: A resize splits usage across instance types

| Priority | Automation |
|---|---|
| critical | automated |

- **Tier:** E2E
- **Execution:** `tests/e2e/vmaas/sanity/test_metering_billing.py`
- **Covers:** `test_metering_resize_splits_dimensions`

#### TC-MU-04: Deleting a VM ends billing

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** E2E
- **Execution:** `tests/e2e/vmaas/sanity/test_metering_billing.py`
- **Covers:** `test_metering_delete_ends_billing`

#### TC-MU-05: Projection and reconciliation agree after a restart

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Component integration
- **Gap:** the design's projection and reconciliation packages no longer exist under the old paths; no replacement test covers the restart behaviour.

#### TC-MU-06: The event contract stays backwards compatible

| Priority | Automation |
|---|---|
| medium | automated |

- **Tier:** Contract
- **Execution:** `osac-metering/metering-service/tools/contract/contract_test.go`
