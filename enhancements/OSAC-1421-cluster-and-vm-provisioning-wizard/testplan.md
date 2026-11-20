# Test Plan — OSAC-1421 Cluster and VM provisioning wizard

## Overview

- **Feature:** OSAC-1421 — Configuration wizard for cluster and VM resources
- **Design:** [design.md](design.md) (§Test Plan)
- **Total test cases:** 4

#### TC-WZ-01: Step validation maps nested errors and touched fields

| Priority | Automation |
|---|---|
| critical | automated |

- **Tier:** Unit
- **Gap:** `validateStep.test.ts` does not exist.

#### TC-WZ-02: Step ordering and payload shape follow the catalog

| Priority | Automation |
|---|---|
| critical | automated |

- **Tier:** Unit
- **Gap:** `wizardBuild.test.ts` does not exist.

#### TC-WZ-03: The catalog overlay applies to non-picker fields

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Unit
- **Gap:** no overlay test exists.

#### TC-WZ-04: Optional fields are omitted from the payload per the schema

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Unit
- **Gap:** no schema/payload test exists.
