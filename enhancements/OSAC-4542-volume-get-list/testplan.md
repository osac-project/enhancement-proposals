# Test Plan — OSAC-4542 Volume Get/List Public API

## Overview

- **Feature:** OSAC-4542 — Volume Get/List public API
- **Design:** [design.md](design.md) (§Test Plan)
- **Total test cases:** 6

#### TC-VP-01: Public Get returns only the public projection

| Priority | Automation |
|---|---|
| critical | automated |

- **Tier:** Unit
- **Execution:** `fulfillment-service/internal/servers/volumes_server_test.go`

#### TC-VP-02: The public Volume descriptor contains no private fields

| Priority | Automation |
|---|---|
| critical | automated |

- **Tier:** Unit
- **Gap:** the generated-schema guard test does not exist.

#### TC-VP-03: A CEL filter over a public field returns the expected subset

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Unit
- **Execution:** `fulfillment-service/internal/servers/volumes_server_test.go`

#### TC-VP-04: A CEL filter over a private field is rejected

| Priority | Automation |
|---|---|
| critical | automated |

- **Tier:** Unit
- **Gap:** no test asserts the filter surface restriction.

#### TC-VP-05: Tenant authorization on Get and List

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Component integration
- **Gap:** no authorization case covers the public volume endpoints.

#### TC-VP-06: A subject in tenant A does not see tenant B volumes

| Priority | Automation |
|---|---|
| critical | automated |

- **Tier:** Component integration
- **Execution:** `fulfillment-service/it/it_public_volumes_test.go`
