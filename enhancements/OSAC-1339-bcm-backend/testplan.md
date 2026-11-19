# Test Plan — OSAC-1339 BCM backend

## Overview

- **Feature:** OSAC-1339 — BCM inventory backend
- **Design:** [design.md](design.md) (§Test Plan)
- **Total test cases:** 5

#### TC-BCM-01: A supported BCM version passes the check

| Priority | Automation |
|---|---|
| critical | automated |

- **Tier:** Unit
- **Execution:** `bare-metal-fulfillment-operator/internal/inventory/bcm_test.go`

#### TC-BCM-02: An unsupported version fails with an actionable error

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Unit
- **Execution:** `bare-metal-fulfillment-operator/internal/inventory/bcm_test.go`

#### TC-BCM-03: An unreachable version endpoint is reported

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Unit
- **Execution:** `bare-metal-fulfillment-operator/internal/inventory/bcm_test.go`

#### TC-BCM-04: Device list and single-device fetches parse correctly

| Priority | Automation |
|---|---|
| critical | automated |

- **Tier:** Unit
- **Execution:** `bare-metal-fulfillment-operator/internal/inventory/bcm_test.go`

#### TC-BCM-05: A nonexistent host returns no device, not an error

| Priority | Automation |
|---|---|
| medium | automated |

- **Tier:** Unit
- **Execution:** `bare-metal-fulfillment-operator/internal/inventory/bcm_test.go`
