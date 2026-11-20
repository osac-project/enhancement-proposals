# Test Plan — OSAC-2921 Metadata display name

## Overview

- **Feature:** OSAC-2921 — Metadata display name and description
- **Design:** [design.md](design.md) (§Test Plan)
- **Total test cases:** 5

#### TC-MD-01: Protovalidate enforces the length limits

| Priority | Automation |
|---|---|
| critical | automated |

- **Tier:** Unit
- **Gap:** no validation test exists.

#### TC-MD-02: Create, Update, and Get round-trip the fields

| Priority | Automation |
|---|---|
| critical | automated |

- **Tier:** Unit
- **Gap:** no DAO round-trip test exists.

#### TC-MD-03: An update mask clears the fields to empty

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Unit
- **Gap:** no clear-to-empty case exists.

#### TC-MD-04: Filters and ordering use metadata.display_name

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Component integration
- **Execution:** `fulfillment-service/it/it_metadata_test.go`

#### TC-MD-05: An unknown list field is rejected

| Priority | Automation |
|---|---|
| medium | automated |

- **Tier:** Unit
- **Gap:** no negative ordering case exists.
