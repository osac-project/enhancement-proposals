# Test Plan — OSAC-1577 API quality

## Overview

- **Feature:** OSAC-1577 — Generated public protos and reference integrity
- **Design:** [design.md](design.md) (§Test Plan)
- **Total test cases:** 5

#### TC-GEN-01: Public protos pass buf lint

| Priority | Automation |
|---|---|
| critical | automated |

- **Tier:** Unit
- **Gap:** no test runs buf lint against the generated tree.

#### TC-GEN-02: Private-marked fields never appear in public protos

| Priority | Automation |
|---|---|
| critical | automated |

- **Tier:** Unit
- **Gap:** no schema guard exists.

#### TC-GEN-03: Field numbers are preserved from the private source

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Unit
- **Gap:** no test compares field numbers.

#### TC-GEN-04: Soft-deleted parents block new children and deletes

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Unit
- **Execution:** `fulfillment-service/internal/database/dao/generic_dao_test.go`

#### TC-GEN-05: translateError maps every SQLSTATE to the right error type

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Unit
- **Execution:** `fulfillment-service/internal/servers/dao_error_converter_test.go`
