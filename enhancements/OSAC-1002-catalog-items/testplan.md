# Test Plan — OSAC-1002 Catalog items

## Overview

- **Feature:** OSAC-1002 — Catalog items
- **Source:** [README.md](README.md). The enhancement predates the PRD/design split.
- **Total test cases:** 4

#### TC-CAT-01: A catalog item can be created, read, and listed

| Priority | Automation |
|---|---|
| critical | automated |

- **Tier:** Component integration
- **Gap:** no test covers catalog items.

#### TC-CAT-02: Invalid catalog item input is rejected

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Unit
- **Gap:** no validation test exists.

#### TC-CAT-03: A catalog item version is immutable after publication

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Component integration
- **Gap:** no test covers the publication rule.

#### TC-CAT-04: A tenant can consume a published catalog item

| Priority | Automation |
|---|---|
| medium | automated |

- **Tier:** E2E
- **Gap:** no E2E journey exists.
