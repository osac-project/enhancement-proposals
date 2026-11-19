# Test Plan — OSAC-1567 Secret management

## Overview

- **Feature:** OSAC-1567 — Secret management with Vault backends
- **Design:** [design.md](design.md) (§Test Plan)
- **Total test cases:** 6

#### TC-SEC-01: Secret proto validation accepts and rejects the documented shapes

| Priority | Automation |
|---|---|
| critical | automated |

- **Tier:** Unit
- **Execution:** `fulfillment-service/internal/servers/secret_validation_test.go`

#### TC-SEC-02: Create, Get, Update, and Delete dispatch to the backend

| Priority | Automation |
|---|---|
| critical | automated |

- **Tier:** Unit
- **Execution:** `fulfillment-service/internal/servers/private_secrets_server_test.go`

#### TC-SEC-03: Public responses omit backend and coordinates

| Priority | Automation |
|---|---|
| critical | automated |

- **Tier:** Unit
- **Execution:** `fulfillment-service/internal/servers/private_secrets_server_test.go`

#### TC-SEC-04: Event payloads are redacted

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Unit
- **Gap:** no test asserts the redaction function.

#### TC-SEC-05: Tenant A cannot read tenant B secrets

| Priority | Automation |
|---|---|
| critical | automated |

- **Tier:** Component integration
- **Gap:** no namespace-isolation test exists.

#### TC-SEC-06: Secret CRUD through gRPC with a Vault-compatible store

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** E2E
- **Gap:** no deployed journey covers secrets.
