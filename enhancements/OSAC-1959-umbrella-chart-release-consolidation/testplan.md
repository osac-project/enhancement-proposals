# Test Plan — OSAC-1959 Umbrella chart release consolidation

## Overview

- **Feature:** OSAC-1959 — Umbrella chart release consolidation
- **Design:** [design.md](design.md) (§Test Plan)
- **Total test cases:** 4

#### TC-UR-01: validate_semver rejects malformed release versions

| Priority | Automation |
|---|---|
| critical | automated |

- **Tier:** Unit
- **Gap:** the helper is inline in the workflow and has no test.

#### TC-UR-02: A version that is not strictly greater is rejected before tagging

| Priority | Automation |
|---|---|
| critical | automated |

- **Tier:** Unit
- **Gap:** no monotonicity test exists.

#### TC-UR-03: An existing release tag blocks publishing

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Component integration
- **Gap:** no workflow test covers the existing-tag case.

#### TC-UR-04: The umbrella chart pins every component chart version

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Component integration
- **Gap:** no chart-consistency test exists.
