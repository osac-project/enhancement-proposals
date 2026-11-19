# Test Plan — OSAC-1319 BareMetalInstance UI

## Overview

- **Feature:** OSAC-1319 — BareMetalInstance UI
- **Design:** [design.md](design.md) (§Test Plan)
- **Total test cases:** 5

#### TC-BUI-01: The status label maps every state to its label and color

| Priority | Automation |
|---|---|
| critical | automated |

- **Tier:** Unit
- **Gap:** `BareMetalStatusLabel` has no test.

#### TC-BUI-02: Action buttons disable correctly per state

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Unit
- **Gap:** `BareMetalActionButtons` has no test.

#### TC-BUI-03: The create payload matches the wire format

| Priority | Automation |
|---|---|
| critical | automated |

- **Tier:** Unit
- **Execution:** `osac-ui/libs/ui-components/src/api/v1/baremetal-instance.test.ts`

#### TC-BUI-04: SSH keys and 64 KB user data are validated

| Priority | Automation |
|---|---|
| critical | automated |

- **Tier:** Unit
- **Gap:** no adapter validation test exists.

#### TC-BUI-05: The conditions list renders empty and populated states

| Priority | Automation |
|---|---|
| medium | automated |

- **Tier:** Unit
- **Gap:** `BareMetalConditionsList` has no test.
