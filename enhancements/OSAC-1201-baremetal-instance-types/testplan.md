# Test Plan — OSAC-1201 BareMetalInstance types

## Overview

- **Feature:** OSAC-1201 — BareMetalInstance types
- **Design:** [design.md](design.md) (§Test Plan)
- **Total test cases:** 6

#### TC-BIT-01: Instance type CRUD through public and private APIs

| Priority | Automation |
|---|---|
| critical | automated |

- **Tier:** Unit
- **Gap:** no API test covers instance types.

#### TC-BIT-02: Malformed hardware metadata is rejected

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Unit
- **Gap:** no validation test exists.

#### TC-BIT-03: The reconciler selects a host by label selector

| Priority | Automation |
|---|---|
| critical | automated |

- **Tier:** Component integration
- **Execution:** `bare-metal-fulfillment-operator/test/integration/baremetalpool_test.go`

#### TC-BIT-04: HostSelectionFailed and Succeeded conditions are set

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Component integration
- **Gap:** no condition test exists.

#### TC-BIT-05: A non-existent instance type is rejected at creation

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Component integration
- **Gap:** no test covers the reference error.

#### TC-BIT-06: No host carries the label, so selection fails cleanly

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Component integration
- **Gap:** no failure-path test exists.
