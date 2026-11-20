# Test Plan — OSAC-3538 Catalog items v2

## Overview

- **Feature:** OSAC-3538 — Catalog items v2
- **Design:** [design.md](design.md). The design has no Test Plan section, so
  cases follow the API design and the policy model.
- **Total test cases:** 4

#### TC-C2-01: A catalog item is created, versioned, and published

| Priority | Automation |
|---|---|
| critical | automated |

- **Tier:** Component integration
- **Gap:** no test covers the catalog item lifecycle.

#### TC-C2-02: The policy model rejects a publish the caller may not perform

| Priority | Automation |
|---|---|
| critical | automated |

- **Tier:** Unit
- **Gap:** no policy test exists.

#### TC-C2-03: A tenant can select a published item version

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Component integration
- **Gap:** no selection test exists.

#### TC-C2-04: An unpublished or retired version is not selectable

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** E2E
- **Gap:** no journey covers retired versions.
