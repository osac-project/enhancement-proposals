# Test Plan — OSAC-6056 Metering event contract

## Overview

- **Feature:** OSAC-6056 — Publish the OSAC metering event contract
- **Design:** [design.md](design.md) (§Test Plan)
- **Total test cases:** 4

#### TC-EC-01: The contract fixture matches the published schema

| Priority | Automation |
|---|---|
| critical | automated |

- **Tier:** Contract
- **Execution:** `osac-metering/metering-service/tools/contract/contract_test.go`

#### TC-EC-02: Heartbeat payload validation accepts and rejects the documented shapes

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Unit
- **Execution:** `osac-metering/schema/heartbeat_test.go`

#### TC-EC-03: An external consumer can build a record from the contract alone

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Component integration
- **Gap:** no consumer-compatibility test exists.

#### TC-EC-04: Published events carry the contract version

| Priority | Automation |
|---|---|
| medium | automated |

- **Tier:** E2E
- **Execution:** `tests/e2e/vmaas/sanity/test_metering_billing.py`
- **Covers:** `test_metering_heartbeat_envelope`
