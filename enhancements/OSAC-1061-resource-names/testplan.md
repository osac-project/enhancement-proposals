# Test Plan — OSAC-1061 Resource names

## Overview

- **Feature:** OSAC-1061 — Resource names
- **Design:** [design.md](design.md) (§Test Plan)
- **Total test cases:** 5

#### TC-RN-01: Name validation accepts DNS labels and rejects invalid forms

| Priority | Automation |
|---|---|
| critical | automated |

- **Tier:** Unit
- **Execution:** `fulfillment-service/internal/servers/secret_validation_test.go`

#### TC-RN-02: Name uniqueness within a table returns ALREADY_EXISTS

| Priority | Automation |
|---|---|
| critical | automated |

- **Tier:** Unit
- **Execution:** `fulfillment-service/internal/database/dao/generic_dao_name_uniqueness_test.go`

#### TC-RN-03: The error names the resource kind, not "object"

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Unit
- **Execution:** `fulfillment-service/internal/servers/dao_error_converter_test.go`

#### TC-RN-04: The constraints hold against PostgreSQL

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Component integration
- **Gap:** no database-level test covers the unique index.

#### TC-RN-05: A deleted name can be reused

| Priority | Automation |
|---|---|
| medium | automated |

- **Tier:** Component integration
- **Gap:** no test covers reuse after deletion.
