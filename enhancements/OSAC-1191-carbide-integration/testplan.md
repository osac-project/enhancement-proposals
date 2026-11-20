# Test Plan — OSAC-1191 Carbide integration

## Overview

- **Feature:** OSAC-1191 — Carbide integration
- **Source:** [README.md](README.md). The enhancement predates the PRD/design split.
- **Total test cases:** 3

#### TC-CB-01: A Carbide provider can be registered

| Priority | Automation |
|---|---|
| critical | automated |

- **Tier:** Component integration
- **Gap:** no test covers provider registration.

#### TC-CB-02: A cluster is provisioned through Carbide

| Priority | Automation |
|---|---|
| critical | automated |

- **Tier:** E2E
- **Gap:** no deployed journey exists.

#### TC-CB-03: Provider failures surface as cluster conditions

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Component integration
- **Gap:** no failure-path test exists.
