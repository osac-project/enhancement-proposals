# Test Plan — OSAC-5753 Event-log driven metering

## Overview

- **Feature:** OSAC-5753 — Event-log driven metering
- **Design:** [design.md](design.md) (§Test Plan)
- **Total test cases:** 5

#### TC-EL-01: The Fold turns event-log entries into billing facts

| Priority | Automation |
|---|---|
| critical | automated |

- **Tier:** Unit
- **Execution:** `osac-metering/metering-service/internal/fold/fold_test.go`

#### TC-EL-02: The Round carries the latest fact into the heartbeat

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Unit
- **Execution:** `osac-metering/metering-service/internal/round/round_test.go`

#### TC-EL-03: A published heartbeat matches the event history

| Priority | Automation |
|---|---|
| critical | automated |

- **Tier:** E2E
- **Execution:** `tests/e2e/vmaas/sanity/test_metering_billing.py`
- **Covers:** `test_metering_heartbeat_envelope`

#### TC-EL-04: Replaying the log does not duplicate a billing record

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Component integration
- **Gap:** no replay-idempotency test exists.

#### TC-EL-05: The event contract matches the published schema

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Contract
- **Execution:** `osac-metering/metering-service/tools/contract/contract_test.go`
