# Test Plan — OSAC-1330 Type-safe resource references

## Overview

- **Feature:** OSAC-1330 — Type-safe resource references
- **Design:** [design.md](design.md) (§Test Plan)
- **Total test cases:** 5

#### TC-REF-01: Reference messages round-trip in proto and JSON

| Priority | Automation |
|---|---|
| critical | automated |

- **Tier:** Unit
- **Execution:** `fulfillment-service/internal/references/reference_validator_test.go`

#### TC-REF-02: The interceptor discovers nested, repeated, and oneof references

| Priority | Automation |
|---|---|
| critical | automated |

- **Tier:** Unit
- **Execution:** `fulfillment-service/internal/references/reference_validator_test.go`

#### TC-REF-03: A missing reference returns InvalidArgument with the field path

| Priority | Automation |
|---|---|
| critical | automated |

- **Tier:** Unit
- **Execution:** `fulfillment-service/internal/references/reference_validator_test.go`

#### TC-REF-04: Name-only and id-only resolution populate the other side

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Unit
- **Execution:** `fulfillment-service/internal/references/reference_validator_test.go`

#### TC-REF-05: Resolution against a real database

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Component integration
- **Gap:** no integration case covers the interceptor end to end.
