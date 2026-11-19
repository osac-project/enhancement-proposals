# Test Plan — OSAC-1118 BareMetalInstance API

## Overview

- **Feature:** OSAC-1118 — BareMetalInstance API
- **Source:** [README.md](README.md)
- **Total test cases:** 4

#### TC-BMI-01: A BareMetalInstance is created and becomes ready

| Priority | Automation |
|---|---|
| critical | automated |

- **Tier:** E2E
- **Execution:** `tests/e2e/bmaas/sanity/test_baremetal_instance_lifecycle.py`

#### TC-BMI-02: Public and private CRUD round-trip

| Priority | Automation |
|---|---|
| critical | automated |

- **Tier:** Unit
- **Gap:** no API test covers the public/private split.

#### TC-BMI-03: Invalid spec is rejected with a field path

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Unit
- **Gap:** no validation test exists.

#### TC-BMI-04: Deletion releases the host

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Component integration
- **Gap:** no test covers host release.
