# Test Plan — OSAC-3254 Expose NIC MAC addresses

## Overview

- **Feature:** OSAC-3254 — Expose BareMetalInstance NIC MAC addresses
- **Design:** [design.md](design.md) (§Test Plan)
- **Total test cases:** 6

#### TC-NIC-01: Metal3 NIC fetch returns lowercased MACs

| Priority | Automation |
|---|---|
| critical | automated |

- **Tier:** Unit
- **Execution:** `bare-metal-fulfillment-operator/internal/inventory/metal3_test.go`

#### TC-NIC-02: OpenStack NIC fetch retries on authentication errors

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Unit
- **Execution:** `bare-metal-fulfillment-operator/internal/inventory/openstack_internal_test.go`

#### TC-NIC-03: Hosts without inventory data are skipped

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Unit
- **Execution:** `bare-metal-fulfillment-operator/internal/inventory/metal3_test.go`

#### TC-NIC-04: The NIC gate is idempotent and sets NICMetadataUnavailable

| Priority | Automation |
|---|---|
| critical | automated |

- **Tier:** Component integration
- **Gap:** no controller test covers the gate.

#### TC-NIC-05: status.hardware.nics is populated and cleared

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Component integration
- **Gap:** no propagation test exists.

#### TC-NIC-06: CLI describe shows the NIC table or N/A

| Priority | Automation |
|---|---|
| medium | automated |

- **Tier:** E2E
- **Gap:** no CLI journey covers the table.
