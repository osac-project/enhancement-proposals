# Test Plan — OSAC-1027 ComputeInstance phase conditions

## Overview

- **Feature:** OSAC-1027 — ComputeInstance phase and condition expansion
- **Source:** [README.md](README.md)
- **Total test cases:** 4

#### TC-PH-01: A provisioning failure surfaces as a condition

| Priority | Automation |
|---|---|
| critical | automated |

- **Tier:** Component integration
- **Gap:** no controller test covers the new conditions.

#### TC-PH-02: Phase and condition agree at each transition

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Unit
- **Gap:** no transition test exists.

#### TC-PH-03: A user sees the failure in lifecycle output

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** E2E
- **Gap:** no journey asserts the new conditions.

#### TC-PH-04: An unknown condition reason does not change the phase

| Priority | Automation |
|---|---|
| medium | automated |

- **Tier:** Unit
- **Gap:** no negative test exists.
