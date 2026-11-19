# Test Plan — OSAC-3145 Metering for Networking

## Overview

- **Feature:** OSAC-3145 — Metering for networking resources
- **Design:** [design.md](design.md) (§Test Plan)
- **Total test cases:** 5

#### TC-N-01: ExternalIP attachment and detach bill disjoint slices

| Priority | Automation |
|---|---|
| critical | automated |

- **Tier:** E2E
- **Gap:** no E2E case covers attachment slices.

#### TC-N-02: NATGateway usage carries VirtualNetwork dimensions

| Priority | Automation |
|---|---|
| critical | automated |

- **Tier:** E2E
- **Gap:** no E2E case covers NAT usage.

#### TC-N-03: The M360 adapter flattens networking dimensions

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Contract
- **Execution:** `osac-metering/adapters/m360/translate_test.go`

#### TC-N-04: Attachment transitions close and open slices at the transition time

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Component integration
- **Gap:** no test covers the timestamp arithmetic.

#### TC-N-05: The API oneof rejects NATGateway where it is not allowed

| Priority | Automation |
|---|---|
| medium | automated |

- **Tier:** Unit
- **Gap:** no API validation test.
