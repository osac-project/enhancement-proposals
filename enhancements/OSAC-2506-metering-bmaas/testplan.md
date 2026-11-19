# Test Plan — OSAC-2506 Metering for BMaaS

## Overview

- **Feature:** OSAC-2506 — Metering for BMaaS resources
- **Design:** [design.md](design.md) (§Test Plan)
- **Total test cases:** 6

Cases follow the design's Test Plan. A case with no named suite is a gap.

#### TC-M-01: A bare-metal instance bills allocation and consumption

| Priority | Automation |
|---|---|
| critical | automated |

- **Tier:** E2E
- **Execution:** `tests/e2e/bmaas/sanity/test_baremetal_metering.py`
- **Covers:** `test_baremetal_instance_bills_allocation_and_consumption`

#### TC-M-02: BMI deletion closes usage at the deletion timestamp

| Priority | Automation |
|---|---|
| critical | automated |

- **Tier:** E2E
- **Gap:** no E2E case covers the closing boundary.

#### TC-M-03: BMaaS dimensions appear in the published event contract

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Contract
- **Gap:** the contract suite does not assert BMaaS dimensions.

#### TC-M-04: The Fold records BMaaS facts from the event log

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Unit
- **Gap:** `fold_test.go` covers billing ids, not BMaaS dimensions.

#### TC-M-05: The heartbeat carries BMaaS dimensions

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Unit
- **Gap:** no heartbeat test asserts BMaaS dimensions.

#### TC-M-06: The adapter submits BMaaS usage once per stable event id

| Priority | Automation |
|---|---|
| medium | automated |

- **Tier:** Contract
- **Gap:** no adapter test covers the BMaaS path.
